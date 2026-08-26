"""Start and stop exactly one persistent browser profile."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import ServiceSettings
from .errors import ServiceError
from .launcher import BrowserLaunchConfig
from .paths import PathValidationError, prepare_profile_directory, validate_extension_path
from .runtime import (
    ProfileBusyError,
    ProfileLock,
    clear_runtime_state,
    process_identity,
    process_matches_identity,
    read_runtime_state,
    stop_process_gracefully,
    write_runtime_state,
)


class BrowserManager:
    def __init__(
        self,
        settings: ServiceSettings,
        *,
        popen: Callable[..., Any] = subprocess.Popen,
        identity_for_pid: Callable[[int], str | None] = process_identity,
        matches_identity: Callable[[int, str], bool] = process_matches_identity,
        stopper: Callable[..., str] = stop_process_gracefully,
    ) -> None:
        self.settings = settings
        self._popen = popen
        self._identity_for_pid = identity_for_pid
        self._matches_identity = matches_identity
        self._stopper = stopper

    def _active_state(self) -> dict[str, Any] | None:
        state = read_runtime_state(self.settings.runtime_root)
        if state is None:
            return None
        pid = state.get("pid")
        identity = state.get("process_identity")
        if (
            isinstance(pid, int)
            and isinstance(identity, str)
            and self._matches_identity(pid, identity)
        ):
            return state
        clear_runtime_state(self.settings.runtime_root)
        return None

    def start(self, profile: str) -> dict[str, Any]:
        extension_dir: Path | None = None
        if self.settings.opencli_enabled and not self.settings.extension_version:
            raise ServiceError(
                "invalid_request",
                "POKECRACK_BRIDGE_VERSION must pin the mounted extension version",
            )
        try:
            profile_dir = prepare_profile_directory(
                self.settings.profile_root,
                profile,
                create=True,
            )
            if self.settings.opencli_enabled:
                extension_dir = validate_extension_path(
                    self.settings.extension_dir,
                    expected_version=self.settings.extension_version,
                )
            active = self._active_state()
            if active is not None:
                raise ServiceError(
                    "profile_busy",
                    f"profile {active.get('profile', 'unknown')} is already active",
                )
            lock = ProfileLock.acquire(self.settings.runtime_root, profile)
        except ProfileBusyError as exc:
            raise ServiceError("profile_busy", str(exc)) from exc
        except PathValidationError as exc:
            raise ServiceError("invalid_request", str(exc)) from exc

        config = BrowserLaunchConfig(
            profile_dir=profile_dir,
            extension_dir=extension_dir,
            cdp_host=self.settings.cdp_host,
            cdp_port=self.settings.cdp_port,
            chromium_executable=self.settings.chromium_executable,
        )
        argv = [
            sys.executable,
            "-m",
            "pokecrack_browser.browser_process",
            "--profile-dir",
            str(config.profile_dir),
            "--cdp-host",
            config.cdp_host,
            "--cdp-port",
            str(config.cdp_port),
            "--lock-fd",
            str(lock.file_descriptor),
        ]
        if config.extension_dir is not None:
            argv.extend(["--extension-dir", str(config.extension_dir)])
        if config.chromium_executable is not None:
            argv.extend(["--chromium-executable", str(config.chromium_executable)])

        process: Any | None = None
        try:
            process = self._popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                pass_fds=(lock.file_descriptor,),
                start_new_session=True,
            )
            pid = int(process.pid)
            identity = self._identity_for_pid(pid)
            if identity is None:
                raise ServiceError(
                    "source_unavailable",
                    "browser process identity could not be established",
                )
            state = {
                "profile": profile,
                "pid": pid,
                "process_identity": identity,
                "status": "starting",
                "started_at": datetime.now(UTC).isoformat(),
                "extension_version": self.settings.extension_version or None,
                "cdp_endpoint": f"http://{config.cdp_host}:{config.cdp_port}",
                "daemon_endpoint": (
                    f"http://{self.settings.daemon_host}:{self.settings.daemon_port}"
                ),
            }
            write_runtime_state(self.settings.runtime_root, state)
            lock.transfer_to_child()
        except Exception:
            if process is not None:
                pid = int(process.pid)
                identity = self._identity_for_pid(pid)
                if identity is not None:
                    self._stopper(
                        pid,
                        expected_identity=identity,
                        timeout=self.settings.shutdown_timeout,
                    )
                elif hasattr(process, "kill"):
                    process.kill()
            lock.close()
            raise
        return {"ok": True, "action": "start-profile", **state}

    def stop(self, profile: str) -> dict[str, Any]:
        state = read_runtime_state(self.settings.runtime_root)
        if state is None:
            raise ServiceError("not_running", "no browser profile is active")
        if state.get("profile") != profile:
            raise ServiceError(
                "invalid_request",
                f"active profile is {state.get('profile')!r}, not {profile!r}",
            )
        pid = state.get("pid")
        identity = state.get("process_identity")
        if (
            not isinstance(pid, int)
            or not isinstance(identity, str)
            or not self._matches_identity(pid, identity)
        ):
            clear_runtime_state(self.settings.runtime_root)
            raise ServiceError("not_running", "browser process identity no longer matches")
        shutdown = self._stopper(
            pid,
            expected_identity=identity,
            timeout=self.settings.shutdown_timeout,
        )
        clear_runtime_state(self.settings.runtime_root)
        return {
            "ok": True,
            "action": "stop-profile",
            "profile": profile,
            "pid": pid,
            "shutdown": shutdown,
        }
