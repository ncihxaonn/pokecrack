from __future__ import annotations

import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pokecrack_browser.runtime import (
    ProfileBusyError,
    ProfileLock,
    process_identity,
    read_runtime_state,
    stop_process_gracefully,
    write_runtime_state,
)


class ProfileLockTests(unittest.TestCase):
    def test_global_lock_allows_only_one_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime_root = Path(temporary) / "runtime"
            with (
                ProfileLock.acquire(runtime_root, "social-western"),
                self.assertRaises(ProfileBusyError),
            ):
                ProfileLock.acquire(runtime_root, "social-chinese")

    def test_runtime_state_is_private_and_contains_no_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime_root = Path(temporary) / "runtime"
            state = {
                "profile": "research-general",
                "pid": 123,
                "status": "starting",
            }
            write_runtime_state(runtime_root, state)
            state_path = runtime_root / "state.json"

            self.assertEqual(stat.S_IMODE(runtime_root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(state_path.stat().st_mode), 0o600)
            self.assertEqual(read_runtime_state(runtime_root), state)
            serialized = state_path.read_text(encoding="utf-8").lower()
            for forbidden in ("cookie", "authorization", "token", "password"):
                self.assertNotIn(forbidden, serialized)


class GracefulShutdownTests(unittest.TestCase):
    def test_wrong_process_identity_never_signals_a_live_process(self) -> None:
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            outcome = stop_process_gracefully(
                process.pid,
                expected_identity="wrong-boot-and-start-time",
                timeout=0,
            )
            self.assertEqual(outcome, "identity_mismatch")
            self.assertIsNone(process.poll())
        finally:
            process.kill()
            process.wait()

    def test_sigterm_is_used_and_process_exits_before_kill(self) -> None:
        script = (
            "import signal,time,sys; "
            "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
            "print('ready', flush=True); time.sleep(30)"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert process.stdout is not None
            self.assertEqual(process.stdout.readline().strip(), "ready")
            identity = process_identity(process.pid)
            assert identity is not None
            outcome = stop_process_gracefully(
                process.pid,
                expected_identity=identity,
                timeout=2.0,
            )
            process.wait(timeout=2.0)
            self.assertEqual(outcome, "terminated")
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdout is not None:
                process.stdout.close()


if __name__ == "__main__":
    unittest.main()
