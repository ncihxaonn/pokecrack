from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import SecretStr

from pokecrack_worker.collectors.official_api.tcgdex import (
    APIResponse,
    InMemoryTCGdexSetsCache,
    TCGdexError,
    TCGdexNetworkError,
    TCGdexSetsClient,
    TCGdexSetsSyncOutcome,
    TCGdexTimeoutError,
    parse_tcgdex_sets,
)
from pokecrack_worker.collectors.official_api.youtube import YouTubeDataClient, YouTubeError
from pokecrack_worker.config.registries import (
    REQUIRED_YOUTUBE_QUERIES,
    YouTubeQueryRegistry,
)
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class SequenceTCGDexTransport:
    responses: list[APIResponse]

    def get(self, url: str, *, headers: dict[str, str], timeout_seconds: float) -> APIResponse:
        return self.responses.pop(0)


@dataclass
class FailingTCGDexTransport:
    error: TCGdexError

    def get(self, url: str, *, headers: dict[str, str], timeout_seconds: float) -> APIResponse:
        del url, headers, timeout_seconds
        raise self.error


def tcgdex_client(
    transport: SequenceTCGDexTransport,
) -> tuple[TCGdexSetsClient, InMemoryTCGdexSetsCache]:
    cache = InMemoryTCGdexSetsCache()
    return (
        TCGdexSetsClient(
            transport=transport,
            cache=cache,
            policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
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

    first = client.sync()
    second = client.sync()

    assert first.outcome is TCGdexSetsSyncOutcome.CHANGED
    assert second.outcome is TCGdexSetsSyncOutcome.UNCHANGED
    assert second.snapshot.etag == '"v2"'
    assert cache.get() == second.snapshot


@pytest.mark.parametrize("status_code", (408, 429, 503))
def test_tcgdex_safe_sync_retries_transient_http_failures(status_code: int) -> None:
    client, _ = tcgdex_client(
        SequenceTCGDexTransport([APIResponse(status_code, {}, b"synthetic unavailable")])
    )

    attempt = client.sync_safe()

    assert attempt.result is None
    assert attempt.error_code == f"http_{status_code}"
    assert attempt.retryable is True


@pytest.mark.parametrize(
    ("error", "expected_code"),
    (
        (TCGdexTimeoutError("synthetic timeout"), "request_timeout"),
        (TCGdexNetworkError("synthetic network failure"), "network_error"),
    ),
)
def test_tcgdex_safe_sync_preserves_sanitized_transport_failure_class(
    error: TCGdexError,
    expected_code: str,
) -> None:
    cache = InMemoryTCGdexSetsCache()
    client = TCGdexSetsClient(
        transport=FailingTCGDexTransport(error),
        cache=cache,
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
    )

    attempt = client.sync_safe()

    assert attempt.result is None
    assert attempt.error_code == expected_code
    assert attempt.retryable is True


def _set_payload(
    *,
    set_id: object = "sv2",
    name: object = "Paldea Evolved",
    total: object = 279,
    official: object = 193,
) -> list[dict[str, object]]:
    return [
        {
            "id": set_id,
            "name": name,
            "cardCount": {"total": total, "official": official},
        }
    ]


@pytest.mark.parametrize(
    ("payload", "message"),
    (
        ([], "1 to 1000"),
        ({"sets": _set_payload()}, "1 to 1000"),
        (_set_payload(set_id=""), "set id"),
        (_set_payload(set_id="x" * 161), "set id"),
        (_set_payload(set_id="\nsv2\t"), "set id"),
        (_set_payload(set_id="sv\n2"), "control characters"),
        (_set_payload(name=""), "set name"),
        (_set_payload(name="x" * 161), "set name"),
        (_set_payload(name=" Paldea Evolved"), "set name"),
        (_set_payload(name="Paldea\x7fEvolved"), "control characters"),
        (_set_payload(total=-1), "nonnegative integer"),
        (_set_payload(total=True), "nonnegative integer"),
        (_set_payload(official=-1), "nonnegative integer"),
        (_set_payload(official=280), "must not exceed"),
    ),
)
def test_tcgdex_set_parser_rejects_non_official_or_invalid_shapes(
    payload: object, message: str
) -> None:
    with pytest.raises(TCGdexError, match=message):
        parse_tcgdex_sets(payload)


def test_tcgdex_set_parser_rejects_duplicate_ids_and_more_than_one_thousand_sets() -> None:
    duplicate = [*_set_payload(), *_set_payload()]
    oversized = [
        {
            "id": f"set-{index}",
            "name": f"Set {index}",
            "cardCount": {"total": 1, "official": 1},
        }
        for index in range(1_001)
    ]

    with pytest.raises(TCGdexError, match="unique"):
        parse_tcgdex_sets(duplicate)
    with pytest.raises(TCGdexError, match="1 to 1000"):
        parse_tcgdex_sets(oversized)


def test_tcgdex_client_rejects_invalid_json_without_retaining_raw_response() -> None:
    client, cache = tcgdex_client(
        SequenceTCGDexTransport([APIResponse(200, {}, json.dumps({"sets": []}).encode())])
    )

    attempt = client.sync_safe()

    assert attempt.error_code == "invalid_response"
    assert attempt.retryable is False
    assert cache.get() is None


@pytest.mark.parametrize("etag", ('"bad\tvalue"', '"ÿ"', "not-an-etag", '"bad"quote"'))
def test_tcgdex_client_rejects_an_unsafe_etag_as_a_permanent_response_error(
    etag: str,
) -> None:
    body = (ROOT / "data" / "examples" / "tcgdex-catalog.json").read_bytes()
    client, cache = tcgdex_client(SequenceTCGDexTransport([APIResponse(200, {"ETag": etag}, body)]))

    attempt = client.sync_safe()

    assert attempt.result is None
    assert attempt.error_code == "invalid_response"
    assert attempt.retryable is False
    assert cache.get() is None


def test_tcgdex_client_rejects_304_when_no_validator_was_sent() -> None:
    body = (ROOT / "data" / "examples" / "tcgdex-catalog.json").read_bytes()
    client, _ = tcgdex_client(
        SequenceTCGDexTransport([APIResponse(200, {}, body), APIResponse(304, {}, b"")])
    )

    client.sync()
    with pytest.raises(TCGdexError, match="without a sent cache validator"):
        client.sync()


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

    def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        api_key: SecretStr,
        timeout_seconds: float,
    ) -> APIResponse:
        assert repr(api_key) == "SecretStr('**********')"
        self.calls.append(params)
        return self.responses.pop(0)


def test_youtube_queries_are_independent_single_request_jobs() -> None:
    body = (ROOT / "data" / "examples" / "youtube-search.json").read_bytes()
    transport = SequenceYouTubeTransport(
        [
            APIResponse(503, {}, b"synthetic unavailable"),
            APIResponse(200, {}, body),
        ]
    )
    client = YouTubeDataClient(
        api_key="fixture-key",
        transport=transport,
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
    )
    queries = YouTubeQueryRegistry.from_yaml(ROOT / "config" / "youtube-queries.yaml").queries[:2]

    with pytest.raises(YouTubeError) as raised:
        client.discover(queries[0])
    items = client.discover(queries[1])

    assert raised.value.code == "http_503"
    assert raised.value.retryable is True
    assert len(items) == 1
    assert items[0].external_id == "dQw4w9WgXcQ"
    assert len(transport.calls) == 2
    assert transport.calls[0]["type"] == "video"
    assert transport.calls[1]["type"] == "video"
    assert all(
        call["fields"] == "items(id(kind,videoId),snippet(publishedAt,title))"
        for call in transport.calls
    )
    assert all("key" not in call for call in transport.calls)
