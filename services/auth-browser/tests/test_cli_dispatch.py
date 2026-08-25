from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from pokecrack_browser.cli import main
from pokecrack_browser.config import ServiceSettings


class CliLifecycleDispatchTests(unittest.TestCase):
    def test_start_profile_dispatches_to_browser_manager(self) -> None:
        settings = ServiceSettings(extension_version="1.0.0")
        result = {"ok": True, "action": "start-profile", "profile": "social-western"}
        manager = Mock()
        manager.start.return_value = result
        with (
            patch("pokecrack_browser.cli.ServiceSettings.from_env", return_value=settings),
            patch("pokecrack_browser.cli.BrowserManager", return_value=manager),
            patch("pokecrack_browser.cli._json") as emit,
        ):
            exit_code = main(["start-profile", "social-western"])

        self.assertEqual(exit_code, 0)
        manager.start.assert_called_once_with("social-western")
        emit.assert_called_once_with(result)

    def test_stop_profile_dispatches_to_browser_manager(self) -> None:
        settings = ServiceSettings(extension_version="1.0.0")
        result = {"ok": True, "action": "stop-profile", "profile": "research-general"}
        manager = Mock()
        manager.stop.return_value = result
        with (
            patch("pokecrack_browser.cli.ServiceSettings.from_env", return_value=settings),
            patch("pokecrack_browser.cli.BrowserManager", return_value=manager),
            patch("pokecrack_browser.cli._json") as emit,
        ):
            exit_code = main(["stop-profile", "research-general"])

        self.assertEqual(exit_code, 0)
        manager.stop.assert_called_once_with("research-general")
        emit.assert_called_once_with(result)

    def test_run_opencli_dispatches_to_bounded_runner(self) -> None:
        settings = ServiceSettings(extension_version="1.0.0")
        result = {"ok": True, "action": "run-opencli", "items": []}
        runner = Mock()
        runner.run.return_value = result
        with (
            patch("pokecrack_browser.cli.ServiceSettings.from_env", return_value=settings),
            patch("pokecrack_browser.cli.OpenCliRunner", return_value=runner),
            patch("pokecrack_browser.cli._json") as emit,
        ):
            exit_code = main(["run-opencli", "fixture", "--query", "cards", "--max-results", "3"])

        self.assertEqual(exit_code, 0)
        runner.run.assert_called_once_with("fixture", query="cards", max_results=3)
        emit.assert_called_once_with(result)

    def test_status_doctor_and_auth_commands_dispatch_to_health_contracts(self) -> None:
        settings = ServiceSettings(extension_version="1.0.0")
        status_result = {"ok": True, "action": "status", "healthy": False}
        doctor_result = {"ok": False, "action": "doctor", "checks": []}
        auth_result = {"ok": True, "action": "check-auth", "state": "authenticated"}
        checker = Mock()
        checker.status.return_value = status_result
        with (
            patch("pokecrack_browser.cli.ServiceSettings.from_env", return_value=settings),
            patch("pokecrack_browser.cli.HealthChecker", return_value=checker),
            patch("pokecrack_browser.cli.run_doctor", return_value=doctor_result),
            patch("pokecrack_browser.cli.check_auth", return_value=auth_result) as auth,
            patch("pokecrack_browser.cli._json") as emit,
        ):
            self.assertEqual(main(["status"]), 0)
            emit.assert_called_with(status_result)
            self.assertEqual(main(["doctor"]), 1)
            emit.assert_called_with(doctor_result)
            self.assertEqual(main(["check-auth", "fixture"]), 0)
            auth.assert_called_once_with(settings, "fixture")
            emit.assert_called_with(auth_result)


if __name__ == "__main__":
    unittest.main()
