#!/usr/bin/env python3
"""Atomically install the protected generic worker database URL."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import secrets
import stat
import urllib.parse


PROJECT_REF = "wohnphsxlquhhknuthrj"
EXPECTED_USERNAME = f"pokecrack_worker.{PROJECT_REF}"
POOLER_HOST = re.compile(r"^aws-[0-9]+-ap-southeast-2\.pooler\.supabase\.com$")
MAX_ENV_BYTES = 64 * 1024
MAX_DATABASE_URL_BYTES = 4096
EXPECTED_QUERY = {
    "application_name": "pokecrack-worker",
    "connect_timeout": "10",
    "sslmode": "verify-full",
    "sslrootcert": "/run/supabase-prod-ca-2021.crt",
}


class WorkerDatabaseUrlError(RuntimeError):
    """A fail-closed credential or target-file validation error."""


def _safe_absolute_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
        raise WorkerDatabaseUrlError("path must be safe and absolute")
    return path


def _read_owner_only(path: Path, *, maximum_bytes: int) -> tuple[bytes, os.stat_result]:
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        metadata = os.fstat(descriptor)
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            payload = stream.read(maximum_bytes + 1)
    except OSError as error:
        raise WorkerDatabaseUrlError("protected file is unavailable") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
        or len(payload) > maximum_bytes
    ):
        raise WorkerDatabaseUrlError("protected file failed ownership or size checks")
    return payload, metadata


def _read_owner_only_at(
    directory_descriptor: int,
    name: str,
    *,
    maximum_bytes: int,
) -> tuple[bytes, os.stat_result]:
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_descriptor,
        )
        metadata = os.fstat(descriptor)
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            payload = stream.read(maximum_bytes + 1)
    except OSError as error:
        raise WorkerDatabaseUrlError("protected file is unavailable") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
        or len(payload) > maximum_bytes
    ):
        raise WorkerDatabaseUrlError("protected file failed ownership or size checks")
    return payload, metadata


def validate_database_url(value: str) -> str:
    if (
        not value
        or len(value.encode("utf-8")) > MAX_DATABASE_URL_BYTES
        or any(character in value for character in ("\x00", "\r", "\n"))
    ):
        raise WorkerDatabaseUrlError("worker database URL is invalid")
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
        username = urllib.parse.unquote(parsed.username or "")
        password = urllib.parse.unquote(parsed.password or "")
        query_pairs = urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
        )
    except (UnicodeError, ValueError) as error:
        raise WorkerDatabaseUrlError("worker database URL is invalid") from error
    query = dict(query_pairs)
    if (
        parsed.scheme != "postgresql"
        or parsed.fragment
        or parsed.hostname is None
        or POOLER_HOST.fullmatch(parsed.hostname) is None
        or port != 5432
        or parsed.path != "/postgres"
        or username != EXPECTED_USERNAME
        or not password
        or len(password.encode("utf-8")) > 1024
        or len(query_pairs) != len(EXPECTED_QUERY)
        or query != EXPECTED_QUERY
    ):
        raise WorkerDatabaseUrlError("worker database URL is outside the reviewed contract")
    return value


def update_worker_database_url(*, env_file: Path, database_url_file: Path) -> None:
    parent = env_file.parent
    if env_file.name in {"", ".", ".."}:
        raise WorkerDatabaseUrlError("environment file name is invalid")

    parent_descriptor = -1
    temporary_name: str | None = None
    descriptor = -1
    try:
        directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        directory_flags |= getattr(os, "O_DIRECTORY", 0)
        parent_descriptor = os.open(parent, directory_flags)
        parent_metadata = os.fstat(parent_descriptor)
        if (
            not stat.S_ISDIR(parent_metadata.st_mode)
            or parent_metadata.st_uid != os.geteuid()
            or stat.S_IMODE(parent_metadata.st_mode) & 0o022
        ):
            raise WorkerDatabaseUrlError(
                "environment directory failed ownership checks"
            )

        env_payload, env_metadata = _read_owner_only_at(
            parent_descriptor,
            env_file.name,
            maximum_bytes=MAX_ENV_BYTES,
        )
        url_payload, _ = _read_owner_only(
            database_url_file,
            maximum_bytes=MAX_DATABASE_URL_BYTES + 1,
        )
        try:
            env_text = env_payload.decode("utf-8")
            url_text = url_payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise WorkerDatabaseUrlError("protected file is not UTF-8") from error
        if "\x00" in env_text or "\r" in env_text or not env_text.endswith("\n"):
            raise WorkerDatabaseUrlError("production environment file is invalid")
        if not url_text.endswith("\n") or url_text.count("\n") != 1:
            raise WorkerDatabaseUrlError(
                "worker database URL file must contain one line"
            )
        database_url = validate_database_url(url_text.removesuffix("\n"))

        lines = env_text.removesuffix("\n").split("\n")
        matching = [
            index
            for index, line in enumerate(lines)
            if line.startswith("SUPABASE_DB_URL=")
        ]
        if len(matching) != 1:
            raise WorkerDatabaseUrlError(
                "production environment must contain exactly one "
                "SUPABASE_DB_URL assignment"
            )
        lines[matching[0]] = f"SUPABASE_DB_URL={database_url}"
        updated = ("\n".join(lines) + "\n").encode("utf-8")

        for _ in range(16):
            candidate = f".{env_file.name}.{secrets.token_hex(12)}"
            try:
                descriptor = os.open(
                    candidate,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent_descriptor,
                )
            except FileExistsError:
                continue
            temporary_name = candidate
            break
        if descriptor < 0 or temporary_name is None:
            raise OSError("cannot allocate environment update file")
        os.fchmod(descriptor, stat.S_IMODE(env_metadata.st_mode))
        remaining = memoryview(updated)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("environment update made no progress")
            remaining = remaining[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        current_metadata = os.stat(
            env_file.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(current_metadata.st_mode)
            or current_metadata.st_dev != env_metadata.st_dev
            or current_metadata.st_ino != env_metadata.st_ino
            or current_metadata.st_uid != env_metadata.st_uid
            or stat.S_IMODE(current_metadata.st_mode)
            != stat.S_IMODE(env_metadata.st_mode)
        ):
            raise WorkerDatabaseUrlError(
                "production environment changed during update"
            )
        os.replace(
            temporary_name,
            env_file.name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        temporary_name = None
        os.fsync(parent_descriptor)
    except OSError as error:
        raise WorkerDatabaseUrlError("production environment update failed") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_name is not None and parent_descriptor >= 0:
            try:
                os.unlink(temporary_name, dir_fd=parent_descriptor)
            except FileNotFoundError:
                pass
        if parent_descriptor >= 0:
            os.close(parent_descriptor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--database-url-file", required=True)
    arguments = parser.parse_args(argv)
    try:
        update_worker_database_url(
            env_file=_safe_absolute_path(arguments.env_file),
            database_url_file=_safe_absolute_path(arguments.database_url_file),
        )
    except WorkerDatabaseUrlError as error:
        parser.error(str(error))
    print("worker database URL updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
