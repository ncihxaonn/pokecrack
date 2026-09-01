#!/usr/bin/env python3
"""Apply this repository's forward-only migrations through Supabase's API.

The Supabase CLI's ``--db-url`` mode necessarily puts a database URL in a
child process environment/argument flow.  This runner uses an owner-scoped
Personal Supabase access token and the Management API instead.  It never
accepts a database URL, writes credentials to disk, or prints API responses.

The runner is intentionally narrow: it discovers the local migration set,
reads the hosted migration ledger, and applies only missing migrations in
lexical version order.  Every migration is executed in one transaction with
its original source retained in the ledger.  Unknown hosted versions,
ambiguous API responses, malformed migration files, and all API failures are
hard errors.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request


API_ROOT = "https://api.supabase.com/v1"
TOKEN_ENV = "SUPABASE_ACCESS_TOKEN"
PROJECT_ENV = "SUPABASE_PROJECT_REF"
PROJECT_REF = re.compile(r"^[a-z0-9]{20}$")
PERSONAL_TOKEN = re.compile(r"^sbp_[A-Za-z0-9._~-]{16,256}$")
MIGRATION_NAME = re.compile(r"^(?P<version>\d{14})_(?P<name>[a-z0-9_]+)\.sql$")
VERSION = re.compile(r"^\d{14}$")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_MIGRATION_BYTES = 4 * 1024 * 1024
TRANSACTION_CONTROL_TOKENS = frozenset(
    {
        "begin",
        "start",
        "commit",
        "end",
        "rollback",
        "abort",
        "savepoint",
        "release",
        "prepare",
    }
)

SERVER_VERSION_SQL = "select current_setting('server_version_num') as server_version_num"
APPLIED_VERSIONS_SQL = (
    "select version::text as version "
    "from supabase_migrations.schema_migrations order by version"
)
LEDGER_COLUMNS_SQL = (
    "select column_name::text as column_name "
    "from information_schema.columns "
    "where table_schema = 'supabase_migrations' "
    "and table_name = 'schema_migrations' "
    "order by ordinal_position"
)


class MigrationRunnerError(RuntimeError):
    """A fail-closed runner configuration, API, or ledger error."""


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Never forward the owner bearer token away from the pinned API URL."""

    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


def _migration_files(directory: Path) -> dict[str, tuple[Path, str]]:
    if not directory.is_dir() or directory.is_symlink():
        raise MigrationRunnerError("migrations directory must be a real directory")
    migrations: dict[str, tuple[Path, str]] = {}
    for path in sorted(directory.glob("*.sql")):
        if path.is_symlink() or not path.is_file():
            raise MigrationRunnerError(f"migration file must be a regular file: {path.name}")
        match = MIGRATION_NAME.fullmatch(path.name)
        if match is None:
            raise MigrationRunnerError(f"invalid migration filename: {path.name}")
        version = match.group("version")
        if version in migrations:
            raise MigrationRunnerError(f"duplicate migration version: {version}")
        migrations[version] = (path, match.group("name"))
    if not migrations:
        raise MigrationRunnerError("no migration files were found")
    return migrations


def _read_migration(path: Path) -> str:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise MigrationRunnerError(f"could not read migration {path.name}") from error
    if len(payload) > MAX_MIGRATION_BYTES:
        raise MigrationRunnerError(f"migration {path.name} exceeds the fixed byte limit")
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MigrationRunnerError(f"migration {path.name} is not UTF-8") from error
    if "\x00" in source or "\r" in source:
        raise MigrationRunnerError(f"migration {path.name} contains an invalid control character")
    return source


def _transaction_body(source: str, *, filename: str) -> str:
    """Remove exactly one top-level BEGIN/COMMIT pair.

    PL/pgSQL function bodies contain ordinary ``begin;`` and ``commit;`` text
    inside dollar-quoted strings.  A line-oriented regular expression cannot
    distinguish those from transaction control.  The small lexer below splits
    only on semicolons outside SQL quotes, comments, and dollar-quoted bodies;
    it then permits exactly the first ``begin;`` and final ``commit;``
    statement.  Any other top-level transaction control is rejected.
    """

    statements = _top_level_statements(source)
    meaningful_statements: list[tuple[int, int]] = []
    transaction_statements: list[tuple[str, int, int]] = []
    canonical_transaction_statements: list[tuple[str, int, int]] = []
    for start, end in statements:
        normalized = _strip_sql_comments(source[start:end]).strip()
        if not normalized:
            continue
        meaningful_statements.append((start, end))
        first_token = re.match(r"([a-z_][a-z0-9_]*)", normalized, flags=re.IGNORECASE)
        token = first_token.group(1).casefold() if first_token is not None else ""
        is_set_transaction = bool(
            re.match(
                r"set\s+(?:local\s+)?(?:session\s+)?(?:characteristics\s+as\s+)?transaction\b",
                normalized,
                flags=re.IGNORECASE,
            )
        )
        changes_string_lexing = bool(
            re.match(
                r"(?:set|reset)\s+(?:local\s+|session\s+)?standard_conforming_strings\b",
                normalized,
                flags=re.IGNORECASE,
            )
        )
        if changes_string_lexing:
            raise MigrationRunnerError(
                f"migration {filename} must not change standard_conforming_strings"
            )
        canonical = re.fullmatch(
            r"(begin|commit)\s*;", normalized, flags=re.IGNORECASE
        )
        if token in TRANSACTION_CONTROL_TOKENS or is_set_transaction:
            transaction_statements.append((token or "set transaction", start, end))
            if canonical is not None:
                canonical_transaction_statements.append(
                    (canonical.group(1).casefold(), start, end)
                )
    if len(transaction_statements) != 2 or len(canonical_transaction_statements) != 2:
        raise MigrationRunnerError(f"migration {filename} must have one outer BEGIN/COMMIT")
    first, last = canonical_transaction_statements
    if first[0] != "begin" or last[0] != "commit" or not meaningful_statements:
        raise MigrationRunnerError(f"migration {filename} must have one outer BEGIN/COMMIT")
    if first[1] != meaningful_statements[0][0]:
        raise MigrationRunnerError(f"migration {filename} must have one outer BEGIN/COMMIT")
    if last[2] != meaningful_statements[-1][1]:
        raise MigrationRunnerError(f"migration {filename} must end with outer COMMIT")
    body = source[first[2] : last[1]].strip()
    if not body:
        raise MigrationRunnerError(f"migration {filename} must contain SQL inside its transaction")
    return body


def _string_uses_backslash_escapes(source: str, quote_index: int) -> bool:
    """Return whether a PostgreSQL quote has an E or U& escape prefix."""

    quote = source[quote_index]
    if quote == "'" and quote_index >= 1 and source[quote_index - 1] in {"e", "E"}:
        prefix_index = quote_index - 1
        if prefix_index == 0 or not (
            source[prefix_index - 1].isalnum()
            or source[prefix_index - 1] in {"_", "$"}
        ):
            return True
    if (
        quote_index >= 2
        and source[quote_index - 1] == "&"
        and source[quote_index - 2] in {"u", "U"}
    ):
        prefix_index = quote_index - 2
        if prefix_index == 0 or not (
            source[prefix_index - 1].isalnum()
            or source[prefix_index - 1] in {"_", "$"}
        ):
            return True
    return False


def _strip_sql_comments(source: str) -> str:
    """Blank SQL comments without interpreting comment markers in strings."""

    output = list(source)
    index = 0
    block_depth = 0
    quote: str | None = None
    quote_backslash_escapes = False
    dollar_quote: str | None = None
    while index < len(source):
        if dollar_quote is not None:
            if source.startswith(dollar_quote, index):
                index += len(dollar_quote)
                dollar_quote = None
            else:
                index += 1
            continue
        if quote is not None:
            if source[index] == quote:
                if index + 1 < len(source) and source[index + 1] == quote:
                    index += 2
                    continue
                quote = None
            elif quote_backslash_escapes and source[index] == "\\" and index + 1 < len(source):
                index += 2
                continue
            index += 1
            continue
        if block_depth:
            if source.startswith("/*", index):
                output[index : index + 2] = "  "
                block_depth += 1
                index += 2
            elif source.startswith("*/", index):
                output[index : index + 2] = "  "
                block_depth -= 1
                index += 2
            else:
                if source[index] != "\n":
                    output[index] = " "
                index += 1
            continue
        if source[index] in {"'", '"'}:
            quote = source[index]
            quote_backslash_escapes = _string_uses_backslash_escapes(source, index)
            index += 1
            continue
        if source.startswith("--", index):
            end = source.find("\n", index)
            if end == -1:
                end = len(source)
            for offset in range(index, end):
                output[offset] = " "
            index = end
            continue
        if source.startswith("/*", index):
            output[index : index + 2] = "  "
            block_depth = 1
            index += 2
            continue
        if source[index] == "$":
            delimiter = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", source[index:])
            if delimiter is not None:
                dollar_quote = delimiter.group(0)
                index += len(dollar_quote)
                continue
        index += 1
    if block_depth:
        raise MigrationRunnerError("migration contains an unterminated SQL block comment")
    if quote is not None or dollar_quote is not None:
        raise MigrationRunnerError("migration contains an unterminated SQL quote")
    return "".join(output)


def _top_level_statements(source: str) -> list[tuple[int, int]]:
    """Return statement spans split only at semicolons outside SQL literals."""

    statements: list[tuple[int, int]] = []
    start = 0
    index = 0
    block_depth = 0
    quote: str | None = None
    quote_backslash_escapes = False
    dollar_quote: str | None = None
    while index < len(source):
        if dollar_quote is not None:
            if source.startswith(dollar_quote, index):
                index += len(dollar_quote)
                dollar_quote = None
            else:
                index += 1
            continue
        if quote is not None:
            if source[index] == quote:
                if index + 1 < len(source) and source[index + 1] == quote:
                    index += 2
                    continue
                quote = None
            elif quote_backslash_escapes and source[index] == "\\" and index + 1 < len(source):
                index += 2
                continue
            index += 1
            continue
        if block_depth:
            if source.startswith("/*", index):
                block_depth += 1
                index += 2
            elif source.startswith("*/", index):
                block_depth -= 1
                index += 2
            else:
                index += 1
            continue
        if source[index] in {"'", '"'}:
            quote = source[index]
            quote_backslash_escapes = _string_uses_backslash_escapes(source, index)
            index += 1
            continue
        if source.startswith("--", index):
            newline = source.find("\n", index)
            index = len(source) if newline == -1 else newline + 1
            continue
        if source.startswith("/*", index):
            block_depth = 1
            index += 2
            continue
        if source[index] == "$":
            delimiter = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", source[index:])
            if delimiter is not None:
                dollar_quote = delimiter.group(0)
                index += len(dollar_quote)
                continue
        if source[index] == ";":
            statements.append((start, index + 1))
            start = index + 1
        index += 1
    if block_depth or quote is not None or dollar_quote is not None:
        raise MigrationRunnerError("migration contains an unterminated SQL literal")
    if source[start:].strip():
        statements.append((start, len(source)))
    return statements


def _hex_sql_text(value: str) -> str:
    encoded = value.encode("utf-8").hex()
    return f"convert_from(decode('{encoded}', 'hex'), 'UTF8')"


def _apply_sql(*, source: str, body: str, version: str, name: str) -> str:
    # The source is encoded as hex, so neither SQL comments, dollar quotes, nor
    # migration text can alter the ledger statement.  The file name is already
    # constrained by MIGRATION_NAME.
    ledger_source = _hex_sql_text(source)
    return (
        "begin;\n"
        "set local statement_timeout = '180s';\n"
        f"{body}\n"
        "insert into supabase_migrations.schema_migrations(version, statements, name)\n"
        f"values ('{version}', array[{ledger_source}], '{name}');\n"
        "commit;\n"
    )


def _response_json(response: object) -> object:
    try:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    except OSError as error:
        raise MigrationRunnerError("Supabase Management API response could not be read") from error
    if len(raw) > MAX_RESPONSE_BYTES:
        raise MigrationRunnerError("Supabase Management API response exceeded the fixed byte limit")
    try:
        return json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationRunnerError("Supabase Management API returned invalid JSON") from error


class SupabaseManagementAPI:
    def __init__(
        self,
        *,
        token: str,
        project_ref: str,
        timeout: float = 60.0,
        opener: urllib.request.OpenerDirector | None = None,
    ) -> None:
        if not PERSONAL_TOKEN.fullmatch(token):
            raise MigrationRunnerError("SUPABASE_ACCESS_TOKEN must be an owner-scoped Personal token")
        if not PROJECT_REF.fullmatch(project_ref):
            raise MigrationRunnerError("SUPABASE_PROJECT_REF must be a canonical project reference")
        self._token = token
        self._project_ref = project_ref
        self._timeout = timeout
        self._opener = opener or urllib.request.build_opener(_RejectRedirects())

    def _request(self, *, method: str, path: str, body: str | None = None) -> object:
        url = f"{API_ROOT}/projects/{self._project_ref}{path}"
        payload = None if body is None else json.dumps({"query": body}).encode("utf-8")
        request = urllib.request.Request(url, data=payload, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Accept", "application/json")
        request.add_header("User-Agent", "pokecrack-supabase-migration-runner/1")
        if payload is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                return _response_json(response)
        except urllib.error.HTTPError as error:
            # Do not include the provider response: it can echo query text or
            # implementation details, and it is not needed to fail closed.
            raise MigrationRunnerError(
                f"Supabase Management API rejected the request (HTTP {error.code})"
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise MigrationRunnerError("Supabase Management API request failed") from error

    def verify_project(self) -> None:
        project = self._request(method="GET", path="")
        if not isinstance(project, dict) or project.get("ref") != self._project_ref:
            raise MigrationRunnerError("Supabase project identity could not be verified")

    def query(self, sql: str) -> object:
        return self._request(method="POST", path="/database/query", body=sql)


def _rows(payload: object, *, query_name: str) -> list[dict[str, object]]:
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise MigrationRunnerError(f"Supabase {query_name} response had an ambiguous shape")
    return [row for row in payload if isinstance(row, dict)]


def _server_version(api: SupabaseManagementAPI) -> int:
    rows = _rows(api.query(SERVER_VERSION_SQL), query_name="version")
    if len(rows) != 1 or set(rows[0]) != {"server_version_num"}:
        raise MigrationRunnerError("hosted PostgreSQL version response was ambiguous")
    value = rows[0]["server_version_num"]
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
        raise MigrationRunnerError("hosted PostgreSQL version response was invalid")
    version = int(value)
    if version < 170000:
        raise MigrationRunnerError("hosted PostgreSQL must be version 17 or newer")
    return version


def _check_ledger_shape(api: SupabaseManagementAPI) -> None:
    rows = _rows(api.query(LEDGER_COLUMNS_SQL), query_name="migration ledger")
    columns = [row.get("column_name") for row in rows]
    if columns != ["version", "statements", "name"]:
        raise MigrationRunnerError("hosted migration ledger shape is not the reviewed Supabase contract")


def _applied_versions(api: SupabaseManagementAPI) -> list[str]:
    rows = _rows(api.query(APPLIED_VERSIONS_SQL), query_name="applied migrations")
    versions: list[str] = []
    for row in rows:
        if set(row) != {"version"} or not isinstance(row["version"], str):
            raise MigrationRunnerError("hosted migration ledger returned an ambiguous version row")
        version = row["version"]
        if VERSION.fullmatch(version) is None:
            raise MigrationRunnerError("hosted migration ledger contains an invalid version")
        versions.append(version)
    if versions != sorted(versions) or len(set(versions)) != len(versions):
        raise MigrationRunnerError("hosted migration ledger is not strictly ordered")
    return versions


def _state(api: SupabaseManagementAPI, migrations: dict[str, tuple[Path, str]]) -> tuple[list[str], list[str]]:
    _server_version(api)
    _check_ledger_shape(api)
    applied = _applied_versions(api)
    local_versions = set(migrations)
    unknown = sorted(set(applied) - local_versions)
    if unknown:
        raise MigrationRunnerError(
            "hosted migration ledger contains versions missing from this checkout"
        )
    pending = sorted(local_versions - set(applied))
    return applied, pending


def _print_versions(versions: list[str]) -> None:
    for version in versions:
        print(version)


def run(arguments: argparse.Namespace) -> int:
    migrations = _migration_files(arguments.migrations_dir.resolve())
    project_ref = os.environ.get(PROJECT_ENV, "")
    token = os.environ.get(TOKEN_ENV, "")
    if arguments.project_ref is not None and arguments.project_ref != project_ref:
        raise MigrationRunnerError("command project reference does not match SUPABASE_PROJECT_REF")
    project_ref = arguments.project_ref or project_ref
    if not project_ref:
        raise MigrationRunnerError("SUPABASE_PROJECT_REF is required")
    if not token:
        raise MigrationRunnerError("SUPABASE_ACCESS_TOKEN is required")

    api = SupabaseManagementAPI(token=token, project_ref=project_ref)
    api.verify_project()
    applied, pending = _state(api, migrations)

    if arguments.mode == "list":
        _print_versions(applied)
        return 0
    if arguments.mode == "preview":
        for version in pending:
            print(migrations[version][0].name)
        return 0
    if arguments.mode == "verify":
        if pending:
            raise MigrationRunnerError("hosted database still has pending migrations")
        print("migration ledger is current")
        return 0

    for version in pending:
        path, name = migrations[version]
        source = _read_migration(path)
        body = _transaction_body(source, filename=path.name)
        api.query(_apply_sql(source=source, body=body, version=version, name=name))
        applied_after = _applied_versions(api)
        if applied_after.count(version) != 1:
            raise MigrationRunnerError(f"migration {version} was not recorded exactly once")
    print(f"applied {len(pending)} forward migration(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("list", "preview", "apply", "verify"), help="read or advance the hosted ledger"
    )
    parser.add_argument(
        "--migrations-dir", type=Path, default=Path("supabase/migrations"), help="local migration directory"
    )
    parser.add_argument(
        "--project-ref", help="optional assertion matching SUPABASE_PROJECT_REF (never a credential)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except MigrationRunnerError as error:
        print(f"supabase migration runner: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
