"""Persist research progress without switching or executing a data branch."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.parse import quote

from research_checkpoint import BRANCH, LEDGER_FILE, REPOSITORY, SHA, pending_checkpoint, run, workflow_revision
from research_ledger import MAX_LEDGER_BYTES, merge_checkpoints, validate_checkpoint


REVIEW_RETRY_DELAYS = (2.0, 5.0, 10.0, 20.0)


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


def review_command(command: list[str]) -> subprocess.CompletedProcess:
    """Run one GitHub review command; the caller owns the retry budget."""
    return run(command)


def review_error(error: BaseException) -> str:
    """Return a bounded, credential-free description for the Actions log."""
    if isinstance(error, subprocess.CalledProcessError):
        detail = error.stderr or error.stdout or ""
        detail = " ".join(str(detail).split())
        for secret_name in ("GH_TOKEN", "GITHUB_TOKEN"):
            secret = os.environ.get(secret_name)
            if secret:
                detail = detail.replace(secret, "[redacted]")
        if detail:
            return detail[:240]
        return f"command_exit_{error.returncode}"
    if isinstance(error, subprocess.TimeoutExpired):
        return "command_timeout"
    return type(error).__name__


def request_review() -> bool:
    """Queue the exact checkpoint PR and ask GitHub to merge it when checks pass."""
    owner = REPOSITORY.split("/", 1)[0]
    head = f"{owner}:{BRANCH}"
    list_command = [
        "gh", "api", "--method", "GET",
        f"repos/{REPOSITORY}/pulls?state=open&base=main&head={quote(head, safe='')}",
    ]
    create_command = [
        "gh", "api", "--method", "POST", f"repos/{REPOSITORY}/pulls",
        "-f", "title=chore(research): update unified research ledger",
        "-f", f"head={head}", "-f", "base=main",
        "-f", "body=Validated research-only checkpoint. No application code or production pack counts are admitted by this data update.",
    ]
    last_error = "unknown_review_error"
    attempts = len(REVIEW_RETRY_DELAYS) + 1
    for attempt in range(attempts):
        try:
            existing = json.loads(review_command(list_command).stdout)
            if not isinstance(existing, list):
                raise ValueError("invalid_review_list")
            if len(existing) > 1:
                print("::warning::Research checkpoint PR unavailable: multiple open PRs found. No merge performed.")
                return False
            if not existing:
                # A push can be accepted before the new ref is visible to the
                # pulls endpoint. Retry the whole lookup/create cycle so a
                # concurrent creator is also picked up on the next attempt.
                created = json.loads(review_command(create_command).stdout)
                if not isinstance(created, dict):
                    raise ValueError("invalid_created_review")
                existing = [created]
            number = existing[0].get("number")
            if type(number) is not int or number < 1:
                raise ValueError("invalid_review_number")
            try:
                run([
                    "gh", "pr", "merge", str(number), "--auto", "--squash",
                    "--repo", REPOSITORY,
                ])
            except (ValueError, OSError, subprocess.SubprocessError):
                # A repository setting may disable auto-merge. The validated PR
                # still exists and remains reviewable; never bypass its checks.
                print("::warning::Research checkpoint PR queued; GitHub auto-merge was unavailable.")
            return True
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            last_error = review_error(error)
            if attempt < len(REVIEW_RETRY_DELAYS):
                time.sleep(REVIEW_RETRY_DELAYS[attempt])
    print(f"::warning::Research checkpoint PR unavailable after {attempts} attempts: {last_error}. No merge performed.")
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
