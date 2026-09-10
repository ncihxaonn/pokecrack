from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_runtime as module

WORKFLOW = "a" * 40
RUNTIME = "b" * 40


def result(stdout=""):
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


class ResearchRuntimeTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main"})
        environment.start()
        self.addCleanup(environment.stop)

    def test_non_main_workflow_is_rejected_before_any_process(self):
        for ref in ("", "refs/heads/feature", "refs/tags/main", "refs/pull/1/merge"):
            with patch.dict(os.environ, {"GITHUB_REF": ref}), patch.object(module.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    module.resolve_runtime(WORKFLOW, ["ssh"])
                run.assert_not_called()

    def test_older_reviewed_runtime_is_resolved_without_deploy_or_intake(self):
        with patch.object(module.subprocess, "run", side_effect=[
                result(WORKFLOW + "\n"), result(RUNTIME + "\n"), result()]) as run:
            self.assertEqual(module.resolve_runtime(WORKFLOW, ["ssh", "target"]), RUNTIME)
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ["git", "rev-parse", "HEAD"],
            ["ssh", "target", "git -C /home/codex/pokecrack rev-parse --verify HEAD"],
            ["git", "merge-base", "--is-ancestor", RUNTIME, WORKFLOW],
        ])
        self.assertTrue(all(call.kwargs["check"] for call in run.call_args_list))
        self.assertTrue(all(0 < call.kwargs["timeout"] <= 45 for call in run.call_args_list))

    def test_invalid_workflow_or_changed_checkout_never_contacts_runtime(self):
        with patch.object(module.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                module.resolve_runtime("main", ["ssh"])
            run.assert_not_called()
        with patch.object(module.subprocess, "run", return_value=result(RUNTIME)) as run:
            with self.assertRaises(ValueError):
                module.resolve_runtime(WORKFLOW, ["ssh"])
            self.assertEqual(run.call_count, 1)

    def test_invalid_or_multiple_remote_revisions_never_reach_ancestry_check(self):
        for remote in ("", "main", RUNTIME + "\n" + WORKFLOW, "b" * 41, "B" * 40):
            with self.subTest(remote=remote), patch.object(module.subprocess, "run",
                    side_effect=[result(WORKFLOW), result(remote)]) as run:
                with self.assertRaises(ValueError):
                    module.resolve_runtime(WORKFLOW, ["ssh"])
                self.assertEqual(run.call_count, 2)

    def test_unreviewed_revision_or_network_failure_is_not_accepted(self):
        for outcomes in (
            [result(WORKFLOW), result(RUNTIME), subprocess.CalledProcessError(1, "git")],
            [result(WORKFLOW), subprocess.TimeoutExpired("ssh", 45)],
        ):
            with patch.object(module.subprocess, "run", side_effect=outcomes):
                with self.assertRaises(subprocess.SubprocessError):
                    module.resolve_runtime(WORKFLOW, ["ssh"])

    def test_cli_pins_target_and_host_key_checks(self):
        args = ["research_runtime.py", "--workflow-sha", WORKFLOW,
                "--host", "72.62.101.225", "--user", "codex", "--port", "22",
                "--identity-file", "/tmp/test-key", "--known-hosts", "/tmp/test-hosts"]
        with patch.object(sys, "argv", args), patch.object(module, "resolve_runtime",
                return_value=RUNTIME) as resolve, patch("builtins.print") as output:
            module.main()
            output.assert_called_once_with(RUNTIME)
            ssh = resolve.call_args.args[1]
            for option in ("StrictHostKeyChecking=yes", "IdentitiesOnly=yes", "BatchMode=yes",
                           "UserKnownHostsFile=/tmp/test-hosts", "codex@72.62.101.225"):
                self.assertIn(option, ssh)
        for field, value in (("--host", "example.com"), ("--user", "root"), ("--port", "0")):
            invalid = args.copy()
            invalid[invalid.index(field) + 1] = value
            with patch.object(sys, "argv", invalid), patch.object(module, "resolve_runtime") as resolve:
                with self.assertRaisesRegex(SystemExit, "runtime_revision_unverified"):
                    module.main()
                resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
