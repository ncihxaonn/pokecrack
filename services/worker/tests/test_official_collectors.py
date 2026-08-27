from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

import pokecrack_worker.collectors.official_api.youtube as youtube_module
from pokecrack_worker.collectors.official_api.tcgdex import (
    TCGDEX_SETS_URL,
    TCGDEX_TIMEOUT_SECONDS,
    APIResponse,
    InMemoryTCGdexSetsCache,
    TCGdexSetsClient,
    TCGdexSetsSyncOutcome,
)
from pokecrack_worker.collectors.official_api.youtube import (
    YOUTUBE_SEARCH_URL,
    HTTPXYouTubeTransport,
    YouTubeDataClient,
    YouTubeError,
)
from pokecrack_worker.config.registries import YouTubeQueryRegistry
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class FixtureTCGDexTransport:
    responses: list[APIResponse]
    calls: list[tuple[str, dict[str, str], float]] = field(default_factory=list)

    def get(self, url: str, *, headers: dict[str, str], timeout_seconds: float) -> APIResponse:
        self.calls.append((url, headers, timeout_seconds))
        return self.responses.pop(0)


def test_tcgdex_sync_maps_only_set_metadata_and_reuses_etag() -> None:
    body = (ROOT / "data" / "examples" / "tcgdex-catalog.json").read_bytes()
    transport = FixtureTCGDexTransport(
        [
            APIResponse(200, {"etag": '"fixture-v1"'}, body),
            APIResponse(304, {"etag": '"fixture-v1"'}, b""),
        ]
    )
    cache = InMemoryTCGdexSetsCache()
    client = TCGdexSetsClient(
        transport=transport,
        cache=cache,
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
    )

    first = client.sync()
    second = client.sync()

    assert first.outcome is TCGdexSetsSyncOutcome.CHANGED
    assert first.snapshot.sets[0].set_id == "sv2"
    assert first.snapshot.sets[0].card_count_total == 279
    assert first.snapshot.sets[0].card_count_official == 193
    assert not hasattr(first.snapshot, "cards")
    assert not hasattr(first.snapshot.sets[0], "rarity")
    assert second.outcome is TCGdexSetsSyncOutcome.NOT_MODIFIED
    assert second.snapshot == first.snapshot
    assert transport.calls == [
        (TCGDEX_SETS_URL, {"Accept": "application/json"}, TCGDEX_TIMEOUT_SECONDS),
        (
            TCGDEX_SETS_URL,
            {"Accept": "application/json", "If-None-Match": '"fixture-v1"'},
            TCGDEX_TIMEOUT_SECONDS,
        ),
    ]


@dataclass
class FixtureYouTubeTransport:
    responses: list[APIResponse]
    calls: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        api_key: SecretStr,
        timeout_seconds: float,
    ) -> APIResponse:
        assert repr(api_key) == "SecretStr('**********')"
        self.calls.append((url, params))
        return self.responses.pop(0)


def test_youtube_discovery_maps_metadata_without_downloading_video_or_raw_author() -> None:
    transport = FixtureYouTubeTransport(
        [
            APIResponse(
                200,
                {},
                (ROOT / "data" / "examples" / "youtube-search.json").read_bytes(),
            ),
            APIResponse(
                200,
                {},
                b'{"items":[{"id":"fixture-channel-id","snippet":{"country":"AU"}}]}',
            ),
        ]
    )
    queries = YouTubeQueryRegistry.from_yaml(ROOT / "config" / "youtube-queries.yaml")
    client = YouTubeDataClient(
        api_key="fixture-key",
        transport=transport,
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
        sleeper=lambda _seconds: None,
    )

    items = client.discover(queries.queries[0])

    assert len(items) == 1
    item = items[0]
    assert item.platform == "youtube"
    assert item.external_id == "dQw4w9WgXcQ"
    assert item.collector.value == "official_api"
    assert item.collector_version == "youtube-global-discovery-v1"
    assert item.author_hash and "Fixture Channel" not in item.model_dump_json()
    assert item.media_urls == ()
    assert item.metadata["geography_status"] == "channel_country_proxy"
    assert item.metadata["channel_country_code"] == "AU"
    assert item.metadata["statistics_eligible"] is False
    assert client.media_download is False
    assert len(transport.calls) == 2
    assert transport.calls[0][0].endswith("/youtube/v3/search")
    assert transport.calls[0][1]["type"] == "video"
    assert "regionCode" not in transport.calls[0][1]
    assert "key" not in transport.calls[0][1]
    assert transport.calls[1][0].endswith("/youtube/v3/channels")


def test_youtube_http_transport_rejects_response_over_byte_cap() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, stream=httpx.ByteStream(b"x" * 65))

    transport = HTTPXYouTubeTransport(
        max_response_bytes=64,
        http_transport=httpx.MockTransport(respond),
    )
    with pytest.raises(YouTubeError, match="response_too_large"):
        transport.get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=2,
        )


def test_youtube_http_transport_rejects_encoded_content_and_unapproved_endpoints() -> None:
    transport = HTTPXYouTubeTransport(
        http_transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"Content-Encoding": "gzip"},
                stream=httpx.ByteStream(gzip.compress(b"{}")),
            )
        )
    )

    with pytest.raises(YouTubeError, match="unsupported_content_encoding"):
        transport.get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=2,
        )
    with pytest.raises(ValueError, match="fixed official endpoints"):
        transport.get(
            "https://example.com/search",
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=2,
        )


def test_youtube_http_transport_has_an_absolute_deadline() -> None:
    moments = iter((0.0, 0.0, 2.0))
    transport = HTTPXYouTubeTransport(
        monotonic_clock=lambda: next(moments),
        http_transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, stream=httpx.ByteStream(b"{}"))
        ),
    )

    with pytest.raises(YouTubeError) as raised:
        transport.get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=1,
        )

    assert raised.value.code == "request_timeout"
    assert raised.value.retryable is True


def test_youtube_http_transport_disables_proxy_env_and_redirect_following(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Response:
        status_code = 302
        headers: dict[str, str] = {}

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def iter_raw(self) -> tuple[bytes, ...]:
            return ()

    class Client:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def stream(self, method: str, url: str, **kwargs: object) -> Response:
            captured["method"] = method
            captured["url"] = url
            params = dict(kwargs["params"])  # type: ignore[arg-type]
            captured["param_keys"] = set(params)
            return Response()

    monkeypatch.setattr(youtube_module.httpx, "Client", Client)
    response = HTTPXYouTubeTransport().get(
        YOUTUBE_SEARCH_URL,
        params={"part": "snippet"},
        api_key=SecretStr("fixture-key"),
        timeout_seconds=2,
    )

    assert response.status_code == 302
    assert captured["follow_redirects"] is False
    assert captured["trust_env"] is False
    assert captured["headers"] == {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }
    assert captured["param_keys"] == {"part", "key"}
    assert "fixture-key" not in repr(captured)
