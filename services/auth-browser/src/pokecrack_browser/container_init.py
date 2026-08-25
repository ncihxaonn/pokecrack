"""Fail-closed container startup validation before supervisor launches UI services."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .config import ServiceSettings
from .paths import validate_extension_path
from .runtime import ensure_private_runtime_root


def _private_regular_file(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise RuntimeError(f"VNC password file must be an absolute regular file: {path}")
    metadata = path.stat()
    mode = stat.S_IMODE(metadata.st_mode)
    if mode & 0o077:
        raise RuntimeError(f"VNC password file must not be group/world accessible: {path}")
    if metadata.st_uid != os.geteuid():
        raise RuntimeError(f"VNC password file must be owned by uid {os.geteuid()}")
    if metadata.st_size == 0 or metadata.st_size > 1024:
        raise RuntimeError("VNC password file has an invalid size")


def main() -> int:
    settings = ServiceSettings.from_env()
    if not settings.extension_version:
        raise RuntimeError("POKECRACK_BRIDGE_VERSION must pin the mounted extension")
    ensure_private_runtime_root(settings.runtime_root)
    ensure_private_runtime_root(settings.profile_root)
    validate_extension_path(
        settings.extension_dir,
        expected_version=settings.extension_version,
    )
    _private_regular_file(Path(os.environ.get("VNC_PASSWORD_FILE", "/run/secrets/vnc_password")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
