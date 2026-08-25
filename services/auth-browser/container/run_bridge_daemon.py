#!/usr/bin/env python3
"""Validate a mounted pinned OpenCLI daemon contract, then exec it without a shell."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import NoReturn

MAX_CONTRACT_BYTES = 64 * 1024
SAFE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")


def fail(message: str) -> NoReturn:
    raise SystemExit(f"browser-bridge-daemon: {message}")


def main() -> int:
    root = Path(os.environ.get("POKECRACK_OPENCLI_ROOT", "/opt/pokecrack/opencli"))
    expected_version = os.environ.get("POKECRACK_OPENCLI_VERSION", "")
    expected_sha = os.environ.get("POKECRACK_OPENCLI_SHA256", "").lower()
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        fail("mounted OpenCLI root must be a real absolute directory")
    if not SAFE_VERSION.fullmatch(expected_version):
        fail("POKECRACK_OPENCLI_VERSION must be pinned")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        fail("POKECRACK_OPENCLI_SHA256 must be a lowercase SHA-256")
    contract_path = root / "daemon-contract.json"
    if contract_path.is_symlink() or not contract_path.is_file():
        fail("mounted daemon-contract.json is unavailable")
    raw = contract_path.read_bytes()
    if len(raw) > MAX_CONTRACT_BYTES:
        fail("daemon contract exceeds size limit")
    try:
        contract = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("daemon contract is invalid JSON")
    if not isinstance(contract, dict) or contract.get("version") != expected_version:
        fail("daemon contract version does not match the pin")
    executable_value = contract.get("executable")
    argv_value = contract.get("argv")
    if not isinstance(executable_value, str) or not isinstance(argv_value, list):
        fail("daemon contract requires executable and argv")
    executable = (root / executable_value).resolve(strict=True)
    try:
        executable.relative_to(root.resolve(strict=True))
    except ValueError:
        fail("daemon executable escapes the mounted root")
    if executable.is_symlink() or not executable.is_file() or not os.access(executable, os.X_OK):
        fail("daemon executable must be a real executable file")
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    if digest != expected_sha or contract.get("sha256") != expected_sha:
        fail("daemon executable checksum does not match the pin")
    if not argv_value or any(
        not isinstance(token, str)
        or not token
        or any(character in token for character in ("\0", "\n", "\r"))
        for token in argv_value
    ):
        fail("daemon argv must be a non-empty string array")
    replacements = {
        "{executable}": str(executable),
        "{host}": "127.0.0.1",
        "{port}": "19825",
    }
    allowed = set(replacements)
    for token in argv_value:
        if ("{" in token or "}" in token) and token not in allowed:
            fail("daemon placeholders must occupy an allowlisted complete token")
    argv = [replacements.get(token, token) for token in argv_value]
    if Path(argv[0]).resolve(strict=True) != executable:
        fail("daemon argv must execute the pinned binary directly")
    os.execv(executable, argv)
    return 0


if __name__ == "__main__":
    main()
