from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from pokecrack_browser.config import ServiceSettings
from pokecrack_browser.container_browser import supervise_profile
from pokecrack_browser.runtime import write_runtime_state


class _FakeManager:
    def __init__(self, settings: ServiceSettings) -> None:
        self.settings = settings
        self.stopped: list[str] = []

    def start(self, profile: str) -> dict[str, object]:
        state: dict[str, object] = {
            "profile": profile,
            "pid": 4242,
            "process_identity": "test-process:4242",
            "status": "starting",
        }
        write_runtime_state(self.settings.runtime_root, state)
        return {"ok": True, "action": "start-profile", **state}

    def stop(self, profile: str) -> dict[str, object]:
        self.stopped.append(profile)
        return {"ok": True, "action": "stop-profile", "profile": profile}


class ContainerBrowserSupervisorTests(unittest.TestCase):
    def test_container_supervisor_starts_and_stops_through_browser_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = ServiceSettings(runtime_root=Path(temporary).resolve() / "runtime")
            manager = _FakeManager(settings)
            stop = threading.Event()
            stop.set()

            result = supervise_profile(
                settings,
                "research-general",
                stop_event=stop,
                manager_factory=lambda _settings: manager,
                matches_identity=lambda pid, identity: (
                    pid == 4242 and identity == "test-process:4242"
                ),
                poll_seconds=0.001,
            )

        self.assertEqual(result, 0)
        self.assertEqual(manager.stopped, ["research-general"])

    def test_container_supervisor_fails_when_manager_child_identity_disappears(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = ServiceSettings(runtime_root=Path(temporary).resolve() / "runtime")
            manager = _FakeManager(settings)

            result = supervise_profile(
                settings,
                "social-western",
                stop_event=threading.Event(),
                manager_factory=lambda _settings: manager,
                matches_identity=lambda _pid, _identity: False,
                poll_seconds=0.001,
            )

        self.assertEqual(result, 1)
        self.assertEqual(manager.stopped, ["social-western"])


if __name__ == "__main__":
    unittest.main()
