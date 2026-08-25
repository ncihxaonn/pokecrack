from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = SERVICE_ROOT / "src"


def run_cli(
    *args: str, env_overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "pokecrack_browser", *args],
        cwd=SERVICE_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


class CliContractTests(unittest.TestCase):
    def test_mutating_profile_commands_offer_dry_run_and_required_profile(self) -> None:
        for command in ("start-profile", "stop-profile"):
            with self.subTest(command=command):
                completed = run_cli(command, "--help")
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("PROFILE", completed.stdout)
                self.assertIn("--dry-run", completed.stdout)

    def test_start_profile_dry_run_is_json_and_has_no_filesystem_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile_root = Path(temporary) / "profiles"
            runtime_root = Path(temporary) / "runtime"
            completed = run_cli(
                "start-profile",
                "social-western",
                "--dry-run",
                env_overrides={
                    "POKECRACK_BROWSER_PROFILE_ROOT": str(profile_root),
                    "POKECRACK_BROWSER_RUNTIME_ROOT": str(runtime_root),
                },
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["profile"], "social-western")
            self.assertFalse(profile_root.exists())
            self.assertFalse(runtime_root.exists())
            self.assertNotIn("cookie", completed.stdout.lower())

    def test_stop_profile_dry_run_does_not_require_runtime_state(self) -> None:
        completed = run_cli("stop-profile", "research-general", "--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["action"], "stop-profile")
        self.assertEqual(payload["profile"], "research-general")
        self.assertTrue(payload["dry_run"])

    def test_opencli_dry_run_validates_adapter_and_preserves_query_as_one_token(self) -> None:
        query = "cards; touch /tmp/never"
        completed = run_cli(
            "run-opencli",
            "fixture",
            "--query",
            query,
            "--max-results",
            "2",
            "--dry-run",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["argv"].count(query), 1)
        self.assertEqual(payload["profile"], "research-general")
        self.assertEqual(payload["adapter_version"], "1.0.0")

    def test_invalid_profile_has_structured_nonzero_error(self) -> None:
        completed = run_cli("start-profile", "../escape", "--dry-run")
        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stderr)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["category"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
