"""Environment-backed, loopback-only service settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .launcher import LOOPBACK_HOSTS

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def _boolean(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{name} must be true or false")


@dataclass(frozen=True, slots=True)
class ServiceSettings:
    profile_root: Path = Path("/var/lib/pokecrack-browser/profiles")
    runtime_root: Path = Path("/run/pokecrack-browser")
    extension_dir: Path = Path("/opt/pokecrack/opencli-extension/current")
    extension_version: str = ""
    opencli_enabled: bool = False
    cdp_host: str = "127.0.0.1"
    cdp_port: int = 9222
    daemon_host: str = "127.0.0.1"
    daemon_port: int = 19825
    adapter_root: Path = SERVICE_ROOT / "adapters"
    chromium_executable: Path | None = None
    shutdown_timeout: float = 10.0

    def __post_init__(self) -> None:
        for field_name in ("profile_root", "runtime_root", "extension_dir", "adapter_root"):
            object.__setattr__(self, field_name, Path(getattr(self, field_name)))
        if self.chromium_executable is not None:
            object.__setattr__(self, "chromium_executable", Path(self.chromium_executable))
        if self.cdp_host not in LOOPBACK_HOSTS or self.daemon_host not in LOOPBACK_HOSTS:
            raise ValueError("CDP and Browser Bridge daemon must bind to loopback")
        for name, port in (("CDP", self.cdp_port), ("daemon", self.daemon_port)):
            if not 1 <= port <= 65535:
                raise ValueError(f"{name} port must be between 1 and 65535")
        if self.shutdown_timeout < 0:
            raise ValueError("shutdown timeout must be non-negative")

    @classmethod
    def from_env(cls) -> ServiceSettings:
        executable = os.environ.get("POKECRACK_CHROMIUM_EXECUTABLE")
        return cls(
            profile_root=Path(
                os.environ.get(
                    "POKECRACK_BROWSER_PROFILE_ROOT",
                    "/var/lib/pokecrack-browser/profiles",
                )
            ),
            runtime_root=Path(
                os.environ.get("POKECRACK_BROWSER_RUNTIME_ROOT", "/run/pokecrack-browser")
            ),
            extension_dir=Path(
                os.environ.get(
                    "POKECRACK_BRIDGE_EXTENSION_PATH",
                    "/opt/pokecrack/opencli-extension/current",
                )
            ),
            extension_version=os.environ.get("POKECRACK_BRIDGE_VERSION", ""),
            opencli_enabled=_boolean("OPENCLI_ENABLED", False),
            cdp_host=os.environ.get("POKECRACK_CDP_HOST", "127.0.0.1"),
            cdp_port=int(os.environ.get("POKECRACK_CDP_PORT", "9222")),
            daemon_host=os.environ.get("POKECRACK_DAEMON_HOST", "127.0.0.1"),
            daemon_port=int(os.environ.get("POKECRACK_DAEMON_PORT", "19825")),
            adapter_root=Path(
                os.environ.get("POKECRACK_ADAPTER_ROOT", str(SERVICE_ROOT / "adapters"))
            ),
            chromium_executable=Path(executable) if executable else None,
            shutdown_timeout=float(os.environ.get("POKECRACK_BROWSER_SHUTDOWN_TIMEOUT", "10")),
        )
