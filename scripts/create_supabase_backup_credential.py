#!/usr/bin/env python3
"""Mint a short-lived Supabase CLI login for one reviewed logical backup.

The owner-scoped Management API token stays in this process. Only a temporary
Postgres URL is written, to a caller-selected owner-only file, and neither the
URL nor either credential is printed. The generated URL uses the project's
direct PostgreSQL endpoint, matching the official CLI login path. The temporary
login is a bare Postgres role; the backup command explicitly requests the
``postgres`` effective role after connecting through that login.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request


API_ROOT = "https://api.supabase.com/v1"
TOKEN_ENV = "SUPABASE_ACCESS_TOKEN"
PROJECT_ENV = "SUPABASE_PROJECT_REF"
PROJECT_REF = re.compile(r"^[a-z0-9]{20}$")
PERSONAL_TOKEN = re.compile(r"^sbp_[A-Za-z0-9._~-]{16,256}$")
LOGIN_ROLE = re.compile(r"^cli_login_[A-Za-z0-9_]{1,48}$")
MAX_RESPONSE_BYTES = 1024 * 1024
MINIMUM_TTL_SECONDS = 300
MAXIMUM_TTL_SECONDS = 3600
CLI_LOGIN_ROLES_SQL = (
    "select rolname::text as role from pg_catalog.pg_roles "
    "where left(rolname, 10) = 'cli_login_' order by rolname"
)


class TemporaryCredentialError(RuntimeError):
    """A temporary backup credential could not be created safely."""


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Never forward the owner bearer token away from the pinned API host."""

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


class SupabaseManagementAPI:
    def __init__(
        self,
        *,
        token: str,
        project_ref: str,
        opener: urllib.request.OpenerDirector | None = None,
        timeout: float = 60.0,
    ) -> None:
        if not PERSONAL_TOKEN.fullmatch(token):
            raise TemporaryCredentialError(
                "SUPABASE_ACCESS_TOKEN must be an owner-scoped personal token"
            )
        if not PROJECT_REF.fullmatch(project_ref):
            raise TemporaryCredentialError(
                "SUPABASE_PROJECT_REF must be a canonical project reference"
            )
        self._token = token
        self._project_ref = project_ref
        self._timeout = timeout
        self._opener = opener or urllib.request.build_opener(_RejectRedirects())

    def _request(
        self, *, method: str, path: str, body: object | None = None
    ) -> object:
        if not path.startswith("/") or "?" in path or "#" in path:
            raise TemporaryCredentialError("invalid Management API path")
        url = f"{API_ROOT}/projects/{self._project_ref}{path}"
        payload = None
        if body is not None:
            payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(url, data=payload, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Accept", "application/json")
        request.add_header("User-Agent", "pokecrack-production-backup/1")
        if payload is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise TemporaryCredentialError(
                f"Supabase Management API rejected the request (HTTP {error.code})"
            ) from error
        except (OSError, urllib.error.URLError) as error:
            raise TemporaryCredentialError(
                "Supabase Management API request failed"
            ) from error
        if len(raw) > MAX_RESPONSE_BYTES:
            raise TemporaryCredentialError("Supabase Management API response was too large")
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TemporaryCredentialError(
                "Supabase Management API returned invalid JSON"
            ) from error

    def create_login_role(self) -> object:
        return self._request(
            method="POST", path="/cli/login-role", body={"read_only": False}
        )

    def query(self, sql: str) -> object:
        return self._request(
            method="POST", path="/database/query", body={"query": sql}
        )

    def delete_login_roles(self) -> None:
        payload = self._request(method="DELETE", path="/cli/login-role")
        if not isinstance(payload, dict) or payload.get("message") != "ok":
            raise TemporaryCredentialError(
                "Supabase login-role cleanup response was ambiguous"
            )


def _login(payload: object) -> tuple[str, str, int]:
    if not isinstance(payload, dict):
        raise TemporaryCredentialError("Supabase login-role response had an ambiguous shape")
    role = payload.get("role")
    password = payload.get("password")
    ttl_seconds = payload.get("ttl_seconds")
    if (
        not isinstance(role, str)
        or LOGIN_ROLE.fullmatch(role) is None
        or not isinstance(password, str)
        or not password
        or len(password.encode("utf-8")) > 1024
        or any(character in password for character in ("\0", "\r", "\n"))
        or not isinstance(ttl_seconds, int)
        or isinstance(ttl_seconds, bool)
        or ttl_seconds < MINIMUM_TTL_SECONDS
        or ttl_seconds > MAXIMUM_TTL_SECONDS
    ):
        raise TemporaryCredentialError("Supabase login-role response was invalid")
    return role, password, ttl_seconds


def _role_name(payload: object) -> str:
    if not isinstance(payload, dict):
        raise TemporaryCredentialError("Supabase login-role response had an ambiguous shape")
    role = payload.get("role")
    if not isinstance(role, str) or LOGIN_ROLE.fullmatch(role) is None:
        raise TemporaryCredentialError("Supabase login-role response had an invalid role")
    return role


def build_database_url(
    *, project_ref: str, role: str, password: str
) -> str:
    if PROJECT_REF.fullmatch(project_ref) is None:
        raise TemporaryCredentialError("Supabase project reference was invalid")
    if LOGIN_ROLE.fullmatch(role) is None:
        raise TemporaryCredentialError("Supabase login role was invalid")
    if (
        not isinstance(password, str)
        or not password
        or len(password.encode("utf-8")) > 1024
        or any(character in password for character in ("\0", "\r", "\n"))
    ):
        raise TemporaryCredentialError("Supabase login password was invalid")

    username = urllib.parse.quote(role, safe="")
    encoded_password = urllib.parse.quote(password, safe="")
    root_certificate = urllib.parse.quote(
        "/run/supabase-prod-ca-2021.crt", safe=""
    )
    return (
        f"postgresql://{username}:{encoded_password}@db.{project_ref}.supabase.co:5432/postgres"
        f"?sslmode=verify-full&sslrootcert={root_certificate}&connect_timeout=15"
        f"&application_name=pokecrack-backup"
    )


def _write_owner_only(path: Path, value: str) -> None:
    if not path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
        raise TemporaryCredentialError("credential output must use a safe absolute path")
    parent = path.parent
    try:
        metadata = parent.lstat()
    except OSError as error:
        raise TemporaryCredentialError("credential output directory is unavailable") from error
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or parent.is_symlink()
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise TemporaryCredentialError(
            "credential output directory must be private, owned, and real"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = -1
    created = False
    try:
        descriptor = os.open(path, flags, 0o600)
        created = True
        remaining = memoryview(value.encode("utf-8") + b"\n")
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("credential write made no progress")
            remaining = remaining[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.chmod(path, 0o600, follow_symlinks=False)
    except OSError as error:
        if descriptor >= 0:
            os.close(descriptor)
        if created:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise TemporaryCredentialError(
            "credential output file could not be created safely"
        ) from error


def _read_owner_only_role(path: Path) -> str:
    if not path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
        raise TemporaryCredentialError("expected role file must use a safe absolute path")
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        metadata = os.fstat(descriptor)
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            raw = stream.read(256)
            if stream.read(1):
                raise TemporaryCredentialError("expected role file was invalid")
        value = raw.decode("utf-8")
    except TemporaryCredentialError:
        raise
    except (OSError, UnicodeError) as error:
        raise TemporaryCredentialError("expected role file is unavailable") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
        or len(value.splitlines()) != 1
        or LOGIN_ROLE.fullmatch(value.rstrip("\n")) is None
    ):
        raise TemporaryCredentialError("expected role file was invalid")
    return value.rstrip("\n")


def _active_cli_login_roles(api: SupabaseManagementAPI) -> list[str]:
    payload = api.query(CLI_LOGIN_ROLES_SQL)
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise TemporaryCredentialError("Supabase CLI role query response was ambiguous")
    roles: list[str] = []
    for row in payload:
        if set(row) != {"role"}:
            raise TemporaryCredentialError("Supabase CLI role query response was ambiguous")
        role = row["role"]
        if not isinstance(role, str) or LOGIN_ROLE.fullmatch(role) is None:
            raise TemporaryCredentialError("Supabase CLI role query response was invalid")
        roles.append(role)
    if roles != sorted(set(roles)):
        raise TemporaryCredentialError("Supabase CLI role query response was not canonical")
    return roles


def delete_expected_login_role(
    api: SupabaseManagementAPI, *, expected_role: str
) -> None:
    if LOGIN_ROLE.fullmatch(expected_role) is None:
        raise TemporaryCredentialError("expected temporary login role was invalid")
    active = _active_cli_login_roles(api)
    if not active:
        return
    if active != [expected_role]:
        raise TemporaryCredentialError(
            "temporary login cleanup refused while another CLI login is active"
        )
    api.delete_login_roles()
    if _active_cli_login_roles(api):
        raise TemporaryCredentialError(
            "temporary login cleanup could not be verified"
        )


def create(
    api: SupabaseManagementAPI,
    *,
    project_ref: str,
    output: Path,
    role_output: Path,
) -> None:
    if _active_cli_login_roles(api):
        raise TemporaryCredentialError(
            "temporary login creation refused while another CLI login is active"
        )
    role_created = False
    role = ""
    try:
        login_payload = api.create_login_role()
        role = _role_name(login_payload)
        role_created = True
        _write_owner_only(role_output, role)
        role, password, _ttl_seconds = _login(login_payload)
        database_url = build_database_url(
            project_ref=project_ref,
            role=role,
            password=password,
        )
        _write_owner_only(output, database_url)
    except Exception:
        if role_created:
            try:
                delete_expected_login_role(api, expected_role=role)
            except TemporaryCredentialError as cleanup_error:
                raise TemporaryCredentialError(
                    "temporary login setup failed and cleanup could not be confirmed"
                ) from cleanup_error
        raise


def _project_ref(arguments: argparse.Namespace) -> str:
    environment_ref = os.environ.get(PROJECT_ENV, "")
    if arguments.project_ref != environment_ref:
        raise TemporaryCredentialError(
            "command project reference must match SUPABASE_PROJECT_REF"
        )
    if PROJECT_REF.fullmatch(environment_ref) is None:
        raise TemporaryCredentialError(
            "SUPABASE_PROJECT_REF must be a canonical project reference"
        )
    return environment_ref


def run(arguments: argparse.Namespace) -> int:
    project_ref = _project_ref(arguments)
    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        raise TemporaryCredentialError("SUPABASE_ACCESS_TOKEN is required")
    api = SupabaseManagementAPI(token=token, project_ref=project_ref)
    if arguments.mode == "create":
        if arguments.output is None or arguments.role_output is None:
            raise TemporaryCredentialError("create requires --output and --role-output")
        if arguments.expected_role_file is not None:
            raise TemporaryCredentialError("create does not accept --expected-role-file")
        create(
            api,
            project_ref=project_ref,
            output=arguments.output,
            role_output=arguments.role_output,
        )
    else:
        if arguments.output is not None or arguments.role_output is not None:
            raise TemporaryCredentialError("delete does not accept output arguments")
        if arguments.expected_role_file is None:
            raise TemporaryCredentialError("delete requires --expected-role-file")
        delete_expected_login_role(
            api,
            expected_role=_read_owner_only_role(arguments.expected_role_file),
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("create", "delete"))
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--role-output", type=Path)
    parser.add_argument("--expected-role-file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except TemporaryCredentialError as error:
        print(f"temporary backup credential: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
