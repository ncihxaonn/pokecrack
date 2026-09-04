"""Run the reviewed backup with a minimal, non-executable dotenv projection."""

from __future__ import annotations

import argparse
import gzip
import os
import pwd
import re
import shlex
import stat
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from io import BufferedReader, TextIOWrapper
from pathlib import Path
from typing import cast

ALLOWED_KEYS = frozenset(
    {
        "BACKUP_DIR",
        "BACKUP_RETENTION_DAILY",
        "BACKUP_RETENTION_WEEKLY",
        "SUPABASE_DB_URL",
        "SUPABASE_DB_URL_FILE",
    }
)
KEY_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
ABSOLUTE_PATH_PATTERN = re.compile(r"/[A-Za-z0-9._/-]+\Z")
BACKUP_FILENAME_PATTERN = re.compile(r"pokecrack-[0-9]{8}T[0-9]{6}Z\.sql\.gz\Z")
SAFE_PATH = (
    "/usr/lib/postgresql/17/bin:/usr/local/sbin:/usr/local/bin:"
    "/usr/sbin:/usr/bin:/sbin:/bin"
)
POSTGRES_CLIENT_COMMANDS = ("pg_dump", "psql")


class BackupEnvironmentError(RuntimeError):
    """An environment or completed-backup contract was not satisfied."""


def _safe_directory(metadata: os.stat_result) -> bool:
    permissions = stat.S_IMODE(metadata.st_mode)
    if not stat.S_ISDIR(metadata.st_mode):
        return False
    if permissions & 0o022 == 0:
        return True
    return metadata.st_uid == 0 and bool(permissions & stat.S_ISVTX)


def _validate_postgres_client_directory(path: Path) -> None:
    """Require a private directory containing only owner-controlled clients."""

    path_text = str(path)
    if (
        not ABSOLUTE_PATH_PATTERN.fullmatch(path_text)
        or ".." in path.parts
        or len(path.parts) < 2
    ):
        raise BackupEnvironmentError(
            "PostgreSQL client directory must use a safe absolute path"
        )
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise BackupEnvironmentError(
            "PostgreSQL client directory is unavailable"
        ) from exc
    permissions = stat.S_IMODE(metadata.st_mode)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or permissions & 0o077
    ):
        raise BackupEnvironmentError(
            "PostgreSQL client directory must be a private owned directory"
        )

    for command in POSTGRES_CLIENT_COMMANDS:
        candidate = path / command
        with _open_owner_only_file(
            candidate, label=f"reviewed PostgreSQL client {command}", binary=True
        ) as stream:
            command_permissions = stat.S_IMODE(os.fstat(stream.fileno()).st_mode)
        if not command_permissions & stat.S_IXUSR:
            raise BackupEnvironmentError(
                f"reviewed PostgreSQL client is not private and executable: {command}"
            )


@contextmanager
def _open_owner_only_file(
    path: Path, *, label: str, binary: bool = False
) -> Iterator[BufferedReader | TextIOWrapper]:
    if not path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
        raise BackupEnvironmentError(f"{label} must use a safe absolute path")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory_fd = -1
    file_fd = -1
    try:
        directory_fd = os.open("/", directory_flags)
        if not _safe_directory(os.fstat(directory_fd)):
            raise BackupEnvironmentError(f"{label} has an unsafe parent directory")
        for component in path.parts[1:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
            if not _safe_directory(os.fstat(directory_fd)):
                raise BackupEnvironmentError(f"{label} has an unsafe parent directory")
        file_fd = os.open(path.name, file_flags, dir_fd=directory_fd)
    except OSError as exc:
        raise BackupEnvironmentError(f"{label} is unavailable") from exc
    finally:
        if directory_fd >= 0:
            os.close(directory_fd)

    try:
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise BackupEnvironmentError(f"{label} must be a regular file")
        if metadata.st_uid != os.geteuid():
            raise BackupEnvironmentError(f"{label} must be owned by the backup user")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise BackupEnvironmentError(
                f"{label} must be inaccessible to group and other users"
            )
        raw_stream = os.fdopen(file_fd, "rb", closefd=True)
        file_fd = -1
        if binary:
            with raw_stream:
                yield raw_stream
        else:
            with TextIOWrapper(raw_stream, encoding="utf-8") as text_stream:
                yield text_stream
    finally:
        if file_fd >= 0:
            os.close(file_fd)


def read_backup_environment(path: Path) -> dict[str, str]:
    """Read only backup-related assignments without executing dotenv content."""

    try:
        with _open_owner_only_file(path, label="production environment file") as stream:
            lines = cast(TextIOWrapper, stream).read().splitlines()
    except (OSError, UnicodeError) as exc:
        raise BackupEnvironmentError(
            "production environment file is unreadable"
        ) from exc

    values: dict[str, str] = {}
    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not KEY_PATTERN.fullmatch(key) or key not in ALLOWED_KEYS:
            continue
        if key in values:
            raise BackupEnvironmentError(f"duplicate backup setting: {key}")
        try:
            tokens = shlex.split(raw_value, comments=True, posix=True)
        except ValueError as exc:
            raise BackupEnvironmentError(
                f"invalid quoting for backup setting: {key}"
            ) from exc
        if len(tokens) > 1:
            raise BackupEnvironmentError(
                f"backup setting must contain one value: {key}"
            )
        values[key] = tokens[0] if tokens else ""
    return values


def build_backup_environment(
    values: dict[str, str],
    *,
    default_db_url_file: Path,
    dedicated_db_url_file: Path | None = None,
    postgres_client_directory: Path | None = None,
) -> tuple[dict[str, str], Path]:
    backup_dir_value = values.get("BACKUP_DIR", "")
    if (
        not ABSOLUTE_PATH_PATTERN.fullmatch(backup_dir_value)
        or ".." in Path(backup_dir_value).parts
    ):
        raise BackupEnvironmentError(
            "BACKUP_DIR must be an explicit safe absolute path"
        )

    database_url = values.get("SUPABASE_DB_URL", "")
    database_url_file = values.get("SUPABASE_DB_URL_FILE", "")
    if dedicated_db_url_file is not None:
        # A production worker DSN and an owner-capable backup DSN are distinct
        # capabilities. An explicit dedicated file always wins and prevents an
        # inline worker credential from being reused accidentally.
        database_url = ""
        database_url_file = str(dedicated_db_url_file)
    else:
        if database_url and database_url_file:
            raise BackupEnvironmentError(
                "configure only one Supabase database credential source"
            )
        if not database_url and not database_url_file:
            database_url_file = str(default_db_url_file)
    if database_url_file:
        database_url_path = Path(database_url_file)
        try:
            with _open_owner_only_file(
                database_url_path, label="Supabase database URL file"
            ) as stream:
                database_url_lines = cast(TextIOWrapper, stream).read().splitlines()
        except (OSError, UnicodeError) as exc:
            raise BackupEnvironmentError(
                "Supabase database URL file is unreadable"
            ) from exc
        if len(database_url_lines) != 1 or not database_url_lines[0]:
            raise BackupEnvironmentError(
                "Supabase database URL file must contain exactly one non-empty line"
            )
        database_url = database_url_lines[0]

    path_value = SAFE_PATH
    if postgres_client_directory is not None:
        _validate_postgres_client_directory(postgres_client_directory)
        path_value = f"{postgres_client_directory}:{SAFE_PATH}"

    child_environment = {
        "BACKUP_DIR": backup_dir_value,
        "HOME": pwd.getpwuid(os.geteuid()).pw_dir,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": path_value,
        "TMPDIR": "/tmp",
    }
    for key in ("BACKUP_RETENTION_DAILY", "BACKUP_RETENTION_WEEKLY"):
        value = values.get(key, "")
        if value:
            child_environment[key] = value
    child_environment["SUPABASE_DB_URL"] = database_url
    return child_environment, Path(backup_dir_value)


def validate_completed_backup(backup_dir: Path) -> str:
    marker = backup_dir / ".last-successful-backup"
    try:
        with _open_owner_only_file(marker, label="backup success marker") as stream:
            filename = cast(TextIOWrapper, stream).read().splitlines()[0]
    except (IndexError, OSError, UnicodeError) as exc:
        raise BackupEnvironmentError("backup success marker is unreadable") from exc
    if not BACKUP_FILENAME_PATTERN.fullmatch(filename):
        raise BackupEnvironmentError("backup success marker has an invalid filename")

    backup_path = backup_dir / filename
    uncompressed_bytes = 0
    try:
        with (
            _open_owner_only_file(
                backup_path, label="completed backup", binary=True
            ) as raw_stream,
            gzip.GzipFile(
                fileobj=cast(BufferedReader, raw_stream), mode="rb"
            ) as stream,
        ):
            while chunk := stream.read(1024 * 1024):
                uncompressed_bytes += len(chunk)
    except (OSError, EOFError) as exc:
        raise BackupEnvironmentError("completed backup failed gzip validation") from exc
    if uncompressed_bytes == 0:
        raise BackupEnvironmentError("completed backup is empty")
    return filename


def run_backup(arguments: argparse.Namespace) -> str:
    backup_script = arguments.backup_script
    try:
        script_metadata = backup_script.lstat()
    except OSError as exc:
        raise BackupEnvironmentError("reviewed backup script is unavailable") from exc
    if not stat.S_ISREG(script_metadata.st_mode) or backup_script.is_symlink():
        raise BackupEnvironmentError("reviewed backup script must be a regular file")

    values = read_backup_environment(arguments.env_file)
    child_environment, backup_dir = build_backup_environment(
        values,
        default_db_url_file=arguments.default_db_url_file,
        dedicated_db_url_file=arguments.dedicated_db_url_file,
        postgres_client_directory=arguments.postgres_client_directory,
    )
    result = subprocess.run(
        [str(backup_script)],
        check=False,
        env=child_environment,
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    if result.returncode != 0:
        raise BackupEnvironmentError("reviewed backup script failed")
    return validate_completed_backup(backup_dir)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--backup-script", required=True, type=Path)
    parser.add_argument("--default-db-url-file", required=True, type=Path)
    parser.add_argument("--dedicated-db-url-file", type=Path)
    parser.add_argument("--postgres-client-directory", type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        filename = run_backup(parse_arguments())
    except BackupEnvironmentError as exc:
        print(f"backup environment: {exc}", file=sys.stderr)
        return 1
    print(filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
