from __future__ import annotations

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from pokecrack_worker.collectors.official_api.tcgdex import (
    TCGDEX_SETS_URL,
    TCGDEX_TIMEOUT_SECONDS,
    APIResponse,
    InMemoryTCGdexSetsCache,
    TCGdexSetsClient,
    TCGdexSetsSyncOutcome,
)
from pokecrack_worker.collectors.official_api.youtube import (
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
    response: APIResponse
    calls: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def get(self, url: str, *, params: dict[str, str], timeout_seconds: float) -> APIResponse:
        self.calls.append((url, params))
        return self.response


def test_youtube_discovery_maps_metadata_without_downloading_video_or_raw_author() -> None:
    transport = FixtureYouTubeTransport(
        APIResponse(
            200,
            {},
            (ROOT / "data" / "examples" / "youtube-search.json").read_bytes(),
        )
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
    assert item.collector_version == "youtube-data-v3"
    assert item.author_hash and "Fixture Channel" not in item.model_dump_json()
    assert item.media_urls == ("https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",)
    assert client.media_download is False
    assert len(transport.calls) == 1
    assert transport.calls[0][0].endswith("/youtube/v3/search")
    assert transport.calls[0][1]["type"] == "video"


def test_youtube_http_transport_rejects_response_over_byte_cap() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
            self.send_response(200)
            self.send_header("Content-Length", "65")
            self.end_headers()
            self.wfile.write(b"x" * 65)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(YouTubeError, match="byte cap"):
            HTTPXYouTubeTransport(max_response_bytes=64).get(
                f"http://127.0.0.1:{server.server_port}/search",
                params={},
                timeout_seconds=2,
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
