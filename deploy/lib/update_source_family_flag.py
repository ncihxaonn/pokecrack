#!/usr/bin/env python3
"""Atomically change only the source-family opt-in; no DB writes or restart."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import secrets
import stat

from update_worker_database_url import (
    MAX_ENV_BYTES,
    WorkerDatabaseUrlError,
    _read_owner_only_at,
    _safe_absolute_path,
)

KEY = "SOURCE_FAMILY_COLLECTION_ENABLED"


def update_flag(env_file: Path, value: str) -> None:
    env_file = _safe_absolute_path(str(env_file))
    if value not in {"true", "false"}:
        raise WorkerDatabaseUrlError("source-family flag must be true or false")
    directory = descriptor = -1
    temporary: str | None = None
    try:
        directory = os.open(
            env_file.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
        )
        parent = os.fstat(directory)
        if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o022:
            raise WorkerDatabaseUrlError(
                "environment directory failed ownership checks"
            )
        payload, original = _read_owner_only_at(
            directory, env_file.name, maximum_bytes=MAX_ENV_BYTES
        )
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise WorkerDatabaseUrlError("environment must be UTF-8") from error
        if "\x00" in text or "\r" in text or not text.endswith("\n"):
            raise WorkerDatabaseUrlError("environment format is invalid")
        lines = text[:-1].split("\n")
        matches = [
            i
            for i, line in enumerate(lines)
            if re.match(r"\s*(?:export\s+)?" + KEY + r"\s*=", line)
        ]
        if len(matches) > 1 or (
            matches and lines[matches[0]] not in {KEY + "=true", KEY + "=false"}
        ):
            raise WorkerDatabaseUrlError("source-family assignment is ambiguous")
        if value == "true":
            prerequisites = [
                line
                for line in lines
                if re.match(
                    r"\s*(?:export\s+)?PUBLIC_STUDY_COLLECTION_ENABLED\s*=", line
                )
            ]
            if prerequisites != ["PUBLIC_STUDY_COLLECTION_ENABLED=true"]:
                raise WorkerDatabaseUrlError(
                    "public-study collection must already be explicitly enabled"
                )
        if matches:
            lines[matches[0]] = KEY + "=" + value
        else:
            lines.append(KEY + "=" + value)
        updated = ("\n".join(lines) + "\n").encode()
        if len(updated) > MAX_ENV_BYTES:
            raise WorkerDatabaseUrlError("updated environment is too large")
        temporary = f".{env_file.name}.{secrets.token_hex(12)}"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        os.fchmod(descriptor, stat.S_IMODE(original.st_mode))
        remaining = memoryview(updated)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("short write")
            remaining = remaining[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        current = os.stat(env_file.name, dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(current.st_mode) or any(
            getattr(current, key) != getattr(original, key)
            for key in (
                "st_dev",
                "st_ino",
                "st_uid",
                "st_mode",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
        ):
            raise WorkerDatabaseUrlError("environment changed during update")
        os.replace(temporary, env_file.name, src_dir_fd=directory, dst_dir_fd=directory)
        temporary = None
        os.fsync(directory)
    except OSError as error:
        raise WorkerDatabaseUrlError(
            "source-family environment update failed"
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary is not None and directory >= 0:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
        if directory >= 0:
            os.close(directory)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--value", required=True, choices=("true", "false"))
    args = parser.parse_args()
    try:
        update_flag(Path(args.env_file), args.value)
    except WorkerDatabaseUrlError as error:
        parser.error(str(error))
    print("source-family flag updated; database gate and services unchanged")


if __name__ == "__main__":
    main()
