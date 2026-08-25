from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pokecrack_browser.config import ServiceSettings
from pokecrack_browser.errors import ServiceError
from pokecrack_browser.manager import BrowserManager
from pokecrack_browser.runtime import read_runtime_state, write_runtime_state


class _Spawned:
    pid = 4242


class BrowserManagerTests(unittest.TestCase):
    def _settings(self, root: Path) -> ServiceSettings:
        extension = root / "bridge" / "extension"
        extension.mkdir(parents=True)
        (extension / "manifest.json").write_text(
            json.dumps(
                {
                    "manifest_version": 3,
                    "name": "Browser Bridge",
                    "version": "4.5.6",
                    "background": {"service_worker": "background.js"},
                }
            ),
            encoding="utf-8",
        )
        return ServiceSettings(
            profile_root=root / "profiles",
            runtime_root=root / "runtime",
            extension_dir=extension,
            extension_version="4.5.6",
        )

    def test_start_spawns_internal_worker_with_inherited_lock_and_private_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = self._settings(root)
            calls: list[tuple[list[str], dict[str, object]]] = []

            def spawn(argv: list[str], **kwargs: object) -> _Spawned:
                calls.append((argv, kwargs))
                return _Spawned()

            manager = BrowserManager(
                settings,
                popen=spawn,
                identity_for_pid=lambda pid: f"test-identity:{pid}",
                matches_identity=lambda _pid, _identity: False,
            )
            result = manager.start("social-western")

            self.assertEqual(result["profile"], "social-western")
            self.assertEqual(result["pid"], 4242)
            self.assertEqual(len(calls), 1)
            argv, kwargs = calls[0]
            self.assertIn("pokecrack_browser.browser_process", argv)
            self.assertIn("--lock-fd", argv)
            self.assertNotIn("--headless", argv)
            self.assertEqual(kwargs["start_new_session"], True)
            pass_fds = kwargs["pass_fds"]
            self.assertIsInstance(pass_fds, tuple)
            assert isinstance(pass_fds, tuple)
            self.assertEqual(len(pass_fds), 1)
            state = read_runtime_state(settings.runtime_root)
            assert state is not None
            self.assertEqual(state["profile"], "social-western")
            self.assertEqual(state["process_identity"], "test-identity:4242")
            self.assertNotIn("cookie", json.dumps(state).lower())

    def test_active_state_prevents_second_profile_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = self._settings(root)
            spawn_count = 0

            def spawn(_argv: list[str], **_kwargs: object) -> _Spawned:
                nonlocal spawn_count
                spawn_count += 1
                return _Spawned()

            manager = BrowserManager(
                settings,
                popen=spawn,
                identity_for_pid=lambda pid: f"test-identity:{pid}",
                matches_identity=lambda pid, identity: (
                    pid == 4242 and identity == "test-identity:4242"
                ),
            )
            manager.start("social-western")
            with self.assertRaises(ServiceError) as caught:
                manager.start("social-chinese")
            self.assertEqual(caught.exception.category, "profile_busy")
            self.assertEqual(spawn_count, 1)

    def test_stop_refuses_to_signal_a_reused_pid_with_the_wrong_process_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = self._settings(root)
            write_runtime_state(
                settings.runtime_root,
                {
                    "profile": "research-general",
                    "pid": 4242,
                    "process_identity": "original-process",
                    "status": "running",
                },
            )
            stopped: list[int] = []

            def stop(pid: int, _expected_identity: str, _timeout: float) -> str:
                stopped.append(pid)
                return "terminated"

            manager = BrowserManager(
                settings,
                matches_identity=lambda pid, identity: False,
                stopper=stop,
            )

            with self.assertRaises(ServiceError) as caught:
                manager.stop("research-general")

            self.assertEqual(caught.exception.category, "not_running")
            self.assertEqual(stopped, [])
            self.assertIsNone(read_runtime_state(settings.runtime_root))

    def test_stop_targets_matching_profile_and_clears_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = self._settings(root)
            stopped: list[tuple[int, str, float]] = []

            def stop(pid: int, expected_identity: str, timeout: float) -> str:
                stopped.append((pid, expected_identity, timeout))
                return "terminated"

            manager = BrowserManager(
                settings,
                popen=lambda _argv, **_kwargs: _Spawned(),
                identity_for_pid=lambda pid: f"test-identity:{pid}",
                matches_identity=lambda pid, identity: (
                    pid == 4242 and identity == "test-identity:4242"
                ),
                stopper=stop,
            )
            manager.start("research-general")

            result = manager.stop("research-general")

            self.assertEqual(result["shutdown"], "terminated")
            self.assertEqual(
                stopped,
                [(4242, "test-identity:4242", settings.shutdown_timeout)],
            )
            self.assertIsNone(read_runtime_state(settings.runtime_root))


if __name__ == "__main__":
    unittest.main()
