"""Strict, auditable, deny-by-default source collection policy."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol, Self
from urllib.parse import urlsplit, urlunsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pokecrack_worker.models import CollectorType


class CollectorRoute(StrEnum):
    """Operation routes are separate from the public collector vocabulary."""

    YOUTUBE = "youtube"
    BLUESKY = "bluesky"
    BLUESKY_JETSTREAM = "bluesky_jetstream"
    NOSTR_RELAY = "nostr_relay"
    MASTODON_REST = "mastodon_rest"
    STATIC = "static"
    DYNAMIC = "dynamic"
    MANUAL = "manual"
    OPENCLI = "opencli"
    CATALOG = "catalog"


class RobotsPolicy(StrEnum):
    RESPECT = "respect"
    NOT_APPLICABLE = "not_applicable"


AccessMode = Literal["public", "official_api", "authenticated", "manual", "disabled"]


_COLLECTOR_ROUTE_DEFAULTS: dict[CollectorType, frozenset[CollectorRoute]] = {
    CollectorType.OFFICIAL_API: frozenset({CollectorRoute.YOUTUBE, CollectorRoute.CATALOG}),
    CollectorType.BLUESKY_JETSTREAM: frozenset(
        {CollectorRoute.BLUESKY, CollectorRoute.BLUESKY_JETSTREAM}
    ),
    CollectorType.NOSTR_RELAY: frozenset({CollectorRoute.NOSTR_RELAY}),
    CollectorType.MASTODON_REST: frozenset({CollectorRoute.MASTODON_REST}),
    CollectorType.SCRAPLING_HTTP: frozenset({CollectorRoute.STATIC}),
    CollectorType.SCRAPLING_DYNAMIC: frozenset({CollectorRoute.DYNAMIC}),
    CollectorType.OPENCLI_AUTHENTICATED: frozenset({CollectorRoute.OPENCLI}),
    CollectorType.MANUAL_IMPORT: frozenset({CollectorRoute.MANUAL}),
    CollectorType.DISABLED: frozenset(),
}
_ACCESS_MODE_DEFAULTS: dict[CollectorType, AccessMode] = {
    CollectorType.OFFICIAL_API: "official_api",
    CollectorType.BLUESKY_JETSTREAM: "official_api",
    CollectorType.NOSTR_RELAY: "public",
    CollectorType.MASTODON_REST: "official_api",
    CollectorType.SCRAPLING_HTTP: "public",
    CollectorType.SCRAPLING_DYNAMIC: "public",
    CollectorType.OPENCLI_AUTHENTICATED: "authenticated",
    CollectorType.MANUAL_IMPORT: "manual",
    CollectorType.DISABLED: "disabled",
}
_LEGACY_ROUTE_COLLECTORS = {
    CollectorRoute.YOUTUBE.value: CollectorType.OFFICIAL_API,
    CollectorRoute.CATALOG.value: CollectorType.OFFICIAL_API,
    CollectorRoute.BLUESKY.value: CollectorType.BLUESKY_JETSTREAM,
    CollectorRoute.BLUESKY_JETSTREAM.value: CollectorType.BLUESKY_JETSTREAM,
    CollectorRoute.NOSTR_RELAY.value: CollectorType.NOSTR_RELAY,
    CollectorRoute.MASTODON_REST.value: CollectorType.MASTODON_REST,
    CollectorRoute.STATIC.value: CollectorType.SCRAPLING_HTTP,
    CollectorRoute.DYNAMIC.value: CollectorType.SCRAPLING_DYNAMIC,
    CollectorRoute.OPENCLI.value: CollectorType.OPENCLI_AUTHENTICATED,
    CollectorRoute.MANUAL.value: CollectorType.MANUAL_IMPORT,
}


def _normalize_hostname(value: str) -> str:
    candidate = value.strip().lower().rstrip(".")
    if "://" in candidate:
        try:
            candidate = urlsplit(candidate).hostname or ""
        except ValueError as error:
            raise ValueError("domain must be a valid hostname") from error
    if not candidate or "/" in candidate or " " in candidate:
        raise ValueError("domain must be a valid hostname")
    try:
        return candidate.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError("domain must be a valid hostname") from error


def _validate_credential_free_fetch_url(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a credential-free HTTPS URL")
    candidate = value.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
        hostname = parsed.hostname
    except ValueError as error:
        raise ValueError(f"{field_name} must be a credential-free HTTPS URL") from error
    del port
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or hostname is None
        or parsed.fragment
    ):
        raise ValueError(f"{field_name} must be a credential-free HTTPS URL")
    return candidate


def _mapping_source_key(value: object) -> tuple[str, str | None]:
    if not isinstance(value, str):
        raise ValueError("source policy mapping keys must be hostnames")
    key = value.strip()
    domain_key, separator, label = key.partition("#")
    if separator and (not label or "#" in label or label != label.strip()):
        raise ValueError("source policy mapping labels must be non-empty and unique")
    if not domain_key or any(character in domain_key for character in "/?:@"):
        raise ValueError("source policy mapping keys must start with a hostname")
    return _normalize_hostname(domain_key), label if separator else None


def _configured_fetch_url(policy: SourcePolicy) -> str | None:
    value = policy.config.get("fetch_url")
    return value if isinstance(value, str) else None


def _is_exact_policy(policy: SourcePolicy) -> bool:
    return _configured_fetch_url(policy) is not None or bool(policy.exact_urls)


def _validate_policy_groups(
    policies: tuple[SourcePolicy, ...] | list[SourcePolicy],
) -> dict[str, tuple[SourcePolicy, ...]]:
    grouped: dict[str, list[SourcePolicy]] = {}
    for policy in policies:
        grouped.setdefault(policy.domain, []).append(policy)

    seen_fetch_urls: set[str] = set()
    normalized_groups: dict[str, tuple[SourcePolicy, ...]] = {}
    for domain, domain_policies in grouped.items():
        if len(domain_policies) > 1:
            fetch_urls = [_configured_fetch_url(policy) for policy in domain_policies]
            if any(fetch_url is None for fetch_url in fetch_urls):
                raise ValueError(
                    "duplicate source policy domains require config.fetch_url on every policy"
                )
            if len(set(fetch_urls)) != len(fetch_urls):
                raise ValueError("config.fetch_url values must be unique")
        for policy in domain_policies:
            fetch_url = _configured_fetch_url(policy)
            if fetch_url is not None:
                if fetch_url in seen_fetch_urls:
                    raise ValueError("config.fetch_url values must be unique")
                seen_fetch_urls.add(fetch_url)
        normalized_groups[domain] = tuple(domain_policies)
    return normalized_groups


class SourcePolicy(BaseModel):
    """Complete policy contract for one exact source domain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: str
    enabled: bool = False
    collector: CollectorType = CollectorType.DISABLED
    access_mode: AccessMode = "disabled"
    robots_policy: RobotsPolicy = RobotsPolicy.RESPECT
    min_delay_seconds: float = Field(default=0, ge=0, le=86_400)
    max_pages_per_run: int = Field(default=1, ge=1, le=10_000)
    max_concurrency: int = Field(default=1, ge=1, le=32)
    dynamic_allowed: bool = False
    login_required: bool = False
    browser_profile: str | None = Field(default=None, max_length=128)
    statistics_eligible_default: bool = False
    retention_days: int = Field(default=30, ge=0, le=3650)
    version: str = Field(default="1", min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="explicit source policy", min_length=1, max_length=1000)

    # Useful routing/adapter metadata supplements rather than replaces the contract.
    name: str | None = None
    routes: frozenset[CollectorRoute] = Field(default_factory=frozenset)
    adapter: str | None = None
    exact_urls: frozenset[str] = Field(default_factory=frozenset)
    include_subdomains: bool = False
    metadata_only: bool = True
    requests_per_minute: float = Field(default=6, gt=0, le=600)
    cache_ttl_seconds: int = Field(default=3600, ge=0)
    retain_raw_html: Literal[False] = False
    credentials_required: bool = False
    terms_url: str | None = None
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def fill_legacy_and_derived_fields(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        if "minimum_delay_seconds" in data and "min_delay_seconds" not in data:
            data["min_delay_seconds"] = data.pop("minimum_delay_seconds")
        routes = data.get("routes") or ()
        if "collector" not in data:
            route_values = [
                route.value if isinstance(route, CollectorRoute) else str(route) for route in routes
            ]
            data["collector"] = next(
                (
                    _LEGACY_ROUTE_COLLECTORS[route]
                    for route in route_values
                    if route in _LEGACY_ROUTE_COLLECTORS
                ),
                CollectorType.DISABLED,
            )
        collector = CollectorType(data["collector"])
        data.setdefault("access_mode", _ACCESS_MODE_DEFAULTS[collector])
        if not routes:
            data["routes"] = _COLLECTOR_ROUTE_DEFAULTS[collector]
        return data

    @field_validator("config")
    @classmethod
    def reject_bypass_controls(cls, value: dict[str, Any]) -> dict[str, Any]:
        prohibited_fragments = ("proxy", "stealth", "captcha", "bypass")

        def check(node: object, path: str = "config") -> None:
            if isinstance(node, Mapping):
                for raw_key, item in node.items():
                    key = str(raw_key).casefold().replace("-", "_")
                    if any(fragment in key for fragment in prohibited_fragments):
                        raise ValueError(f"prohibited collection control at {path}.{raw_key}")
                    check(item, f"{path}.{raw_key}")
            elif isinstance(node, list | tuple):
                for index, item in enumerate(node):
                    check(item, f"{path}[{index}]")

        check(value)
        if "fetch_url" in value:
            normalized = dict(value)
            normalized["fetch_url"] = _validate_credential_free_fetch_url(
                value["fetch_url"],
                field_name="config.fetch_url",
            )
            return normalized
        return value

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        return _normalize_hostname(value)

    @field_validator("exact_urls")
    @classmethod
    def validate_exact_urls(cls, values: frozenset[str]) -> frozenset[str]:
        normalized: set[str] = set()
        for value in values:
            candidate = value.strip()
            parsed = urlsplit(candidate)
            if (
                parsed.scheme != "https"
                or parsed.username is not None
                or parsed.password is not None
                or parsed.hostname is None
                or parsed.fragment
            ):
                raise ValueError("exact_urls must contain credential-free HTTPS URLs")
            normalized.add(candidate)
        return frozenset(normalized)

    @model_validator(mode="after")
    def validate_collector_safety(self) -> Self:
        fetch_url = _configured_fetch_url(self)
        if fetch_url is not None:
            try:
                fetch_domain = _normalize_hostname(urlsplit(fetch_url).hostname or "")
            except ValueError as error:
                raise ValueError("config.fetch_url must contain a valid hostname") from error
            if fetch_domain != self.domain:
                raise ValueError("config.fetch_url hostname must match policy domain")
        if self.enabled and self.collector is CollectorType.DISABLED:
            raise ValueError("enabled policy cannot use the disabled collector")
        if self.collector is CollectorType.SCRAPLING_DYNAMIC and not self.dynamic_allowed:
            raise ValueError("scrapling_dynamic requires dynamic_allowed=true")
        if self.dynamic_allowed and self.collector is not CollectorType.SCRAPLING_DYNAMIC:
            raise ValueError("dynamic_allowed is only valid for scrapling_dynamic")
        if self.login_required and self.collector is not CollectorType.OPENCLI_AUTHENTICATED:
            raise ValueError("login_required is only valid for opencli_authenticated")
        if self.browser_profile and not self.login_required:
            raise ValueError("browser_profile requires login_required=true")
        return self

    @property
    def minimum_delay_seconds(self) -> float:
        return self.min_delay_seconds


class SourcePolicyDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    default: Literal["disabled"] = "disabled"
    sources: tuple[SourcePolicy, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def normalize_keyed_sources(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        legacy_default = data.pop("default_enabled", None)
        if legacy_default not in (None, False):
            raise ValueError("source policy default must remain disabled")
        data.setdefault("default", "disabled")
        sources = data.get("sources", ())
        if isinstance(sources, Mapping):
            normalized: list[dict[str, Any]] = []
            for raw_key, raw_policy in sources.items():
                domain, _label = _mapping_source_key(raw_key)
                if not isinstance(raw_policy, Mapping):
                    raise ValueError(f"source policy for {domain} must be a mapping")
                policy = dict(raw_policy)
                configured_domain = policy.get("domain", domain)
                try:
                    configured_domain = _normalize_hostname(configured_domain)
                except (AttributeError, TypeError, ValueError) as error:
                    raise ValueError(f"source policy domain key mismatch: {raw_key}") from error
                if configured_domain != domain:
                    raise ValueError(f"source policy domain key mismatch: {domain}")
                policy["domain"] = domain
                normalized.append(policy)
            data["sources"] = normalized
        return data

    @model_validator(mode="after")
    def validate_policy_groups(self) -> Self:
        _validate_policy_groups(self.sources)
        return self


class PolicyAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: Literal["source_policy_decision"] = "source_policy_decision"
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str
    domain: str
    route: str
    outcome: Literal["allowed", "denied"]
    reason: Literal[
        "allowed",
        "unknown_domain",
        "source_disabled",
        "route_not_allowed",
        "source_url_not_allowed",
    ]
    policy_domain: str | None = None
    policy_version: str | None = None
    collector: CollectorType | None = None
    adapter: str | None = None


class PolicyAuditSink(Protocol):
    def emit(self, event: PolicyAuditEvent) -> None: ...


class NullPolicyAuditSink:
    def emit(self, event: PolicyAuditEvent) -> None:
        del event


class InMemoryPolicyAuditSink:
    def __init__(self) -> None:
        self.events: list[PolicyAuditEvent] = []

    def emit(self, event: PolicyAuditEvent) -> None:
        self.events.append(event)


class PolicyDeniedError(PermissionError):
    def __init__(self, event: PolicyAuditEvent) -> None:
        self.event = event
        super().__init__(f"source policy denied {event.route} for {event.domain}: {event.reason}")


class SourcePolicyRegistry:
    """No force/override argument exists: unknown and disabled domains always deny."""

    def __init__(
        self,
        policies: list[SourcePolicy] | tuple[SourcePolicy, ...] = (),
        *,
        audit_sink: PolicyAuditSink | None = None,
        default: Literal["disabled"] = "disabled",
        default_enabled: Literal[False] = False,
    ) -> None:
        if default != "disabled" or default_enabled is not False:
            raise ValueError("source policy default must remain disabled")
        self._policies = _validate_policy_groups(tuple(policies))
        self._audit = audit_sink or NullPolicyAuditSink()
        self.default = "disabled"
        self.default_enabled = False

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
        *,
        audit_sink: PolicyAuditSink | None = None,
    ) -> SourcePolicyRegistry:
        document = SourcePolicyDocument.model_validate(value)
        return cls(document.sources, audit_sink=audit_sink, default=document.default)

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        *,
        audit_sink: PolicyAuditSink | None = None,
    ) -> SourcePolicyRegistry:
        with Path(path).open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
        if not isinstance(value, Mapping):
            raise ValueError("source policy YAML must contain a mapping")
        return cls.from_mapping(value, audit_sink=audit_sink)

    @staticmethod
    def _safe_parts(value: str) -> tuple[str, str, int | None, str]:
        parsed = urlsplit(value if "://" in value else f"https://{value}")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("source URLs containing credentials are not accepted")
        scheme = parsed.scheme.casefold()
        if scheme not in {"https", "wss"}:
            raise ValueError("source URLs must use HTTPS or secure WebSocket transport")
        domain = (parsed.hostname or "").casefold().rstrip(".")
        if not domain:
            raise ValueError("source must contain a hostname")
        domain = domain.encode("idna").decode("ascii")
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError("source URL contains an invalid port") from error
        return scheme, domain, port, parsed.path

    @classmethod
    def _domain(cls, value: str) -> str:
        _, domain, _, _ = cls._safe_parts(value)
        return domain

    @classmethod
    def _audit_source(cls, value: str) -> str:
        scheme, domain, port, path = cls._safe_parts(value)
        host = f"[{domain}]" if ":" in domain else domain
        if port is not None and not (
            (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
        ):
            host = f"{host}:{port}"
        return urlunsplit((scheme, host, path, "", ""))

    def _lookup(self, domain: str, source: str | None = None) -> SourcePolicy | None:
        domain_policies = self._policies.get(domain, ())
        if source is not None:
            normalized_source = source.strip()
            for policy in domain_policies:
                fetch_url = _configured_fetch_url(policy)
                if fetch_url is not None and normalized_source == fetch_url:
                    return policy
                if (
                    fetch_url is None
                    and policy.exact_urls
                    and normalized_source in policy.exact_urls
                ):
                    return policy

        unrestricted = [policy for policy in domain_policies if not _is_exact_policy(policy)]
        if unrestricted:
            return unrestricted[0]

        matches = [
            policy
            for policy_group in self._policies.values()
            for policy in policy_group
            if policy.include_subdomains
            and domain.endswith(f".{policy.domain}")
            and policy.domain != domain
            and not _is_exact_policy(policy)
        ]
        return max(matches, key=lambda policy: len(policy.domain)) if matches else None

    def resolve(self, source: str) -> SourcePolicy:
        domain = self._domain(source)
        return self._lookup(domain, source) or SourcePolicy(domain=domain)

    def require(self, source: str, route: CollectorRoute | str) -> SourcePolicy:
        domain = self._domain(source)
        try:
            normalized_route = CollectorRoute(route)
            route_value = normalized_route.value
        except ValueError:
            normalized_route = None
            route_value = str(route)
        policy = self._lookup(domain, source)
        if policy is None:
            reason = "unknown_domain"
        elif not policy.enabled or policy.collector is CollectorType.DISABLED:
            reason = "source_disabled"
        elif normalized_route is None or normalized_route not in policy.routes:
            reason = "route_not_allowed"
        elif (
            isinstance(policy.config.get("fetch_url"), str)
            and source.strip() != str(policy.config["fetch_url"]).strip()
        ):
            reason = "source_url_not_allowed"
        else:
            event = PolicyAuditEvent(
                source=self._audit_source(source),
                domain=domain,
                route=route_value,
                outcome="allowed",
                reason="allowed",
                policy_domain=policy.domain,
                policy_version=policy.version,
                collector=policy.collector,
                adapter=policy.adapter,
            )
            self._audit.emit(event)
            return policy
        event = PolicyAuditEvent(
            source=self._audit_source(source),
            domain=domain,
            route=route_value,
            outcome="denied",
            reason=reason,
            policy_domain=policy.domain if policy else None,
            policy_version=policy.version if policy else None,
            collector=policy.collector if policy else None,
            adapter=policy.adapter if policy else None,
        )
        self._audit.emit(event)
        raise PolicyDeniedError(event)

    def allows(self, source: str, route: CollectorRoute | str) -> bool:
        try:
            self.require(source, route)
        except PolicyDeniedError:
            return False
        return True

    @property
    def policies(self) -> tuple[SourcePolicy, ...]:
        return tuple(policy for group in self._policies.values() for policy in group)
