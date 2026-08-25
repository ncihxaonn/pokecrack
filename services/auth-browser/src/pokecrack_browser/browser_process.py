"""Long-lived headed Playwright worker started by the lifecycle manager."""

from __future__ import annotations

import argparse
import os
import signal
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from .launcher import BrowserLaunchConfig, playwright_launch_options


class _Context(Protocol):
    def close(self) -> None: ...


class _PlaywrightManager(Protocol):
    def __enter__(self) -> Any: ...
    def __exit__(self, *args: object) -> object: ...


def run_persistent_context(
    config: BrowserLaunchConfig,
    *,
    stop_event: threading.Event,
    playwright_factory: Callable[[], _PlaywrightManager],
) -> None:
    """Own one persistent headed context until a finite shutdown signal arrives."""
    with playwright_factory() as playwright:
        context: _Context = playwright.chromium.launch_persistent_context(
            **playwright_launch_options(config)
        )
        try:
            while not stop_event.wait(0.25):
                pass
        finally:
            context.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal persistent Chromium worker")
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--extension-dir", type=Path, required=True)
    parser.add_argument("--cdp-host", default="127.0.0.1")
    parser.add_argument("--cdp-port", type=int, default=9222)
    parser.add_argument("--lock-fd", type=int, required=True)
    parser.add_argument("--chromium-executable", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    os.fstat(args.lock_fd)
    config = BrowserLaunchConfig(
        profile_dir=args.profile_dir,
        extension_dir=args.extension_dir,
        cdp_host=args.cdp_host,
        cdp_port=args.cdp_port,
        chromium_executable=args.chromium_executable,
    )
    stop = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        from playwright.sync_api import sync_playwright

        run_persistent_context(
            config,
            stop_event=stop,
            playwright_factory=sync_playwright,
        )
    finally:
        os.close(args.lock_fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
