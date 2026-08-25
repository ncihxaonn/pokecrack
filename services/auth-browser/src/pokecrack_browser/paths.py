from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

ALLOWED_PROFILES = frozenset(
    {
        "social-western",
        "social-chinese",
        "research-general",
    }
)


class PathValidationError(ValueError):
    """A runtime path or profile name violates the security policy."""


def validate_profile_name(name: str) -> str:
    if name not in ALLOWED_PROFILES:
        allowed = ", ".join(sorted(ALLOWED_PROFILES))
        raise PathValidationError(f"profile must be one of: {allowed}")
    return name


def _validate_absolute_real_path(path: Path) -> None:
    if not path.is_absolute():
        raise PathValidationError(f"path must be absolute: {path}")
    if path != path.resolve(strict=False):
        raise PathValidationError(f"path must not contain a symbolic link or traversal: {path}")


def _validate_mode_0700(path: Path) -> None:
    metadata = path.stat()
    mode = stat.S_IMODE(metadata.st_mode)
    if mode != 0o700:
        raise PathValidationError(f"{path} must have mode 0700 (found {mode:04o})")
    if metadata.st_uid != os.geteuid():
        raise PathValidationError(f"{path} must be owned by uid {os.geteuid()}")


def _ensure_private_directory(path: Path, *, create: bool) -> None:
    if path.is_symlink():
        raise PathValidationError(f"directory must not be a symbolic link: {path}")
    if not path.exists():
        if not create:
            raise PathValidationError(f"directory does not exist: {path}")
        path.mkdir(mode=0o700, parents=False)
        os.chmod(path, 0o700)
    if path.is_symlink():
        raise PathValidationError(f"directory must not be a symbolic link: {path}")
    if not path.is_dir():
        raise PathValidationError(f"not a directory: {path}")
    _validate_mode_0700(path)


def prepare_profile_directory(
    root: str | os.PathLike[str],
    profile: str,
    *,
    create: bool = False,
) -> Path:
    validate_profile_name(profile)
    root_path = Path(root)
    _validate_absolute_real_path(root_path)
    if create and not root_path.exists():
        root_path.mkdir(mode=0o700, parents=True)
        os.chmod(root_path, 0o700)
    _ensure_private_directory(root_path, create=create)
    profile_path = root_path / profile
    _ensure_private_directory(profile_path, create=create)
    return profile_path


def validate_extension_path(
    path: str | os.PathLike[str],
    *,
    expected_version: str,
) -> Path:
    """Validate a mounted, pinned unpacked Browser Bridge extension."""
    extension = Path(path)
    if not extension.is_absolute():
        raise PathValidationError(f"path must be absolute: {extension}")
    if extension.is_symlink():
        if extension.name != "current":
            raise PathValidationError(
                f"only the managed current extension symbolic link is allowed: {extension}"
            )
        install_root = extension.parent
        _validate_absolute_real_path(install_root)
        releases_root = install_root / "releases"
        if releases_root.is_symlink() or not releases_root.is_dir():
            raise PathValidationError(
                f"managed extension releases directory is invalid: {releases_root}"
            )
        _validate_absolute_real_path(releases_root)
        if (
            not expected_version
            or expected_version in {".", ".."}
            or Path(expected_version).name != expected_version
            or "\\" in expected_version
        ):
            raise PathValidationError("expected extension version is not a safe directory name")
        expected_target = releases_root / expected_version
        if expected_target.is_symlink() or not expected_target.is_dir():
            raise PathValidationError(
                f"managed extension release is unavailable: {expected_target}"
            )
        _validate_absolute_real_path(expected_target)
        try:
            resolved = extension.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise PathValidationError(
                f"managed current extension link is invalid: {extension}"
            ) from exc
        if resolved != expected_target:
            raise PathValidationError(
                "managed current extension resolves outside the pinned managed release directory"
            )
        extension = resolved
    else:
        _validate_absolute_real_path(extension)
    if not extension.is_dir():
        raise PathValidationError(f"extension must be an unpacked directory: {extension}")
    manifest_path = extension / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PathValidationError(f"extension manifest is missing: {manifest_path}")
    try:
        manifest: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PathValidationError(f"extension manifest is invalid: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise PathValidationError("extension manifest must be a JSON object")
    if manifest.get("version") != expected_version:
        raise PathValidationError(
            f"extension version must be {expected_version!r} (found {manifest.get('version')!r})"
        )
    if manifest.get("manifest_version") not in {2, 3}:
        raise PathValidationError("extension manifest_version must be 2 or 3")
    return extension
