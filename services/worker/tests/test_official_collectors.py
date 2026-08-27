from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

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
    wait_effect: BaseException | int | None = None
    communicate_inputs: list[bytes | None] = field(default_factory=list)
    communicate_timeouts: list[float | None] = field(default_factory=list)
    wait_timeouts: list[float | None] = field(default_factory=list)
    active: bool = True
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
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeouts.append(timeout)
        if isinstance(self.wait_effect, BaseException):
            raise self.wait_effect
        self.active = False
        return self.wait_effect or self.returncode or 0


@dataclass
class FixturePopenFactory:
    process: FixtureCurlProcess
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = field(default_factory=list)

    def __call__(self, command: tuple[str, ...], **kwargs: object) -> FixtureCurlProcess:
        self.calls.append((command, kwargs))
        return self.process


def test_youtube_curl_transport_rejects_response_over_byte_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(stdout=b"x" * 64, returncode=63)
    factory = FixturePopenFactory(process)
    monkeypatch.setattr(subprocess, "Popen", factory)

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
    factory = FixturePopenFactory(process)
    monkeypatch.setattr(subprocess, "Popen", factory)
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
    monkeypatch.setattr(subprocess, "Popen", FixturePopenFactory(process))
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
    assert len(process.communicate_timeouts) == 2
    assert process.communicate_timeouts[0] is not None
    assert 26.0 < process.communicate_timeouts[0] <= 27.0
    assert process.communicate_timeouts[1] is not None
    assert process.communicate_timeouts[1] <= 30.0
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_fails_closed_if_reaping_stalls_at_hard_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(
        returncode=None,
        communicate_effects=[
            subprocess.TimeoutExpired("curl", 27),
            subprocess.TimeoutExpired("curl", 1.5),
        ],
        wait_effect=subprocess.TimeoutExpired("curl", 0.2),
    )
    factory = FixturePopenFactory(process)
    moments = iter((0.0, 0.0, 27.5, 28.8, 29.1))
    monkeypatch.setattr(subprocess, "Popen", factory)
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
    assert process.kill_calls == 2
    assert process.active is False
    assert process.wait_timeouts == [pytest.approx(0.2)]
    assert "fixture-key" not in repr(raised.value)


def test_youtube_curl_transport_reaps_process_group_before_propagating_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interrupt = KeyboardInterrupt("shutdown requested")
    process = FixtureCurlProcess(
        communicate_effects=[interrupt, RuntimeError("cleanup pipe failed")]
    )
    factory = FixturePopenFactory(process)
    group_kills: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(subprocess, "Popen", factory)
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
    ]
    assert process.kill_calls == 2
    assert process.active is False
    assert len(process.communicate_timeouts) == 2


def test_youtube_curl_transport_reaps_unexpected_communicate_failure_and_sanitizes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FixtureCurlProcess(
        communicate_effects=[RuntimeError("fixture-key must not cross the job boundary")]
    )
    factory = FixturePopenFactory(process)
    group_kills: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(subprocess, "Popen", factory)
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
    assert group_kills == [(process.pid, signal.SIGKILL)]
    assert process.kill_calls == 1
    assert process.active is False
    assert len(process.communicate_timeouts) == 2
    assert "fixture-key" not in repr(raised.value)


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

    monkeypatch.setattr(subprocess, "Popen", FixturePopenFactory(FixtureCurlProcess()))
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
    factory = FixturePopenFactory(process)
    monkeypatch.setattr(subprocess, "Popen", factory)

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
