"""Queue a checked-out research ledger behind one reviewed pull request."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
LEDGER_BRANCH = "automation/research-ledger"
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "ncihxaonn/pokecrack")


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, capture_output=True, text=True)


def main() -> None:
    if not REPOSITORY_PATTERN.fullmatch(REPOSITORY) or not os.environ.get("GH_TOKEN"):
        raise SystemExit("research_ledger_queue_failed: invalid_workflow_context")

    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="data/research/research-ledger.json")
    args = parser.parse_args()
    ledger_path = Path(args.path)
    try:
        raw = ledger_path.read_bytes()
    except OSError:
        raise SystemExit("research_ledger_queue_failed: ledger_unavailable") from None

    try:
        run(["gh", "auth", "setup-git"])
        run(["git", "fetch", "origin", "main"])
        branch_exists = bool(run(["git", "ls-remote", "--exit-code", "--heads",
                                  "origin", LEDGER_BRANCH], check=False).stdout.strip())
        if branch_exists:
            run(["git", "fetch", "origin", LEDGER_BRANCH])
            run(["git", "switch", "--force-create", LEDGER_BRANCH,
                 f"refs/remotes/origin/{LEDGER_BRANCH}"])
        else:
            run(["git", "switch", "--create", LEDGER_BRANCH, "origin/main"])
        ledger_path.write_bytes(raw)
        run(["git", "add", "--", str(ledger_path)])
        staged = run(["git", "diff", "--cached", "--quiet"], check=False)
        if staged.returncode == 0:
            print("research_ledger_unchanged")
            return
        if staged.returncode != 1:
            raise subprocess.CalledProcessError(staged.returncode, staged.args)
        run(["git", "config", "user.name", "github-actions[bot]"])
        run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
        run(["git", "commit", "-m", "chore(research): update unified research ledger"])
        run(["git", "push", "origin", f"HEAD:{LEDGER_BRANCH}"])
    except subprocess.CalledProcessError:
        raise SystemExit("research_ledger_queue_failed: git_operation_failed") from None

    head = f"ncihxaonn:{LEDGER_BRANCH}"
    try:
        existing = run(["gh", "pr", "list", "--repo", REPOSITORY, "--base", "main",
                        "--head", head, "--state", "open", "--json", "number,url"]).stdout
        if existing.strip() == "[]":
            created = run([
                "gh", "pr", "create", "--repo", REPOSITORY, "--base", "main",
                "--head", LEDGER_BRANCH,
                "--title", "chore(research): update unified research ledger",
                "--body", "Automated research history update. This PR keeps the single machine-readable ledger current without creating public issue records.",
            ]).stdout.strip()
            print(f"research_ledger_pr_created: {created}")
        else:
            print("research_ledger_pr_updated")
    except subprocess.CalledProcessError:
        raise SystemExit("research_ledger_queue_failed: pull_request_operation_failed") from None


if __name__ == "__main__":
    main()
