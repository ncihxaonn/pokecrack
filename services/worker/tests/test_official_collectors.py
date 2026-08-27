from __future__ import annotations

import asyncio
import gzip
import json
import signal
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

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
    calls: list[tuple[str, dict[str, str], float]] = field(default_factory=list)

    def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        api_key: SecretStr,
        timeout_seconds: float,
    ) -> APIResponse:
        assert repr(api_key) == "SecretStr('**********')"
        self.calls.append((url, params, timeout_seconds))
        return self.responses.pop(0)


def test_youtube_discovery_maps_only_bounded_activity_metadata() -> None:
    transport = FixtureYouTubeTransport(
        [
            APIResponse(
                200,
                {},
                (ROOT / "data" / "examples" / "youtube-search.json").read_bytes(),
            )
        ]
    )
    queries = YouTubeQueryRegistry.from_yaml(ROOT / "config" / "youtube-queries.yaml")
    client = YouTubeDataClient(
        api_key="fixture-key",
        transport=transport,
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
    )

    items = client.discover(queries.queries[0])

    assert len(items) == 1
    item = items[0]
    assert item.platform == "youtube"
    assert item.external_id == "dQw4w9WgXcQ"
    assert item.collector.value == "official_api"
    assert item.collector_version == "youtube-global-discovery-v1"
    assert item.title == "Synthetic Pokémon TCG opening"
    assert item.published_at == datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
    assert item.text is None
    assert item.author_hash is None
    assert item.content_hash is None
    serialized = item.model_dump_json()
    assert "fixture-channel-id" not in serialized
    assert "Fixture Channel" not in serialized
    assert "Synthetic fixture only" not in serialized
    assert item.media_urls == ()
    assert item.metadata == {}
    assert len(transport.calls) == 1
    assert transport.calls[0][0].endswith("/youtube/v3/search")
    assert transport.calls[0][1]["type"] == "video"
    assert transport.calls[0][1]["q"] == queries.queries[0].query
    assert transport.calls[0][1]["relevanceLanguage"] == "en"
    assert transport.calls[0][1]["fields"] == ("items(id(kind,videoId),snippet(publishedAt,title))")
    assert "regionCode" not in transport.calls[0][1]
    assert "key" not in transport.calls[0][1]
    assert transport.calls[0][2] == 30.0


def test_youtube_discovery_ignores_unrequested_channel_and_description_fields() -> None:
    body = json.dumps(
        {
            "items": [
                {
                    "id": {"kind": "youtube#video", "videoId": "dQw4w9WgXcQ"},
                    "snippet": {
                        "publishedAt": "2026-08-24T08:00:00Z",
                        "channelId": "fixture-channel-id",
                        "title": "Synthetic Pokémon TCG opening",
                        "description": None,
                    },
                }
            ]
        }
    ).encode()
    transport = FixtureYouTubeTransport([APIResponse(200, {}, body)])
    client = YouTubeDataClient(
        api_key="fixture-key",
        transport=transport,
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
    )
    query = YouTubeQueryRegistry.from_yaml(ROOT / "config" / "youtube-queries.yaml").queries[0]

    items = client.discover(query)

    assert len(items) == 1
    serialized = items[0].model_dump_json()
    assert "fixture-channel-id" not in serialized
    assert "description" not in serialized
    assert items[0].metadata == {}
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("field", "drifted_value"),
    (
        ("name", "pokemon-tcg-etb-opening"),
        ("query", "Pokemon TCG booster box opening altered"),
        ("enabled", True),
        ("metadata_only", False),
        ("max_results", 50),
        ("region_code", "AU"),
        ("published_within_days", 31),
        ("order", "relevance"),
    ),
)
def test_youtube_programmatic_query_drift_is_rejected_before_network(
    field: str,
    drifted_value: object,
) -> None:
    transport = FixtureYouTubeTransport([])
    client = YouTubeDataClient(
        api_key="fixture-key",
        transport=transport,
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
    )
    approved = YouTubeQueryRegistry.from_yaml(ROOT / "config" / "youtube-queries.yaml").queries[0]
    drifted = approved.model_copy(update={field: drifted_value})

    with pytest.raises(YouTubeError) as raised:
        client.discover(drifted)

    assert raised.value.code == "source_policy_version_mismatch"
    assert raised.value.retryable is False
    assert transport.calls == []


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
            timeout_seconds=30,
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
            timeout_seconds=30,
        )
    with pytest.raises(ValueError, match="fixed search endpoint"):
        transport.get(
            "https://example.com/search",
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )


def test_youtube_http_transport_interrupts_a_blocked_request_at_one_absolute_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_deadlines: list[float | None] = []
    real_timeout = asyncio.timeout

    def accelerated_timeout(delay: float | None) -> asyncio.Timeout:
        requested_deadlines.append(delay)
        return real_timeout(0.02)

    class BlockingTransport(httpx.AsyncBaseTransport):
        cancelled = False
        closed = False

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            assert request.url.host == "youtube.googleapis.com"
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
            raise AssertionError("the blocked request must be cancelled")

        async def aclose(self) -> None:
            self.closed = True

    blocking_transport = BlockingTransport()
    monkeypatch.setattr(asyncio, "timeout", accelerated_timeout)
    transport = HTTPXYouTubeTransport(http_transport=blocking_transport)

    started = time.monotonic()
    with pytest.raises(YouTubeError) as raised:
        transport.get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert time.monotonic() - started < 0.5
    assert raised.value.code == "request_timeout"
    assert raised.value.retryable is True
    assert requested_deadlines == [30]
    assert blocking_transport.cancelled is True
    assert blocking_transport.closed is True
    assert "fixture-key" not in repr(raised.value)


@pytest.mark.skipif(
    not all(hasattr(signal, name) for name in ("SIGALRM", "ITIMER_REAL", "getitimer", "setitimer")),
    reason="POSIX real-time timers are unavailable",
)
def test_youtube_http_transport_preserves_existing_process_timer_and_handler() -> None:
    alarm = signal.SIGALRM
    timer = signal.ITIMER_REAL
    original_handler = signal.getsignal(alarm)
    original_timer = signal.getitimer(timer)
    test_started = time.monotonic()
    observed_signals: list[int] = []

    def existing_handler(signum: int, _frame: object) -> None:
        observed_signals.append(signum)

    try:
        signal.signal(alarm, existing_handler)
        signal.setitimer(timer, 60.0, 10.0)
        response = HTTPXYouTubeTransport(
            http_transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, stream=httpx.ByteStream(b"{}"))
            )
        ).get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

        remaining, interval = signal.getitimer(timer)
        assert response.status_code == 200
        assert signal.getsignal(alarm) is existing_handler
        assert 58.0 < remaining <= 60.0
        assert interval == 10.0
        assert observed_signals == []
    finally:
        signal.setitimer(timer, 0.0)
        signal.signal(alarm, original_handler)
        elapsed = time.monotonic() - test_started
        restored_remaining = max(0.0, original_timer[0] - elapsed)
        signal.setitimer(timer, restored_remaining, original_timer[1])


def test_youtube_http_transport_fails_closed_inside_a_running_event_loop() -> None:
    class CountingTransport(httpx.AsyncBaseTransport):
        calls = 0

        async def handle_async_request(self, _request: httpx.Request) -> httpx.Response:
            self.calls += 1
            return httpx.Response(200, stream=httpx.ByteStream(b"{}"))

    counting_transport = CountingTransport()
    transport = HTTPXYouTubeTransport(http_transport=counting_transport)

    async def invoke_from_unsupported_context() -> YouTubeError:
        with pytest.raises(YouTubeError) as raised:
            transport.get(
                YOUTUBE_SEARCH_URL,
                params={},
                api_key=SecretStr("fixture-key"),
                timeout_seconds=30,
            )
        return raised.value

    error = asyncio.run(invoke_from_unsupported_context())

    assert error.code == "absolute_deadline_unavailable"
    assert error.retryable is False
    assert counting_transport.calls == 0
    assert "fixture-key" not in repr(error)


def test_youtube_http_transport_disables_proxy_env_and_redirect_following(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Response:
        status_code = 302
        headers: dict[str, str] = {}

        async def __aenter__(self) -> Response:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def aiter_raw(self) -> AsyncIterator[bytes]:
            if False:
                yield b""

    class Client:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        def stream(self, method: str, url: str, **kwargs: object) -> Response:
            captured["method"] = method
            captured["url"] = url
            raw_params = kwargs["params"]
            assert isinstance(raw_params, dict)
            params = dict(raw_params)
            captured["param_keys"] = set(params)
            return Response()

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    response = HTTPXYouTubeTransport().get(
        YOUTUBE_SEARCH_URL,
        params={"part": "snippet"},
        api_key=SecretStr("fixture-key"),
        timeout_seconds=30,
    )

    assert response.status_code == 302
    assert captured["follow_redirects"] is False
    assert captured["trust_env"] is False
    assert captured["headers"] == {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }
    timeout = captured["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 10.0
    assert timeout.read == 10.0
    assert timeout.write == 10.0
    assert timeout.pool == 10.0
    assert captured["param_keys"] == {"part", "key"}
    assert "fixture-key" not in repr(captured)
