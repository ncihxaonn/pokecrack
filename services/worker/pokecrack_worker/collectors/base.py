"""Policy-gated collector interfaces and adapter registries."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from pokecrack_worker.config.source_policy import (
    CollectorRoute,
    RobotsPolicy,
    SourcePolicy,
    SourcePolicyRegistry,
)
from pokecrack_worker.models import SourceItemCandidate

PUBLIC_COLLECTOR_USER_AGENT = "PokecrackMetadataCollector/0.1"


class CollectorError(RuntimeError):
    pass


class AdapterUnavailableError(CollectorError):
    pass


class RobotsDeniedError(CollectorError):
    pass


@dataclass(frozen=True, slots=True)
class FetchResponse:
    status_code: int
    url: str
    headers: Mapping[str, str]
    body: bytes


class HTTPClient(Protocol):
    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse: ...


class RobotsChecker(Protocol):
    def allowed(self, url: str, *, user_agent: str) -> bool: ...


class CollectorAdapter(Protocol):
    def collect(self, url: str, policy: SourcePolicy) -> Sequence[SourceItemCandidate]: ...


class HTTPAdapterRegistry:
    """Explicit static HTTP adapter registry; there is no catch-all adapter."""

    def __init__(self) -> None:
        self._adapters: dict[str, CollectorAdapter] = {}

    def register(self, name: str, adapter: CollectorAdapter) -> None:
        if not name or name in self._adapters:
            raise ValueError(f"adapter name must be non-empty and unique: {name!r}")
        self._adapters[name] = adapter

    def get(self, name: str) -> CollectorAdapter:
        try:
            return self._adapters[name]
        except KeyError as error:
            raise AdapterUnavailableError(f"collector adapter is unavailable: {name}") from error

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


class DynamicAdapterRegistry(HTTPAdapterRegistry):
    """Separate registry so a static policy can never invoke a browser adapter."""


class DenyRobotsChecker:
    """Fail-closed default used until a robots implementation is explicitly supplied."""

    def allowed(self, url: str, *, user_agent: str) -> bool:
        del url, user_agent
        return False


class ConcurrencyLimitError(CollectorError):
    def __init__(self, domain: str, limit: int) -> None:
        self.domain = domain
        self.limit = limit
        super().__init__(f"source concurrency limit reached for {domain}: {limit}")


class CollectionGuard:
    """Thread-safe per-domain policy gate used around every network acquisition."""

    def __init__(
        self,
        *,
        clock: Callable[[], float],
        sleeper: Callable[[float], None],
    ) -> None:
        self._clock = clock
        self._sleeper = sleeper
        self._active: dict[str, int] = {}
        self._last_started: dict[str, float] = {}
        self._lock = RLock()

    @contextmanager
    def limit(self, policy: SourcePolicy) -> Iterator[None]:
        with self._lock:
            active = self._active.get(policy.domain, 0)
            if active >= policy.max_concurrency:
                raise ConcurrencyLimitError(policy.domain, policy.max_concurrency)
            interval = max(policy.minimum_delay_seconds, 60.0 / policy.requests_per_minute)
            now = self._clock()
            last_started = self._last_started.get(policy.domain)
            if last_started is not None:
                delay = interval - (now - last_started)
                if delay > 0:
                    self._sleeper(delay)
                    now = self._clock()
            self._last_started[policy.domain] = now
            self._active[policy.domain] = active + 1
        try:
            yield
        finally:
            with self._lock:
                remaining = self._active[policy.domain] - 1
                if remaining:
                    self._active[policy.domain] = remaining
                else:
                    self._active.pop(policy.domain, None)


class CollectionService:
    def __init__(
        self,
        *,
        policies: SourcePolicyRegistry,
        http_adapters: HTTPAdapterRegistry,
        dynamic_adapters: DynamicAdapterRegistry | None = None,
        robots: RobotsChecker | None = None,
        guard: CollectionGuard | None = None,
        user_agent: str = PUBLIC_COLLECTOR_USER_AGENT,
    ) -> None:
        self.policies = policies
        self.http_adapters = http_adapters
        self.dynamic_adapters = dynamic_adapters or DynamicAdapterRegistry()
        self.robots = robots or DenyRobotsChecker()
        self.guard = guard or CollectionGuard(clock=time.monotonic, sleeper=time.sleep)
        self.user_agent = user_agent

    def collect_url(
        self, url: str, *, route: CollectorRoute | str
    ) -> tuple[SourceItemCandidate, ...]:
        policy = self.policies.require(url, route)
        normalized_route = CollectorRoute(route)
        if normalized_route not in {CollectorRoute.STATIC, CollectorRoute.DYNAMIC}:
            raise CollectorError("CollectionService supports only static and dynamic routes")
        if policy.adapter is None:
            raise AdapterUnavailableError(f"policy has no adapter: {policy.domain}")
        if (
            normalized_route in {CollectorRoute.STATIC, CollectorRoute.DYNAMIC}
            and policy.robots_policy is RobotsPolicy.RESPECT
            and not self.robots.allowed(url, user_agent=self.user_agent)
        ):
            raise RobotsDeniedError(f"robots policy denied collection for {policy.domain}")
        registry: HTTPAdapterRegistry = (
            self.dynamic_adapters
            if normalized_route is CollectorRoute.DYNAMIC
            else self.http_adapters
        )
        adapter = registry.get(policy.adapter)
        with self.guard.limit(policy):
            items = tuple(adapter.collect(url, policy))
        for item in items:
            if item.source_domain != policy.domain and not (
                policy.include_subdomains
                and item.source_domain is not None
                and item.source_domain.endswith(f".{policy.domain}")
            ):
                raise CollectorError("adapter emitted an item outside its authorized domain")
            if item.collector is not policy.collector:
                raise CollectorError("adapter emitted an item for a different collector policy")
        return items
