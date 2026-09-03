#!/usr/bin/env python3
"""Fail-closed preflight for the opt-in Bluesky worker service set.

Only the three variables in the dedicated Bluesky file are accepted.  The
worker DSN is translated to libpq environment variables and passed to one
fixed, boolean-only attestation query; it is never put in argv, output, or an
exception message.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from run_with_database_url import child_environment, libpq_environment


MAX_ENV_FILE_BYTES = 64 * 1024
ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CONNECT_TIMEOUT = re.compile(r"^[1-9][0-9]*$")
MAX_CONNECT_TIMEOUT_SECONDS = 60
ENABLED_ENV_KEYS = frozenset(
    {
        "DATA_MODE",
        "BLUESKY_COLLECTION_ENABLED",
        "BLUESKY_SUPABASE_DB_URL",
    }
)
REQUIRED_CONTRACT_KEYS = frozenset(
    {
        "postgresql17",
        "ledger_210",
        "ledger_260",
        "ledger_270",
        "bluesky_worker_role_exact",
        "bluesky_policy_exact",
        "bluesky_acl_exact",
    }
)

WORKER_ROLE_OPTION = "-c role=pokecrack_bluesky_worker"
WORKER_LOGIN = "pokecrack_bluesky_worker_login"
CONTRACT_QUERY = (
    "select ingest.verify_bluesky_release_v1() "
    "where session_user = 'pokecrack_bluesky_worker_login' "
    "and current_user = 'pokecrack_bluesky_worker' "
    "and session_user <> current_user;"
)


class BlueskyPreflightError(RuntimeError):
    """A malformed environment or failed hosted Bluesky contract preflight."""


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise BlueskyPreflightError(
            "environment file must be an absolute regular, non-symlink file"
        )
    try:
        mode = path.stat().st_mode & 0o7777
        payload = path.read_bytes()
    except OSError as error:
        raise BlueskyPreflightError("environment file could not be read") from error
    if mode != 0o600:
        raise BlueskyPreflightError("environment file must have mode 0600")
    if len(payload) > MAX_ENV_FILE_BYTES:
        raise BlueskyPreflightError("environment file exceeds the fixed size limit")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise BlueskyPreflightError("environment file must be UTF-8") from error
    if "\x00" in text or "\r" in text:
        raise BlueskyPreflightError(
            "environment file contains an invalid control character"
        )

    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise BlueskyPreflightError(
                "environment file contains an invalid assignment"
            )
        key, value = stripped.split("=", 1)
        key = key.strip()
        if ENV_KEY.fullmatch(key) is None:
            raise BlueskyPreflightError(
                "environment file contains an invalid variable name"
            )
        if key in values:
            raise BlueskyPreflightError("environment file contains a duplicate variable")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if any(character in value for character in ("\x00", "\r", "\n")):
            raise BlueskyPreflightError(
                "environment file contains an invalid variable value"
            )
        values[key] = value
    return values


def _require_connect_timeout(parsed: dict[str, str]) -> None:
    value = parsed.get("PGCONNECT_TIMEOUT")
    if value is None or CONNECT_TIMEOUT.fullmatch(value) is None:
        raise BlueskyPreflightError(
            "Bluesky worker URL requires a positive bounded connect_timeout"
        )
    if len(value) > len(str(MAX_CONNECT_TIMEOUT_SECONDS)):
        raise BlueskyPreflightError(
            "Bluesky worker URL requires a positive bounded connect_timeout"
        )
    if int(value) > MAX_CONNECT_TIMEOUT_SECONDS:
        raise BlueskyPreflightError(
            "Bluesky worker URL requires a positive bounded connect_timeout"
        )


def _validated_target(database_url: str) -> dict[str, str]:
    try:
        parsed = libpq_environment(database_url)
    except (ValueError, UnicodeError) as error:
        raise BlueskyPreflightError("hosted database URL is invalid") from error
    if parsed.get("PGUSER") != WORKER_LOGIN:
        raise BlueskyPreflightError(
            "Bluesky worker URL must authenticate as the dedicated worker login"
        )
    if parsed.get("PGOPTIONS") != WORKER_ROLE_OPTION:
        raise BlueskyPreflightError(
            "Bluesky worker URL must select the dedicated capability role"
        )
    _require_connect_timeout(parsed)
    return parsed


def _psql_contract(
    parsed_environment: dict[str, str], *, psql_path: str
) -> dict[str, object]:
    environment = child_environment(parsed_environment)
    for name in (
        "SUPABASE_DB_URL",
        "SUPABASE_DB_URL_FILE",
        "SUPABASE_ACCESS_TOKEN",
        "BLUESKY_SUPABASE_DB_URL",
        "NOSTR_SUPABASE_DB_URL",
        "DATABASE_URL",
    ):
        environment.pop(name, None)
    try:
        result = subprocess.run(
            [
                psql_path,
                "--no-psqlrc",
                "--set=ON_ERROR_STOP=1",
                "--tuples-only",
                "--no-align",
                "--quiet",
                "--command",
                CONTRACT_QUERY,
            ],
            check=False,
            text=True,
            capture_output=True,
            env=environment,
            timeout=45,
        )
    except OSError as error:
        raise BlueskyPreflightError(
            "hosted Bluesky contract client could not start"
        ) from error
    if result.returncode != 0:
        raise BlueskyPreflightError("hosted Bluesky contract query failed")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise BlueskyPreflightError(
            "hosted Bluesky contract query returned an ambiguous result"
        )
    try:
        contract = json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise BlueskyPreflightError(
            "hosted Bluesky contract result was not JSON"
        ) from error
    if not isinstance(contract, dict) or set(contract) != REQUIRED_CONTRACT_KEYS:
        raise BlueskyPreflightError(
            "hosted Bluesky contract result had an unexpected shape"
        )
    if any(value is not True for value in contract.values()):
        raise BlueskyPreflightError("hosted Bluesky contract is not ready")
    return contract


def run(arguments: argparse.Namespace) -> int:
    values = _read_env_file(arguments.env_file)
    if not set(values) <= ENABLED_ENV_KEYS:
        raise BlueskyPreflightError(
            "Bluesky environment must contain only the exact release variables"
        )
    flag = values.get("BLUESKY_COLLECTION_ENABLED", "false")
    if flag == "false":
        if getattr(arguments, "require_enabled", False):
            raise BlueskyPreflightError(
                "this release path requires BLUESKY_COLLECTION_ENABLED=true"
            )
        return 0
    if flag != "true":
        raise BlueskyPreflightError(
            "BLUESKY_COLLECTION_ENABLED must be exactly true or false"
        )
    if set(values) != ENABLED_ENV_KEYS:
        raise BlueskyPreflightError(
            "enabled Bluesky environment must contain only the exact release variables"
        )
    if values.get("DATA_MODE") != "live":
        raise BlueskyPreflightError("Bluesky collection requires DATA_MODE=live")
    database_url = values.get("BLUESKY_SUPABASE_DB_URL", "")
    if not database_url:
        raise BlueskyPreflightError(
            "Bluesky collection requires the dedicated worker database URL"
        )
    parsed_environment = _validated_target(database_url)
    psql_path = shutil.which("psql")
    if psql_path is None:
        raise BlueskyPreflightError(
            "psql is required for the hosted Bluesky contract preflight"
        )
    _psql_contract(parsed_environment, psql_path=psql_path)
    print("Bluesky hosted migration and contract preflight passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument(
        "--require-enabled",
        action="store_true",
        help=(
            "fail unless the exact enabled three-key Bluesky release file is present"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except (BlueskyPreflightError, subprocess.TimeoutExpired, OSError):
        print("Bluesky hosted contract preflight failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
