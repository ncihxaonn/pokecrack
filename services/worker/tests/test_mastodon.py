from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pokecrack_worker.collectors.official_api.mastodon import (
    MASTODON_MAX_RESPONSE_BYTES,
    HTTPXMastodonTransport,
    MastodonHTTPError,
    MastodonInvalidResponse,
    MastodonPreflightError,
    MastodonPublicHashtagCollector,
    MastodonRateLimited,
    MastodonRequestLimiter,
    MastodonStatus,
    _hashtag_url,
    _validate_transport_url,
    parse_mastodon_status,
)
from pokecrack_worker.collectors.official_api.postgres import (
    BEGIN_MASTODON_PUBLIC_HASHTAG_SQL,
    RECORD_MASTODON_RATE_LIMIT_SQL,
    MastodonRequestDeferred,
    PostgresMastodonPublicHashtagGate,
)
from pokecrack_worker.collectors.official_api.tcgdex import APIResponse
from pokecrack_worker.composition import (
    MASTODON_PUBLIC_HASHTAG_JOB_TYPE,
    LiveCompositionError,
    live_schedule_entries,
    require_worker_job_types,
    write_health_heartbeat,
)
from pokecrack_worker.config.mastodon import (
    MASTODON_APPROVED_TAGS,
    MASTODON_TAG_KEYS,
    MASTODON_TAG_ROWS,
    MastodonInstance,
    MastodonRegistry,
)
from pokecrack_worker.config.settings import Settings
from pokecrack_worker.jobs import (
    LeaseLostError,
    MastodonPublicHashtagCompletion,
    MastodonStatusWrite,
)

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 31, 4, 0, tzinfo=UTC)
RESET = "2026-09-01T00:00:00Z"


def _headers(*, remaining: int = 59, reset: str = RESET) -> dict[str, str]:
    return {
        "content-type": "application/json",
        "x-ratelimit-limit": "60",
        "x-ratelimit-remaining": str(remaining),
        "x-ratelimit-reset": reset,
    }


def _preflight(
    *, domain: str = "mastodon.social", local: str = "public", remote: str = "public"
) -> bytes:
    return json.dumps(
        {
            "domain": domain,
            "configuration": {
                "timelines_access": {"hashtag_feeds": {"local": local, "remote": remote}}
            },
        },
        separators=(",", ":"),
    ).encode()


def _status(
    status_id: str,
    *,
    tag: str = "pokemontcg",
    visibility: str = "public",
    reblog: object = None,
    created_at: str = "2026-08-31T03:59:00Z",
    tags: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    # These values deliberately look like fields that must never cross the
    # parser boundary.  A fixture regression must not make them appear in a
    # candidate or completion DTO.
    return {
        "id": status_id,
        "created_at": created_at,
        "visibility": visibility,
        "reblog": reblog,
        "tags": tags if tags is not None else [{"name": tag}],
        "content": "PRIVATE_CONTENT_SHOULD_NOT_ESCAPE",
        "account": {"acct": "private-handle", "id": "private-did"},
        "media_attachments": [{"url": "https://private.invalid/media"}],
        "url": "https://private.invalid/status/opaque",
        "uri": "https://private.invalid/@private/opaque",
        "location": "private location",
        "product": "private product",
        "opening": "private opening",
        "pack_count": 99,
        "hit_count": 99,
    }


class FixtureTransport:
    def __init__(self, *responses: APIResponse) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> APIResponse:
        assert connect_timeout_seconds == 10
        assert read_timeout_seconds == 15
        self.calls.append((url, dict(headers)))
        if not self.responses:
            raise AssertionError(f"unexpected fixture request: {url}")
        return self.responses.pop(0)


def _response(
    value: object, *, headers: Mapping[str, str] | None = None, status: int = 200
) -> APIResponse:
    return APIResponse(
        status,
        dict(headers or _headers()),
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(),
    )


def _collector(*responses: APIResponse) -> tuple[MastodonPublicHashtagCollector, FixtureTransport]:
    transport = FixtureTransport(*responses)
    # Keep fixture tests instant while still exercising the limiter call on
    # every request. Production collectors use a per-collector real limiter;
    # cross-worker pacing is enforced by the fenced database gate.
    limiter = MastodonRequestLimiter(clock=lambda: 0.0, sleeper=lambda _seconds: None)
    return (
        MastodonPublicHashtagCollector(
            transport=transport,
            registry=MastodonRegistry.from_yaml(ROOT / "config" / "mastodon.yaml"),
            limiter=limiter,
            clock=lambda: NOW,
        ),
        transport,
    )


def test_reviewed_registry_has_exact_keys_values_and_deterministic_matching() -> None:
    registry = MastodonRegistry.from_yaml(ROOT / "config" / "mastodon.yaml")

    assert tuple((tag.key, tag.value) for tag in registry.tags) == MASTODON_TAG_ROWS
    assert registry.instances == (MastodonInstance(),)
    assert registry.default_enabled is False
    assert registry.protocol == "rest"
    assert MASTODON_APPROVED_TAGS == tuple(value for _key, value in MASTODON_TAG_ROWS)
    assert tuple(registry.approved_tags) == MASTODON_TAG_KEYS
    assert registry.matched_tag_keys(
        [
            {"name": "寶可夢卡牌"},
            {"name": "pokemontcg"},
            {"name": "ポケカ"},
            {"name": "pokemontcg"},
        ]
    ) == ("pokemontcg", "pokeca_ja", "pokemon_card_zh_hant")
    with pytest.raises(ValueError, match="not approved"):
        registry.require_tag("arbitrary")


def test_status_parser_keeps_only_approved_activity_fields() -> None:
    parsed = parse_mastodon_status(_status("opaque-001"), now=NOW)

    assert parsed == MastodonStatus(
        status_id="opaque-001",
        status_key_sha256=hashlib.sha256(b"mastodon_social\nopaque-001").hexdigest(),
        published_at=datetime(2026, 8, 31, 3, 59, tzinfo=UTC),
        matched_tags=("pokemontcg",),
    )
    assert set(parsed.__slots__) == {
        "status_id",
        "status_key_sha256",
        "published_at",
        "matched_tags",
    }
    serialized = repr(parsed)
    for secret in (
        "PRIVATE_CONTENT_SHOULD_NOT_ESCAPE",
        "private-handle",
        "private-did",
        "private.invalid",
        "private location",
        "private product",
        "private opening",
    ):
        assert secret not in serialized


@pytest.mark.parametrize(
    "raw",
    (
        _status("opaque-private", visibility="private"),
        _status("opaque-reblog", reblog={"id": "nested"}),
        {**_status("opaque-missing-id"), "id": None},
    ),
)
def test_parser_rejects_non_public_or_non_opaque_statuses(raw: dict[str, object]) -> None:
    with pytest.raises(MastodonInvalidResponse):
        parse_mastodon_status(raw, now=NOW)


def test_url_builder_uses_base_path_once_and_transport_rejects_arbitrary_queries() -> None:
    instance = MastodonInstance()
    url = _hashtag_url(instance, "ポケカ", min_id="001")
    assert url == (
        "https://mastodon.social/api/v1/timelines/tag/%E3%83%9D%E3%82%B1%E3%82%AB"
        "?limit=40&min_id=001"
    )
    assert "https://mastodon.social/https://" not in url
    _validate_transport_url(url)
    with pytest.raises(ValueError, match="not approved"):
        _hashtag_url(instance, "arbitrary", min_id=None)
    with pytest.raises(ValueError):
        _validate_transport_url(url + "&unexpected=1")
    with pytest.raises(ValueError):
        _validate_transport_url("https://mastodon.social/api/v2/instance?x=1")
    with pytest.raises(ValueError):
        _validate_transport_url("https://other.invalid/api/v2/instance")


def test_transport_rejects_auth_proxy_and_non_identity_controls_before_network() -> None:
    transport = HTTPXMastodonTransport()
    fixed = "https://mastodon.social/api/v2/instance"
    with pytest.raises(ValueError, match="authentication"):
        transport.get(
            fixed,
            headers={"Authorization": "Bearer secret"},
            connect_timeout_seconds=10,
            read_timeout_seconds=15,
        )
    with pytest.raises(ValueError, match="identity"):
        transport.get(
            fixed,
            headers={"Accept-Encoding": "gzip"},
            connect_timeout_seconds=10,
            read_timeout_seconds=15,
        )


def test_transport_rejects_user_agent_override_and_collector_sends_fixed_identity() -> None:
    transport = HTTPXMastodonTransport()
    fixed = "https://mastodon.social/api/v2/instance"
    with pytest.raises(ValueError, match="fixed User-Agent"):
        transport.get(
            fixed,
            headers={"User-Agent": "caller-controlled"},
            connect_timeout_seconds=10,
            read_timeout_seconds=15,
        )

    collector, fixture = _collector(
        _response(_preflight_payload()),
        APIResponse(302, {"location": "https://other.invalid/"}, b"redirect"),
    )
    with pytest.raises(MastodonHTTPError):
        collector.collect(
            instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
        )
    assert fixture.calls[0][1]["User-Agent"] == (
        "PokecrackMetadataCollector/0.1 (+https://pokecrack.vercel.app)"
    )


def test_request_limiter_enforces_two_second_spacing_for_the_full_instance() -> None:
    clock_value = 0.0
    sleeps: list[float] = []

    def clock() -> float:
        return clock_value

    def sleep(seconds: float) -> None:
        nonlocal clock_value
        sleeps.append(seconds)
        clock_value += seconds

    limiter = MastodonRequestLimiter(clock=clock, sleeper=sleep)
    limiter.wait()
    limiter.wait()
    limiter.wait()

    assert sleeps == [2.0, 2.0]


@pytest.mark.parametrize(
    "preflight",
    (
        _preflight(domain="other.invalid"),
        _preflight(local="private"),
        _preflight(remote="private"),
    ),
)
def test_preflight_is_exact_and_fail_closed(preflight: bytes) -> None:
    collector, transport = _collector(
        APIResponse(200, _headers(), preflight),
    )

    with pytest.raises(MastodonPreflightError):
        collector.collect(
            instance_key="mastodon_social", tag_key="pokeca_ja", start_status_id=None, now=NOW
        )
    assert len(transport.calls) == 1


def test_redirect_status_is_not_followed_or_treated_as_data() -> None:
    collector, transport = _collector(
        APIResponse(302, {"location": "https://other.invalid/"}, b"redirect"),
    )

    with pytest.raises(MastodonHTTPError) as raised:
        collector.collect(
            instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
        )
    assert raised.value.status_code == 302
    assert len(transport.calls) == 1


def test_opaque_no_link_pagination_advances_past_irrelevant_rows() -> None:
    collector, transport = _collector(
        _response(_preflight_payload(), headers=_headers(remaining=59)),
        _response(
            [
                _status("001", tag="other"),
                _status("opaque-002", visibility="private"),
            ],
            headers=_headers(remaining=58),
        ),
        _response([], headers=_headers(remaining=57)),
    )

    result = collector.collect(
        instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
    )
    assert result.candidates == ()
    assert result.statuses_seen == 2
    assert result.end_status_id == "opaque-002"
    assert result.incomplete is True  # the private row is safely skipped, not replayed
    assert "min_id=opaque-002" in transport.calls[2][0]


def test_link_cursor_requires_same_origin_exact_limit_and_forward_progress() -> None:
    next_url = "https://mastodon.social/api/v1/timelines/tag/pokemontcg?limit=40&min_id=opaque-next"
    older_url = "https://mastodon.social/api/v1/timelines/tag/pokemontcg?limit=40&max_id=opaque-old"
    collector, transport = _collector(
        _response(_preflight_payload()),
        _response(
            [_status("opaque-first")],
            headers={
                **_headers(remaining=58),
                "link": f'<{older_url}>; rel="next", <{next_url}>; rel="prev"',
            },
        ),
        _response([], headers=_headers(remaining=57)),
    )

    result = collector.collect(
        instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
    )
    assert result.end_status_id == "opaque-first"
    assert transport.calls[2][0] == next_url

    for link in (
        '<https://other.invalid/api/v1/timelines/tag/pokemontcg?limit=40&min_id=x>; rel="prev"',
        '<https://mastodon.social/api/v1/timelines/tag/pokemontcg?min_id=x>; rel="prev"',
        '<https://mastodon.social/api/v1/timelines/tag/pokemontcg?limit=40&min_id=x&min_id=y>; rel="prev"',
        '<https://mastodon.social/api/v1/timelines/tag/pokemontcg?limit=40&min_id=x>; rel="prev", '
        '<https://mastodon.social/api/v1/timelines/tag/pokemontcg?limit=40&min_id=y>; rel="prev"',
    ):
        collector, _transport = _collector(
            _response(_preflight_payload()),
            _response([_status("opaque-first")], headers={**_headers(), "link": link}),
        )
        with pytest.raises(MastodonInvalidResponse):
            collector.collect(
                instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
            )


def test_bounds_cover_pages_statuses_bytes_and_deterministic_empty_cursor() -> None:
    too_many = [_status(f"status-{index:02d}") for index in range(41)]
    collector, _transport = _collector(_response(_preflight_payload()), _response(too_many))
    with pytest.raises(MastodonInvalidResponse, match="page_status_limit"):
        collector.collect(
            instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
        )

    collector, _transport = _collector(
        _response(_preflight_payload()),
        APIResponse(200, _headers(), b"x" * (MASTODON_MAX_RESPONSE_BYTES + 1)),
    )
    with pytest.raises(MastodonInvalidResponse, match="run_response_too_large"):
        collector.collect(
            instance_key="mastodon_social",
            tag_key="pokemontcg",
            start_status_id="opaque-start",
            now=NOW,
        )

    collector, transport = _collector(
        _response(_preflight_payload()),
        _response([], headers=_headers(remaining=58)),
    )
    result = collector.collect(
        instance_key="mastodon_social",
        tag_key="pokemontcg",
        start_status_id="opaque-start",
        now=NOW,
    )
    assert result.end_status_id == "opaque-start"
    assert result.requests_made == 1
    assert result.statuses_seen == 0
    assert transport.calls[1][0].endswith("?limit=40&min_id=opaque-start")


def test_rate_limit_zero_stops_without_a_third_request_and_429_is_retryable() -> None:
    collector, transport = _collector(
        _response(_preflight_payload(), headers=_headers(remaining=59)),
        _response([_status("opaque-first")], headers=_headers(remaining=0)),
    )
    result = collector.collect(
        instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
    )
    assert result.incomplete is True
    assert result.requests_made == 1
    assert len(transport.calls) == 2

    collector, _transport = _collector(
        _response(_preflight_payload()),
        APIResponse(429, {"x-ratelimit-reset": RESET}, b"rate limited"),
    )
    with pytest.raises(MastodonRateLimited) as raised:
        collector.collect(
            instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
        )
    assert raised.value.retry_at == datetime(2026, 9, 1, tzinfo=UTC)

    collector, _transport = _collector(
        _response(_preflight_payload()),
        APIResponse(429, {"retry-after": "120"}, b"rate limited"),
    )
    with pytest.raises(MastodonRateLimited) as raised:
        collector.collect(
            instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
        )
    assert raised.value.retry_at == NOW + timedelta(seconds=120)

    collector, _transport = _collector(
        _response(_preflight_payload()),
        APIResponse(429, {"retry-after": "not-a-date"}, b"rate limited"),
    )
    with pytest.raises(MastodonInvalidResponse, match="retry_after_invalid"):
        collector.collect(
            instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
        )

    collector, _transport = _collector(
        _response(_preflight_payload()),
        APIResponse(429, {}, b"rate limited"),
    )
    with pytest.raises(MastodonInvalidResponse, match="retry_after_missing"):
        collector.collect(
            instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
        )

    collector, _transport = _collector(
        _response(_preflight_payload()),
        _response(
            [_status("opaque-first")],
            headers={
                "content-type": "application/json",
                "x-ratelimit-remaining": "0",
            },
        ),
    )
    with pytest.raises(MastodonInvalidResponse, match="reset_missing"):
        collector.collect(
            instance_key="mastodon_social", tag_key="pokemontcg", start_status_id=None, now=NOW
        )


def test_numeric_retry_after_starts_when_the_slow_response_is_received() -> None:
    transport = FixtureTransport(
        _response(_preflight_payload()),
        APIResponse(429, {"retry-after": "120"}, b"rate limited"),
    )
    response_times = iter((NOW, NOW + timedelta(seconds=20)))
    collector = MastodonPublicHashtagCollector(
        transport=transport,
        registry=MastodonRegistry.from_yaml(ROOT / "config" / "mastodon.yaml"),
        limiter=MastodonRequestLimiter(clock=lambda: 0.0, sleeper=lambda _seconds: None),
        clock=lambda: next(response_times),
    )

    with pytest.raises(MastodonRateLimited) as raised:
        collector.collect(
            instance_key="mastodon_social",
            tag_key="pokemontcg",
            start_status_id=None,
            now=NOW,
        )

    assert raised.value.retry_at == NOW + timedelta(seconds=140)


def test_numeric_retry_after_on_timeline_uses_that_response_time() -> None:
    transport = FixtureTransport(
        _response(_preflight_payload()),
        APIResponse(429, {"retry-after": "120"}, b"rate limited"),
    )
    response_times = iter((NOW, NOW + timedelta(seconds=20)))
    collector = MastodonPublicHashtagCollector(
        transport=transport,
        registry=MastodonRegistry.from_yaml(ROOT / "config" / "mastodon.yaml"),
        limiter=MastodonRequestLimiter(clock=lambda: 0.0, sleeper=lambda _seconds: None),
        clock=lambda: next(response_times),
    )

    with pytest.raises(MastodonRateLimited) as raised:
        collector.collect(
            instance_key="mastodon_social",
            tag_key="pokemontcg",
            start_status_id=None,
            now=NOW,
        )

    assert raised.value.retry_at == NOW + timedelta(seconds=140)


def test_completion_payload_is_exact_replay_safe_and_activity_only() -> None:
    candidate = MastodonStatusWrite(
        status_id="opaque-001",
        status_key_sha256=hashlib.sha256(b"mastodon_social\nopaque-001").hexdigest(),
        published_at=NOW - timedelta(minutes=1),
        matched_tags=("pokemontcg", "pokeca_ja"),
    )
    completion = MastodonPublicHashtagCompletion(
        instance_key="mastodon_social",
        tag_key="pokemontcg",
        start_status_id=None,
        end_status_id="opaque-001",
        incomplete=False,
        requests_made=1,
        statuses_seen=1,
        bytes_seen=128,
        candidates=(candidate,),
        rate_limit_limit=60,
        rate_limit_remaining=59,
        rate_limit_reset_at=NOW + timedelta(hours=1),
    )
    payload = completion.as_payload()
    assert set(payload) == {
        "version",
        "instance_key",
        "tag_key",
        "start_status_id",
        "end_status_id",
        "incomplete",
        "requests_made",
        "statuses_seen",
        "bytes_seen",
        "candidates",
        "rate_limit_limit",
        "rate_limit_remaining",
        "rate_limit_reset_at",
    }
    assert set(payload["candidates"][0]) == {
        "status_id",
        "status_key_sha256",
        "published_at",
        "matched_tags",
        "activity_only",
        "statistics_eligible",
    }
    assert payload["candidates"][0]["activity_only"] is True
    assert payload["candidates"][0]["statistics_eligible"] is False
    assert "PRIVATE_CONTENT" not in json.dumps(payload)
    with pytest.raises(ValueError, match="matched tags"):
        MastodonStatusWrite(
            status_id="opaque-002",
            status_key_sha256=hashlib.sha256(b"mastodon_social\nopaque-002").hexdigest(),
            published_at=NOW,
            matched_tags=("pokeca_ja", "pokemontcg"),
        )
    nonmatching = MastodonStatusWrite(
        status_id="opaque-003",
        status_key_sha256=hashlib.sha256(b"mastodon_social\nopaque-003").hexdigest(),
        published_at=NOW,
        matched_tags=("pokeca_ja",),
    )
    with pytest.raises(ValueError, match="requested tag"):
        MastodonPublicHashtagCompletion(
            instance_key="mastodon_social",
            tag_key="pokemontcg",
            start_status_id=None,
            end_status_id="opaque-003",
            incomplete=False,
            requests_made=1,
            statuses_seen=1,
            bytes_seen=1,
            candidates=(nonmatching,),
        )
    with pytest.raises(ValueError, match="empty completion"):
        MastodonPublicHashtagCompletion(
            instance_key="mastodon_social",
            tag_key="pokemontcg",
            start_status_id="opaque-start",
            end_status_id="opaque-end",
            incomplete=True,
            requests_made=0,
            statuses_seen=0,
            bytes_seen=0,
        )
    with pytest.raises(ValueError, match="exhausted rate limit"):
        MastodonPublicHashtagCompletion(
            instance_key="mastodon_social",
            tag_key="pokemontcg",
            start_status_id=None,
            end_status_id=None,
            incomplete=True,
            requests_made=0,
            statuses_seen=0,
            bytes_seen=0,
            rate_limit_remaining=0,
        )


class RecordingExecutor:
    def __init__(self, responses: Sequence[Sequence[Mapping[str, Any]]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    def query(self, sql: str, params: Mapping[str, object]) -> Sequence[Mapping[str, Any]]:
        self.calls.append((sql, dict(params)))
        return self.responses.pop(0) if self.responses else ()


def test_postgres_gate_signature_and_opaque_checkpoint_are_exact() -> None:
    executor = RecordingExecutor(
        [
            [
                {
                    "acquired": True,
                    "retry_at": None,
                    "start_status_id": "opaque-001",
                    "cooldown_until": NOW,
                }
            ]
        ]
    )
    checkpoint = PostgresMastodonPublicHashtagGate(executor).begin(
        job_id="00000000-0000-0000-0000-000000000001",
        worker_id="worker-1",
        lease_generation=1,
        instance_key="mastodon_social",
        tag_key="pokemontcg",
    )
    assert checkpoint.last_status_id == "opaque-001"
    sql, params = executor.calls[0]
    assert sql == BEGIN_MASTODON_PUBLIC_HASHTAG_SQL
    assert params["instance_key"] == "mastodon_social"
    assert params["tag_key"] == "pokemontcg"
    assert "begin_mastodon_public_hashtag_job(" in sql

    deferred = RecordingExecutor([[{"acquired": False, "retry_at": NOW}]])
    with pytest.raises(MastodonRequestDeferred):
        PostgresMastodonPublicHashtagGate(deferred).begin(
            job_id="00000000-0000-0000-0000-000000000001",
            worker_id="worker-1",
            lease_generation=1,
            instance_key="mastodon_social",
            tag_key="pokemontcg",
        )

    recorder = RecordingExecutor([[{"recorded": True}]])
    PostgresMastodonPublicHashtagGate(recorder).record_rate_limit(
        job_id="00000000-0000-0000-0000-000000000001",
        worker_id="worker-1",
        lease_generation=1,
        retry_at=NOW + timedelta(minutes=2),
    )
    sql, params = recorder.calls[0]
    assert sql == RECORD_MASTODON_RATE_LIMIT_SQL
    assert params["retry_at"] == NOW + timedelta(minutes=2)

    not_recorded = RecordingExecutor([[{"recorded": False}]])
    with pytest.raises(LeaseLostError):
        PostgresMastodonPublicHashtagGate(not_recorded).record_rate_limit(
            job_id="00000000-0000-0000-0000-000000000001",
            worker_id="worker-1",
            lease_generation=1,
            retry_at=NOW + timedelta(minutes=2),
        )


def test_toggle_schedule_and_readiness_contracts_are_fail_closed() -> None:
    disabled = Settings(
        _env_file=None,
        data_mode="live",
        supabase_db_url="postgresql://db.example.invalid/pokecrack",
        worker_role="collector",
    )
    assert disabled.mastodon_collection_enabled is False
    assert MASTODON_PUBLIC_HASHTAG_JOB_TYPE not in require_worker_job_types(disabled)

    enabled = Settings(
        _env_file=None,
        data_mode="live",
        supabase_db_url="postgresql://db.example.invalid/pokecrack",
        worker_role="scheduler",
        mastodon_collection_enabled=True,
    )
    entries = [
        entry
        for entry in live_schedule_entries(enabled)
        if entry.job_type == MASTODON_PUBLIC_HASHTAG_JOB_TYPE
    ]
    assert [entry.name for entry in entries] == [
        f"mastodon_social_{tag_key}" for tag_key in MASTODON_TAG_KEYS
    ]
    assert [entry.payload for entry in entries] == [
        {"instance_key": "mastodon_social", "tag_key": tag_key} for tag_key in MASTODON_TAG_KEYS
    ]
    assert {entry.cron for entry in entries} == {"*/5 * * * *"}

    executor = RecordingExecutor([[{"ready": False}]])
    collector_settings = enabled.model_copy(update={"worker_role": "collector"})
    with pytest.raises(LiveCompositionError, match="dependencies"):
        write_health_heartbeat(collector_settings, executor=executor)
    sql, params = executor.calls[0]
    assert params["mastodon_enabled"] is True
    assert "begin_mastodon_public_hashtag_job(uuid,text,bigint,text,text)" in sql
    assert "finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)" in sql
    assert "record_mastodon_rate_limit(uuid,text,bigint,timestamptz)" in sql

    with pytest.raises(ValueError, match="SCHEDULE_MASTODON_COLLECTION"):
        Settings(
            _env_file=None,
            mastodon_collection_enabled=True,
            schedule_mastodon_collection="* * * * *",
        )


def _preflight_payload() -> dict[str, object]:
    return json.loads(_preflight())
