#!/usr/bin/env python3
"""Safely unpack and validate a pinned Chromium extension artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import tempfile
import zipfile


MAX_FILES = 10_000
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024


class ExtensionArtifactError(ValueError):
    """The downloaded extension artifact violates the install policy."""


def _safe_relative(name: str) -> Path:
    if "\\" in name:
        raise ExtensionArtifactError(f"archive entry uses a backslash: {name!r}")
    posix = PurePosixPath(name)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise ExtensionArtifactError(f"unsafe archive entry: {name!r}")
    useful = [part for part in posix.parts if part not in {"", "."}]
    if not useful:
        raise ExtensionArtifactError(f"empty archive entry: {name!r}")
    return Path(*useful)


def _check_budget(count: int, total: int) -> None:
    if count > MAX_FILES:
        raise ExtensionArtifactError("archive contains too many files")
    if total > MAX_UNCOMPRESSED_BYTES:
        raise ExtensionArtifactError("archive is larger than the unpacked size limit")


def _extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        _check_budget(len(infos), sum(info.file_size for info in infos))
        for info in infos:
            relative = _safe_relative(info.filename)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ExtensionArtifactError(f"symlink entries are not allowed: {info.filename!r}")
            target = destination / relative
            if info.is_dir():
                target.mkdir(mode=0o755, parents=True, exist_ok=True)
                continue
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            with bundle.open(info) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o644)


def _extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, mode="r:*") as bundle:
        members = bundle.getmembers()
        _check_budget(len(members), sum(member.size for member in members))
        for member in members:
            relative = _safe_relative(member.name)
            if member.issym() or member.islnk() or member.isdev():
                raise ExtensionArtifactError(f"links and devices are not allowed: {member.name!r}")
            target = destination / relative
            if member.isdir():
                target.mkdir(mode=0o755, parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ExtensionArtifactError(f"unsupported archive entry: {member.name!r}")
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise ExtensionArtifactError(f"cannot read archive entry: {member.name!r}")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o644)


def validate_extension_directory(directory: Path, expected_version: str) -> dict[str, object]:
    if not directory.is_dir() or directory.is_symlink():
        raise ExtensionArtifactError("extension root must be a real directory")
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ExtensionArtifactError("extension root does not contain a regular manifest.json")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExtensionArtifactError("manifest.json is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise ExtensionArtifactError("manifest.json must contain an object")
    if payload.get("manifest_version") not in {2, 3}:
        raise ExtensionArtifactError("manifest_version must be 2 or 3")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ExtensionArtifactError("extension manifest requires a non-empty name")
    if payload.get("version") != expected_version:
        raise ExtensionArtifactError("extension manifest version does not match the pinned version")
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ExtensionArtifactError(f"extension contains a symlink: {path.relative_to(directory)}")
    return payload


def prepare_extension(archive: Path, destination: Path, expected_version: str) -> None:
    archive = archive.resolve(strict=True)
    if destination.exists() or destination.is_symlink():
        raise ExtensionArtifactError("destination already exists")
    destination_parent = destination.parent.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="opencli-unpack-", dir=destination_parent) as temporary:
        extracted = Path(temporary)
        if zipfile.is_zipfile(archive):
            _extract_zip(archive, extracted)
        elif tarfile.is_tarfile(archive):
            _extract_tar(archive, extracted)
        else:
            raise ExtensionArtifactError("artifact is neither a ZIP nor a supported tar archive")
        manifests = [
            path
            for path in extracted.rglob("manifest.json")
            if path.is_file() and not path.is_symlink()
        ]
        if len(manifests) != 1:
            raise ExtensionArtifactError("artifact must contain exactly one manifest.json")
        extension_root = manifests[0].parent
        if len(extension_root.relative_to(extracted).parts) > 3:
            raise ExtensionArtifactError("extension root is nested too deeply")
        validate_extension_directory(extension_root, expected_version)
        shutil.copytree(extension_root, destination, symlinks=False)
        validate_extension_directory(destination, expected_version)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("archive", type=Path)
    prepare.add_argument("destination", type=Path)
    prepare.add_argument("expected_version")
    validate = subparsers.add_parser("validate")
    validate.add_argument("directory", type=Path)
    validate.add_argument("expected_version")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare_extension(args.archive, args.destination, args.expected_version)
    else:
        validate_extension_directory(args.directory, args.expected_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
