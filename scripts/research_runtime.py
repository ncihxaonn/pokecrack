"""Resolve an already-deployed, main-history runtime without deploying code."""
from __future__ import annotations

import argparse
import os
import re
import subprocess

SHA = re.compile(r"[0-9a-f]{40}")


def resolve_runtime(workflow_sha: str, ssh: list[str]) -> str:
    # The workflow already has the same main-only job guard. Enforce it here
    # too so standalone/reused callers cannot validate an arbitrary branch.
    if os.environ.get("GITHUB_REF") != "refs/heads/main" or not SHA.fullmatch(workflow_sha):
        raise ValueError("invalid_workflow_revision")
    checkout = subprocess.run(["git", "rev-parse", "HEAD"], check=True,
                              capture_output=True, text=True, timeout=15).stdout.strip()
    if checkout != workflow_sha:
        raise ValueError("workflow_checkout_mismatch")
    revision = subprocess.run([
        *ssh, "git -C /home/codex/pokecrack rev-parse --verify HEAD",
    ], check=True, capture_output=True, text=True, timeout=45).stdout.strip()
    if not SHA.fullmatch(revision):
        raise ValueError("invalid_runtime_revision")
    # A deployed older backend is valid after a frontend-only main merge. It
    # must still belong to this exact reviewed main history, never another ref.
    subprocess.run(["git", "merge-base", "--is-ancestor", revision, workflow_sha],
                   check=True, capture_output=True, text=True, timeout=15)
    return revision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--port", required=True)
    parser.add_argument("--identity-file", required=True)
    parser.add_argument("--known-hosts", required=True)
    args = parser.parse_args()
    try:
        if (args.host != "72.62.101.225" or args.user != "codex"
                or not args.port.isdecimal() or not 1 <= int(args.port) <= 65535):
            raise ValueError("unapproved_target")
        ssh = ["ssh", "-i", args.identity_file,
               "-o", f"UserKnownHostsFile={args.known_hosts}",
               "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=15",
               "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
               "-p", args.port, f"{args.user}@{args.host}"]
        print(resolve_runtime(args.workflow_sha, ssh))
    except (ValueError, OSError, subprocess.SubprocessError):
        # Provider/SSH output can contain operational details; never echo it.
        raise SystemExit("research-intake: runtime_revision_unverified") from None


if __name__ == "__main__":
    main()
