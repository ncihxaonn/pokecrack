from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from coincurve import PrivateKey
from pydantic import ValidationError

from pokecrack_worker.collectors.official_api.nostr import (
    NostrInvalidEvent,
    NostrRelayCollector,
    parse_nostr_event,
)
from pokecrack_worker.composition import (
    NOSTR_RELAY_JOB_TYPE,
    LiveCompositionError,
    build_live_worker_runtime,
    live_schedule_entries,
    write_health_heartbeat,
)
from pokecrack_worker.config.nostr import NOSTR_APPROVED_TAGS, NostrRelayRegistry
from pokecrack_worker.config.settings import Settings
from pokecrack_worker.jobs import NostrCandidateWrite, NostrRelayCompletion
from pokecrack_worker.jobs.postgres import FINALIZE_NOSTR_RELAY_SQL

REPO_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 31, 4, 0, tzinfo=UTC)


def _signed_event(
    *,
    kind: int = 1,
    tags: list[list[str]] | None = None,
    content: str = "bounded test note",
    created_at: int | None = None,
) -> dict[str, object]:
    private_key = PrivateKey(bytes.fromhex("01".zfill(64)))
    pubkey = private_key.public_key_xonly.format().hex()
    payload: dict[str, object] = {
        "pubkey": pubkey,
        "created_at": created_at or int(NOW.timestamp()),
        "kind": kind,
        "tags": tags if tags is not None else [["t", "PokemonTCG"]],
        "content": content,
    }
    canonical = json.dumps(
        [
            0,
            payload["pubkey"],
            payload["created_at"],
            payload["kind"],
            payload["tags"],
            payload["content"],
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    event_id = hashlib.sha256(canonical).digest()
    payload["id"] = event_id.hex()
    payload["sig"] = private_key.sign_schnorr(event_id, aux_randomness=bytes(32)).hex()
    return payload


def _envelope(event: dict[str, object]) -> bytes:
    return json.dumps(["EVENT", "fixture", event], ensure_ascii=False, separators=(",", ":")).encode()


class FixtureTransport:
    def __init__(self, *messages: bytes) -> None:
        self.messages = messages
        self.calls: list[dict[str, object]] = []

    def iter_messages(self, **kwargs: object) -> tuple[bytes, ...]:
        self.calls.append(dict(kwargs))
        return self.messages


class RecordingExecutor:
    def __init__(self, responses: Sequence[Sequence[Mapping[str, Any]]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    def query(self, sql: str, params: Mapping[str, object]) -> Sequence[Mapping[str, Any]]:
        self.calls.append((sql, dict(params)))
        return self.responses.pop(0) if self.responses else ()


def _job_row(*, status: str) -> dict[str, object]:
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "job_type": NOSTR_RELAY_JOB_TYPE,
        "payload": {"relay_key": "primal"},
        "status": status,
        "priority": -49,
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
        "dedupe_key": "schedule:nostr_primal:20260831T040000Z",
        "created_at": NOW,
        "updated_at": NOW,
    }


def test_registry_is_exact_and_casefolds_only_reviewed_hashtags() -> None:
    registry = NostrRelayRegistry.from_yaml(REPO_ROOT / "config/nostr-relays.yaml")

    assert tuple(relay.key for relay in registry.relays) == ("primal", "nos_lol", "nostr_net")
    assert registry.tags == NOSTR_APPROVED_TAGS
    assert registry.matched_tags([["t", "POKEMONTCG"], ["t", "ポケカ"]]) == (
        "pokemontcg",
        "ポケカ",
    )
    assert registry.matched_tags([["t", "pokemon"], ["t", "opening"]]) == ()


def test_event_id_and_bip340_signature_are_verified() -> None:
    event = _signed_event()
    parsed = parse_nostr_event(event, completion_time=NOW)
    assert parsed.event_id == event["id"]

    tampered = {**event, "content": "changed"}
    with pytest.raises(NostrInvalidEvent, match="nostr_event_id_mismatch"):
        parse_nostr_event(tampered, completion_time=NOW)

    invalid_signature = {**event, "sig": "00" * 64}
    with pytest.raises(NostrInvalidEvent, match="nostr_signature_invalid"):
        parse_nostr_event(invalid_signature, completion_time=NOW)


def test_collector_emits_minimal_candidate_and_known_target_deletion() -> None:
    candidate_event = _signed_event(tags=[["t", "ポケモンカード"]], content="private raw body")
    deletion_event = _signed_event(
        kind=5,
        tags=[["e", str(candidate_event["id"])], ["e", "f" * 64]],
        content="deleted",
        created_at=int((NOW + timedelta(seconds=1)).timestamp()),
    )
    transport = FixtureTransport(_envelope(candidate_event), _envelope(deletion_event))
    collector = NostrRelayCollector(
        transport=transport,
        registry=NostrRelayRegistry.from_yaml(REPO_ROOT / "config/nostr-relays.yaml"),
    )

    result = collector.collect(
        relay_key="primal",
        since=NOW - timedelta(minutes=5),
        until=NOW + timedelta(minutes=1),
        checkpoint=NOW - timedelta(minutes=4),
        known_event_ids=(str(candidate_event["id"]),),
    )

    assert result.events_seen == 2
    assert result.candidates[0].event_id == candidate_event["id"]
    assert result.candidates[0].matched_tags == ("ポケモンカード",)
    assert not hasattr(result.candidates[0], "content")
    assert not hasattr(result.candidates[0], "public_url")
    assert result.deletions[0].target_event_ids == (candidate_event["id"],)
    assert transport.calls[0]["tags"] == NOSTR_APPROVED_TAGS


def test_unknown_delete_and_unreviewed_tag_do_not_become_candidates() -> None:
    delete = _signed_event(kind=5, tags=[["e", "a" * 64]], content="")
    transport = FixtureTransport(_envelope(delete))
    registry = NostrRelayRegistry.from_yaml(REPO_ROOT / "config/nostr-relays.yaml")
    result = NostrRelayCollector(transport=transport, registry=registry).collect(
        relay_key="nos_lol",
        since=NOW - timedelta(minutes=5),
        until=NOW + timedelta(minutes=1),
        checkpoint=None,
        known_event_ids=(),
    )
    assert result.candidates == ()
    assert result.deletions == ()

    unmatched = FixtureTransport(_envelope(_signed_event(tags=[["t", "pokemon"]])))
    with pytest.raises(NostrInvalidEvent, match="nostr_tag_filter_mismatch"):
        NostrRelayCollector(transport=unmatched, registry=registry).collect(
            relay_key="nostr_net",
            since=NOW - timedelta(minutes=5),
            until=NOW + timedelta(minutes=1),
            checkpoint=None,
            known_event_ids=(),
        )


def test_relay_cannot_widen_the_database_authorized_window() -> None:
    registry = NostrRelayRegistry.from_yaml(REPO_ROOT / "config/nostr-relays.yaml")
    outside = FixtureTransport(
        _envelope(_signed_event(created_at=int((NOW - timedelta(minutes=6)).timestamp())))
    )

    with pytest.raises(NostrInvalidEvent, match="nostr_event_outside_window"):
        NostrRelayCollector(transport=outside, registry=registry).collect(
            relay_key="primal",
            since=NOW - timedelta(minutes=5),
            until=NOW,
            checkpoint=NOW,
            known_event_ids=(),
        )


def test_registry_rejects_dynamic_relays_and_filters() -> None:
    registry = NostrRelayRegistry.from_yaml(REPO_ROOT / "config/nostr-relays.yaml")
    with pytest.raises(ValueError, match="not approved"):
        registry.require("arbitrary")

    configured = {
        "version": 1,
        "default_enabled": False,
        "protocol": "nip01",
        "replay_overlap_seconds": 300,
        "stream_window_seconds": 15,
        "max_events": 100,
        "max_message_bytes": 262144,
        "max_stream_bytes": 2097152,
        "relays": [relay.model_dump() for relay in registry.relays],
        "tags": [*registry.tags, "dynamic"],
    }
    with pytest.raises(ValueError, match="exact approved tag"):
        NostrRelayRegistry.from_mapping(configured)


def test_completion_payload_is_exact_and_never_contains_raw_content() -> None:
    event = _signed_event()
    candidate = NostrCandidateWrite(
        event_id=str(event["id"]),
        pubkey=str(event["pubkey"]),
        signature=str(event["sig"]),
        published_at=NOW,
        content_sha256=hashlib.sha256(b"private raw body").hexdigest(),
        matched_tags=("pokemontcg",),
        relay_key="primal",
    )
    payload = NostrRelayCompletion(
        relay_key="primal",
        since=NOW - timedelta(minutes=5),
        until=NOW,
        checkpoint=None,
        incomplete=False,
        events_seen=1,
        bytes_seen=100,
        candidates=(candidate,),
    ).as_payload()

    assert set(payload) == {
        "version",
        "relay_key",
        "since",
        "until",
        "checkpoint",
        "incomplete",
        "events_seen",
        "bytes_seen",
        "candidates",
        "deletions",
    }
    assert set(payload["candidates"][0]) == {
        "event_id",
        "pubkey",
        "signature",
        "published_at",
        "content_sha256",
        "matched_tags",
        "relay_key",
        "activity_only",
        "statistics_eligible",
    }
    assert '"content":' not in json.dumps(payload)
    assert payload["candidates"][0]["statistics_eligible"] is False


def test_live_scheduler_emits_three_fixed_jobs_and_runtime_uses_typed_finalizer() -> None:
    scheduler_settings = Settings(
        _env_file=None,
        data_mode="live",
        supabase_db_url="postgresql://db.example.invalid/pokecrack",
        worker_id="scheduler-1",
        worker_role="scheduler",
        nostr_collection_enabled=True,
    )
    entries = [
        entry
        for entry in live_schedule_entries(scheduler_settings)
        if entry.job_type == NOSTR_RELAY_JOB_TYPE
    ]
    assert [entry.name for entry in entries] == [
        "nostr_primal",
        "nostr_nos_lol",
        "nostr_nostr_net",
    ]
    assert [entry.payload for entry in entries] == [
        {"relay_key": "primal"},
        {"relay_key": "nos_lol"},
        {"relay_key": "nostr_net"},
    ]

    event = _signed_event()
    executor = RecordingExecutor(
        [
            [_job_row(status="running")],
            [
                {
                    "acquired": True,
                    "retry_at": None,
                    "since": NOW - timedelta(minutes=5),
                    "until": NOW + timedelta(minutes=1),
                    "checkpoint": None,
                    "recent_candidate_ids": [],
                }
            ],
            [_job_row(status="completed")],
        ]
    )
    collector_settings = scheduler_settings.model_copy(
        update={"worker_role": "collector", "worker_id": "worker-1"}
    )
    runtime = build_live_worker_runtime(
        collector_settings,
        executor=executor,
        nostr_transport=FixtureTransport(_envelope(event)),
    )
    assert NOSTR_RELAY_JOB_TYPE in runtime.handlers
    assert runtime.run_once().status.value == "completed"
    assert any(sql == FINALIZE_NOSTR_RELAY_SQL for sql, _params in executor.calls)


def test_enabled_nostr_health_requires_the_exact_three_relay_contracts() -> None:
    settings = Settings(
        _env_file=None,
        data_mode="live",
        supabase_db_url="postgresql://db.example.invalid/pokecrack",
        worker_id="worker-1",
        worker_role="collector",
        nostr_collection_enabled=True,
    )
    executor = RecordingExecutor([[{"ready": False}]])

    with pytest.raises(LiveCompositionError, match="dependencies"):
        write_health_heartbeat(settings, executor=executor)

    sql, params = executor.calls[0]
    assert params["nostr_enabled"] is True
    assert "ingest.begin_nostr_relay_job(uuid,text,bigint,text)" in sql
    assert "ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)" in sql
    assert sql.count("policies.config - 'relay_key' - 'endpoint' - 'nip11_url'") == 1
    assert "degraded_missing_relay_specific_terms" in sql
    assert "wss://relay.primal.net/" in sql
    assert "wss://nos.lol/" in sql
    assert "wss://relay.nostr.net/" in sql


def test_nostr_enablement_freezes_collection_and_cleanup_schedules() -> None:
    with pytest.raises(ValidationError, match="SCHEDULE_NOSTR_COLLECTION"):
        Settings(
            _env_file=None,
            nostr_collection_enabled=True,
            schedule_nostr_collection="*/5 * * * *",
        )
    with pytest.raises(ValidationError, match="NOSTR_COLLECTION_ENABLED.*SCHEDULE_CLEANUP"):
        Settings(
            _env_file=None,
            nostr_collection_enabled=True,
            schedule_cleanup="0 0 * * 0",
        )
