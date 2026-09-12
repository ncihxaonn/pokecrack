from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import country_research
import research_checkpoint as checkpoint
import research_ledger as ledger
import queue_research_ledger as queue


def report(history=()):
    selection = country_research.select_targets(list(history))
    return {**selection, "results": [{"target": target, "studies": []}
                                      for target in selection["targets"]]}


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def outcome(stdout="", code=0):
    return subprocess.CompletedProcess([], code, stdout=stdout, stderr="")


class CheckpointMergeTests(unittest.TestCase):
    def test_pending_progress_advances_without_merge_and_is_idempotent(self):
        current = ledger.empty_ledger()
        pending = ledger.empty_ledger()
        pending["country_reports"] = [report()]
        combined = ledger.merge_checkpoints(current, pending)
        self.assertEqual(country_research.select_targets(combined["country_reports"]),
                         country_research.select_targets([report()]))
        self.assertEqual(ledger.merge_checkpoints(combined, pending), combined)
        self.assertEqual(current, ledger.empty_ledger())
        self.assertEqual(combined["global_batches"], [])

    def test_both_histories_are_preserved_and_competing_progress_is_rejected(self):
        current = ledger.empty_ledger()
        current["country_reports"] = [report()]
        pending = copy.deepcopy(current)
        pending["country_reports"].append(report(current["country_reports"]))
        self.assertEqual(len(ledger.merge_checkpoints(current, pending)["country_reports"]), 2)
        competing = copy.deepcopy(current)
        sample = json.loads((ROOT / "data/research/global-studies.json").read_text())["studies"][0]
        competing["country_reports"][0]["results"][0]["studies"] = [sample]
        with self.assertRaisesRegex(ValueError, "checkpoint_conflict"):
            ledger.merge_checkpoints(current, competing)

    def test_untrusted_checkpoint_requires_bounded_complete_valid_data(self):
        for raw in (b"{}", b"x" * (ledger.MAX_LEDGER_BYTES + 1),
                    encoded({**ledger.empty_ledger(), "version": True}).encode(),
                    encoded({**ledger.empty_ledger(), "country_reports": [{}]}).encode()):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                ledger.validate_checkpoint(raw)

    def test_remote_failure_is_not_mistaken_for_absent_checkpoint(self):
        with patch.object(checkpoint, "run", return_value=outcome(code=2)):
            self.assertEqual(checkpoint.pending_checkpoint("a" * 40), (None, None))
        for result in (outcome(code=128), outcome("unexpected", code=2)):
            with patch.object(checkpoint, "run", return_value=result), self.assertRaises(ValueError):
                checkpoint.pending_checkpoint("a" * 40)

    def test_checkpoint_code_is_rejected_without_reading_or_executing_it(self):
        replies = [outcome("present"), outcome(), outcome("b" * 40), outcome("a" * 40),
                   outcome("scripts/research_checkpoint.py\n")]
        with patch.object(checkpoint, "run", side_effect=replies) as run:
            with self.assertRaisesRegex(ValueError, "contains_code_changes"):
                checkpoint.pending_checkpoint("a" * 40)
            self.assertEqual(run.call_count, 5)

    def test_review_unavailable_does_not_change_repository_permissions(self):
        with patch.object(queue, "run", side_effect=[outcome("[]"),
                subprocess.CalledProcessError(1, "gh")]) as run:
            self.assertFalse(queue.request_review())
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args[0][:3], ["gh", "api", "--method"])

    def test_review_uses_same_repository_head_branch(self):
        with patch.object(queue, "run", side_effect=[outcome("[]"),
                subprocess.CalledProcessError(1, "gh")]) as run:
            queue.request_review()
        create_command = run.call_args_list[1].args[0]
        self.assertIn(f"head=ncihxaonn:{queue.BRANCH}", create_command)

    def test_checkpoint_pr_uses_github_auto_merge_without_bypassing_checks(self):
        with patch.object(queue, "run", side_effect=[
            outcome("[]"),
            outcome('{"number": 286}'),
            outcome(),
        ]) as run:
            self.assertTrue(queue.request_review())
        self.assertEqual(run.call_args.args[0], [
            "gh", "api", "--method", "PUT",
            f"repos/{queue.REPOSITORY}/pulls/286/auto-merge",
            "-f", "merge_method=squash",
        ])

    def test_main_and_exact_origin_are_required(self):
        env = {"GITHUB_REPOSITORY": "ncihxaonn/pokecrack", "GITHUB_REF": "refs/heads/main",
               "GITHUB_SHA": "a" * 40}
        with patch.dict(os.environ, env), patch.object(checkpoint, "run", side_effect=[
                outcome("a" * 40), outcome("https://github.com/ncihxaonn/pokecrack.git")]):
            self.assertEqual(checkpoint.workflow_revision(), "a" * 40)
        for key, value in (("GITHUB_REF", "refs/heads/feature"),
                           ("GITHUB_REPOSITORY", "other/repo"), ("GITHUB_SHA", "main")):
            with patch.dict(os.environ, {**env, key: value}), patch.object(checkpoint, "run") as run:
                with self.assertRaises(ValueError):
                    checkpoint.workflow_revision()
                run.assert_not_called()


class CheckpointGitTests(unittest.TestCase):
    def test_real_git_checkpoint_preserves_checkout_index_history_and_main_code(self):
        with tempfile.TemporaryDirectory(prefix="pokecrack-checkpoint-test-") as directory:
            root = Path(directory)
            remote = root / "remote.git"
            work = root / "work"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "main", str(work)], check=True, capture_output=True)
            previous_cwd = Path.cwd()
            try:
                os.chdir(work)
                checkpoint.run(["git", "config", "user.name", "Fixture"])
                checkpoint.run(["git", "config", "user.email", "fixture@example.invalid"])
                checkpoint.run(["git", "remote", "add", "origin", str(remote)])
                path = work / checkpoint.LEDGER_FILE
                path.parent.mkdir(parents=True)
                path.write_text(encoded(ledger.empty_ledger()))
                (work / "app.txt").write_text("reviewed-v1\n")
                checkpoint.run(["git", "add", "app.txt", checkpoint.LEDGER_FILE])
                checkpoint.run(["git", "commit", "-m", "fixture baseline"])
                revision = checkpoint.run(["git", "rev-parse", "HEAD"]).stdout.strip()
                checkpoint.run(["git", "push", "origin", "main"])
                data = ledger.empty_ledger()
                data["country_reports"].append(report())
                raw = encoded(data)
                path.write_text(raw)
                self.assertTrue(queue.commit_checkpoint(revision, None, raw))
                tip = checkpoint.run(["git", "ls-remote", "origin", checkpoint.BRANCH]).stdout.split()[0]
                self.assertEqual(checkpoint.run(["git", "rev-parse", "HEAD"]).stdout.strip(), revision)
                self.assertEqual(checkpoint.run(["git", "diff", "--cached", "--name-only"]).stdout, "")
                self.assertEqual(path.read_text(), raw)
                self.assertFalse(queue.commit_checkpoint(revision, tip, raw))
                # A reviewed main code release must not be reverted by the next
                # data checkpoint; both histories remain parents of its commit.
                (work / "app.txt").write_text("reviewed-v2\n")
                checkpoint.run(["git", "add", "app.txt"])
                checkpoint.run(["git", "commit", "-m", "fixture main release"])
                latest = checkpoint.run(["git", "rev-parse", "HEAD"]).stdout.strip()
                data["country_reports"].append(report(data["country_reports"]))
                raw2 = encoded(data)
                self.assertTrue(queue.commit_checkpoint(latest, tip, raw2))
                second = checkpoint.run(["git", "ls-remote", "origin", checkpoint.BRANCH]).stdout.split()[0]
                self.assertEqual(checkpoint.run(["git", "show", f"{second}:app.txt"]).stdout, "reviewed-v2\n")
                self.assertEqual(checkpoint.run(["git", "show", f"{second}:{checkpoint.LEDGER_FILE}"]).stdout, raw2)
                checkpoint.run(["git", "merge-base", "--is-ancestor", tip, second])
                checkpoint.run(["git", "merge-base", "--is-ancestor", latest, second])
                self.assertEqual(checkpoint.run(["git", "rev-parse", "HEAD"]).stdout.strip(), latest)
                # A competing writer cannot overwrite an already advanced ref.
                with self.assertRaises(subprocess.CalledProcessError):
                    queue.commit_checkpoint(latest, tip, raw2 + "\n")
                self.assertEqual(checkpoint.run(["git", "ls-remote", "origin", checkpoint.BRANCH]).stdout.split()[0], second)
            finally:
                os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
