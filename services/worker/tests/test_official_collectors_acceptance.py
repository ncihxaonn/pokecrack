from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from pokecrack_worker.collectors.official_api.tcgdex import (
    APIResponse,
    InMemoryTCGdexCache,
    TCGdexClient,
)
from pokecrack_worker.collectors.official_api.youtube import YouTubeDataClient
from pokecrack_worker.config.registries import (
    REQUIRED_YOUTUBE_QUERIES,
    RarityTaxonomy,
    YouTubeQuery,
    YouTubeQueryRegistry,
)
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class SequenceTCGDexTransport:
    responses: list[APIResponse]

    def get(self, url: str, *, headers: dict[str, str], timeout_seconds: float) -> APIResponse:
        return self.responses.pop(0)


def tcgdex_client(transport: SequenceTCGDexTransport) -> tuple[TCGdexClient, InMemoryTCGdexCache]:
    cache = InMemoryTCGdexCache()
    return (
        TCGdexClient(
            transport=transport,
            cache=cache,
            policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
            taxonomy=RarityTaxonomy.from_yaml(ROOT / "config" / "rarity-taxonomy.yaml"),
        ),
        cache,
    )


def test_tcgdex_unchanged_payload_refreshes_cache_validators_without_marking_changed() -> None:
    body = (ROOT / "data" / "examples" / "tcgdex-catalog.json").read_bytes()
    client, cache = tcgdex_client(
        SequenceTCGDexTransport(
            [
                APIResponse(200, {"ETag": '"v1"'}, body),
                APIResponse(200, {"ETag": '"v2"'}, body),
            ]
        )
    )

    first = client.sync(language="en")
    second = client.sync(language="en")

    assert first.changed is True
    assert second.changed is False
    assert second.snapshot.etag == '"v2"'
    assert cache.get("en") == second.snapshot


def test_tcgdex_safe_sync_reports_nonfatal_failure() -> None:
    client, _ = tcgdex_client(
        SequenceTCGDexTransport([APIResponse(503, {}, b"synthetic unavailable")])
    )

    attempt = client.sync_safe(language="en")

    assert attempt.result is None
    assert attempt.error_code == "http_error"
    assert attempt.retryable is True


def test_youtube_registry_requires_the_exact_five_metadata_queries() -> None:
    registry = YouTubeQueryRegistry.from_yaml(ROOT / "config" / "youtube-queries.yaml")
    assert tuple((item.name, item.query) for item in registry.queries) == REQUIRED_YOUTUBE_QUERIES

    with pytest.raises(ValueError, match="exact five"):
        YouTubeQueryRegistry.from_mapping(
            {
                "version": 1,
                "default_enabled": False,
                "queries": [registry.queries[0].model_dump()],
            }
        )


@dataclass
class SequenceYouTubeTransport:
    responses: list[APIResponse]
    calls: list[dict[str, str]] = field(default_factory=list)

    def get(self, url: str, *, params: dict[str, str], timeout_seconds: float) -> APIResponse:
        self.calls.append(params)
        return self.responses.pop(0)


def test_youtube_query_batch_continues_after_nonfatal_api_failure() -> None:
    body = (ROOT / "data" / "examples" / "youtube-search.json").read_bytes()
    transport = SequenceYouTubeTransport(
        [APIResponse(503, {}, b"synthetic unavailable"), APIResponse(200, {}, body)]
    )
    client = YouTubeDataClient(
        api_key="fixture-key",
        transport=transport,
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
    )
    queries = (
        YouTubeQuery(
            name="first-synthetic",
            query="first synthetic query",
            enabled=True,
            metadata_only=True,
        ),
        YouTubeQuery(
            name="second-synthetic",
            query="second synthetic query",
            enabled=True,
            metadata_only=True,
        ),
    )

    result = client.discover_many(queries)

    assert len(result.items) == 1
    assert result.items[0].external_id == "dQw4w9WgXcQ"
    assert [(failure.query_name, failure.error_code) for failure in result.failures] == [
        ("first-synthetic", "http_error")
    ]
    assert len(transport.calls) == 2
    assert all(call["type"] == "video" for call in transport.calls)
