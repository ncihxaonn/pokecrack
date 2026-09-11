"""Persist research progress without switching or executing a data branch."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from research_checkpoint import BRANCH, LEDGER_FILE, REPOSITORY, SHA, pending_checkpoint, run, workflow_revision
from research_ledger import MAX_LEDGER_BYTES, merge_checkpoints, validate_checkpoint


def commit_checkpoint(revision: str, previous: str | None, raw: str) -> bool:
    """Fast-forward the checkpoint using an isolated index; never force push."""
    with tempfile.TemporaryDirectory(prefix="pokecrack-ledger-index-") as directory:
        environment = {**os.environ, "GIT_INDEX_FILE": str(Path(directory) / "index"),
                       "GIT_AUTHOR_NAME": "github-actions[bot]",
                       "GIT_COMMITTER_NAME": "github-actions[bot]",
                       "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
                       "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com"}
        blob = run(["git", "hash-object", "-w", "--stdin"], input=raw, env=environment).stdout.strip()
        if not SHA.fullmatch(blob):
            raise ValueError("invalid_checkpoint_blob")
        old_blob = run(["git", "rev-parse", f"{previous or revision}:{LEDGER_FILE}"]).stdout.strip()
        if blob == old_blob:
            return False
        run(["git", "read-tree", revision], env=environment)
        run(["git", "update-index", "--add", "--cacheinfo", f"100644,{blob},{LEDGER_FILE}"], env=environment)
        tree = run(["git", "write-tree"], env=environment).stdout.strip()
        if not SHA.fullmatch(tree):
            raise ValueError("invalid_checkpoint_tree")
        parents = ["-p", previous or revision]
        if previous is not None:
            ancestry = run(["git", "merge-base", "--is-ancestor", revision, previous], check=False)
            if ancestry.returncode == 1:
                parents += ["-p", revision]
            elif ancestry.returncode != 0:
                raise ValueError("invalid_checkpoint_ancestry")
        commit = run(["git", "commit-tree", tree, *parents,
                      "-m", "chore(research): update unified research ledger"], env=environment).stdout.strip()
        if not SHA.fullmatch(commit):
            raise ValueError("invalid_checkpoint_commit")
        run(["git", "push", "origin", f"{commit}:refs/heads/{BRANCH}"])
        return True


def request_review() -> bool:
    """A persisted data checkpoint does not depend on bot PR-creation rights."""
    try:
        existing = json.loads(run([
            "gh", "pr", "list", "--repo", REPOSITORY, "--base", "main",
            "--head", f"ncihxaonn:{BRANCH}", "--state", "open", "--json", "number",
        ]).stdout)
        if not isinstance(existing, list):
            return False
        if not existing:
            run(["gh", "pr", "create", "--repo", REPOSITORY, "--base", "main",
                 "--head", BRANCH, "--title", "chore(research): update unified research ledger",
                 "--body", "Validated research-only checkpoint. No application code or production pack counts are admitted by this data update."])
        return True
    except (ValueError, OSError, subprocess.SubprocessError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=LEDGER_FILE)
    args = parser.parse_args()
    try:
        if args.path != LEDGER_FILE or not os.environ.get("GH_TOKEN"):
            raise ValueError("invalid_workflow_context")
        revision = workflow_revision()
        with Path(args.path).open("rb") as source:
            current = validate_checkpoint(source.read(MAX_LEDGER_BYTES + 1))
        run(["gh", "auth", "setup-git"])
        previous, pending = pending_checkpoint(revision)
        ledger = merge_checkpoints(current, pending) if pending is not None else current
        raw = json.dumps(ledger, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        validate_checkpoint(raw.encode())
        changed = commit_checkpoint(revision, previous, raw)
        print("research_ledger_saved" if changed else "research_ledger_unchanged")
    except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
        raise SystemExit("research_ledger_queue_failed: checkpoint_not_saved") from None
    if changed or previous is not None:
        if request_review():
            print("research_ledger_review_queued")
        else:
            # Do not enable broader repository permissions or bypass review.
            # The next run resumes this validated reference-only checkpoint;
            # application code stays on main, and source admission is separate.
            print("::warning::Research checkpoint saved; review PR unavailable. No merge performed.")


if __name__ == "__main__":
    main()
