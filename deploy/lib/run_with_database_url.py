#!/usr/bin/env python3
"""Run a fixed PostgreSQL client with a URL supplied on standard input.

The URL is translated into libpq environment variables so credentials never
appear in the child command line or normal output.
"""

from __future__ import annotations

import os
import shutil
import sys
from urllib.parse import parse_qsl, unquote, urlsplit

MAX_DATABASE_URL_BYTES = 8192
ALLOWED_COMMANDS = frozenset({"pg_dump", "psql"})
ALLOWED_SSL_MODES = frozenset({"require", "verify-ca", "verify-full"})
QUERY_ENVIRONMENT = {
    "application_name": "PGAPPNAME",
    "channel_binding": "PGCHANNELBINDING",
    "connect_timeout": "PGCONNECT_TIMEOUT",
    "gssencmode": "PGGSSENCMODE",
    "options": "PGOPTIONS",
    "require_auth": "PGREQUIREAUTH",
    "sslcert": "PGSSLCERT",
    "sslcrl": "PGSSLCRL",
    "sslcrldir": "PGSSLCRLDIR",
    "sslkey": "PGSSLKEY",
    "sslmode": "PGSSLMODE",
    "sslnegotiation": "PGSSLNEGOTIATION",
    "sslrootcert": "PGSSLROOTCERT",
    "target_session_attrs": "PGTARGETSESSIONATTRS",
}


class DatabaseURLConfigurationError(ValueError):
    """The supplied URL cannot be translated without ambiguity."""


def _safe_component(
    value: str | None, *, name: str, percent_encoded: bool = True
) -> str:
    if value is None:
        raise DatabaseURLConfigurationError(f"database URL requires {name}")
    decoded = unquote(value) if percent_encoded else value
    if not decoded or any(character in decoded for character in ("\0", "\r", "\n")):
        raise DatabaseURLConfigurationError(f"database URL has invalid {name}")
    return decoded


def libpq_environment(database_url: str) -> dict[str, str]:
    if len(database_url.encode("utf-8")) > MAX_DATABASE_URL_BYTES:
        raise DatabaseURLConfigurationError("database URL exceeds the fixed byte limit")
    if any(character in database_url for character in ("\0", "\r", "\n")):
        raise DatabaseURLConfigurationError("database URL contains a control character")

    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise DatabaseURLConfigurationError("database URL requires a PostgreSQL scheme")
    if parsed.fragment:
        raise DatabaseURLConfigurationError("database URL fragments are not supported")
    if parsed.hostname is None:
        raise DatabaseURLConfigurationError("database URL requires host")
    try:
        port = parsed.port or 5432
    except ValueError as error:
        raise DatabaseURLConfigurationError("database URL has invalid port") from error
    if not 1 <= port <= 65535:
        raise DatabaseURLConfigurationError("database URL has invalid port")

    path_parts = parsed.path.split("/")
    if len(path_parts) != 2 or path_parts[0] or not path_parts[1]:
        raise DatabaseURLConfigurationError("database URL requires one database path")
    database = _safe_component(path_parts[1], name="database")
    if "/" in database:
        raise DatabaseURLConfigurationError("database URL has invalid database")

    environment = {
        "PGDATABASE": database,
        "PGHOST": _safe_component(parsed.hostname, name="host"),
        "PGPASSWORD": _safe_component(parsed.password, name="password"),
        "PGPORT": str(port),
        "PGUSER": _safe_component(parsed.username, name="user"),
    }
    seen_query_keys: set[str] = set()
    for key, value in parse_qsl(
        parsed.query,
        keep_blank_values=True,
        strict_parsing=True,
        max_num_fields=len(QUERY_ENVIRONMENT),
    ):
        if key in seen_query_keys:
            raise DatabaseURLConfigurationError("database URL has duplicate query option")
        seen_query_keys.add(key)
        variable = QUERY_ENVIRONMENT.get(key)
        if variable is None:
            raise DatabaseURLConfigurationError("database URL has unsupported query option")
        # parse_qsl has already decoded this component; decoding it again would
        # reinterpret a literal percent escape.
        environment[variable] = _safe_component(
            value, name="query option", percent_encoded=False
        )
    if environment.get("PGSSLMODE") not in ALLOWED_SSL_MODES:
        raise DatabaseURLConfigurationError(
            "database URL requires sslmode=require or stronger"
        )
    return environment


def child_environment(
    parsed_environment: dict[str, str],
    *,
    parent_environment: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a deterministic libpq environment without inherited PG settings."""

    environment = dict(os.environ if parent_environment is None else parent_environment)
    for name in tuple(environment):
        if name.startswith("PG"):
            environment.pop(name)
    environment.update(parsed_environment)
    return environment


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["--"]:
        arguments.pop(0)
    if not arguments or arguments[0] not in ALLOWED_COMMANDS:
        print("database URL runner: command must be psql or pg_dump", file=sys.stderr)
        return 2

    payload = sys.stdin.buffer.read(MAX_DATABASE_URL_BYTES + 1)
    try:
        database_url = payload.decode("utf-8")
        parsed_environment = libpq_environment(database_url)
    except (UnicodeDecodeError, DatabaseURLConfigurationError, ValueError):
        print("database URL runner: invalid database URL", file=sys.stderr)
        return 2

    executable = shutil.which(arguments[0])
    if executable is None:
        print("database URL runner: required command is unavailable", file=sys.stderr)
        return 127

    environment = child_environment(parsed_environment)
    os.execve(executable, arguments, environment)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
