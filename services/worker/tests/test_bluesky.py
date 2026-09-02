from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError
from websockets.datastructures import Headers
from websockets.exceptions import InvalidStatus
from websockets.http11 import Response

from pokecrack_worker.collectors.official_api.bluesky import (
    BLUESKY_JETSTREAM_URL,
    BLUESKY_MAX_CANDIDATES,
    BLUESKY_MAX_DELETIONS,
    BLUESKY_MAX_EVENTS,
    BLUESKY_MAX_MESSAGE_BYTES,
    BLUESKY_MAX_RECORD_BYTES,
    BLUESKY_MAX_STREAM_BYTES,
    BLUESKY_POLICY_URL,
    BLUESKY_STREAM_WINDOW_SECONDS,
    BLUESKY_SUBPROTOCOL,
    BlueskyConsumerTooSlowError,
    BlueskyCursorTooOldError,
    BlueskyInvalidMessage,
    BlueskyJetstreamCollector,
    BlueskyTransportError,
    WebsocketsBlueskyJetstreamTransport,
    parse_jetstream_message,
)
from pokecrack_worker.collectors.official_api.postgres import (
    BEGIN_BLUESKY_JETSTREAM_SQL,
    BlueskyRequestDeferred,
    PostgresBlueskyJetstreamGate,
)
from pokecrack_worker.composition import (
    BLUESKY_JETSTREAM_JOB_TYPE,
    LIVE_ROLE_DEPENDENCIES_SQL,
    build_live_worker_runtime,
    live_schedule_entries,
)
from pokecrack_worker.config.bluesky import (
    BLUESKY_FILTER_OPERATIONS,
    BLUESKY_POST_COLLECTION,
    REQUIRED_BLUESKY_KEYWORDS,
    BlueskyKeywordRegistry,
)
from pokecrack_worker.config.settings import Settings
from pokecrack_worker.config.source_policy import CollectorRoute, SourcePolicyRegistry
from pokecrack_worker.jobs import (
    BlueskyCursorRecoveryCompletion,
    BlueskyJetstreamCompletion,
    BlueskySourceItemWrite,
    JobStatus,
    PostgresJobRepository,
)
from pokecrack_worker.jobs.postgres import (
    FINALIZE_BLUESKY_JETSTREAM_SQL,
    RECOVER_BLUESKY_CURSOR_TOO_OLD_SQL,
)

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
DID = "did:plc:abc123"


def _frame(
    seq: int,
    *,
    operation: str = "create",
    rkey: str = "post1",
    text: str = "Pokemon TCG opening",
    collection: str = BLUESKY_POST_COLLECTION,
    time: str = "2026-08-30T12:00:00Z",
    created_at: object = "2026-08-30T11:59:00Z",
    did: str = DID,
) -> bytes:
    payload: dict[str, object] = {
        "$type": "network.bsky.jetstream.subscribeEvents#commit",
        "seq": seq,
        "did": did,
        "time": time,
        "rev": f"rev{seq}",
        "operation": operation,
        "collection": collection,
        "rkey": rkey,
    }
    if operation != "delete":
        payload["cid"] = f"bafy{seq}"
        payload["record"] = {
            "$type": BLUESKY_POST_COLLECTION,
            "text": text,
            "createdAt": created_at,
        }
    return json.dumps(
        {"$type": "message", "payload": payload},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def _error_frame(error: str) -> bytes:
    return json.dumps(
        {"$type": "message", "payload": {"error": error}}, separators=(",", ":")
    ).encode()


def _registry() -> BlueskyKeywordRegistry:
    return BlueskyKeywordRegistry.from_yaml(ROOT / "config" / "bluesky-keywords.yaml")


@dataclass
class RecordingTransport:
    messages: tuple[bytes, ...]
    calls: list[dict[str, object]]

    def __init__(self, messages: Sequence[bytes]) -> None:
        self.messages = tuple(messages)
        self.calls = []

    def iter_messages(
        self,
        *,
        start_cursor: int | None,
        max_events: int,
        max_bytes: int,
        window_seconds: float,
    ) -> tuple[bytes, ...]:
        self.calls.append(
            {
                "start_cursor": start_cursor,
                "max_events": max_events,
                "max_bytes": max_bytes,
                "window_seconds": window_seconds,
            }
        )
        return self.messages


class RecordingExecutor:
    def __init__(self, responses: Sequence[Sequence[Mapping[str, object]]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    def query(self, sql: str, params: Mapping[str, object]) -> Sequence[Mapping[str, object]]:
        self.calls.append((sql, dict(params)))
        return self.responses.pop(0)


def _job_row(*, status: str, job_type: str = BLUESKY_JETSTREAM_JOB_TYPE) -> dict[str, object]:
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "job_type": job_type,
        "payload": {},
        "status": status,
        "priority": -50,
        "available_at": NOW,
        "attempts": 1,
        "max_attempts": 3,
        "lease_generation": 1,
        "locked_by": "worker-1" if status == "running" else None,
        "locked_at": NOW if status == "running" else None,
        "lock_expires_at": NOW + timedelta(minutes=5) if status == "running" else None,
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": NOW if status == "completed" else None,
        "dedupe_key": "schedule:bluesky_jetstream:20260830T120000Z",
        "created_at": NOW,
        "updated_at": NOW,
    }


def test_keyword_registry_is_frozen_global_and_requires_both_groups() -> None:
    registry = _registry()

    assert len(registry.keywords) == len(REQUIRED_BLUESKY_KEYWORDS)
    assert registry.collection == BLUESKY_POST_COLLECTION
    assert registry.operations == BLUESKY_FILTER_OPERATIONS
    assert registry.default_enabled is False
    assert registry.matches("Pokemon TCG!")
    assert registry.matches("Pokémon: apertura de sobres")
    assert registry.matches("ポケモンカード開封")
    assert registry.matches("포켓몬카드 개봉")
    assert registry.matches("宝可梦卡包开箱")
    assert registry.matches("寶可夢卡包開箱")
    assert registry.matches("#PokemonTCG")
    assert registry.matches("Pokemon packing") == ()
    assert registry.matches("opening only") == ()
    assert registry.matches("Pokemon GO raid") == ()

    with pytest.raises((AttributeError, TypeError)):
        registry.keywords += ()  # type: ignore[misc]
    with pytest.raises(AttributeError, match="immutable"):
        registry._document = registry._document  # type: ignore[misc]
    with pytest.raises(ValidationError):
        registry.from_mapping(
            {
                "version": 1,
                "default_enabled": False,
                "collection": BLUESKY_POST_COLLECTION,
                "operations": list(BLUESKY_FILTER_OPERATIONS),
                "keywords": [{"name": "pokemon", "keyword": "Pokemon", "group": "identity"}],
            }
        )


def test_bluesky_source_policy_pins_endpoint_transport_and_bounds() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").require(
        BLUESKY_POLICY_URL, CollectorRoute.BLUESKY_JETSTREAM
    )
    assert policy.domain == "jetstream.us-west.bsky.network"
    assert policy.routes == frozenset({CollectorRoute.BLUESKY_JETSTREAM})
    assert policy.config == {
        "collection": BLUESKY_POST_COLLECTION,
        "endpoint": BLUESKY_JETSTREAM_URL,
        "kinds": ["commit"],
        "keyword_registry": "bluesky-keywords-v1",
        "max_candidates": 100,
        "max_deletions": 100,
        "max_events": 10_000,
        "max_excerpt_chars": 500,
        "max_message_bytes": BLUESKY_MAX_MESSAGE_BYTES,
        "max_stream_bytes": BLUESKY_MAX_STREAM_BYTES,
        "operations": list(BLUESKY_FILTER_OPERATIONS),
        "statistics_eligible": False,
        "stream_window_seconds": 10,
        "subprotocol": BLUESKY_SUBPROTOCOL,
    }
    assert "policies.config = '{" in LIVE_ROLE_DEPENDENCIES_SQL
    assert '"stream_window_seconds":10' in LIVE_ROLE_DEPENDENCIES_SQL
    assert '"stream_window_seconds":40' not in LIVE_ROLE_DEPENDENCIES_SQL
    assert '"subprotocol":"xrpc.v1.json"' in LIVE_ROLE_DEPENDENCIES_SQL


def test_fixed_window_preserves_two_mib_cap_with_production_throughput_margin() -> None:
    observed_bytes = 1_139_364
    observed_window_seconds = 40
    projected_bytes = observed_bytes * BLUESKY_STREAM_WINDOW_SECONDS / observed_window_seconds

    assert BLUESKY_STREAM_WINDOW_SECONDS == 10.0
    assert projected_bytes == pytest.approx(284_841, abs=1)
    assert projected_bytes < BLUESKY_MAX_STREAM_BYTES
    assert BLUESKY_MAX_STREAM_BYTES == 2 * 1024 * 1024
    assert BLUESKY_MAX_STREAM_BYTES / projected_bytes > 7


def test_parser_validates_v2_envelope_time_and_operations() -> None:
    event = parse_jetstream_message(_frame(42, operation="update"))
    assert event is not None
    assert event.seq == 42
    assert event.did == DID
    assert event.operation == "update"
    assert event.time == datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    assert event.record is not None
    assert event.record_fingerprint is not None
    assert event.record["text"] == "Pokemon TCG opening"
    assert event.published_at == datetime(2026, 8, 30, 11, 59, tzinfo=UTC)
    assert event.candidate_record_within_bound is True
    assert event.candidate_timestamp_valid is True

    deletion = parse_jetstream_message(_frame(43, operation="delete", rkey="post2"))
    assert deletion is not None
    assert deletion.record is None
    assert deletion.record_fingerprint is None
    assert deletion.operation == "delete"
    assert deletion.published_at is None
    assert deletion.candidate_record_within_bound is True
    assert deletion.candidate_timestamp_valid is True

    assert parse_jetstream_message(_frame(44, collection="app.bsky.feed.like")) is None
    with pytest.raises(BlueskyInvalidMessage):
        parse_jetstream_message(b"x" * (BLUESKY_MAX_MESSAGE_BYTES + 1))
    with pytest.raises(Exception, match="bluesky_time_invalid"):
        parse_jetstream_message(_frame(45, time="1700000000"))
    with pytest.raises(BlueskyConsumerTooSlowError):
        parse_jetstream_message(_error_frame("ConsumerTooSlow"))
    with pytest.raises(BlueskyCursorTooOldError):
        parse_jetstream_message(_error_frame("CursorTooOld"))


@pytest.mark.parametrize(
    "poison_created_at",
    (
        "not-an-rfc3339-timestamp",
        {"not": "a string"},
        "2026-08-30T11:59:00",
        "0001-01-01T00:00:00+23:59",
        "1999-12-31T23:59:59Z",
        "2999-01-01T00:00:00Z",
        None,
    ),
    ids=(
        "malformed",
        "non-string",
        "naive",
        "normalization-overflow",
        "too-old",
        "too-new",
        "null",
    ),
)
def test_collector_skips_poison_created_at_and_advances_checkpoint(
    poison_created_at: object,
) -> None:
    poison_text = "POISON-TIMESTAMP Pokemon TCG opening"
    poison_did = "did:plc:poison123"
    poison = _frame(
        11,
        rkey="poison-timestamp",
        text=poison_text,
        created_at=poison_created_at,
        did=poison_did,
    )
    messages = (
        _frame(10, rkey="before-poison", text="Pokemon TCG before"),
        poison,
        _frame(12, rkey="after-poison", text="Pokemon TCG after"),
    )
    collector = BlueskyJetstreamCollector(
        transport=RecordingTransport(messages),
        keywords=_registry(),
    )

    first = collector.collect(start_cursor=9)

    assert first.start_cursor == 9
    assert first.end_cursor == 12
    assert first.events_seen == len(messages)
    assert first.events_seen <= BLUESKY_MAX_EVENTS
    assert first.bytes_seen == sum(map(len, messages))
    assert first.bytes_seen <= BLUESKY_MAX_STREAM_BYTES
    assert [item.cursor for item in first.candidates] == [10, 12]
    assert len(first.candidates) <= BLUESKY_MAX_CANDIDATES
    assert first.deletions == ()
    poison_record = json.loads(poison)["payload"]["record"]
    poison_hash = hashlib.sha256(
        json.dumps(
            poison_record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    assert poison_hash not in {item.record_sha256 for item in first.candidates}
    assert poison_text not in repr(first)
    assert poison_did not in repr(first)
    assert "poison-timestamp" not in repr(first)

    replay = BlueskyJetstreamCollector(
        transport=RecordingTransport(messages),
        keywords=_registry(),
    ).collect(start_cursor=first.end_cursor)

    assert replay.start_cursor == 12
    assert replay.end_cursor == 12
    assert replay.events_seen == len(messages)
    assert replay.bytes_seen == sum(map(len, messages))
    assert replay.candidates == ()
    assert replay.deletions == ()


def test_collector_suppresses_missing_created_at_without_stalling() -> None:
    missing_created_at = json.loads(_frame(30, rkey="missing-created-at"))
    del missing_created_at["payload"]["record"]["createdAt"]
    raw = json.dumps(missing_created_at, separators=(",", ":")).encode()
    valid_after = _frame(31, rkey="valid-after-missing")

    result = BlueskyJetstreamCollector(
        transport=RecordingTransport((raw, valid_after)),
        keywords=_registry(),
    ).collect(start_cursor=29)

    assert result.end_cursor == 31
    assert result.events_seen == 2
    assert result.bytes_seen == len(raw) + len(valid_after)
    assert [item.cursor for item in result.candidates] == [31]
    assert "missing-created-at" not in repr(result)


def test_collector_skips_oversized_record_and_advances_checkpoint() -> None:
    oversized = json.loads(_frame(41, rkey="oversized-record"))
    oversized["payload"]["record"]["embed"] = "OVERSIZED-SENTINEL" + (
        "x" * BLUESKY_MAX_RECORD_BYTES
    )
    raw = json.dumps(oversized, separators=(",", ":")).encode()
    assert BLUESKY_MAX_RECORD_BYTES < len(raw) <= BLUESKY_MAX_MESSAGE_BYTES

    parsed = parse_jetstream_message(raw)
    assert parsed is not None
    assert parsed.seq == 41
    assert parsed.candidate_record_within_bound is False
    assert parsed.record is None
    assert "OVERSIZED-SENTINEL" not in repr(parsed)

    messages = (
        _frame(40, rkey="before-oversized"),
        raw,
        _frame(42, rkey="after-oversized"),
    )
    result = BlueskyJetstreamCollector(
        transport=RecordingTransport(messages),
        keywords=_registry(),
    ).collect(start_cursor=39)

    assert result.end_cursor == 42
    assert result.events_seen == 3
    assert result.bytes_seen == sum(map(len, messages))
    assert [item.cursor for item in result.candidates] == [40, 42]
    assert "OVERSIZED-SENTINEL" not in repr(result)
    assert "oversized-record" not in repr(result)

    replay = BlueskyJetstreamCollector(
        transport=RecordingTransport((raw, raw)),
        keywords=_registry(),
    ).collect(start_cursor=40)
    assert replay.end_cursor == 41
    assert replay.events_seen == 2
    assert replay.candidates == ()

    conflict = json.loads(raw)
    conflict["payload"]["record"]["embed"] += "different"
    conflicting_raw = json.dumps(conflict, separators=(",", ":")).encode()
    with pytest.raises(BlueskyInvalidMessage, match="bluesky_sequence_conflict"):
        BlueskyJetstreamCollector(
            transport=RecordingTransport((raw, conflicting_raw)),
            keywords=_registry(),
        ).collect(start_cursor=40)


@pytest.mark.parametrize("invalid_text", ({"not": "text"}, "x" * 10_001))
def test_oversized_record_does_not_bypass_text_validation(invalid_text: object) -> None:
    oversized = json.loads(_frame(50, rkey="oversized-invalid-text"))
    oversized["payload"]["record"]["text"] = invalid_text
    oversized["payload"]["record"]["embed"] = "x" * BLUESKY_MAX_RECORD_BYTES
    raw = json.dumps(oversized, separators=(",", ":")).encode()
    assert len(raw) <= BLUESKY_MAX_MESSAGE_BYTES

    with pytest.raises(BlueskyInvalidMessage, match="bluesky_record_text_invalid"):
        BlueskyJetstreamCollector(
            transport=RecordingTransport((raw,)),
            keywords=_registry(),
        ).collect(start_cursor=49)


def test_oversized_record_with_poison_timestamp_still_advances() -> None:
    oversized = json.loads(_frame(60, rkey="oversized-poison-time"))
    oversized["payload"]["record"]["embed"] = "x" * BLUESKY_MAX_RECORD_BYTES
    oversized["payload"]["record"]["createdAt"] = "not-a-timestamp"
    raw = json.dumps(oversized, separators=(",", ":")).encode()

    event = parse_jetstream_message(raw)
    assert event is not None
    assert event.record is None
    assert event.candidate_record_within_bound is False
    assert event.candidate_timestamp_valid is False

    result = BlueskyJetstreamCollector(
        transport=RecordingTransport((raw,)),
        keywords=_registry(),
    ).collect(start_cursor=59)
    assert result.end_cursor == 60
    assert result.events_seen == 1
    assert result.candidates == ()


def test_invalid_created_at_does_not_bypass_structural_record_validation() -> None:
    malformed = json.loads(_frame(20, created_at="not-a-timestamp"))
    malformed["payload"]["record"]["$type"] = "app.bsky.feed.like"

    with pytest.raises(BlueskyInvalidMessage, match="bluesky_record_invalid"):
        parse_jetstream_message(malformed)

    invalid_text = json.loads(_frame(21, created_at="not-a-timestamp"))
    invalid_text["payload"]["record"]["text"] = {"unsafe": "Pokemon TCG"}
    raw_invalid_text = json.dumps(invalid_text, separators=(",", ":")).encode()
    collector = BlueskyJetstreamCollector(
        transport=RecordingTransport((raw_invalid_text,)),
        keywords=_registry(),
    )

    with pytest.raises(BlueskyInvalidMessage, match="bluesky_record_text_invalid"):
        collector.collect()


def test_collector_is_bounded_idempotent_and_advances_cursor_for_nonmatches() -> None:
    messages = (
        _frame(1, text="just opening"),
        _frame(2, rkey="post2", text="Pokemon TCG!\r\x00opening"),
        _frame(3, operation="update", rkey="post3", text="Pokemon TCG updated"),
        _frame(3, operation="update", rkey="post3", text="Pokemon TCG updated"),
        _frame(4, rkey="post4", text="Pokemon TCG second"),
        _frame(5, operation="delete", rkey="post5"),
    )
    transport = RecordingTransport(messages)
    collector = BlueskyJetstreamCollector(transport=transport, keywords=_registry())

    result = collector.collect()

    assert result.start_cursor is None
    assert result.end_cursor == 5
    assert result.events_seen == len(messages)
    assert result.bytes_seen == sum(map(len, messages))
    assert [item.cursor for item in result.candidates] == [2, 3, 4]
    assert result.candidates[1].at_uri.endswith("/post3")
    assert result.candidates[1].text_excerpt == "Pokemon TCG updated"
    assert result.candidates[0].record_sha256.isascii()
    assert len(result.candidates[0].record_sha256) == 64
    assert [(item.at_uri, item.cursor) for item in result.deletions] == [
        (f"at://{DID}/{BLUESKY_POST_COLLECTION}/post5", 5)
    ]
    assert transport.calls == [
        {
            "start_cursor": None,
            "max_events": BLUESKY_MAX_EVENTS,
            "max_bytes": BLUESKY_MAX_STREAM_BYTES,
            "window_seconds": BLUESKY_STREAM_WINDOW_SECONDS,
        }
    ]

    inclusive = BlueskyJetstreamCollector(
        transport=RecordingTransport(
            (_frame(5, operation="delete", rkey="post5"), _frame(6, rkey="post6"))
        ),
        keywords=_registry(),
    )
    resumed = inclusive.collect(start_cursor=5)
    assert resumed.end_cursor == 6
    assert resumed.events_seen == 2
    assert resumed.candidates[0].cursor == 6


@pytest.mark.parametrize("second_operation", ("update", "delete"))
def test_collector_stops_before_a_second_event_reuses_one_identity(
    second_operation: str,
) -> None:
    messages = (
        _frame(10, rkey="same-post"),
        _frame(11, operation=second_operation, rkey="same-post", text="Pokemon TCG update"),
        _frame(12, rkey="other-post"),
    )
    first = BlueskyJetstreamCollector(
        transport=RecordingTransport(messages),
        keywords=_registry(),
    ).collect()

    assert first.end_cursor == 10
    assert first.events_seen == 1
    assert [item.cursor for item in first.candidates] == [10]
    assert first.deletions == ()

    resumed = BlueskyJetstreamCollector(
        transport=RecordingTransport(messages),
        keywords=_registry(),
    ).collect(start_cursor=10)

    assert resumed.end_cursor == 12
    assert resumed.events_seen == 3
    if second_operation == "delete":
        assert [item.cursor for item in resumed.candidates] == [12]
        assert [item.cursor for item in resumed.deletions] == [11]
    else:
        assert [item.cursor for item in resumed.candidates] == [11, 12]
        assert resumed.deletions == ()


def test_collector_rejects_a_conflicting_duplicate_sequence() -> None:
    collector = BlueskyJetstreamCollector(
        transport=RecordingTransport((_frame(7, rkey="post1"), _frame(7, rkey="post2"))),
        keywords=_registry(),
    )

    with pytest.raises(BlueskyInvalidMessage, match="bluesky_sequence_conflict"):
        collector.collect()


@pytest.mark.parametrize(
    ("operation", "result_field", "output_cap"),
    (
        ("create", "candidates", BLUESKY_MAX_CANDIDATES),
        ("delete", "deletions", BLUESKY_MAX_DELETIONS),
    ),
)
def test_collector_resumes_before_an_output_cap_would_drop_an_event(
    operation: str,
    result_field: str,
    output_cap: int,
) -> None:
    capped_messages = tuple(
        _frame(
            seq,
            operation=operation,
            rkey=f"post{seq}",
        )
        for seq in range(1, output_cap + 1)
    )
    messages = (
        *capped_messages,
        _frame(output_cap + 1, rkey="nonmatch", text="just opening"),
        _frame(
            output_cap + 2,
            operation=operation,
            rkey=f"post{output_cap + 2}",
        ),
    )
    collector = BlueskyJetstreamCollector(
        transport=RecordingTransport(messages),
        keywords=_registry(),
    )

    first = collector.collect()

    first_items = getattr(first, result_field)
    assert len(first_items) == output_cap
    assert [item.cursor for item in first_items] == list(range(1, output_cap + 1))
    assert first.end_cursor == output_cap + 1
    assert first.events_seen == output_cap + 1
    assert first.bytes_seen == sum(map(len, messages[: output_cap + 1]))

    resumed = BlueskyJetstreamCollector(
        transport=RecordingTransport(messages[output_cap:]),
        keywords=_registry(),
    ).collect(start_cursor=output_cap + 1)

    resumed_items = getattr(resumed, result_field)
    assert [item.cursor for item in resumed_items] == [output_cap + 2]
    assert resumed.end_cursor == output_cap + 2
    assert resumed.events_seen == 2
    assert resumed.bytes_seen == sum(map(len, messages[output_cap:]))


def test_collector_rejects_a_non_monotonic_unique_sequence() -> None:
    collector = BlueskyJetstreamCollector(
        transport=RecordingTransport((_frame(2), _frame(1, rkey="post2"))),
        keywords=_registry(),
    )

    with pytest.raises(BlueskyInvalidMessage, match="bluesky_sequence_non_monotonic"):
        collector.collect()


def test_completion_dto_has_exact_bounded_result_contract() -> None:
    candidate = BlueskySourceItemWrite(
        cursor="7",
        at_uri=f"at://{DID}/{BLUESKY_POST_COLLECTION}/post1",
        public_url=f"https://bsky.app/profile/{DID}/post/post1",
        text_excerpt="Pokemon TCG opening",
        record_sha256="a" * 64,
        published_at=NOW,
    )
    completion = BlueskyJetstreamCompletion(
        start_cursor=6,
        end_cursor=7,
        events_seen=1,
        bytes_seen=100,
        candidates=(candidate,),
    )
    payload = completion.as_payload()
    assert set(payload) == {
        "version",
        "start_cursor",
        "end_cursor",
        "events_seen",
        "bytes_seen",
        "candidates",
        "deletions",
    }
    assert payload["version"] == "1.0.0"
    assert set(payload["candidates"][0]) == {
        "cursor",
        "at_uri",
        "public_url",
        "text_excerpt",
        "record_sha256",
        "published_at",
    }
    assert "did" not in payload["candidates"][0]
    assert "geography" not in payload["candidates"][0]
    assert "opening_rate" not in payload["candidates"][0]
    with pytest.raises(ValueError):
        BlueskySourceItemWrite(
            cursor=0,
            at_uri=f"at://{DID}/{BLUESKY_POST_COLLECTION}/post1",
            public_url=f"https://bsky.app/profile/{DID}/post/post1",
            text_excerpt="x" * 501,
            record_sha256="a" * 64,
            published_at=None,
        )

    recovery = BlueskyCursorRecoveryCompletion(start_cursor="7")
    assert recovery.start_cursor == 7
    with pytest.raises(ValueError):
        BlueskyCursorRecoveryCompletion(start_cursor="007")


@pytest.mark.parametrize(
    "value",
    (None, True, 1.0, -1, "01", "9223372036854775808"),
)
def test_cursor_recovery_completion_accepts_only_a_canonical_nonnegative_bigint(
    value: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        BlueskyCursorRecoveryCompletion(start_cursor=value)  # type: ignore[arg-type]


def test_postgres_gate_and_finalizer_use_dedicated_fenced_rpcs() -> None:
    executor = RecordingExecutor(
        [
            [{"acquired": True, "retry_at": None, "start_cursor": "41"}],
            [_job_row(status="completed")],
        ]
    )
    checkpoint = PostgresBlueskyJetstreamGate(executor).begin(
        job_id="00000000-0000-0000-0000-000000000001",
        worker_id="worker-1",
        lease_generation=1,
    )
    assert checkpoint.start_cursor == 41
    assert BEGIN_BLUESKY_JETSTREAM_SQL.count("ingest.begin_bluesky_jetstream_job") == 1

    candidate = BlueskySourceItemWrite(
        cursor=42,
        at_uri=f"at://{DID}/{BLUESKY_POST_COLLECTION}/post1",
        public_url=f"https://bsky.app/profile/{DID}/post/post1",
        text_excerpt="Pokemon TCG",
        record_sha256="b" * 64,
        published_at=NOW,
    )
    completion = BlueskyJetstreamCompletion(
        start_cursor=41,
        end_cursor=42,
        events_seen=1,
        bytes_seen=10,
        candidates=(candidate,),
    )
    completed = PostgresJobRepository(executor).complete(
        "00000000-0000-0000-0000-000000000001",
        worker_id="worker-1",
        lease_generation=1,
        now=NOW,
        effect=completion,
    )
    assert completed.status is JobStatus.COMPLETED
    sql, params = executor.calls[-1]
    assert sql == FINALIZE_BLUESKY_JETSTREAM_SQL
    assert "ingest.finalize_bluesky_jetstream_job" in sql
    assert json.loads(str(params["result"]))["candidates"][0]["cursor"] == 42

    deferred_executor = RecordingExecutor(
        [[{"acquired": False, "retry_at": NOW + timedelta(seconds=30)}]]
    )
    with pytest.raises(BlueskyRequestDeferred):
        PostgresBlueskyJetstreamGate(deferred_executor).begin(
            job_id="00000000-0000-0000-0000-000000000001",
            worker_id="worker-1",
            lease_generation=1,
        )


def test_postgres_repository_uses_fenced_cursor_recovery_rpc() -> None:
    executor = RecordingExecutor([[_job_row(status="completed")]])

    completed = PostgresJobRepository(executor).complete(
        "00000000-0000-0000-0000-000000000001",
        worker_id="worker-1",
        lease_generation=1,
        now=NOW,
        effect=BlueskyCursorRecoveryCompletion(start_cursor=41),
    )

    assert completed.status is JobStatus.COMPLETED
    sql, params = executor.calls[-1]
    assert sql == RECOVER_BLUESKY_CURSOR_TOO_OLD_SQL
    assert "ingest.recover_bluesky_cursor_too_old_job_v1" in sql
    assert params["start_cursor"] == 41


def test_websocket_transport_pins_protocol_query_and_proxy_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}
            self.uri = ""
            self.received = False

        async def __aenter__(self) -> FakeConnection:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def recv(self) -> bytes:
            if not self.received:
                self.received = True
                return _frame(99)
            raise TimeoutError

    connection = FakeConnection()

    def connect(uri: str, **kwargs: object) -> FakeConnection:
        connection.uri = uri
        connection.kwargs = kwargs
        return connection

    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=connect))
    transport = WebsocketsBlueskyJetstreamTransport()
    messages = transport.iter_messages(
        start_cursor=98,
        max_events=BLUESKY_MAX_EVENTS,
        max_bytes=BLUESKY_MAX_STREAM_BYTES,
        window_seconds=BLUESKY_STREAM_WINDOW_SECONDS,
    )

    query = parse_qs(urlsplit(connection.uri).query)
    assert urlsplit(connection.uri).scheme == "wss"
    assert urlsplit(connection.uri)._replace(query="").geturl() == BLUESKY_JETSTREAM_URL
    assert query == {
        "kinds": ["commit"],
        "collections": [BLUESKY_POST_COLLECTION],
        "maxMessageSizeBytes": [str(BLUESKY_MAX_MESSAGE_BYTES)],
        "cursor": ["98"],
    }
    assert connection.kwargs["subprotocols"] == [BLUESKY_SUBPROTOCOL]
    assert connection.kwargs["proxy"] is None
    assert messages == (_frame(99),)


def test_websocket_transport_returns_a_complete_prefix_at_the_byte_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _frame(100)
    second = _frame(101, rkey="post101")

    class PrefixConnection:
        async def __aenter__(self) -> PrefixConnection:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def __init__(self) -> None:
            self.messages = iter((first, second))

        async def recv(self) -> bytes:
            return next(self.messages)

    connection = PrefixConnection()

    def connect(_uri: str, **_kwargs: object) -> PrefixConnection:
        return connection

    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=connect))
    transport = WebsocketsBlueskyJetstreamTransport()

    messages = transport.iter_messages(
        start_cursor=99,
        max_events=BLUESKY_MAX_EVENTS,
        max_bytes=len(first),
        window_seconds=BLUESKY_STREAM_WINDOW_SECONDS,
    )

    assert messages == (first,)
    assert sum(map(len, messages)) <= BLUESKY_MAX_STREAM_BYTES


def test_websocket_transport_rejects_window_override_and_byte_cap_above_two_mib() -> None:
    with pytest.raises(ValueError, match="fixed stream window"):
        WebsocketsBlueskyJetstreamTransport(stream_window_seconds=BLUESKY_STREAM_WINDOW_SECONDS + 1)

    transport = WebsocketsBlueskyJetstreamTransport()
    with pytest.raises(ValueError, match="stream byte cap"):
        transport.iter_messages(
            start_cursor=None,
            max_events=BLUESKY_MAX_EVENTS,
            max_bytes=BLUESKY_MAX_STREAM_BYTES + 1,
            window_seconds=BLUESKY_STREAM_WINDOW_SECONDS,
        )


def test_websocket_transport_classifies_structured_stale_cursor_handshake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Response(
        400,
        "Bad Request",
        Headers({"Content-Type": "application/json"}),
        b' {"error":"CursorTooOld","message":"floor is 123","extra":true} ',
    )

    def connect(_uri: str, **_kwargs: object) -> object:
        raise InvalidStatus(response)

    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=connect))
    transport = WebsocketsBlueskyJetstreamTransport()

    with pytest.raises(BlueskyCursorTooOldError) as raised:
        transport.iter_messages(
            start_cursor=1,
            max_events=BLUESKY_MAX_EVENTS,
            max_bytes=BLUESKY_MAX_STREAM_BYTES,
            window_seconds=BLUESKY_STREAM_WINDOW_SECONDS,
        )

    assert raised.value.code == "bluesky_cursor_too_old"
    assert raised.value.retryable is False


def test_websocket_transport_classifies_wrapped_structured_stale_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class WrappedHandshakeError(RuntimeError):
        def __init__(self) -> None:
            self.response = SimpleNamespace(
                status_code=400,
                body=bytearray(b'{"error":"CursorTooOld"}'),
            )

    def connect(_uri: str, **_kwargs: object) -> object:
        raise WrappedHandshakeError()

    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=connect))
    transport = WebsocketsBlueskyJetstreamTransport()

    with pytest.raises(BlueskyCursorTooOldError):
        transport.iter_messages(
            start_cursor=1,
            max_events=BLUESKY_MAX_EVENTS,
            max_bytes=BLUESKY_MAX_STREAM_BYTES,
            window_seconds=BLUESKY_STREAM_WINDOW_SECONDS,
        )


@pytest.mark.parametrize(
    "response",
    (
        SimpleNamespace(status_code=500, body=b'{"error":"CursorTooOld"}'),
        SimpleNamespace(status_code=400, body=b'{"error":"cursortooold"}'),
        SimpleNamespace(status_code=400, body=b"not-json"),
    ),
)
def test_websocket_transport_keeps_malformed_wrapped_errors_retryable(
    monkeypatch: pytest.MonkeyPatch,
    response: object,
) -> None:
    class WrappedHandshakeError(RuntimeError):
        def __init__(self) -> None:
            self.response = response

    def connect(_uri: str, **_kwargs: object) -> object:
        raise WrappedHandshakeError()

    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=connect))
    transport = WebsocketsBlueskyJetstreamTransport()

    with pytest.raises(BlueskyTransportError):
        transport.iter_messages(
            start_cursor=1,
            max_events=BLUESKY_MAX_EVENTS,
            max_bytes=BLUESKY_MAX_STREAM_BYTES,
            window_seconds=BLUESKY_STREAM_WINDOW_SECONDS,
        )


@pytest.mark.parametrize(
    ("status_code", "body"),
    (
        (500, b'{"error":"CursorTooOld"}'),
        (400, b'{"error":"InvalidRequest"}'),
        (400, b'{"error":"cursortooold"}'),
        (400, b'{"message":"CursorTooOld"}'),
        (400, b'["CursorTooOld"]'),
        (400, b"{not-json"),
        (400, b"\xff"),
        (400, b""),
    ),
)
def test_websocket_transport_keeps_other_handshake_failures_retryable(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    body: bytes,
) -> None:
    response = Response(status_code, "Rejected", Headers(), body)

    def connect(_uri: str, **_kwargs: object) -> object:
        raise InvalidStatus(response)

    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=connect))
    transport = WebsocketsBlueskyJetstreamTransport()

    with pytest.raises(BlueskyTransportError) as raised:
        transport.iter_messages(
            start_cursor=1,
            max_events=BLUESKY_MAX_EVENTS,
            max_bytes=BLUESKY_MAX_STREAM_BYTES,
            window_seconds=BLUESKY_STREAM_WINDOW_SECONDS,
        )

    assert raised.value.code == "bluesky_transport_error"
    assert raised.value.retryable is True


def test_live_composition_flag_schedule_priority_and_runtime_dispatch() -> None:
    settings = Settings(
        _env_file=None,
        data_mode="live",
        supabase_db_url="postgresql://db.example.invalid/pokecrack",
        worker_id="worker-1",
        worker_role="scheduler",
        bluesky_collection_enabled=True,
    )
    entries = live_schedule_entries(settings)
    bluesky_entries = [entry for entry in entries if entry.job_type == BLUESKY_JETSTREAM_JOB_TYPE]
    assert len(bluesky_entries) == 1
    assert bluesky_entries[0].cron == "* * * * *"
    assert bluesky_entries[0].payload == {}
    assert bluesky_entries[0].priority == -50
    cleanup = next(entry for entry in entries if entry.name == "cleanup")
    assert cleanup.catch_up_within == timedelta(hours=36)
    assert cleanup.catch_up_check_interval == timedelta(hours=1)
    assert cleanup.slot(NOW) == NOW.replace(hour=3, minute=30)

    collector_settings = settings.model_copy(update={"worker_role": "collector"})
    executor = RecordingExecutor(
        [
            [_job_row(status="running")],
            [{"acquired": True, "retry_at": None, "start_cursor": None}],
            [_job_row(status="completed")],
        ]
    )
    runtime = build_live_worker_runtime(
        collector_settings,
        executor=executor,
        bluesky_transport=RecordingTransport((_frame(1),)),
    )
    assert set(runtime.handlers) == {
        "catalog.tcgdex.sets.sync",
        BLUESKY_JETSTREAM_JOB_TYPE,
    }
    result = runtime.run_once()
    assert result.status.value == "completed"
    assert any(sql == FINALIZE_BLUESKY_JETSTREAM_SQL for sql, _params in executor.calls)


def test_live_composition_recovers_only_a_nonnull_structured_stale_cursor() -> None:
    class CursorTooOldTransport:
        def iter_messages(self, **_kwargs: object) -> tuple[bytes, ...]:
            raise BlueskyCursorTooOldError()

    settings = Settings(
        _env_file=None,
        data_mode="live",
        supabase_db_url="postgresql://db.example.invalid/pokecrack",
        worker_id="worker-1",
        worker_role="collector",
        bluesky_collection_enabled=True,
    )
    executor = RecordingExecutor(
        [
            [_job_row(status="running")],
            [{"acquired": True, "retry_at": None, "start_cursor": 41}],
            [_job_row(status="completed")],
        ]
    )
    runtime = build_live_worker_runtime(
        settings,
        executor=executor,
        bluesky_transport=CursorTooOldTransport(),
    )

    completed = runtime.run_once()
    assert completed.status.value == "completed"
    assert any(sql == RECOVER_BLUESKY_CURSOR_TOO_OLD_SQL for sql, _params in executor.calls)


def test_live_composition_refuses_to_reset_a_nullable_checkpoint() -> None:
    class CursorTooOldTransport:
        def iter_messages(self, **_kwargs: object) -> tuple[bytes, ...]:
            raise BlueskyCursorTooOldError()

    settings = Settings(
        _env_file=None,
        data_mode="live",
        supabase_db_url="postgresql://db.example.invalid/pokecrack",
        worker_id="worker-1",
        worker_role="collector",
        bluesky_collection_enabled=True,
    )
    executor = RecordingExecutor(
        [
            [_job_row(status="running")],
            [{"acquired": True, "retry_at": None, "start_cursor": None}],
            [_job_row(status="failed")],
        ]
    )
    runtime = build_live_worker_runtime(
        settings,
        executor=executor,
        bluesky_transport=CursorTooOldTransport(),
    )

    result = runtime.run_once()
    assert result.status.value == "failed"
    assert result.error_code == "bluesky_cursor_reset_invalid"
    assert not any(sql == RECOVER_BLUESKY_CURSOR_TOO_OLD_SQL for sql, _params in executor.calls)


def test_bluesky_enablement_keeps_schedule_fixed() -> None:
    with pytest.raises(ValidationError, match="SCHEDULE_BLUESKY_COLLECTION"):
        Settings(
            _env_file=None,
            bluesky_collection_enabled=True,
            schedule_bluesky_collection="*/5 * * * *",
        )
