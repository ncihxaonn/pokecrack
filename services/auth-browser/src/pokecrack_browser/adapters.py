"""Strict allowlisted OpenCLI adapter descriptor loading and argv rendering."""

from __future__ import annotations

import ipaddress
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from .paths import ALLOWED_PROFILES

DEFAULT_ADAPTER_ROOT = Path(__file__).resolve().parents[2] / "adapters"
MAX_DESCRIPTOR_BYTES = 256 * 1024
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_PLACEHOLDER_PATTERN = re.compile(r"\{[^{}]+\}")
_ALLOWED_PLACEHOLDERS = frozenset({"{python}", "{query}", "{max_results}", "{fixture_output}"})
_SHELL_WRAPPERS = frozenset(
    {"sh", "bash", "dash", "zsh", "fish", "cmd", "cmd.exe", "powershell", "pwsh"}
)


class AdapterConfigError(ValueError):
    """An adapter descriptor violates the no-shell, bounded execution contract."""


def _argv(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise AdapterConfigError(f"{field} must be a non-empty argv array")
    result: list[str] = []
    for index, token in enumerate(value):
        if not isinstance(token, str) or not token:
            raise AdapterConfigError(f"{field}[{index}] must be a non-empty string")
        if any(character in token for character in ("\0", "\n", "\r")):
            raise AdapterConfigError(f"{field}[{index}] contains a control character")
        placeholders = _PLACEHOLDER_PATTERN.findall(token)
        if placeholders and (len(placeholders) != 1 or token not in _ALLOWED_PLACEHOLDERS):
            raise AdapterConfigError(
                f"{field}[{index}] placeholders must occupy a complete argv token"
            )
        result.append(token)
    executable = Path(result[0]).name.lower()
    if executable in _SHELL_WRAPPERS:
        raise AdapterConfigError(f"{field} cannot invoke a shell wrapper")
    return tuple(result)


def _allowed_source_hosts(value: Any) -> frozenset[str]:
    if not isinstance(value, list) or not value or len(value) > 32:
        raise AdapterConfigError("allowed_source_hosts must contain between 1 and 32 hosts")
    hosts: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item or item != item.strip():
            raise AdapterConfigError("allowed_source_hosts entries must be hostnames")
        try:
            host = item.casefold().rstrip(".").encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise AdapterConfigError("allowed_source_hosts contains an invalid hostname") from exc
        if not host or len(host) > 253 or "." not in host or "*" in host:
            raise AdapterConfigError("allowed_source_hosts entries must be exact domain names")
        labels = host.split(".")
        if any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or re.fullmatch(r"[a-z0-9-]+", label) is None
            for label in labels
        ):
            raise AdapterConfigError("allowed_source_hosts contains an invalid hostname")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise AdapterConfigError("allowed_source_hosts cannot contain IP addresses")
        if host == "localhost" or host.endswith(".localhost"):
            raise AdapterConfigError("allowed_source_hosts cannot contain localhost")
        hosts.add(host)
    if len(hosts) != len(value):
        raise AdapterConfigError("allowed_source_hosts entries must be unique")
    return frozenset(hosts)


def _positive_number(value: Any, *, field: str, integer: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AdapterConfigError(f"{field} must be numeric")
    if value <= 0:
        raise AdapterConfigError(f"{field} must be positive")
    if integer:
        if not isinstance(value, int):
            raise AdapterConfigError(f"{field} must be an integer")
        return value
    return float(value)


@dataclass(frozen=True, slots=True)
class AdapterSpec:
    name: str
    version: str
    argv: tuple[str, ...]
    profile: str
    allowed_source_hosts: frozenset[str]
    query_required: bool
    query_max_length: int
    query_default: str
    json_schema: dict[str, Any]
    timeout_seconds: float
    max_results: int
    min_interval_seconds: float
    auth_health_argv: tuple[str, ...]
    version_argv: tuple[str, ...]
    source: Path
    requires_browser: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, source: Path) -> Self:
        name = value.get("name")
        version = value.get("version")
        profile = value.get("profile")
        query = value.get("query")
        schema = value.get("json_schema")
        if not isinstance(name, str) or not _NAME_PATTERN.fullmatch(name):
            raise AdapterConfigError("adapter name is invalid")
        if not isinstance(version, str) or not version.strip():
            raise AdapterConfigError("adapter version must be a non-empty pinned value")
        if profile not in ALLOWED_PROFILES:
            raise AdapterConfigError("adapter profile is not allowlisted")
        if not isinstance(query, Mapping):
            raise AdapterConfigError("adapter query must be an object")
        required = query.get("required", False)
        max_length = query.get("max_length", 2048)
        default = query.get("default", "")
        if not isinstance(required, bool):
            raise AdapterConfigError("query.required must be boolean")
        if (
            not isinstance(max_length, int)
            or isinstance(max_length, bool)
            or not 1 <= max_length <= 16_384
        ):
            raise AdapterConfigError("query.max_length must be between 1 and 16384")
        if not isinstance(default, str) or len(default) > max_length:
            raise AdapterConfigError("query.default must fit query.max_length")
        if not isinstance(schema, dict):
            raise AdapterConfigError("json_schema must be an object")
        min_interval = value.get("min_interval_seconds")
        if (
            isinstance(min_interval, bool)
            or not isinstance(min_interval, (int, float))
            or min_interval < 0
        ):
            raise AdapterConfigError("min_interval_seconds must be non-negative")
        requires_browser = value.get("requires_browser", True)
        if not isinstance(requires_browser, bool):
            raise AdapterConfigError("requires_browser must be boolean")
        return cls(
            name=name,
            version=version,
            argv=_argv(value.get("argv"), field="argv"),
            profile=str(profile),
            allowed_source_hosts=_allowed_source_hosts(value.get("allowed_source_hosts")),
            query_required=required,
            query_max_length=max_length,
            query_default=default,
            json_schema=dict(schema),
            timeout_seconds=float(
                _positive_number(value.get("timeout_seconds"), field="timeout_seconds")
            ),
            max_results=int(
                _positive_number(value.get("max_results"), field="max_results", integer=True)
            ),
            min_interval_seconds=float(min_interval),
            auth_health_argv=_argv(value.get("auth_health_argv"), field="auth_health_argv"),
            version_argv=_argv(value.get("version_argv"), field="version_argv"),
            source=source,
            requires_browser=requires_browser,
        )

    def _render(self, template: Sequence[str], *, query: str, max_results: int) -> list[str]:
        if not query:
            query = self.query_default
        if self.query_required and not query:
            raise AdapterConfigError("query is required")
        if any(character in query for character in ("\0", "\n", "\r")):
            raise AdapterConfigError("query contains a control character")
        if len(query) > self.query_max_length:
            raise AdapterConfigError(
                f"query exceeds the {self.query_max_length} character adapter limit"
            )
        if not 1 <= max_results <= self.max_results:
            raise AdapterConfigError(f"max_results must be between 1 and {self.max_results}")
        fixture_output = self.source.parent / "fixture-output.json"
        replacements = {
            "{python}": sys.executable,
            "{query}": query,
            "{max_results}": str(max_results),
            "{fixture_output}": str(fixture_output),
        }
        return [replacements.get(token, token) for token in template]

    def render_argv(self, *, query: str, max_results: int) -> list[str]:
        return self._render(self.argv, query=query, max_results=max_results)

    def render_auth_health_argv(self) -> list[str]:
        return self._render(
            self.auth_health_argv,
            query=self.query_default,
            max_results=1,
        )

    def render_version_argv(self) -> list[str]:
        return self._render(self.version_argv, query=self.query_default, max_results=1)


def load_adapter(name: str, root: str | Path = DEFAULT_ADAPTER_ROOT) -> AdapterSpec:
    if not _NAME_PATTERN.fullmatch(name):
        raise AdapterConfigError("adapter name is invalid")
    adapter_root = Path(root)
    if not adapter_root.is_absolute():
        raise AdapterConfigError("adapter root must be absolute")
    if adapter_root.is_symlink() or not adapter_root.is_dir():
        raise AdapterConfigError("adapter root must be a real directory")
    descriptor = adapter_root / f"{name}.json"
    if descriptor.is_symlink() or not descriptor.is_file():
        raise AdapterConfigError(f"adapter is not allowlisted: {name}")
    try:
        raw = descriptor.read_bytes()
    except OSError as exc:
        raise AdapterConfigError(f"cannot read adapter: {name}") from exc
    if len(raw) > MAX_DESCRIPTOR_BYTES:
        raise AdapterConfigError("adapter descriptor exceeds size limit")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterConfigError("adapter descriptor is invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise AdapterConfigError("adapter descriptor must contain an object")
    adapter = AdapterSpec.from_mapping(value, source=descriptor)
    if adapter.name != name:
        raise AdapterConfigError("adapter descriptor name does not match its filename")
    return adapter
