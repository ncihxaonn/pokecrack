from __future__ import annotations

from dataclasses import dataclass

from pokecrack_worker.collectors.base import (
    CollectionGuard,
    CollectionService,
    ConcurrencyLimitError,
    FetchResponse,
    HTTPAdapterRegistry,
)
from pokecrack_worker.collectors.public import ExamplePublicAdapter
from pokecrack_worker.config.source_policy import SourcePolicy, SourcePolicyRegistry


@dataclass
class FixtureHTTPClient:
    response: FetchResponse
    calls: int = 0

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls += 1
        return self.response


@dataclass
class RecordingRobotsChecker:
    allowed_result: bool = True
    urls: list[str] | None = None

    def allowed(self, url: str, *, user_agent: str) -> bool:
        if self.urls is None:
            self.urls = []
        self.urls.append(url)
        return self.allowed_result


def test_public_adapter_is_policy_and_robots_gated_and_never_retains_html() -> None:
    policy = SourcePolicy(
        domain="example.com",
        enabled=True,
        routes={"static"},
        adapter="example_public",
        metadata_only=True,
        robots_policy="respect",
        requests_per_minute=60,
        max_concurrency=1,
    )
    policies = SourcePolicyRegistry([policy])
    client = FixtureHTTPClient(
        FetchResponse(
            status_code=200,
            url="https://example.com/",
            headers={"content-type": "text/html; charset=utf-8"},
            body=(
                b"<html><head><title>Example Domain</title></head>"
                b"<body><h1>Example Domain</h1><p>Fixture opening summary.</p></body></html>"
            ),
        )
    )
    robots = RecordingRobotsChecker()
    adapters = HTTPAdapterRegistry()
    adapters.register("example_public", ExamplePublicAdapter(client=client))
    service = CollectionService(
        policies=policies,
        http_adapters=adapters,
        robots=robots,
    )

    items = service.collect_url("https://example.com/", route="static")

    assert len(items) == 1
    assert items[0].title == "Example Domain"
    assert items[0].excerpt == "Fixture opening summary."
    assert "<html" not in (items[0].content or "")
    assert "raw_html" not in items[0].metadata
    assert robots.urls == ["https://example.com/"]
    assert client.calls == 1


def test_collection_guard_rejects_concurrency_above_the_source_policy() -> None:
    policy = SourcePolicy(
        domain="example.com",
        enabled=True,
        routes={"static"},
        max_concurrency=1,
    )
    guard = CollectionGuard(clock=lambda: 0.0, sleeper=lambda _: None)

    with guard.limit(policy):
        try:
            with guard.limit(policy):
                raise AssertionError("nested acquisition should not run")
        except ConcurrencyLimitError as error:
            assert error.domain == "example.com"
        else:
            raise AssertionError("expected concurrency denial")


def test_collection_guard_waits_for_rate_and_minimum_delay_policy() -> None:
    policy = SourcePolicy(
        domain="example.com",
        enabled=True,
        routes={"static"},
        requests_per_minute=2,
        minimum_delay_seconds=5,
    )
    now = [0.0]
    sleeps: list[float] = []

    def sleep(delay: float) -> None:
        sleeps.append(delay)
        now[0] += delay

    guard = CollectionGuard(clock=lambda: now[0], sleeper=sleep)
    with guard.limit(policy):
        pass
    with guard.limit(policy):
        pass

    assert sleeps == [30.0]
