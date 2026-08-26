"""Bounded, serialized, schema-validating OpenCLI adapter execution."""

from __future__ import annotations

import fcntl
import hashlib
import ipaddress
import json
import os
import selectors
import signal
import subprocess
import tempfile
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .adapters import AdapterConfigError, AdapterSpec, load_adapter
from .config import ServiceSettings
from .errors import ServiceError
from .redaction import redact, redact_text, strip_ansi
from .runtime import ensure_private_runtime_root, process_matches_identity, read_runtime_state

MAX_JSON_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 256 * 1024
MAX_VERSION_BYTES = 4096


@dataclass(frozen=True, slots=True)
class ProcessCapture:
    returncode: int
    stdout: str
    stderr: str
    stdout_bytes: int
    stderr_bytes: int
    duration_seconds: float


def _kill_process(process: subprocess.Popen[bytes]) -> None:
    # The session leader may exit while a descendant still holds our capture pipes.
    # Its process group remains addressable until the last descendant exits.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        if process.poll() is None:
            with suppress(ProcessLookupError, PermissionError):
                process.kill()
    with suppress(subprocess.TimeoutExpired):
        process.wait(timeout=1)


def run_bounded_process(
    argv: Sequence[str],
    *,
    timeout_seconds: float,
    max_stdout_bytes: int = MAX_JSON_BYTES,
    max_stderr_bytes: int = MAX_STDERR_BYTES,
) -> ProcessCapture:
    """Execute argv directly (shell=False) while enforcing byte and wall-clock caps."""
    if not argv or any(
        not isinstance(token, str)
        or not token
        or any(character in token for character in ("\0", "\n", "\r"))
        for token in argv
    ):
        raise ServiceError("adapter_failed", "adapter argv is invalid")
    if timeout_seconds <= 0 or max_stdout_bytes <= 0 or max_stderr_bytes <= 0:
        raise ServiceError("adapter_failed", "adapter execution bounds are invalid")
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise ServiceError("source_unavailable", "adapter executable is unavailable") from exc
    except OSError as exc:
        raise ServiceError("adapter_failed", "adapter process could not start") from exc

    assert process.stdout is not None
    assert process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, ("stdout", max_stdout_bytes))
    selector.register(process.stderr, selectors.EVENT_READ, ("stderr", max_stderr_bytes))
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = started + timeout_seconds
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _kill_process(process)
                raise ServiceError(
                    "timeout",
                    "adapter command exceeded its finite timeout",
                    {"timeout_seconds": timeout_seconds},
                )
            events = selector.select(min(remaining, 0.1))
            for key, _mask in events:
                stream_name, limit = key.data
                try:
                    chunk = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer = buffers[stream_name]
                if len(buffer) + len(chunk) > limit:
                    _kill_process(process)
                    raise ServiceError(
                        "adapter_failed",
                        "adapter output exceeded its byte limit",
                        {"reason": "output_limit_exceeded", "stream": stream_name, "limit": limit},
                    )
                buffer.extend(chunk)
        remaining = max(0.01, deadline - time.monotonic())
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            _kill_process(process)
            raise ServiceError(
                "timeout",
                "adapter command exceeded its finite timeout",
                {"timeout_seconds": timeout_seconds},
            ) from exc
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()

    duration = time.monotonic() - started
    stdout = redact_text(buffers["stdout"].decode("utf-8", errors="replace"))
    stderr = redact_text(buffers["stderr"].decode("utf-8", errors="replace"))
    return ProcessCapture(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        stdout_bytes=len(buffers["stdout"]),
        stderr_bytes=len(buffers["stderr"]),
        duration_seconds=duration,
    )


class _SchemaError(ValueError):
    pass


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    raise _SchemaError(f"unsupported schema type: {expected}")


def _validate_schema(value: Any, schema: Mapping[str, Any], *, path: str = "$") -> None:
    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else expected
        if not isinstance(expected_types, list) or not all(
            isinstance(item, str) for item in expected_types
        ):
            raise _SchemaError(f"{path}: schema type is invalid")
        if not any(_matches_type(value, item) for item in expected_types):
            raise _SchemaError(f"{path}: value has the wrong type")
    if "enum" in schema and value not in schema["enum"]:
        raise _SchemaError(f"{path}: value is not in enum")
    if isinstance(value, Mapping):
        required = schema.get("required", [])
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise _SchemaError(f"{path}: required must be a string array")
        missing = [key for key in required if key not in value]
        if missing:
            raise _SchemaError(f"{path}: missing required field {missing[0]!r}")
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            raise _SchemaError(f"{path}: properties must be an object")
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise _SchemaError(f"{path}: unexpected field {sorted(extra)[0]!r}")
        for key, nested in value.items():
            nested_schema = properties.get(key)
            if isinstance(nested_schema, Mapping):
                _validate_schema(nested, nested_schema, path=f"{path}.{key}")
    if isinstance(value, list):
        max_items = schema.get("maxItems")
        if isinstance(max_items, int) and len(value) > max_items:
            raise _SchemaError(f"{path}: array exceeds maxItems")
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            raise _SchemaError(f"{path}: array is below minItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate_schema(item, item_schema, path=f"{path}[{index}]")
    if isinstance(value, str):
        max_length = schema.get("maxLength")
        if isinstance(max_length, int) and len(value) > max_length:
            raise _SchemaError(f"{path}: string exceeds maxLength")
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            raise _SchemaError(f"{path}: string is below minLength")


def parse_and_validate_output(
    raw: bytes | str,
    schema: Mapping[str, Any],
    *,
    max_bytes: int = MAX_JSON_BYTES,
) -> Any:
    encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(encoded) > max_bytes:
        raise ServiceError(
            "invalid_json",
            "adapter JSON exceeds the byte limit",
            {"reason": "output_too_large", "limit": max_bytes},
        )
    try:
        text = strip_ansi(encoded.decode("utf-8"))
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ServiceError("invalid_json", "adapter output is not valid UTF-8 JSON") from exc
    try:
        _validate_schema(value, schema)
    except _SchemaError as exc:
        raise ServiceError(
            "invalid_json",
            "adapter JSON does not match its pinned schema",
            {"reason": str(exc)},
        ) from exc
    return value


_EXIT_CATEGORY = {
    10: "auth_required",
    11: "extension_disconnected",
    12: "daemon_unavailable",
    13: "rate_limited",
    14: "source_unavailable",
}


def map_adapter_failure(returncode: int, stderr: str) -> str:
    if returncode in _EXIT_CATEGORY:
        return _EXIT_CATEGORY[returncode]
    diagnostic = strip_ansi(stderr).lower()
    if any(
        pattern in diagnostic
        for pattern in ("auth required", "login required", "unauthorized", "http 401")
    ):
        return "auth_required"
    if "extension" in diagnostic and any(
        pattern in diagnostic for pattern in ("disconnect", "not connected", "unavailable")
    ):
        return "extension_disconnected"
    if any(
        pattern in diagnostic
        for pattern in (
            "127.0.0.1:19825",
            "daemon unavailable",
            "econnrefused",
            "connection refused",
        )
    ):
        return "daemon_unavailable"
    if any(pattern in diagnostic for pattern in ("http 429", "rate limit", "too many requests")):
        return "rate_limited"
    if any(
        pattern in diagnostic
        for pattern in ("source unavailable", "http 404", "(404)", "not found")
    ):
        return "source_unavailable"
    return "adapter_failed"


class SerialScheduler:
    """One finite non-blocking execution slot plus per-adapter minimum interval."""

    def __init__(self, runtime_root: Path) -> None:
        self.root = ensure_private_runtime_root(runtime_root)

    @contextmanager
    def slot(self, adapter: str, min_interval_seconds: float) -> Iterator[None]:
        lock_path = self.root / "opencli.lock"
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ServiceError(
                    "rate_limited",
                    "another OpenCLI adapter is already running",
                    {"reason": "scheduler_busy"},
                ) from exc
            timestamps = self._read_timestamps()
            previous = timestamps.get(adapter)
            now = time.time()
            if isinstance(previous, (int, float)):
                retry_after = min_interval_seconds - (now - float(previous))
                if retry_after > 0:
                    raise ServiceError(
                        "rate_limited",
                        "adapter minimum interval has not elapsed",
                        {"retry_after_seconds": round(retry_after, 3)},
                    )
            try:
                yield
            finally:
                timestamps[adapter] = time.time()
                self._write_timestamps(timestamps)
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _read_timestamps(self) -> dict[str, float]:
        path = self.root / "opencli-schedule.json"
        if path.is_symlink():
            raise ServiceError("adapter_failed", "scheduler state must not be a symlink")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise ServiceError("adapter_failed", "scheduler state is invalid") from exc
        if not isinstance(value, dict):
            raise ServiceError("adapter_failed", "scheduler state must be an object")
        return {
            str(key): float(timestamp)
            for key, timestamp in value.items()
            if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool)
        }

    def _write_timestamps(self, value: Mapping[str, float]) -> None:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".schedule-", dir=self.root)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(dict(value), stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
            os.replace(temporary_name, self.root / "opencli-schedule.json")
            os.chmod(self.root / "opencli-schedule.json", 0o600)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)


def _failure(capture: ProcessCapture) -> ServiceError:
    category = map_adapter_failure(capture.returncode, capture.stderr)
    return ServiceError(
        category,
        "OpenCLI adapter command failed",
        {"returncode": capture.returncode, "stderr": redact_text(capture.stderr)},
    )


def _public_source_url(value: object, allowed_hosts: frozenset[str]) -> str:
    if not isinstance(value, str):
        raise ServiceError(
            "invalid_json",
            "candidate source_url must use an allowlisted HTTPS host",
        )
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ServiceError("invalid_json", "candidate source_url is invalid") from exc
    if parsed.scheme.casefold() != "https" or not parsed.hostname or port not in (None, 443):
        raise ServiceError(
            "invalid_json",
            "candidate source_url must use an allowlisted HTTPS host",
        )
    if parsed.username is not None or parsed.password is not None:
        raise ServiceError("invalid_json", "candidate source_url must not contain userinfo")
    try:
        hostname = parsed.hostname.casefold().rstrip(".").encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ServiceError("invalid_json", "candidate source_url hostname is invalid") from exc
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ServiceError("invalid_json", "candidate source_url cannot use an IP address")
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname not in allowed_hosts:
        raise ServiceError("invalid_json", "candidate source_url host is not allowlisted")
    return urlunsplit(("https", hostname, parsed.path or "/", "", ""))


def _author_hash(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ServiceError("invalid_json", "candidate author must be text")
    normalized = " ".join(value.casefold().strip().split())
    if not normalized:
        return None
    return hashlib.sha256(f"pokecrack-author-v1:{normalized}".encode()).hexdigest()


def _candidate(item: Mapping[str, Any], adapter: AdapterSpec) -> dict[str, Any]:
    source_url = _public_source_url(item.get("source_url"), adapter.allowed_source_hosts)
    safe_item = redact(dict(item))
    candidate: dict[str, Any] = {
        "source_url": source_url,
        "collector": "opencli_authenticated",
        "collector_version": f"opencli-{adapter.name}-{adapter.version}",
    }
    for key in ("title", "published_at"):
        if key in safe_item and safe_item[key] is not None:
            candidate[key] = safe_item[key]

    text = safe_item.get("content") or safe_item.get("excerpt")
    if text is not None:
        if not isinstance(text, str) or len(text) > 20_000:
            raise ServiceError("invalid_json", "candidate text exceeds the 20,000 character limit")
        candidate["text"] = text

    author_hash = _author_hash(safe_item.get("author"))
    if author_hash is not None:
        candidate["author_hash"] = author_hash

    image_urls = safe_item.get("image_urls", [])
    if (
        not isinstance(image_urls, Sequence)
        or isinstance(image_urls, (str, bytes))
        or len(image_urls) > 12
    ):
        raise ServiceError("invalid_json", "candidate image_urls must contain at most 12 URLs")
    candidate["media_urls"] = [
        _public_source_url(url, adapter.allowed_source_hosts) for url in image_urls
    ]

    metadata = safe_item.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ServiceError("invalid_json", "candidate metadata must be an object")
    candidate["metadata"] = {
        **dict(metadata),
        "opencli_adapter": adapter.name,
        "opencli_adapter_version": adapter.version,
    }
    return candidate


class OpenCliRunner:
    def __init__(self, settings: ServiceSettings) -> None:
        self.settings = settings

    def _assert_browser(self, adapter: AdapterSpec) -> None:
        if not adapter.requires_browser:
            return
        if not self.settings.opencli_enabled:
            raise ServiceError("source_unavailable", "OpenCLI is disabled")
        state = read_runtime_state(self.settings.runtime_root)
        if (
            state is None
            or not isinstance(state.get("pid"), int)
            or not isinstance(state.get("process_identity"), str)
            or not process_matches_identity(state["pid"], state["process_identity"])
        ):
            raise ServiceError("daemon_unavailable", "persistent browser process is unavailable")
        if state.get("profile") != adapter.profile:
            raise ServiceError(
                "auth_required",
                f"adapter requires active profile {adapter.profile}",
            )

    def run(
        self,
        adapter_name: str,
        *,
        query: str = "",
        max_results: int | None = None,
    ) -> dict[str, Any]:
        try:
            adapter = load_adapter(adapter_name, self.settings.adapter_root)
            requested_max = adapter.max_results if max_results is None else max_results
            argv = adapter.render_argv(query=query, max_results=requested_max)
        except AdapterConfigError as exc:
            raise ServiceError("source_unavailable", str(exc)) from exc
        self._assert_browser(adapter)
        scheduler = SerialScheduler(self.settings.runtime_root)
        with scheduler.slot(adapter.name, adapter.min_interval_seconds):
            version_capture = run_bounded_process(
                adapter.render_version_argv(),
                timeout_seconds=min(adapter.timeout_seconds, 5.0),
                max_stdout_bytes=MAX_VERSION_BYTES,
                max_stderr_bytes=MAX_VERSION_BYTES,
            )
            if version_capture.returncode != 0:
                raise _failure(version_capture)
            cli_version = version_capture.stdout.strip().splitlines()
            if not cli_version:
                raise ServiceError("adapter_failed", "adapter CLI version output is empty")
            capture = run_bounded_process(
                argv,
                timeout_seconds=adapter.timeout_seconds,
                max_stdout_bytes=MAX_JSON_BYTES,
                max_stderr_bytes=MAX_STDERR_BYTES,
            )
            if capture.returncode != 0:
                raise _failure(capture)
            value = parse_and_validate_output(
                capture.stdout,
                adapter.json_schema,
                max_bytes=MAX_JSON_BYTES,
            )
            if not isinstance(value, Mapping) or not isinstance(value.get("items"), list):
                raise ServiceError("invalid_json", "adapter output must contain an items array")
            items = [_candidate(item, adapter) for item in value["items"]]
        return {
            "ok": True,
            "action": "run-opencli",
            "contract": "SourceItemCandidate",
            "adapter": adapter.name,
            "profile": adapter.profile,
            "items": items,
            "versions": {"adapter": adapter.version, "cli": cli_version[0]},
            "execution": {
                "duration_ms": round(capture.duration_seconds * 1000, 3),
                "stdout_bytes": capture.stdout_bytes,
                "stderr_bytes": capture.stderr_bytes,
                "stderr": capture.stderr or None,
            },
        }
