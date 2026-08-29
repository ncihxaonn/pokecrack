from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

from pokecrack_worker.collectors.official_api import youtube as youtube_module
from pokecrack_worker.collectors.official_api.tcgdex import (
    TCGDEX_SETS_URL,
    TCGDEX_TIMEOUT_SECONDS,
    APIResponse,
    InMemoryTCGdexSetsCache,
    TCGdexSetsClient,
    TCGdexSetsSyncOutcome,
)
from pokecrack_worker.collectors.official_api.youtube import (
    MATON_YOUTUBE_SEARCH_URL,
    YOUTUBE_SEARCH_URL,
    HTTPXYouTubeTransport,
    MatonYouTubeTransport,
    YouTubeDataClient,
    YouTubeError,
    YouTubeRequestStateUnknown,
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
        clock=lambda: datetime(2026, 8, 28, 0, 0, tzinfo=UTC),
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
    assert transport.calls[0][1]["publishedAfter"] == "2026-07-29T00:00:00Z"
    assert transport.calls[0][1]["publishedBefore"] == "2026-08-28T00:00:00Z"
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


def test_youtube_discovery_skips_upcoming_items_without_rejecting_the_batch() -> None:
    cutoff = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
    body = json.dumps(
        {
            "items": [
                {
                    "id": {"kind": "youtube#video", "videoId": "pastvideo01"},
                    "snippet": {
                        "publishedAt": "2026-08-25T11:59:59Z",
                        "title": "Already published",
                    },
                },
                {
                    "id": {"kind": "youtube#video", "videoId": "exactvideo1"},
                    "snippet": {
                        "publishedAt": "2026-08-25T12:00:00Z",
                        "title": "Published at cutoff",
                    },
                },
                {
                    "id": {"kind": "youtube#video", "videoId": "futurevid01"},
                    "snippet": {
                        "publishedAt": "2026-08-25T12:00:01Z",
                        "title": "Upcoming premiere",
                    },
                },
            ]
        }
    ).encode()
    transport = FixtureYouTubeTransport([APIResponse(200, {}, body)])
    client = YouTubeDataClient(
        api_key="fixture-key",
        transport=transport,
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
        clock=lambda: cutoff,
    )
    query = YouTubeQueryRegistry.from_yaml(ROOT / "config" / "youtube-queries.yaml").queries[0]

    items = client.discover(query)

    assert [item.external_id for item in items] == ["pastvideo01", "exactvideo1"]
    assert transport.calls[0][1]["publishedBefore"] == "2026-08-25T12:00:00Z"


def test_youtube_discovery_treats_a_future_only_page_as_an_empty_success() -> None:
    body = json.dumps(
        {
            "items": [
                {
                    "id": {"kind": "youtube#video", "videoId": "futurevid01"},
                    "snippet": {
                        "publishedAt": "2026-08-25T12:00:01Z",
                        "title": "Upcoming premiere",
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
        clock=lambda: datetime(2026, 8, 25, 12, 0, tzinfo=UTC),
    )
    query = YouTubeQueryRegistry.from_yaml(ROOT / "config" / "youtube-queries.yaml").queries[0]

    assert client.discover(query) == ()


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


def _curl_metadata(
    *,
    status: int = 200,
    content_encoding: str = "",
    content_length: str = "2",
) -> bytes:
    return (
        f"POKECRACK_HTTP_CODE:{status}\n"
        f"POKECRACK_CONTENT_ENCODING:{content_encoding}\n"
        f"POKECRACK_CONTENT_LENGTH:{content_length}\n"
    ).encode()


@dataclass
class FixtureCurlProcess:
    pid: int = 424242
    stdout: bytes = b"{}"
    stderr: bytes = field(default_factory=_curl_metadata)
    returncode: int | None = 0
    communicate_effects: list[BaseException | tuple[bytes, bytes]] = field(default_factory=list)
    wait_effects: list[BaseException | int] = field(default_factory=list)
    poll_effects: list[BaseException | int | None] = field(default_factory=list)
    communicate_inputs: list[bytes | None] = field(default_factory=list)
    communicate_timeouts: list[float | None] = field(default_factory=list)
    wait_timeouts: list[float | None] = field(default_factory=list)
    active: bool = True
    reaped: bool = False
    kill_calls: int = 0

    def communicate(
        self,
        input: bytes | None = None,
        timeout: float | None = None,
    ) -> tuple[bytes, bytes]:
        self.communicate_inputs.append(input)
        self.communicate_timeouts.append(timeout)
        if self.communicate_effects:
            effect = self.communicate_effects.pop(0)
            if isinstance(effect, BaseException):
                raise effect
            self.active = False
            return effect
        self.active = False
        return self.stdout, self.stderr

    def kill(self) -> None:
        self.kill_calls += 1
        self.active = False

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeouts.append(timeout)
        if self.wait_effects:
            effect = self.wait_effects.pop(0)
            if isinstance(effect, BaseException):
                raise effect
            self.returncode = effect
        elif self.returncode is None:
            self.returncode = -9
        self.active = False
        self.reaped = True
        return self.returncode

    def poll(self) -> int | None:
        if self.poll_effects:
            effect = self.poll_effects.pop(0)
            if isinstance(effect, BaseException):
                raise effect
            if effect is not None:
                self.returncode = effect
                self.reaped = True
            return effect
        return self.returncode if self.reaped else None


@dataclass
class FixturePopenFactory:
    process: FixtureCurlProcess
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = field(default_factory=list)

    def __call__(self, command: tuple[str, ...], **kwargs: object) -> FixtureCurlProcess:
        self.calls.append((command, kwargs))
        return self.process


def _install_fixture_curl(
    monkeypatch: pytest.MonkeyPatch,
    process: FixtureCurlProcess,
) -> FixturePopenFactory:
    factory = FixturePopenFactory(process)
    monkeypatch.setattr(subprocess, "Popen", factory)

    def fixture_exchange(
        actual_process: subprocess.Popen[bytes],
        *,
        stdin_bytes: bytes,
        stdout_limit: int,
        stderr_limit: int,
        deadline: float,
    ) -> tuple[bytes, bytes]:
        assert actual_process is process
        assert stdout_limit > 0
        assert stderr_limit > 0
        return process.communicate(
            input=stdin_bytes,
            timeout=youtube_module._remaining_seconds(deadline),
        )

    monkeypatch.setattr(youtube_module, "_bounded_exchange", fixture_exchange)
    return factory


def _install_real_curl_child(
    monkeypatch: pytest.MonkeyPatch,
    child_code: str,
) -> list[subprocess.Popen[bytes]]:
    real_popen = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []

    def spawn_child(
        _command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.Popen[bytes]:
        child = real_popen((sys.executable, "-c", child_code), **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", spawn_child)
    return children


def _cleanup_test_children(children: list[subprocess.Popen[bytes]]) -> None:
    for child in children:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2)


def test_youtube_curl_streams_unknown_length_body_through_a_hard_memory_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    children = _install_real_curl_child(
        monkeypatch,
        "import sys,time; "
        "sys.stdin.buffer.read(); "
        "sys.stdout.buffer.write(b'x' * 65); "
        "sys.stdout.buffer.flush(); "
        "time.sleep(10)",
    )
    try:
        with pytest.raises(YouTubeError) as raised:
            HTTPXYouTubeTransport(max_response_bytes=64).get(
                YOUTUBE_SEARCH_URL,
                params={},
                api_key=SecretStr("fixture-key"),
                timeout_seconds=30,
            )
    finally:
        _cleanup_test_children(children)

    assert raised.value.code == "response_too_large"
    assert len(children) == 1
    assert children[0].poll() is not None
    assert "fixture-key" not in repr(children[0].args)


def test_youtube_curl_stream_accepts_exactly_the_body_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = _curl_metadata(content_length="2")
    children = _install_real_curl_child(
        monkeypatch,
        "import sys; "
        "sys.stdin.buffer.read(); "
        "sys.stdout.buffer.write(b'{}'); "
        f"sys.stderr.buffer.write({metadata!r})",
    )
    try:
        response = HTTPXYouTubeTransport(max_response_bytes=2).get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )
    finally:
        _cleanup_test_children(children)

    assert response.status_code == 200
    assert response.body == b"{}"


def test_youtube_curl_stream_caps_stderr_before_metadata_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    children = _install_real_curl_child(
        monkeypatch,
        "import sys,time; "
        "sys.stdin.buffer.read(); "
        "sys.stderr.buffer.write(b'x' * 65537); "
        "sys.stderr.buffer.flush(); "
        "time.sleep(10)",
    )
    try:
        with pytest.raises(YouTubeError) as raised:
            HTTPXYouTubeTransport().get(
                YOUTUBE_SEARCH_URL,
                params={},
                api_key=SecretStr("fixture-key"),
                timeout_seconds=30,
            )
    finally:
        _cleanup_test_children(children)

    assert raised.value.code == "response_headers_too_large"
    assert len(children) == 1
    assert children[0].poll() is not None


def test_youtube_curl_stream_limit_keeps_the_gate_fenced_if_reaping_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(
        returncode=None,
        wait_effects=[subprocess.TimeoutExpired("curl", 0.4)] * 4,
        poll_effects=[None] * 4,
    )
    _install_fixture_curl(monkeypatch, process)

    def over_limit(*_args: object, **_kwargs: object) -> tuple[bytes, bytes]:
        raise youtube_module._StreamLimitExceeded("response_too_large")

    moments = iter((0.0, 27.1, 27.2, 27.3, 27.4))
    monkeypatch.setattr(youtube_module, "_bounded_exchange", over_limit)
    monkeypatch.setattr(os, "killpg", lambda _pid, _sig: None)
    monkeypatch.setattr(youtube_module, "monotonic", lambda: next(moments))

    with pytest.raises(YouTubeRequestStateUnknown):
        HTTPXYouTubeTransport(max_response_bytes=64).get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert process.kill_calls == 4
    assert process.reaped is False


def test_youtube_curl_transport_rejects_response_over_byte_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(stdout=b"x" * 64, returncode=63)
    factory = _install_fixture_curl(monkeypatch, process)

    transport = HTTPXYouTubeTransport(max_response_bytes=64)
    with pytest.raises(YouTubeError, match="response_too_large"):
        transport.get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )
    command, _options = factory.calls[0]
    assert command[command.index("--max-filesize") + 1] == "64"


def test_youtube_curl_transport_rejects_encoded_content_and_unapproved_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(stderr=_curl_metadata(content_encoding="gzip"))
    factory = _install_fixture_curl(monkeypatch, process)
    transport = HTTPXYouTubeTransport()

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
    assert len(factory.calls) == 1


def test_youtube_curl_transport_kills_and_reaps_a_stalled_dns_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[subprocess.TimeoutExpired("curl", 27)],
    )
    _install_fixture_curl(monkeypatch, process)
    transport = HTTPXYouTubeTransport()

    with pytest.raises(YouTubeError) as raised:
        transport.get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value.code == "request_timeout"
    assert raised.value.retryable is True
    assert process.kill_calls == 1
    assert process.active is False
    assert process.reaped is True
    assert len(process.communicate_timeouts) == 1
    assert process.communicate_timeouts[0] is not None
    assert 26.0 < process.communicate_timeouts[0] <= 27.0
    assert process.wait_timeouts == [pytest.approx(0.4)]
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_fails_closed_if_reaping_stalls_at_hard_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[subprocess.TimeoutExpired("curl", 27)],
        wait_effects=[
            subprocess.TimeoutExpired("curl", 1.5),
            subprocess.TimeoutExpired("curl", 0.2),
        ],
    )
    _install_fixture_curl(monkeypatch, process)
    moments = iter((0.0, 0.0, 27.5, 28.8, 29.1))
    monkeypatch.setattr(
        "pokecrack_worker.collectors.official_api.youtube.monotonic",
        lambda: next(moments),
    )

    with pytest.raises(YouTubeRequestStateUnknown) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert str(raised.value) == "youtube_request_state_unknown"
    assert process.kill_calls == 3
    assert process.active is False
    assert process.reaped is False
    assert process.wait_timeouts == [pytest.approx(0.4), pytest.approx(0.2)]
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_propagates_cleanup_keyboard_interrupt_after_timeout_and_reap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interrupt = KeyboardInterrupt("shutdown requested")
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[subprocess.TimeoutExpired("curl", 27)],
        wait_effects=[interrupt, RuntimeError("cleanup wait failed"), -9],
    )
    _install_fixture_curl(monkeypatch, process)
    group_kills: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: group_kills.append((pid, sig)))

    with pytest.raises(KeyboardInterrupt) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value is interrupt
    assert group_kills == [
        (process.pid, signal.SIGKILL),
        (process.pid, signal.SIGKILL),
        (process.pid, signal.SIGKILL),
    ]
    assert process.kill_calls == 3
    assert process.active is False
    assert process.reaped is True
    assert len(process.communicate_timeouts) == 1
    assert len(process.wait_timeouts) == 3


def test_youtube_curl_transport_propagates_cleanup_system_exit_after_ordinary_failure_and_reap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shutdown = SystemExit(17)
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[RuntimeError("fixture-key must not cross the job boundary")],
        wait_effects=[shutdown, RuntimeError("cleanup wait failed"), -9],
    )
    _install_fixture_curl(monkeypatch, process)
    group_kills: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: group_kills.append((pid, sig)))

    with pytest.raises(SystemExit) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value is shutdown
    assert group_kills == [
        (process.pid, signal.SIGKILL),
        (process.pid, signal.SIGKILL),
        (process.pid, signal.SIGKILL),
    ]
    assert process.kill_calls == 3
    assert process.active is False
    assert process.reaped is True
    assert len(process.communicate_timeouts) == 1
    assert len(process.wait_timeouts) == 3


def test_youtube_curl_transport_fails_closed_when_cleanup_control_flow_is_not_reaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interrupt = KeyboardInterrupt("shutdown requested")
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[subprocess.TimeoutExpired("curl", 27)],
        wait_effects=[
            interrupt,
            subprocess.TimeoutExpired("curl", 0.4),
            RuntimeError("cleanup wait failed"),
            subprocess.TimeoutExpired("curl", 0.4),
        ],
        poll_effects=[None, None, None, None],
    )
    group_kills: list[tuple[int, signal.Signals]] = []
    moments = iter((0.0, 0.0, 27.1, 27.2, 27.3, 27.4))
    _install_fixture_curl(monkeypatch, process)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: group_kills.append((pid, sig)))
    monkeypatch.setattr(
        "pokecrack_worker.collectors.official_api.youtube.monotonic",
        lambda: next(moments),
    )

    with pytest.raises(KeyboardInterrupt) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value is interrupt
    assert group_kills == [(process.pid, signal.SIGKILL)] * 4
    assert process.kill_calls == 4
    assert process.reaped is False
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_fails_closed_when_initial_control_flow_is_not_reaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interrupt = KeyboardInterrupt("shutdown requested")
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[interrupt],
        wait_effects=[subprocess.TimeoutExpired("curl", 0.4)] * 4,
        poll_effects=[None, None, None, None],
    )
    moments = iter((0.0, 0.0, 27.1, 27.2, 27.3, 27.4))
    _install_fixture_curl(monkeypatch, process)
    monkeypatch.setattr(os, "killpg", lambda _pid, _sig: None)
    monkeypatch.setattr(
        "pokecrack_worker.collectors.official_api.youtube.monotonic",
        lambda: next(moments),
    )

    with pytest.raises(KeyboardInterrupt) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value is interrupt
    assert process.kill_calls == 4
    assert process.reaped is False
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_retries_when_cleanup_clock_is_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock_interrupt = KeyboardInterrupt("shutdown requested")
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[subprocess.TimeoutExpired("curl", 27)],
    )
    clock_effects = iter((0.0, 0.0, clock_interrupt, 27.2, 27.3))

    def interrupted_clock() -> float:
        effect = next(clock_effects)
        if isinstance(effect, BaseException):
            raise effect
        assert isinstance(effect, float)
        return effect

    _install_fixture_curl(monkeypatch, process)
    monkeypatch.setattr(
        "pokecrack_worker.collectors.official_api.youtube.monotonic",
        interrupted_clock,
    )

    with pytest.raises(KeyboardInterrupt) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value is clock_interrupt
    assert process.kill_calls == 2
    assert process.reaped is True
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_fails_closed_when_reap_finishes_after_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cleanup_interrupt = KeyboardInterrupt("shutdown requested")
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[subprocess.TimeoutExpired("curl", 27)],
        wait_effects=[cleanup_interrupt, -9],
        poll_effects=[None],
    )
    moments = iter((0.0, 0.0, 27.1, 27.2, 29.1))
    _install_fixture_curl(monkeypatch, process)
    monkeypatch.setattr(
        "pokecrack_worker.collectors.official_api.youtube.monotonic",
        lambda: next(moments),
    )

    with pytest.raises(KeyboardInterrupt) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value is cleanup_interrupt
    assert process.kill_calls == 2
    assert process.reaped is True
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_classifies_confirmed_late_reap_as_normal_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[subprocess.TimeoutExpired("curl", 27)],
        wait_effects=[-9],
    )
    moments = iter((0.0, 0.0, 27.1, 29.1))
    _install_fixture_curl(monkeypatch, process)
    monkeypatch.setattr(
        "pokecrack_worker.collectors.official_api.youtube.monotonic",
        lambda: next(moments),
    )

    with pytest.raises(YouTubeError) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value.code == "deadline_cleanup_failed"
    assert raised.value.retryable is False
    assert process.reaped is True
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_uses_fatal_boundary_for_unreaped_ordinary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[RuntimeError("fixture-key must not cross the boundary")],
        wait_effects=[subprocess.TimeoutExpired("curl", 0.4)] * 4,
        poll_effects=[None, None, None, None],
    )
    moments = iter((0.0, 0.0, 27.1, 27.2, 27.3, 27.4))
    _install_fixture_curl(monkeypatch, process)
    monkeypatch.setattr(os, "killpg", lambda _pid, _sig: None)
    monkeypatch.setattr(
        "pokecrack_worker.collectors.official_api.youtube.monotonic",
        lambda: next(moments),
    )

    with pytest.raises(YouTubeRequestStateUnknown) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert str(raised.value) == "youtube_request_state_unknown"
    assert process.reaped is False
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_sanitizes_unexpected_failure_after_successful_reap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[RuntimeError("fixture-key must not cross the job boundary")],
    )
    _install_fixture_curl(monkeypatch, process)

    with pytest.raises(YouTubeError) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value.code == "network_error"
    assert raised.value.retryable is True
    assert process.active is False
    assert process.reaped is True
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_never_resignals_a_reaped_pid_after_control_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interrupt = KeyboardInterrupt("shutdown after pipe cleanup")
    process = FixtureCurlProcess(returncode=0)
    _install_fixture_curl(monkeypatch, process)
    group_kills: list[tuple[int, signal.Signals]] = []

    def fail_after_reap(*_args: object, **_kwargs: object) -> tuple[bytes, bytes]:
        process.wait()
        raise interrupt

    monkeypatch.setattr(youtube_module, "_bounded_exchange", fail_after_reap)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: group_kills.append((pid, sig)))

    with pytest.raises(KeyboardInterrupt) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value is interrupt
    assert group_kills == []
    assert process.kill_calls == 0
    assert process.reaped is True


def test_youtube_curl_transport_sanitizes_post_reap_failure_without_resignaling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(returncode=0)
    _install_fixture_curl(monkeypatch, process)
    group_kills: list[tuple[int, signal.Signals]] = []

    def fail_after_reap(*_args: object, **_kwargs: object) -> tuple[bytes, bytes]:
        process.wait()
        raise RuntimeError("fixture-key must not cross the boundary")

    monkeypatch.setattr(youtube_module, "_bounded_exchange", fail_after_reap)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: group_kills.append((pid, sig)))

    with pytest.raises(YouTubeError) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value.code == "network_error"
    assert raised.value.retryable is True
    assert group_kills == []
    assert process.kill_calls == 0
    assert process.reaped is True
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_cleanup_rechecks_reap_state_before_each_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_shutdown = SystemExit(23)
    second_interrupt = KeyboardInterrupt("poll interrupted during shutdown")
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[subprocess.TimeoutExpired("curl", 27)],
    )
    _install_fixture_curl(monkeypatch, process)
    group_kills: list[tuple[int, signal.Signals]] = []

    def wait_after_reap(timeout: float | None = None) -> int:
        process.wait_timeouts.append(timeout)
        # Model waitpid() having collected the child before CPython publishes
        # Popen.returncode. A control-flow exception can land in that window.
        process.reaped = True
        raise first_shutdown

    poll_calls = 0

    def interrupted_poll() -> int | None:
        nonlocal poll_calls
        poll_calls += 1
        if poll_calls == 1:
            return None
        if poll_calls == 2:
            raise second_interrupt
        process.returncode = 0
        return process.returncode

    process.wait = wait_after_reap  # type: ignore[method-assign]
    process.poll = interrupted_poll  # type: ignore[method-assign]
    monkeypatch.setattr(os, "killpg", lambda pid, sig: group_kills.append((pid, sig)))

    with pytest.raises(SystemExit) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value is first_shutdown
    assert group_kills == [(process.pid, signal.SIGKILL)]
    assert process.kill_calls == 1
    assert poll_calls == 3
    assert process.reaped is True


@pytest.mark.skipif(
    not all(hasattr(signal, name) for name in ("SIGALRM", "ITIMER_REAL", "getitimer", "setitimer")),
    reason="POSIX real-time timers are unavailable",
)
def test_youtube_curl_transport_preserves_existing_process_timer_and_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alarm = signal.SIGALRM
    timer = signal.ITIMER_REAL
    original_handler = signal.getsignal(alarm)
    original_timer = signal.getitimer(timer)
    test_started = time.monotonic()
    observed_signals: list[int] = []

    def existing_handler(signum: int, _frame: object) -> None:
        observed_signals.append(signum)

    _install_fixture_curl(monkeypatch, FixtureCurlProcess())
    try:
        signal.signal(alarm, existing_handler)
        signal.setitimer(timer, 60.0, 10.0)
        response = HTTPXYouTubeTransport().get(
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


def test_youtube_curl_transport_fails_closed_when_curl_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "Popen", unavailable)

    with pytest.raises(YouTubeError) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value.code == "transport_unavailable"
    assert raised.value.retryable is False
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_fails_closed_on_unsupported_process_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = FixturePopenFactory(FixtureCurlProcess())
    monkeypatch.setattr(subprocess, "Popen", factory)
    monkeypatch.setattr(
        "pokecrack_worker.collectors.official_api.youtube._PROCESS_DEADLINE_SUPPORTED",
        False,
    )

    with pytest.raises(YouTubeError) as raised:
        HTTPXYouTubeTransport().get(
            YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-key"),
            timeout_seconds=30,
        )

    assert raised.value.code == "absolute_deadline_unavailable"
    assert raised.value.retryable is False
    assert factory.calls == []


def test_youtube_curl_transport_fixes_network_boundaries_and_hides_key_from_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(stderr=_curl_metadata(status=302, content_length="0"))
    factory = _install_fixture_curl(monkeypatch, process)

    response = HTTPXYouTubeTransport().get(
        YOUTUBE_SEARCH_URL,
        params={"part": "snippet"},
        api_key=SecretStr("fixture-key"),
        timeout_seconds=30,
    )

    command, options = factory.calls[0]
    assert response.status_code == 302
    assert command[0] == "/usr/bin/curl"
    assert command[1] == "--disable"
    assert command[command.index("--proto") + 1] == "=https"
    assert command[command.index("--proxy") + 1] == ""
    assert command[command.index("--noproxy") + 1] == "*"
    assert command[command.index("--max-redirs") + 1] == "0"
    assert command[command.index("--connect-timeout") + 1] == "10"
    assert command[command.index("--max-time") + 1] == "27"
    assert "Accept-Encoding: identity" in command
    assert "--location" not in command
    assert command[-1] == f"{YOUTUBE_SEARCH_URL}?part=snippet"
    assert options["start_new_session"] is True
    assert options["close_fds"] is True
    assert options["env"] == {"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"}
    assert process.communicate_inputs == [b"X-Goog-Api-Key: fixture-key\n"]
    assert "fixture-key" not in repr(command)
    assert "fixture-key" not in repr(options)


def test_maton_youtube_transport_uses_fixed_gateway_and_stdin_only_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection_id = "ba16a50a-9e24-4fb6-9ce3-6cf7d52643da"
    process = FixtureCurlProcess(stderr=_curl_metadata(status=200, content_length="2"))
    factory = _install_fixture_curl(monkeypatch, process)

    response = MatonYouTubeTransport(connection_id=connection_id).get(
        YOUTUBE_SEARCH_URL,
        params={"part": "snippet"},
        api_key=SecretStr("fixture-maton-secret"),
        timeout_seconds=30,
    )

    command, options = factory.calls[0]
    assert response.status_code == 200
    assert command[-1] == f"{MATON_YOUTUBE_SEARCH_URL}?part=snippet"
    assert process.communicate_inputs == [
        (f"Authorization: Bearer fixture-maton-secret\nMaton-Connection: {connection_id}\n").encode(
            "ascii"
        )
    ]
    assert "fixture-maton-secret" not in repr(command)
    assert connection_id not in repr(command)
    assert options["env"] == {"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"}

    with pytest.raises(ValueError, match="fixed search endpoint"):
        MatonYouTubeTransport(connection_id=connection_id).get(
            MATON_YOUTUBE_SEARCH_URL,
            params={},
            api_key=SecretStr("fixture-maton-secret"),
            timeout_seconds=30,
        )


@pytest.mark.parametrize(
    "connection_id",
    ("", "not-a-uuid", "BA16A50A-9E24-4FB6-9CE3-6CF7D52643DA"),
)
def test_maton_youtube_transport_rejects_noncanonical_connection_id(
    connection_id: str,
) -> None:
    with pytest.raises(ValueError, match="canonical UUID"):
        MatonYouTubeTransport(connection_id=connection_id)
