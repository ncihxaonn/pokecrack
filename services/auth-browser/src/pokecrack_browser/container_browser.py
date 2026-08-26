"""Container-owned BrowserManager supervisor for exactly one configured profile."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from collections.abc import Callable
from typing import Any, Protocol

from .config import ServiceSettings
from .errors import ServiceError
from .manager import BrowserManager
from .paths import PathValidationError, validate_profile_name
from .runtime import process_matches_identity, read_runtime_state


class _Manager(Protocol):
    def start(self, profile: str) -> dict[str, Any]: ...
    def stop(self, profile: str) -> dict[str, Any]: ...


def supervise_profile(
    settings: ServiceSettings,
    profile: str,
    *,
    stop_event: threading.Event,
    manager_factory: Callable[[ServiceSettings], _Manager] = BrowserManager,
    matches_identity: Callable[[int, str], bool] = process_matches_identity,
    poll_seconds: float = 0.25,
) -> int:
    """Keep the manager-owned child alive and release its lock on shutdown."""

    validate_profile_name(profile)
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be positive")
    manager = manager_factory(settings)
    started = manager.start(profile)
    pid = started.get("pid")
    identity = started.get("process_identity")
    if isinstance(pid, bool) or not isinstance(pid, int) or not isinstance(identity, str):
        raise ServiceError("internal_error", "browser manager returned invalid process state")
    try:
        while not stop_event.wait(poll_seconds):
            state = read_runtime_state(settings.runtime_root)
            if (
                state is None
                or state.get("profile") != profile
                or state.get("pid") != pid
                or state.get("process_identity") != identity
                or not matches_identity(pid, identity)
            ):
                return 1
        return 0
    finally:
        state = read_runtime_state(settings.runtime_root)
        if state is not None and state.get("profile") == profile:
            try:
                manager.stop(profile)
            except ServiceError as error:
                if error.category != "not_running":
                    raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stop = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        return supervise_profile(
            ServiceSettings.from_env(),
            args.profile,
            stop_event=stop,
        )
    except (PathValidationError, ValueError) as error:
        failure = ServiceError("invalid_request", str(error))
    except ServiceError as error:
        failure = error
    print(json.dumps(failure.as_payload(), sort_keys=True), file=sys.stderr)
    return failure.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
