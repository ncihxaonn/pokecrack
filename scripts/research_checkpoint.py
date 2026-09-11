"""Resume validated research data from the pending ledger, never its code."""
from __future__ import annotations

import os
import re
import subprocess

from research_ledger import LEDGER_PATH, MAX_LEDGER_BYTES, load, merge_checkpoints, save, validate_checkpoint

BRANCH = "automation/research-ledger"
LEDGER_FILE = "data/research/research-ledger.json"
REPOSITORY = "ncihxaonn/pokecrack"
SHA = re.compile(r"[0-9a-f]{40}")


def run(command: list[str], *, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, capture_output=True, text=True, timeout=60, **kwargs)


def workflow_revision() -> str:
    revision = os.environ.get("GITHUB_SHA", "")
    if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or not SHA.fullmatch(revision)
            or run(["git", "rev-parse", "HEAD"]).stdout.strip() != revision):
        raise ValueError("invalid_workflow_context")
    origin = run(["git", "remote", "get-url", "origin"]).stdout.strip()
    if origin not in (f"https://github.com/{REPOSITORY}", f"https://github.com/{REPOSITORY}.git"):
        raise ValueError("invalid_workflow_origin")
    return revision


def pending_checkpoint(revision: str) -> tuple[str | None, dict | None]:
    exists = run(["git", "ls-remote", "--exit-code", "--heads", "origin", BRANCH], check=False)
    if exists.returncode == 2 and not exists.stdout.strip():
        return None, None
    if exists.returncode != 0:
        raise ValueError("checkpoint_remote_unavailable")
    run(["git", "fetch", "--no-tags", "origin", f"{BRANCH}:refs/remotes/origin/{BRANCH}"])
    tip = run(["git", "rev-parse", f"refs/remotes/origin/{BRANCH}"]).stdout.strip()
    if not SHA.fullmatch(tip):
        raise ValueError("invalid_checkpoint_revision")
    base = run(["git", "merge-base", revision, tip]).stdout.strip()
    if not SHA.fullmatch(base):
        raise ValueError("invalid_checkpoint_base")
    changed = run(["git", "diff", "--name-only", base, tip]).stdout.splitlines()
    if set(changed) - {LEDGER_FILE}:
        raise ValueError("checkpoint_contains_code_changes")
    size = int(run(["git", "cat-file", "-s", f"{tip}:{LEDGER_FILE}"]).stdout)
    if not 0 < size <= MAX_LEDGER_BYTES:
        raise ValueError("research_checkpoint_too_large")
    raw = run(["git", "show", f"{tip}:{LEDGER_FILE}"]).stdout.encode()
    return tip, validate_checkpoint(raw)


def main() -> None:
    try:
        revision = workflow_revision()
        _, pending = pending_checkpoint(revision)
        if pending is not None:
            save(merge_checkpoints(load(), pending), LEDGER_PATH)
        print("research_checkpoint_ready")
    except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
        raise SystemExit("research_checkpoint_unverified") from None


if __name__ == "__main__":
    main()
