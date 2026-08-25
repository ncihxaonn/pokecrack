from __future__ import annotations

from dataclasses import dataclass

import pytest

from pokecrack_worker.collectors.base import CollectorError, FetchResponse
from pokecrack_worker.collectors.scrapling.adapters.dynamic_fixture import DynamicFixtureAdapter
from pokecrack_worker.collectors.scrapling.adapters.example_public import ExamplePublicAdapter
from pokecrack_worker.collectors.scrapling.dynamic import ScraplingDynamicClient
from pokecrack_worker.collectors.scrapling.http import ScraplingHTTPClient
from pokecrack_worker.collectors.scrapling.registry import build_fixture_registries
from pokecrack_worker.config.source_policy import SourcePolicy
from pokecrack_worker.models import CollectorType


@dataclass
class RecordingClient:
    response: FetchResponse
    calls: int = 0

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls += 1
        return self.response


class FixtureBackend:
    def __init__(self, response: FetchResponse) -> None:
        self.response = response
        self.calls: list[str] = []

    def fetch_http(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls.append(f"http:{url}:{timeout_seconds}")
        return self.response

    def fetch_dynamic(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls.append(f"dynamic:{url}:{timeout_seconds}")
        return self.response


def public_policy() -> SourcePolicy:
    return SourcePolicy(
        domain="example.com",
        enabled=True,
        collector="scrapling_http",
        routes={"static"},
        adapter="example_public",
        retain_raw_html=False,
    )


def dynamic_policy() -> SourcePolicy:
    return SourcePolicy(
        domain="dynamic.example",
        enabled=True,
        collector="scrapling_dynamic",
        routes={"dynamic"},
        adapter="dynamic_fixture",
        dynamic_allowed=True,
        retain_raw_html=False,
    )


def test_example_adapter_is_source_specific_and_serializes_exact_candidate_fields() -> None:
    client = RecordingClient(
        FetchResponse(
            200,
            "https://example.com/opening/fixture",
            {"content-type": "text/html; charset=utf-8"},
            (
                b"<html><head><title>Synthetic title</title></head>"
                b"<body><p>Synthetic fixture text.</p></body></html>"
            ),
        )
    )
    adapter = ExamplePublicAdapter(client=client)

    item = adapter.collect("https://example.com/opening/fixture", public_policy())[0]

    assert set(item.model_dump()) == {
        "platform",
        "external_id",
        "source_url",
        "title",
        "text",
        "published_at",
        "author_hash",
        "media_urls",
        "metadata",
        "collector",
        "collector_version",
        "source_policy_version",
    }
    assert item.collector is CollectorType.SCRAPLING_HTTP
    assert item.text == "Synthetic fixture text."
    assert "<html" not in item.model_dump_json().casefold()
    assert "raw_html" not in item.metadata

    with pytest.raises(CollectorError, match="example.com"):
        adapter.collect("https://unknown.example/item", public_policy())
    assert client.calls == 1


def test_scrapling_clients_delegate_only_to_the_explicit_transport_path() -> None:
    response = FetchResponse(200, "https://example.com/", {}, b"ok")
    backend = FixtureBackend(response)

    assert (
        ScraplingHTTPClient(backend=backend, timeout_seconds=7).get(
            "https://example.com/", timeout_seconds=5
        )
        == response
    )
    assert (
        ScraplingDynamicClient(backend=backend, timeout_seconds=11).get(
            "https://dynamic.example/", timeout_seconds=9
        )
        == response
    )
    assert backend.calls == [
        "http:https://example.com/:5",
        "dynamic:https://dynamic.example/:9",
    ]


def test_dynamic_fixture_adapter_requires_dynamic_policy_and_discards_html() -> None:
    response = FetchResponse(
        200,
        "https://dynamic.example/opening/fixture",
        {"content-type": "text/html"},
        (
            b"<html><body><h1>Synthetic dynamic opening</h1>"
            b"<p>Three synthetic packs.</p></body></html>"
        ),
    )
    client = RecordingClient(response)
    adapter = DynamicFixtureAdapter(client=client)

    item = adapter.collect(response.url, dynamic_policy())[0]
    assert item.collector is CollectorType.SCRAPLING_DYNAMIC
    assert item.metadata["rendered"] is True
    assert "<html" not in item.model_dump_json().casefold()

    with pytest.raises(CollectorError, match="dynamic_allowed"):
        adapter.collect("https://dynamic.example/", public_policy())
    assert client.calls == 1


def test_fixture_registry_keeps_static_and_dynamic_adapters_separate() -> None:
    static = RecordingClient(FetchResponse(200, "https://example.com/", {}, b""))
    dynamic = RecordingClient(FetchResponse(200, "https://dynamic.example/", {}, b""))

    static_registry, dynamic_registry = build_fixture_registries(
        http_client=static, dynamic_client=dynamic
    )

    assert static_registry.names == ("example_public",)
    assert dynamic_registry.names == ("dynamic_fixture",)


def test_collection_service_applies_guard_to_every_network_acquisition() -> None:
    from pokecrack_worker.collectors.base import (
        CollectionGuard,
        CollectionService,
        HTTPAdapterRegistry,
    )
    from pokecrack_worker.config.source_policy import SourcePolicyRegistry

    now = [0.0]
    sleeps: list[float] = []

    def sleep(delay: float) -> None:
        sleeps.append(delay)
        now[0] += delay

    client = RecordingClient(
        FetchResponse(
            200,
            "https://example.com/",
            {"content-type": "text/html"},
            b"<html><body><p>Synthetic.</p></body></html>",
        )
    )
    adapters = HTTPAdapterRegistry()
    adapters.register("example_public", ExamplePublicAdapter(client=client))
    policy = public_policy().model_copy(
        update={"requests_per_minute": 2.0, "min_delay_seconds": 5.0}
    )
    service = CollectionService(
        policies=SourcePolicyRegistry([policy]),
        http_adapters=adapters,
        robots=type("AllowRobots", (), {"allowed": lambda self, url, user_agent: True})(),
        guard=CollectionGuard(clock=lambda: now[0], sleeper=sleep),
    )

    service.collect_url("https://example.com/", route="static")
    service.collect_url("https://example.com/", route="static")

    assert sleeps == [30.0]
    assert client.calls == 2
