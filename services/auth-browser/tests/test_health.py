from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from pokecrack_browser.config import ServiceSettings
from pokecrack_browser.errors import ServiceError
from pokecrack_browser.health import (
    HealthChecker,
    check_auth,
    interpret_auth_health,
    parse_version_output,
    write_auth_state,
    write_extension_health,
)
from pokecrack_browser.runtime import write_runtime_state


class DoctorParserTests(unittest.TestCase):
    def test_version_parser_strips_ansi_and_accepts_first_nonempty_line(self) -> None:
        output = "\n\x1b[32mOpenCLI Browser Bridge 1.2.3\x1b[0m\nextra\n"
        self.assertEqual(parse_version_output(output), "OpenCLI Browser Bridge 1.2.3")

    def test_version_parser_rejects_empty_or_unbounded_output(self) -> None:
        for output in ("", " \n", "x" * 4097):
            with self.subTest(length=len(output)), self.assertRaises(ValueError):
                parse_version_output(output)


class AuthHealthTests(unittest.TestCase):
    def test_fixture_auth_check_is_structured_and_never_returns_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = ServiceSettings(runtime_root=Path(temporary).resolve() / "runtime")
            result = check_auth(settings, "fixture")

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "authenticated")
        self.assertTrue(result["fixture"])
        serialized = json.dumps(result).lower()
        for forbidden in ("cookie", "authorization", "token", "password"):
            self.assertNotIn(forbidden, serialized)

    def test_browser_auth_check_fails_before_adapter_execution_when_opencli_is_disabled(
        self,
    ) -> None:
        from pokecrack_browser.adapters import load_adapter

        with tempfile.TemporaryDirectory() as temporary:
            settings = ServiceSettings(runtime_root=Path(temporary).resolve() / "runtime")
            adapter = replace(
                load_adapter("fixture", settings.adapter_root),
                requires_browser=True,
            )
            with (
                patch("pokecrack_browser.health.load_adapter", return_value=adapter),
                patch("pokecrack_browser.health.run_bounded_process") as run,
                self.assertRaises(ServiceError) as caught,
            ):
                check_auth(settings, "fixture")

        self.assertEqual(caught.exception.category, "source_unavailable")
        run.assert_not_called()

    def test_auth_health_false_values_map_to_exact_categories(self) -> None:
        cases = (
            (
                {"daemon_available": False, "extension_connected": True, "authenticated": True},
                "daemon_unavailable",
            ),
            (
                {"daemon_available": True, "extension_connected": False, "authenticated": True},
                "extension_disconnected",
            ),
            (
                {"daemon_available": True, "extension_connected": True, "authenticated": False},
                "auth_required",
            ),
        )
        for payload, category in cases:
            with self.subTest(category=category), self.assertRaises(ServiceError) as caught:
                interpret_auth_health(payload)
            self.assertEqual(caught.exception.category, category)


class StatusHealthTests(unittest.TestCase):
    def test_status_checks_process_daemon_extension_cdp_and_auth_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            settings = ServiceSettings(
                runtime_root=root / "runtime",
                extension_version="1.2.3",
                opencli_enabled=True,
            )
            now = datetime.now(UTC)
            write_runtime_state(
                settings.runtime_root,
                {
                    "profile": "research-general",
                    "pid": 777,
                    "process_identity": "test-identity:777",
                    "status": "running",
                },
            )
            write_extension_health(
                settings.runtime_root,
                connected=True,
                version="1.2.3",
                checked_at=now,
            )
            write_auth_state(
                settings.runtime_root,
                "fixture",
                state="authenticated",
                checked_at=now,
            )
            checker = HealthChecker(
                settings,
                matches_identity=lambda pid, identity: (
                    pid == 777 and identity == "test-identity:777"
                ),
                tcp_check=lambda host, port, timeout: host == "127.0.0.1" and port in {9222, 19825},
                now=lambda: now,
            )

            result = checker.status()

        self.assertTrue(result["healthy"])
        self.assertTrue(result["checks"]["browser_process"]["ok"])
        self.assertTrue(result["checks"]["daemon"]["ok"])
        self.assertTrue(result["checks"]["extension"]["ok"])
        self.assertTrue(result["checks"]["cdp"]["ok"])
        self.assertEqual(result["checks"]["cdp"]["purpose"], "health/debug only")
        self.assertEqual(result["auth"]["fixture"]["state"], "authenticated")


if __name__ == "__main__":
    unittest.main()
