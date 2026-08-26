"""Finite browser, daemon, extension, auth, and installation health checks."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import shutil
import socket
import stat
import tempfile
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .adapters import AdapterConfigError, load_adapter
from .config import ServiceSettings
from .errors import ServiceError
from .paths import PathValidationError, validate_extension_path
from .redaction import redact, redact_text, strip_ansi
from .runner import map_adapter_failure, parse_and_validate_output, run_bounded_process
from .runtime import ensure_private_runtime_root, process_matches_identity, read_runtime_state

HEALTH_STALE_SECONDS = 60.0
MAX_HEALTH_BYTES = 64 * 1024


def parse_version_output(output: str, *, max_bytes: int = 4096) -> str:
    if len(output.encode("utf-8")) > max_bytes:
        raise ValueError("version output exceeds its byte limit")
    lines = [line.strip() for line in strip_ansi(output).splitlines() if line.strip()]
    if not lines:
        raise ValueError("version output is empty")
    return redact_text(lines[0])


def _atomic_json(root: Path, name: str, value: Mapping[str, Any]) -> Path:
    private_root = ensure_private_runtime_root(root)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{name}-", dir=private_root)
    destination = private_root / f"{name}.json"
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(dict(value), stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
        os.replace(temporary_name, destination)
        os.chmod(destination, 0o600)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary_name)
    return destination


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def write_extension_health(
    runtime_root: Path,
    *,
    connected: bool,
    version: str,
    checked_at: datetime | None = None,
) -> Path:
    if not isinstance(connected, bool) or not isinstance(version, str):
        raise ValueError("extension health fields are invalid")
    return _atomic_json(
        runtime_root,
        "extension-health",
        {
            "connected": connected,
            "version": version,
            "checked_at": _iso(checked_at or datetime.now(UTC)),
        },
    )


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if path.is_symlink():
        raise ValueError(f"health state must not be a symlink: {path}")
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    if len(raw) > MAX_HEALTH_BYTES:
        raise ValueError(f"health state exceeds size limit: {path}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"health state must be an object: {path}")
    return value


def write_auth_state(
    runtime_root: Path,
    source: str,
    *,
    state: str,
    checked_at: datetime | None = None,
) -> Path:
    if state not in {"authenticated", "auth_required", "unavailable"}:
        raise ValueError("auth state is invalid")
    root = ensure_private_runtime_root(runtime_root)
    current = _read_json_file(root / "auth-state.json") or {"sources": {}}
    sources = current.get("sources")
    if not isinstance(sources, dict):
        sources = {}
    sources[source] = {
        "state": state,
        "checked_at": _iso(checked_at or datetime.now(UTC)),
    }
    return _atomic_json(root, "auth-state", {"sources": sources})


def interpret_auth_health(payload: Mapping[str, Any]) -> None:
    fields = ("daemon_available", "extension_connected", "authenticated")
    if any(not isinstance(payload.get(field), bool) for field in fields):
        raise ServiceError("invalid_json", "auth-health output requires boolean health fields")
    if not payload["daemon_available"]:
        raise ServiceError("daemon_unavailable", "Browser Bridge daemon is unavailable")
    if not payload["extension_connected"]:
        raise ServiceError("extension_disconnected", "Browser Bridge extension is disconnected")
    if not payload["authenticated"]:
        raise ServiceError("auth_required", "platform authentication is required")


def check_auth(settings: ServiceSettings, source: str) -> dict[str, Any]:
    try:
        adapter = load_adapter(source, settings.adapter_root)
    except AdapterConfigError as exc:
        raise ServiceError("source_unavailable", str(exc)) from exc
    if adapter.requires_browser:
        if not settings.opencli_enabled:
            write_auth_state(settings.runtime_root, source, state="unavailable")
            raise ServiceError("source_unavailable", "OpenCLI is disabled")
        state = read_runtime_state(settings.runtime_root)
        if state is None or state.get("profile") != adapter.profile:
            write_auth_state(settings.runtime_root, source, state="auth_required")
            raise ServiceError("auth_required", f"active profile {adapter.profile} is required")
    capture = run_bounded_process(
        adapter.render_auth_health_argv(),
        timeout_seconds=min(adapter.timeout_seconds, 10.0),
        max_stdout_bytes=MAX_HEALTH_BYTES,
        max_stderr_bytes=MAX_HEALTH_BYTES,
    )
    if capture.returncode != 0:
        category = map_adapter_failure(capture.returncode, capture.stderr)
        state_name = "auth_required" if category == "auth_required" else "unavailable"
        write_auth_state(settings.runtime_root, source, state=state_name)
        raise ServiceError(
            category,
            "adapter auth-health command failed",
            {"returncode": capture.returncode, "stderr": redact_text(capture.stderr)},
        )
    schema = {
        "type": "object",
        "required": ["authenticated", "daemon_available", "extension_connected"],
        "properties": {
            "authenticated": {"type": "boolean"},
            "daemon_available": {"type": "boolean"},
            "extension_connected": {"type": "boolean"},
            "fixture": {"type": "boolean"},
        },
    }
    payload = parse_and_validate_output(
        capture.stdout,
        schema,
        max_bytes=MAX_HEALTH_BYTES,
    )
    assert isinstance(payload, Mapping)
    try:
        interpret_auth_health(payload)
    except ServiceError as exc:
        state_name = "auth_required" if exc.category == "auth_required" else "unavailable"
        write_auth_state(settings.runtime_root, source, state=state_name)
        raise
    write_auth_state(settings.runtime_root, source, state="authenticated")
    return {
        "ok": True,
        "action": "check-auth",
        "source": adapter.name,
        "profile": adapter.profile,
        "state": "authenticated",
        "fixture": bool(payload.get("fixture", False)),
        "checked_at": datetime.now(UTC).isoformat(),
        "versions": {"adapter": adapter.version},
    }


def _tcp(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _parse_checked_at(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


class HealthChecker:
    def __init__(
        self,
        settings: ServiceSettings,
        *,
        matches_identity: Callable[[int, str], bool] = process_matches_identity,
        tcp_check: Callable[[str, int, float], bool] = _tcp,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.settings = settings
        self._matches_identity = matches_identity
        self._tcp_check = tcp_check
        self._now = now

    def status(self) -> dict[str, Any]:
        state = read_runtime_state(self.settings.runtime_root)
        pid = state.get("pid") if state else None
        identity = state.get("process_identity") if state else None
        browser_ok = (
            isinstance(pid, int)
            and isinstance(identity, str)
            and self._matches_identity(pid, identity)
        )
        daemon_ok = not self.settings.opencli_enabled or self._tcp_check(
            self.settings.daemon_host,
            self.settings.daemon_port,
            0.5,
        )
        cdp_ok = self._tcp_check(self.settings.cdp_host, self.settings.cdp_port, 0.5)
        try:
            extension = _read_json_file(self.settings.runtime_root / "extension-health.json")
        except (OSError, ValueError, json.JSONDecodeError):
            extension = None
        extension_checked = _parse_checked_at(extension.get("checked_at")) if extension else None
        extension_fresh = bool(
            extension_checked
            and 0 <= (self._now() - extension_checked).total_seconds() <= HEALTH_STALE_SECONDS
        )
        extension_ok = not self.settings.opencli_enabled or bool(
            extension
            and extension.get("connected") is True
            and extension.get("version") == self.settings.extension_version
            and extension_fresh
        )
        try:
            auth_document = _read_json_file(self.settings.runtime_root / "auth-state.json")
        except (OSError, ValueError, json.JSONDecodeError):
            auth_document = None
        auth = auth_document.get("sources", {}) if auth_document else {}
        if not isinstance(auth, Mapping):
            auth = {}
        checks = {
            "browser_process": {
                "ok": browser_ok,
                "pid": pid,
                "profile": state.get("profile") if state else None,
            },
            "daemon": {
                "ok": daemon_ok,
                "enabled": self.settings.opencli_enabled,
                "endpoint": f"{self.settings.daemon_host}:{self.settings.daemon_port}",
                "loopback_only": True,
            },
            "extension": {
                "ok": extension_ok,
                "enabled": self.settings.opencli_enabled,
                "connected": bool(extension and extension.get("connected") is True),
                "version": extension.get("version") if extension else None,
                "fresh": extension_fresh,
            },
            "cdp": {
                "ok": cdp_ok,
                "endpoint": f"{self.settings.cdp_host}:{self.settings.cdp_port}",
                "loopback_only": True,
                "purpose": "health/debug only",
            },
        }
        return {
            "ok": True,
            "action": "status",
            "healthy": all(check["ok"] for check in checks.values()),
            "checks": checks,
            "auth": redact(dict(auth)),
        }


def run_doctor(settings: ServiceSettings) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": redact_text(detail)})

    add(
        "loopback-bindings",
        settings.cdp_host in {"127.0.0.1", "localhost", "::1"}
        and settings.daemon_host in {"127.0.0.1", "localhost", "::1"},
        "CDP and daemon endpoints must remain loopback-only",
    )
    try:
        adapter = load_adapter("fixture", settings.adapter_root)
        add("fixture-adapter", True, f"{adapter.name} {adapter.version}")
    except AdapterConfigError as exc:
        add("fixture-adapter", False, str(exc))
    if settings.opencli_enabled:
        try:
            if not settings.extension_version:
                raise PathValidationError("POKECRACK_BRIDGE_VERSION is not pinned")
            extension = validate_extension_path(
                settings.extension_dir,
                expected_version=settings.extension_version,
            )
            add("browser-bridge-extension", True, str(extension))
        except (PathValidationError, OSError) as exc:
            add("browser-bridge-extension", False, str(exc))
    else:
        add("browser-bridge-extension", True, "disabled by OPENCLI_ENABLED=false")
    add(
        "playwright-python",
        importlib.util.find_spec("playwright") is not None,
        "playwright package import",
    )
    for command in ("Xvfb", "x11vnc", "websockify"):
        executable = shutil.which(command)
        add(command, executable is not None, executable or "not installed")
    profile_root = settings.profile_root
    if profile_root.exists() and not profile_root.is_symlink():
        mode = stat.S_IMODE(profile_root.stat().st_mode)
        add("profile-root", mode == 0o700, f"mode {mode:04o}")
    else:
        add("profile-root", False, "not created yet or is a symlink")
    return {
        "ok": all(check["ok"] for check in checks),
        "action": "doctor",
        "checks": checks,
    }
