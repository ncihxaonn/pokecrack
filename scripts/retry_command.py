#!/usr/bin/env python3
"""Run a non-interactive command with a small, bounded retry budget.

This is used by GitHub Actions around the approved MAM SSH/scp hops.  It only
retries the exact command supplied by the workflow, never changes routes or
credentials, and publishes captured stdout only after a successful attempt so
that a dropped connection cannot leave a partial JSON artifact behind.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (5, 10)


def run_with_retries(
    command: Sequence[str],
    *,
    attempts: int = MAX_ATTEMPTS,
    input_path: Path | None = None,
    output_path: Path | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    if not command or type(attempts) is not int or not 1 <= attempts <= MAX_ATTEMPTS:
        raise ValueError("invalid_retry_command")
    if input_path is not None and not input_path.is_file():
        raise ValueError("invalid_retry_input")

    for attempt in range(1, attempts + 1):
        try:
            input_handle = input_path.open("rb") if input_path is not None else None
            try:
                completed = subprocess.run(
                    list(command),
                    stdin=input_handle,
                    stdout=subprocess.PIPE,
                    check=False,
                )
            finally:
                if input_handle is not None:
                    input_handle.close()
        except OSError:
            completed = subprocess.CompletedProcess(list(command), 127, b"")

        if completed.returncode == 0:
            if output_path is None:
                sys.stdout.buffer.write(completed.stdout)
                sys.stdout.buffer.flush()
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path: str | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=output_path.parent,
                        prefix=f".{output_path.name}.retry-",
                        delete=False,
                    ) as temporary:
                        temporary_path = temporary.name
                        temporary.write(completed.stdout)
                        temporary.flush()
                        os.fsync(temporary.fileno())
                    os.replace(temporary_path, output_path)
                    temporary_path = None
                finally:
                    if temporary_path is not None:
                        try:
                            os.unlink(temporary_path)
                        except FileNotFoundError:
                            pass
            return 0

        if attempt < attempts:
            sleeper(BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)])

    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts", type=int, default=MAX_ATTEMPTS)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    try:
        return run_with_retries(
            command,
            attempts=args.attempts,
            input_path=args.input,
            output_path=args.output,
        )
    except ValueError:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
