"""Private runtime state, process lifecycle, and one-profile locking."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import signal
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from .paths import PathValidationError, validate_profile_name

SENSITIVE_STATE_KEYS = frozenset(
    {"authorization", "cookie", "cookies", "password", "secret", "token"}
)


class ProfileBusyError(RuntimeError):
    """Another persistent profile owns the process-wide browser lock."""


def ensure_private_runtime_root(root: str | os.PathLike[str]) -> Path:
    path = Path(root)
    if not path.is_absolute():
        raise PathValidationError(f"runtime root must be absolute: {path}")
    if path.is_symlink():
        raise PathValidationError(f"runtime root must not be a symbolic link: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise PathValidationError(f"runtime root must be a directory: {path}")
    os.chmod(path, 0o700)
    return path


class ProfileLock:
    """A non-blocking flock held for the lifetime of the headed browser."""

    def __init__(self, file_descriptor: int, path: Path, profile: str) -> None:
        self.file_descriptor = file_descriptor
        self.path = path
        self.profile = profile
        self._closed = False

    @classmethod
    def acquire(
        cls,
        runtime_root: str | os.PathLike[str],
        profile: str,
    ) -> Self:
        validate_profile_name(profile)
        root = ensure_private_runtime_root(runtime_root)
        path = root / "profile.lock"
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(descriptor)
            raise ProfileBusyError("another browser profile is already active") from exc
        os.set_inheritable(descriptor, True)
        return cls(descriptor, path, profile)

    def close(self) -> None:
        if self._closed:
            return
        fcntl.flock(self.file_descriptor, fcntl.LOCK_UN)
        os.close(self.file_descriptor)
        self._closed = True

    def transfer_to_child(self) -> None:
        """Close only the parent copy; an inherited child fd keeps the flock held."""
        if self._closed:
            return
        os.close(self.file_descriptor)
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _reject_sensitive_state(value: Any, *, path: str = "state") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SENSITIVE_STATE_KEYS or any(
                fragment in normalized for fragment in ("cookie", "password", "secret", "token")
            ):
                raise ValueError(f"sensitive field is forbidden in runtime state: {path}.{key}")
            _reject_sensitive_state(nested, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_sensitive_state(nested, path=f"{path}[{index}]")


def write_runtime_state(
    runtime_root: str | os.PathLike[str],
    state: Mapping[str, Any],
) -> Path:
    _reject_sensitive_state(state)
    root = ensure_private_runtime_root(runtime_root)
    state_path = root / "state.json"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".state-", dir=root)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(dict(state), stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, state_path)
        os.chmod(state_path, 0o600)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary_name)
    return state_path


def read_runtime_state(runtime_root: str | os.PathLike[str]) -> dict[str, Any] | None:
    root = Path(runtime_root)
    state_path = root / "state.json"
    if state_path.is_symlink():
        raise PathValidationError(f"runtime state must not be a symbolic link: {state_path}")
    try:
        raw = state_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("runtime state must be a JSON object")
    _reject_sensitive_state(value)
    return value


def clear_runtime_state(runtime_root: str | os.PathLike[str]) -> None:
    state_path = Path(runtime_root) / "state.json"
    if state_path.is_symlink():
        raise PathValidationError(f"runtime state must not be a symbolic link: {state_path}")
    with contextlib.suppress(FileNotFoundError):
        state_path.unlink()


def process_identity(pid: int) -> str | None:
    """Return a boot-scoped Linux process identity, not merely a reusable PID."""
    if pid <= 0:
        return None
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        raw_stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeError):
        return None
    closing_parenthesis = raw_stat.rfind(")")
    if not boot_id or closing_parenthesis < 0:
        return None
    fields = raw_stat[closing_parenthesis + 1 :].split()
    if len(fields) <= 19 or fields[0] == "Z":
        return None
    start_ticks = fields[19]
    if not start_ticks.isdigit():
        return None
    return f"{boot_id}:{start_ticks}"


def process_matches_identity(pid: int, expected_identity: str) -> bool:
    return bool(expected_identity) and process_identity(pid) == expected_identity


def process_is_alive(pid: int) -> bool:
    return process_identity(pid) is not None


def _send_verified_signal(pid: int, expected_identity: str, signum: int) -> bool:
    pidfd_open = getattr(os, "pidfd_open", None)
    pidfd_send_signal = getattr(signal, "pidfd_send_signal", None)
    if callable(pidfd_open) and callable(pidfd_send_signal):
        try:
            descriptor = pidfd_open(pid, 0)
        except (ProcessLookupError, PermissionError, OSError):
            return False
        try:
            if not process_matches_identity(pid, expected_identity):
                return False
            try:
                pidfd_send_signal(descriptor, signum)
            except (ProcessLookupError, PermissionError, OSError):
                return False
            return True
        finally:
            os.close(descriptor)
    if not process_matches_identity(pid, expected_identity):
        return False
    try:
        os.kill(pid, signum)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def stop_process_gracefully(
    pid: int,
    *,
    expected_identity: str,
    timeout: float = 10.0,
) -> str:
    """Stop only the boot-scoped process identity recorded at browser launch."""
    if not process_matches_identity(pid, expected_identity):
        return "identity_mismatch"
    if not _send_verified_signal(pid, expected_identity, signal.SIGTERM):
        return "not_running"
    deadline = time.monotonic() + max(timeout, 0.0)
    while time.monotonic() < deadline:
        if not process_matches_identity(pid, expected_identity):
            return "terminated"
        time.sleep(0.05)
    if process_matches_identity(pid, expected_identity):
        if _send_verified_signal(pid, expected_identity, signal.SIGKILL):
            return "killed"
        return "identity_mismatch"
    return "terminated"
