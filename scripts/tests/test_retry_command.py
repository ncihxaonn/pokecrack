from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("retry_command", ROOT / "scripts/retry_command.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class RetryCommandTests(unittest.TestCase):
    def test_retries_then_atomically_publishes_only_successful_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            calls = [
                subprocess.CompletedProcess(["ssh"], 255, b"partial"),
                subprocess.CompletedProcess(["ssh"], 0, b'{"ok":true}\n'),
            ]
            with patch.object(module.subprocess, "run", side_effect=calls) as run:
                result = module.run_with_retries(
                    ["ssh", "target"],
                    output_path=output,
                    sleeper=lambda _: None,
                )
            self.assertEqual(result, 0)
            self.assertEqual(output.read_bytes(), b'{"ok":true}\n')
            self.assertEqual(run.call_count, 2)

    def test_reopens_input_for_each_attempt_and_returns_final_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_bytes(b"manifest")
            calls = [
                subprocess.CompletedProcess(["ssh"], 255, b""),
                subprocess.CompletedProcess(["ssh"], 255, b""),
                subprocess.CompletedProcess(["ssh"], 255, b""),
            ]
            seen_input: list[bytes] = []

            def fake_run(command, *, stdin, stdout, check):
                del command, stdout, check
                self.assertIsNotNone(stdin)
                seen_input.append(stdin.read())
                return calls[len(seen_input) - 1]

            with patch.object(module.subprocess, "run", side_effect=fake_run) as run:
                result = module.run_with_retries(
                    ["ssh", "target"],
                    input_path=input_path,
                    sleeper=lambda _: None,
                )
            self.assertEqual(result, 255)
            self.assertEqual(run.call_count, 3)
            self.assertEqual(seen_input, [b"manifest", b"manifest", b"manifest"])
