from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = SERVICE_ROOT / "src"
COMMANDS = (
    "start-profile",
    "stop-profile",
    "status",
    "doctor",
    "run-opencli",
    "check-auth",
)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "pokecrack_browser", *args],
        cwd=SERVICE_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


class CliHelpTests(unittest.TestCase):
    def test_every_required_command_has_help(self) -> None:
        for command in COMMANDS:
            with self.subTest(command=command):
                completed = run_cli(command, "--help")
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("usage:", completed.stdout.lower())
                self.assertIn(command, completed.stdout)

    def test_opencli_dry_run_redacts_query_credentials_from_rendered_argv(self) -> None:
        completed = run_cli(
            "run-opencli",
            "fixture",
            "--query",
            "https://user:password@fixture.example/item?access_token=do-not-log#private",
            "--dry-run",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("user:password", completed.stdout)
        self.assertNotIn("do-not-log", completed.stdout)
        self.assertNotIn("#private", completed.stdout)
        payload = __import__("json").loads(completed.stdout)
        query_index = payload["argv"].index("--query") + 1
        self.assertEqual(payload["argv"][query_index], "https://fixture.example/item")


if __name__ == "__main__":
    unittest.main()
