from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_ci_checks.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class CanonicalCiRunnerTests(unittest.TestCase):
    def run_runner(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.pop("GITHUB_SHA", None)
        return subprocess.run(
            [str(RUNNER), *arguments],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_runner_is_executable_and_lists_every_stage(self) -> None:
        self.assertTrue(os.access(RUNNER, os.X_OK))
        result = self.run_runner("--list")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "web",
                "worker",
                "auth-browser",
                "database",
                "container-worker",
                "repository-policy",
                "deployment-contracts",
            ],
        )

    def test_runner_requires_an_explicit_expected_sha(self) -> None:
        result = self.run_runner("web")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--expected-sha is required", result.stdout)

    def test_sha_mismatch_is_rejected_before_running_a_stage(self) -> None:
        result = self.run_runner(
            "web",
            "--expected-sha",
            "0" * 40,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checkout SHA does not match", result.stdout)

    def test_workflow_delegates_each_check_job_to_the_runner(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for stage in (
            "web",
            "worker",
            "auth-browser",
            "database",
            "container-worker",
            "repository-policy",
            "deployment-contracts",
        ):
            self.assertIn(
                f"scripts/run_ci_checks.sh {stage} --expected-sha",
                workflow,
            )

    def test_runner_does_not_contain_production_mutation_entrypoints(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        for forbidden in (
            "SUPABASE_ACCESS_TOKEN",
            "run_supabase_migrations.py apply",
            "deploy.sh",
            "vercel --prod",
            "VPS_SSH_PRIVATE_KEY",
        ):
            self.assertNotIn(forbidden, source)

    def test_runner_accepts_the_github_checkout_origin_variant(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn(
            r"^https://github\.com/ncihxaonn/pokecrack(\.git)?$",
            source,
        )


if __name__ == "__main__":
    unittest.main()
