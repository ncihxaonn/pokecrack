from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from pokecrack_browser.config import ServiceSettings
from pokecrack_browser.errors import ServiceError
from pokecrack_browser.runner import (
    OpenCliRunner,
    _candidate,
    _public_source_url,
    map_adapter_failure,
    parse_and_validate_output,
    run_bounded_process,
)
from pokecrack_browser.runtime import write_runtime_state


def _process_is_running(pid: int) -> bool:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except (FileNotFoundError, OSError):
        return False
    closing_parenthesis = raw.rfind(")")
    if closing_parenthesis < 0:
        return False
    fields = raw[closing_parenthesis + 1 :].split()
    return bool(fields) and fields[0] != "Z"


class JsonOutputTests(unittest.TestCase):
    def test_ansi_json_is_parsed_and_schema_validated(self) -> None:
        schema = {
            "type": "object",
            "required": ["items"],
            "additionalProperties": False,
            "properties": {"items": {"type": "array", "maxItems": 2}},
        }
        value = parse_and_validate_output(
            b'\x1b[32m{"items":[]}\x1b[0m',
            schema,
            max_bytes=100,
        )
        self.assertEqual(value, {"items": []})

    def test_oversized_and_schema_invalid_json_have_invalid_json_category(self) -> None:
        with self.assertRaises(ServiceError) as oversized:
            parse_and_validate_output(b"{}" + b" " * 101, {"type": "object"}, max_bytes=100)
        self.assertEqual(oversized.exception.category, "invalid_json")

        schema = {"type": "object", "required": ["items"]}
        with self.assertRaises(ServiceError) as invalid:
            parse_and_validate_output(b"{}", schema, max_bytes=100)
        self.assertEqual(invalid.exception.category, "invalid_json")


class ErrorMappingTests(unittest.TestCase):
    def test_every_required_error_category_has_a_deterministic_mapping(self) -> None:
        cases = (
            (10, "", "auth_required"),
            (1, "browser extension disconnected", "extension_disconnected"),
            (1, "connect ECONNREFUSED 127.0.0.1:19825", "daemon_unavailable"),
            (1, "HTTP 429 too many requests", "rate_limited"),
            (1, "source unavailable (404)", "source_unavailable"),
            (1, "unknown adapter failure", "adapter_failed"),
        )
        for returncode, stderr, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(map_adapter_failure(returncode, stderr), expected)

    def test_timeout_and_bounded_capture_kill_instead_of_retrying_forever(self) -> None:
        with self.assertRaises(ServiceError) as timeout:
            run_bounded_process(
                [sys.executable, "-c", "import time; time.sleep(2)"],
                timeout_seconds=0.05,
            )
        self.assertEqual(timeout.exception.category, "timeout")

        with self.assertRaises(ServiceError) as too_large:
            run_bounded_process(
                [sys.executable, "-c", "print('x' * 10000)"],
                timeout_seconds=2,
                max_stdout_bytes=100,
            )
        self.assertEqual(too_large.exception.category, "adapter_failed")

    def test_timeout_kills_descendants_when_the_process_leader_has_already_exited(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            child_pid_path = Path(temporary).resolve() / "child.pid"
            leader = (
                "import subprocess, sys; from pathlib import Path; "
                "child = subprocess.Popen([sys.executable, '-c', "
                "'import time; time.sleep(30)']); "
                f"Path({str(child_pid_path)!r}).write_text(str(child.pid), encoding='ascii')"
            )
            child_pid: int | None = None
            try:
                with self.assertRaises(ServiceError) as timeout:
                    run_bounded_process(
                        [sys.executable, "-c", leader],
                        timeout_seconds=0.5,
                    )
                self.assertEqual(timeout.exception.category, "timeout")
                child_pid = int(child_pid_path.read_text(encoding="ascii"))

                deadline = time.monotonic() + 1
                while time.monotonic() < deadline and _process_is_running(child_pid):
                    time.sleep(0.02)
                self.assertFalse(
                    _process_is_running(child_pid),
                    "timed-out adapter descendant survived its process-group bound",
                )
            finally:
                if child_pid is not None and _process_is_running(child_pid):
                    os.kill(child_pid, signal.SIGKILL)

    def test_captured_stderr_is_ansi_stripped_and_redacted(self) -> None:
        capture = run_bounded_process(
            [
                sys.executable,
                "-c",
                "import sys; sys.stderr.write('\\x1b[31mAuthorization: "
                "Bearer secret-value\\x1b[0m')",
            ],
            timeout_seconds=2,
        )
        self.assertNotIn("secret-value", capture.stderr)
        self.assertNotIn("\x1b", capture.stderr)
        self.assertIn("[REDACTED]", capture.stderr)


class FixtureRunnerTests(unittest.TestCase):
    def test_fixture_runner_emits_only_source_item_candidates_with_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = ServiceSettings(
                runtime_root=Path(temporary).resolve() / "runtime",
                extension_version="fixture-not-used",
            )
            result = OpenCliRunner(settings).run(
                "fixture",
                query="pokemon fixture",
                max_results=1,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["contract"], "SourceItemCandidate")
        self.assertEqual(result["adapter"], "fixture")
        self.assertEqual(result["profile"], "research-general")
        self.assertEqual(result["versions"]["adapter"], "1.0.0")
        self.assertEqual(result["versions"]["cli"], "fixture-opencli 1.0.0")
        self.assertEqual(len(result["items"]), 1)
        candidate = result["items"][0]
        self.assertEqual(candidate["collector"], "opencli_authenticated")
        self.assertTrue(candidate["source_url"].startswith("https://"))
        self.assertRegex(candidate["author_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(candidate["text"], "Synthetic fixture item; no platform session was used.")
        self.assertEqual(candidate["media_urls"], [])
        self.assertEqual(candidate["collector_version"], "opencli-fixture-1.0.0")
        for forbidden in ("author", "excerpt", "content", "image_urls", "opening"):
            self.assertNotIn(forbidden, candidate)
        self.assertNotIn("fixture-author", json.dumps(result))
        self.assertNotIn("cookie", json.dumps(result).lower())


class BrowserIdentityTests(unittest.TestCase):
    def test_runner_rejects_a_reused_pid_that_does_not_match_recorded_identity(self) -> None:
        from pokecrack_browser.adapters import load_adapter

        with tempfile.TemporaryDirectory() as temporary:
            settings = ServiceSettings(
                runtime_root=Path(temporary).resolve() / "runtime",
                opencli_enabled=True,
            )
            write_runtime_state(
                settings.runtime_root,
                {
                    "profile": "research-general",
                    "pid": 4242,
                    "process_identity": "original-process",
                    "status": "running",
                },
            )
            adapter = replace(
                load_adapter("fixture", settings.adapter_root),
                requires_browser=True,
            )
            with (
                patch(
                    "pokecrack_browser.runner.process_matches_identity",
                    return_value=False,
                ),
                self.assertRaises(ServiceError) as caught,
            ):
                OpenCliRunner(settings)._assert_browser(adapter)

        self.assertEqual(caught.exception.category, "daemon_unavailable")


class CandidateSafetyTests(unittest.TestCase):
    def test_candidate_strips_query_and_fragment_and_rejects_url_userinfo(self) -> None:
        from pokecrack_browser.adapters import load_adapter

        adapter = load_adapter("fixture", ServiceSettings().adapter_root)
        candidate = _candidate(
            {"source_url": ("https://research.example.invalid/path?token=private#fragment")},
            adapter,
        )
        self.assertEqual(
            candidate["source_url"],
            "https://research.example.invalid/path",
        )
        with self.assertRaises(ServiceError):
            _candidate(
                {"source_url": ("https://user:pass@research.example.invalid/path")},
                adapter,
            )

    def test_candidate_urls_require_https_pinned_hosts_and_reject_private_targets(self) -> None:
        allowed = frozenset({"research.example.invalid", "127.0.0.1", "localhost"})
        for value in (
            "http://research.example.invalid/plaintext",
            "https://other.example/item",
            "https://127.0.0.1/private",
            "https://localhost/private",
        ):
            with self.subTest(value=value), self.assertRaises(ServiceError):
                _public_source_url(value, allowed)


if __name__ == "__main__":
    unittest.main()
