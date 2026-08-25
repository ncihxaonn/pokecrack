#!/usr/bin/env python3
"""Fail-closed repository checks for credentials and forbidden MVP scope."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

SKIP_PARTS = {".git", "node_modules", ".next", ".venv", "dist", "build", "coverage"}
MEDIA_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
BACKUP_SUFFIXES = {".dump", ".bak"}
PAID_DEPENDENCIES = {
    "stripe",
    "@stripe/stripe-js",
    "paypal-rest-sdk",
    "@paypal/react-paypal-js",
    "@paddle/paddle-js",
    "lemonsqueezy.js",
}
CLIENT_SECRET_RE = re.compile(
    r"NEXT_PUBLIC_[A-Z0-9_]*(?:SECRET|SERVICE_ROLE|DB_URL|PASSWORD|PRIVATE_KEY|ACCESS_TOKEN)",
)
TEXT_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".yaml", ".yml", ".env", ".py", ".sh", ".md"}


def _files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        yield path


def find_forbidden_artifacts(root: Path) -> list[str]:
    findings: list[str] = []
    for path in _files(root):
        relative = path.relative_to(root)
        parts = set(relative.parts)
        name = path.name

        is_env = name == ".env" or name.startswith(".env.")
        env_allowed = name.endswith(".example") or name == ".env.example"
        is_profile = bool(parts & {"browser-profiles", "profiles"}) and name != ".gitkeep"
        is_backup = "backups" in parts or path.suffix.lower() in BACKUP_SUFFIXES or name.endswith(".sql.gz")
        is_media = path.suffix.lower() in MEDIA_SUFFIXES
        if (is_env and not env_allowed) or is_profile or is_backup or is_media:
            findings.append(str(relative))
    return sorted(findings)


def find_client_secret_exposure(root: Path) -> list[str]:
    findings: list[str] = []
    search_roots = [root / "apps", root / "packages"]
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in _files(search_root):
            if path.suffix.lower() not in TEXT_SUFFIXES and not path.name.startswith(".env"):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for match in CLIENT_SECRET_RE.finditer(text):
                findings.append(f"{path.relative_to(root)}:{match.group(0)}")
    return sorted(findings)


def find_forbidden_dependencies(root: Path) -> list[str]:
    findings: list[str] = []
    for package in root.rglob("package.json"):
        if any(part in SKIP_PARTS for part in package.parts):
            continue
        try:
            payload = json.loads(package.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            findings.append(f"{package.relative_to(root)}:invalid-json")
            continue
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            dependencies = payload.get(section, {})
            if not isinstance(dependencies, dict):
                continue
            for dependency in dependencies:
                if dependency.casefold() in PAID_DEPENDENCIES:
                    findings.append(f"{package.relative_to(root)}:{dependency}")
    return sorted(findings)


def find_unpinned_actions(root: Path) -> list[str]:
    findings: list[str] = []
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return findings
    use_pattern = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)")
    pinned_ref = re.compile(r"^[0-9a-f]{40}$")
    for path in sorted((*workflows.glob("*.yml"), *workflows.glob("*.yaml"))):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = use_pattern.match(line)
            if not match:
                continue
            action = match.group(1)
            if action.startswith("./"):
                continue
            reference = action.rsplit("@", 1)[1] if "@" in action else ""
            if not pinned_ref.fullmatch(reference):
                findings.append(f"{path.relative_to(root)}:{line_number}:{action}")
    return findings


def find_large_files(root: Path, max_bytes: int = 10 * 1024 * 1024) -> list[str]:
    findings: list[str] = []
    for path in _files(root):
        try:
            if path.stat().st_size > max_bytes:
                findings.append(str(path.relative_to(root)))
        except OSError:
            findings.append(f"{path.relative_to(root)}:unreadable")
    return sorted(findings)


def find_probable_secrets(root: Path) -> list[str]:
    assignment = re.compile(
        '(?i)(?:api[_-]?key|access[_-]?token|secret|password|private[_-]?key)\\s*[:=]\\s*\\x22([^\\x22\\r\\n]{12,})\\x22'
    )
    high_confidence = (
        re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    )
    placeholders = ("example", "placeholder", "changeme", "replace-me", "your-", "process.env")
    findings: list[str] = []
    for path in _files(root):
        relative = path.relative_to(root)
        if "tests" in relative.parts or path.name.endswith(".example"):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".env":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in high_confidence:
            if pattern.search(text):
                findings.append(f"{relative}:high-confidence-token")
        for match in assignment.finditer(text):
            value = match.group(1).strip().casefold()
            if value and not any(item in value for item in placeholders):
                findings.append(f"{relative}:literal-secret")
    return sorted(set(findings))


def verify(root: Path) -> list[str]:
    return [
        *(f"forbidden artifact: {item}" for item in find_forbidden_artifacts(root)),
        *(f"large file: {item}" for item in find_large_files(root)),
        *(f"probable secret: {item}" for item in find_probable_secrets(root)),
        *(f"client secret exposure: {item}" for item in find_client_secret_exposure(root)),
        *(f"paid dependency: {item}" for item in find_forbidden_dependencies(root)),
        *(f"unpinned action: {item}" for item in find_unpinned_actions(root)),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    findings = verify(args.root.resolve())
    print(json.dumps({"ok": not findings, "findings": findings}, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
