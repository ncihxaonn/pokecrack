#!/usr/bin/env python3
"""Fail-closed hosted-contract preflight for a Nostr-enabled deployment.

The deployment script passes only the absolute environment-file path.  This
helper reads the database URL from that file, translates it to the fixed libpq
environment runner, and invokes only a fixed ``psql`` command.  The URL is
never placed in an argument, a child log, or an exception message.  A missing
or false Nostr flag is a successful no-op so a Bluesky-only hotfix is not
blocked by the Nostr release contract.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from run_with_database_url import child_environment, libpq_environment


MAX_ENV_FILE_BYTES = 64 * 1024
ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ENABLED_ENV_KEYS = frozenset(
    {
        "DATA_MODE",
        "NOSTR_COLLECTION_ENABLED",
        "NOSTR_SUPABASE_DB_URL",
        "SUPABASE_NOSTR_PREFLIGHT_DB_URL",
    }
)
REQUIRED_CONTRACT_KEYS = frozenset(
    {
        "postgresql17",
        "ledger_060",
        "ledger_090",
        "ledger_100",
        "source_policies_exact",
        "request_gates_exact",
        "nostr_tables_rls_exact",
        "nostr_policies_exact",
        "nostr_acl_exact",
        "nostr_checkpoints_exact",
        "cleanup_capacity_exact",
        "public_v2_shape_exact",
        "public_v2_acl_exact",
        "attestor_role_exact",
        "nostr_worker_role_exact",
    }
)


ATTESTOR_ROLE_OPTION = "-c role=pokecrack_nostr_attestor"
ATTESTOR_LOGIN = "pokecrack_nostr_attestor_login"
WORKER_ROLE_OPTION = "-c role=pokecrack_nostr_worker"
WORKER_LOGIN = "pokecrack_nostr_worker_login"
CONTRACT_QUERY = (
    "select ingest.verify_nostr_release_v2() "
    "where session_user = 'pokecrack_nostr_attestor_login' "
    "and current_user = 'pokecrack_nostr_attestor' "
    "and session_user <> current_user;"
)


class NostrPreflightError(RuntimeError):
    """A malformed environment or failed hosted contract preflight."""


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise NostrPreflightError("environment file must be an absolute regular, non-symlink file")
    try:
        mode = path.stat().st_mode & 0o7777
        payload = path.read_bytes()
    except OSError as error:
        raise NostrPreflightError("environment file could not be read") from error
    if mode & 0o77:
        raise NostrPreflightError("environment file must be owner-only")
    if len(payload) > MAX_ENV_FILE_BYTES:
        raise NostrPreflightError("environment file exceeds the fixed size limit")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise NostrPreflightError("environment file must be UTF-8") from error
    if "\x00" in text or "\r" in text:
        raise NostrPreflightError("environment file contains an invalid control character")

    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise NostrPreflightError("environment file contains an invalid assignment")
        key, value = stripped.split("=", 1)
        key = key.strip()
        if ENV_KEY.fullmatch(key) is None:
            raise NostrPreflightError("environment file contains an invalid variable name")
        if key in values:
            raise NostrPreflightError("environment file contains a duplicate variable")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if any(character in value for character in ("\x00", "\r", "\n")):
            raise NostrPreflightError("environment file contains an invalid variable value")
        values[key] = value
    return values


def _psql_contract(database_url: str, *, psql_path: str) -> dict[str, object]:
    try:
        parsed_environment = libpq_environment(database_url)
    except (ValueError, UnicodeError) as error:
        raise NostrPreflightError("hosted database URL is invalid") from error
    if parsed_environment.get("PGOPTIONS") != ATTESTOR_ROLE_OPTION:
        raise NostrPreflightError(
            "Nostr preflight URL must select the dedicated attestor role"
        )
    if parsed_environment.get("PGUSER") != ATTESTOR_LOGIN:
        raise NostrPreflightError(
            "Nostr preflight URL must authenticate as the dedicated attestor login"
        )
    environment = child_environment(parsed_environment)
    for name in (
        "SUPABASE_DB_URL",
        "SUPABASE_DB_URL_FILE",
        "SUPABASE_ACCESS_TOKEN",
        "SUPABASE_NOSTR_PREFLIGHT_DB_URL",
        "NOSTR_SUPABASE_DB_URL",
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
        raise NostrPreflightError("hosted Nostr contract client could not start") from error
    if result.returncode != 0:
        raise NostrPreflightError("hosted Nostr contract query failed")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise NostrPreflightError("hosted Nostr contract query returned an ambiguous result")
    try:
        contract = json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise NostrPreflightError("hosted Nostr contract result was not JSON") from error
    if not isinstance(contract, dict) or set(contract) != REQUIRED_CONTRACT_KEYS:
        raise NostrPreflightError("hosted Nostr contract result had an unexpected shape")
    if any(value is not True for value in contract.values()):
        raise NostrPreflightError("hosted Nostr contract is not ready")
    return contract


def _validated_target(database_url: str, *, login: str, role_option: str) -> tuple[str, str, str]:
    try:
        parsed = libpq_environment(database_url)
    except (ValueError, UnicodeError) as error:
        raise NostrPreflightError("hosted database URL is invalid") from error
    if parsed.get("PGUSER") != login or parsed.get("PGOPTIONS") != role_option:
        raise NostrPreflightError("hosted database URL does not use its dedicated identity")
    return parsed["PGHOST"], parsed["PGPORT"], parsed["PGDATABASE"]


def run(arguments: argparse.Namespace) -> int:
    values = _read_env_file(arguments.env_file)
    flag = values.get("NOSTR_COLLECTION_ENABLED", "false")
    if flag == "false":
        if getattr(arguments, "require_enabled", False):
            raise NostrPreflightError(
                "this release path requires NOSTR_COLLECTION_ENABLED=true"
            )
        return 0
    if flag != "true":
        raise NostrPreflightError("NOSTR_COLLECTION_ENABLED must be exactly true or false")
    if set(values) != ENABLED_ENV_KEYS:
        raise NostrPreflightError(
            "enabled Nostr environment must contain only the exact release variables"
        )
    if values.get("DATA_MODE") != "live":
        raise NostrPreflightError("Nostr collection requires DATA_MODE=live")
    database_url = values.get("SUPABASE_NOSTR_PREFLIGHT_DB_URL", "")
    if not database_url:
        raise NostrPreflightError(
            "Nostr collection requires the separate least-privilege attestor database URL"
        )
    worker_database_url = values.get("NOSTR_SUPABASE_DB_URL", "")
    if not worker_database_url:
        raise NostrPreflightError(
            "Nostr collection requires the separate least-privilege worker database URL"
        )
    if database_url == worker_database_url:
        raise NostrPreflightError(
            "Nostr preflight must not reuse the worker database URL"
        )
    attestor_target = _validated_target(
        database_url,
        login=ATTESTOR_LOGIN,
        role_option=ATTESTOR_ROLE_OPTION,
    )
    worker_target = _validated_target(
        worker_database_url,
        login=WORKER_LOGIN,
        role_option=WORKER_ROLE_OPTION,
    )
    if attestor_target != worker_target:
        raise NostrPreflightError(
            "Nostr preflight and worker URLs must target the same database"
        )
    psql_path = shutil.which("psql")
    if psql_path is None:
        raise NostrPreflightError("psql is required for the hosted Nostr contract preflight")
    _psql_contract(database_url, psql_path=psql_path)
    print("Nostr hosted migration and contract preflight passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument(
        "--require-enabled",
        action="store_true",
        help="fail unless the exact enabled four-key Nostr release file is present",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except (NostrPreflightError, subprocess.TimeoutExpired, OSError):
        print("Nostr hosted contract preflight failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
