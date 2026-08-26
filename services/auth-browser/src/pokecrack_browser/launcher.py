"""Playwright persistent-context launch configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True, slots=True)
class BrowserLaunchConfig:
    profile_dir: Path
    extension_dir: Path | None = None
    cdp_host: str = "127.0.0.1"
    cdp_port: int = 9222
    chromium_executable: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_dir", Path(self.profile_dir))
        if self.extension_dir is not None:
            object.__setattr__(self, "extension_dir", Path(self.extension_dir))
        if self.chromium_executable is not None:
            object.__setattr__(self, "chromium_executable", Path(self.chromium_executable))
        if self.cdp_host not in LOOPBACK_HOSTS:
            raise ValueError("CDP must bind to a loopback host")
        if not 1 <= self.cdp_port <= 65535:
            raise ValueError("CDP port must be between 1 and 65535")

    @property
    def chromium_args(self) -> tuple[str, ...]:
        arguments = [
            f"--remote-debugging-address={self.cdp_host}",
            f"--remote-debugging-port={self.cdp_port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-dev-shm-usage",
        ]
        if self.extension_dir is not None:
            extension = str(self.extension_dir)
            arguments[0:0] = [
                f"--disable-extensions-except={extension}",
                f"--load-extension={extension}",
            ]
        return tuple(arguments)


def playwright_launch_options(config: BrowserLaunchConfig) -> dict[str, Any]:
    """Return options for chromium.launch_persistent_context, never CDP connect."""
    options: dict[str, Any] = {
        "user_data_dir": str(config.profile_dir),
        "headless": False,
        "args": list(config.chromium_args),
        "handle_sigint": False,
        "handle_sigterm": False,
        "handle_sighup": False,
    }
    if config.chromium_executable is not None:
        options["executable_path"] = str(config.chromium_executable)
    return options
