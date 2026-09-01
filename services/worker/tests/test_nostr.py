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
    _NoRedirectWebSocketConnect,
    parse_nostr_event,
)
from pokecrack_worker.composition import (
    NOSTR_RELAY_JOB_TYPE,
    LiveCompositionError,
    WorkerRole,
    _dsn_with_fixed_nostr_role,
    build_live_worker_runtime,
    live_schedule_entries,
    write_health_heartbeat,
)
from pokecrack_worker.config.nostr import NOSTR_APPROVED_TAGS, NostrRelayRegistry
from pokecrack_worker.config.settings import Settings
from pokecrack_worker.jobs import (
    NostrCandidateWrite,
    NostrPostgresJobRepository,
    NostrRelayCompletion,
)
from pokecrack_worker.jobs.postgres import (
    FINALIZE_NOSTR_RELAY_SQL,
    NOSTR_CLAIM_SQL,
    NOSTR_FAIL_SQL,
    NOSTR_HEARTBEAT_SQL,
    NOSTR_PAUSE_BUDGET_SQL,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 31, 4, 0, tzinfo=UTC)


def _signed_event(
    *,
    kind: int | float = 1,
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
    return json.dumps(
        ["EVENT", "fixture", event], ensure_ascii=False, separators=(",", ":")
    ).encode()


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

    extreme_timestamp = _signed_event(created_at=10**30)
    with pytest.raises(NostrInvalidEvent, match="nostr_created_at_invalid"):
        parse_nostr_event(extreme_timestamp, completion_time=NOW)

    non_integer_kind = _signed_event(kind=1.0)
    with pytest.raises(NostrInvalidEvent, match="nostr_kind_invalid"):
        parse_nostr_event(non_integer_kind, completion_time=NOW)


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
    assert not hasattr(result.candidates[0], "pubkey")
    assert not hasattr(result.candidates[0], "signature")
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
    unmatched_result = NostrRelayCollector(transport=unmatched, registry=registry).collect(
        relay_key="nostr_net",
        since=NOW - timedelta(minutes=5),
        until=NOW + timedelta(minutes=1),
        checkpoint=None,
        known_event_ids=(),
    )
    assert unmatched_result.events_seen == 1
    assert unmatched_result.candidates == ()

    tampered = _signed_event(tags=[["t", "PokemonTCG"]])
    tampered["content"] = "changed after signing"
    invalid_result = NostrRelayCollector(
        transport=FixtureTransport(_envelope(tampered)), registry=registry
    ).collect(
        relay_key="nostr_net",
        since=NOW - timedelta(minutes=5),
        until=NOW + timedelta(minutes=1),
        checkpoint=None,
        known_event_ids=(),
    )
    assert invalid_result.events_seen == 1
    assert invalid_result.candidates == ()


def test_relay_events_outside_the_database_authorized_window_are_ignored() -> None:
    registry = NostrRelayRegistry.from_yaml(REPO_ROOT / "config/nostr-relays.yaml")
    outside = FixtureTransport(
        _envelope(_signed_event(created_at=int((NOW - timedelta(minutes=6)).timestamp()))),
        _envelope(_signed_event(created_at=int((NOW + timedelta(seconds=1)).timestamp()))),
    )

    result = NostrRelayCollector(transport=outside, registry=registry).collect(
        relay_key="primal",
        since=NOW - timedelta(minutes=5),
        until=NOW,
        checkpoint=NOW,
        known_event_ids=(),
    )

    assert result.events_seen == 2
    assert result.candidates == ()
    assert result.deletions == ()


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


def test_websocket_connector_rejects_every_redirect() -> None:
    connector = _NoRedirectWebSocketConnect("wss://relay.primal.net/")
    redirect = RuntimeError("redirect")

    assert connector.process_redirect(redirect) is redirect


def test_completion_payload_is_exact_and_never_contains_raw_content() -> None:
    event = _signed_event()
    candidate = NostrCandidateWrite(
        event_id=str(event["id"]),
        author_sha256=hashlib.sha256(bytes.fromhex(str(event["pubkey"]))).hexdigest(),
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
        "author_sha256",
        "published_at",
        "content_sha256",
        "matched_tags",
        "relay_key",
        "activity_only",
        "statistics_eligible",
    }
    assert '"content":' not in json.dumps(payload)
    assert str(event["pubkey"]) not in json.dumps(payload)
    assert str(event["sig"]) not in json.dumps(payload)
    assert payload["candidates"][0]["statistics_eligible"] is False


def test_isolated_collector_self_schedules_and_uses_typed_finalizer() -> None:
    collector_settings = Settings(
        _env_file=None,
        data_mode="live",
        nostr_supabase_db_url="postgresql://nostr.example.invalid/pokecrack",
        worker_id="nostr-collector-test",
        worker_role="nostr-collector",
        nostr_collection_enabled=True,
    )

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
    runtime = build_live_worker_runtime(
        collector_settings,
        executor=executor,
        nostr_transport=FixtureTransport(_envelope(event)),
    )
    assert NOSTR_RELAY_JOB_TYPE in runtime.handlers
    assert tuple(runtime.handlers) == (NOSTR_RELAY_JOB_TYPE,)
    assert isinstance(runtime.repository, NostrPostgresJobRepository)
    assert runtime.run_once().status.value == "completed"
    assert "WITH due_jobs AS MATERIALIZED" in NOSTR_CLAIM_SQL
    assert "ingest.enqueue_due_nostr_relay_jobs_v1" in NOSTR_CLAIM_SQL
    assert any(sql == FINALIZE_NOSTR_RELAY_SQL for sql, _params in executor.calls)


def test_nostr_dsn_adds_a_fixed_libpq_role_option() -> None:
    source = (
        "postgresql://pokecrack_nostr_worker_login:fixture-secret@"
        "nostr.example.invalid/pokecrack?sslmode=require"
    )
    dsn = _dsn_with_fixed_nostr_role(source)

    assert dsn == (
        "postgresql://pokecrack_nostr_worker_login:fixture-secret@"
        "nostr.example.invalid/pokecrack?sslmode=require&"
        "options=-c%20role%3Dpokecrack_nostr_worker"
    )
    assert WorkerRole.NOSTR_COLLECTOR.value == "nostr-collector"

    already_fixed = _dsn_with_fixed_nostr_role(
        "postgresql://pokecrack_nostr_worker_login:fixture-secret@"
        "nostr.example.invalid/pokecrack?sslmode=require&"
        "options=-c%20role%3Dpokecrack_nostr_worker"
    )
    assert already_fixed.count("options=") == 1
    assert already_fixed == dsn


@pytest.mark.parametrize(
    "dsn",
    (
        "host=db.example.invalid dbname=pokecrack",
        "postgresql://wrong-worker:fixture-secret@nostr.example.invalid/pokecrack",
        "postgresql://pokecrack_nostr_worker_login:fixture-secret@"
        "nostr.example.invalid/pokecrack#fragment",
        "postgresql://pokecrack_nostr_worker_login:fixture-secret@"
        "nostr.example.invalid/pokecrack?options=-c%20statement_timeout%3D0",
        "postgresql://pokecrack_nostr_worker_login:fixture-secret@"
        "nostr.example.invalid/pokecrack?"
        "options=-c%20role%3Dpokecrack_nostr_worker&"
        "options=-c%20role%3Dpokecrack_nostr_worker",
        "postgresql://pokecrack_nostr_worker_login:fixture-secret@"
        "nostr.example.invalid/pokecrack?sslmode=require&sslmode=require",
        "postgresql://pokecrack_nostr_worker_login:fixture-secret@"
        "nostr.example.invalid/pokecrack?user=pokecrack_nostr_attestor_login&"
        "sslmode=require",
        "postgresql://pokecrack_nostr_worker_login:fixture-secret@"
        "nostr.example.invalid/pokecrack?sslmode=prefer",
        "postgresql://pokecrack_nostr_worker_login:fixture-secret@"
        "nostr.example.invalid/pokecrack",
    ),
)
def test_nostr_dsn_rejects_ambiguous_or_caller_controlled_options(dsn: str) -> None:
    with pytest.raises(LiveCompositionError):
        _dsn_with_fixed_nostr_role(dsn)


def test_nostr_repository_uses_only_source_scoped_queue_wrappers() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running")],
            [_job_row(status="running")],
            [_job_row(status="completed")],
            [_job_row(status="pending")],
            [_job_row(status="failed")],
        ]
    )
    repository = NostrPostgresJobRepository(executor)
    completion = NostrRelayCompletion(
        relay_key="primal",
        since=NOW - timedelta(minutes=5),
        until=NOW,
        checkpoint=None,
        incomplete=False,
        events_seen=0,
        bytes_seen=0,
    )

    assert repository.lease(
        "worker-1",
        now=NOW,
        lease_for=timedelta(minutes=5),
        kinds={NOSTR_RELAY_JOB_TYPE},
    )
    assert repository.heartbeat(
        "00000000-0000-0000-0000-000000000001",
        worker_id="worker-1",
        lease_generation=1,
        now=NOW,
        lease_for=timedelta(minutes=5),
    )
    assert repository.complete(
        "00000000-0000-0000-0000-000000000001",
        worker_id="worker-1",
        lease_generation=1,
        now=NOW,
        effect=completion,
    )
    assert repository.pause_for_budget(
        "00000000-0000-0000-0000-000000000001",
        worker_id="worker-1",
        lease_generation=1,
        now=NOW,
        retry_at=NOW + timedelta(hours=1),
    )
    assert repository.fail(
        "00000000-0000-0000-0000-000000000001",
        "bounded failure",
        worker_id="worker-1",
        lease_generation=1,
        now=NOW,
    )

    assert [sql for sql, _params in executor.calls] == [
        NOSTR_CLAIM_SQL,
        NOSTR_HEARTBEAT_SQL,
        FINALIZE_NOSTR_RELAY_SQL,
        NOSTR_PAUSE_BUDGET_SQL,
        NOSTR_FAIL_SQL,
    ]
    assert "kinds" not in executor.calls[0][1]
    for sql, _params in executor.calls:
        assert "ingest.claim_jobs_v2" not in sql
        assert "ingest.heartbeat_job_v2" not in sql
        assert "ingest.fail_job_v2" not in sql
        assert "ingest.pause_job_for_budget_v2" not in sql

    assert "p_worker_id => %(worker_id)s" in NOSTR_CLAIM_SQL
    assert "p_lease_seconds => %(lease_seconds)s::integer" in NOSTR_CLAIM_SQL
    assert "ingest.enqueue_due_nostr_relay_jobs_v1" in NOSTR_CLAIM_SQL
    assert "p_job_id => %(job_id)s::uuid" in NOSTR_HEARTBEAT_SQL
    assert "p_lease_generation => %(lease_generation)s::bigint" in NOSTR_HEARTBEAT_SQL
    assert "p_error_code => %(error_code)s" in NOSTR_FAIL_SQL
    assert "p_retryable => %(retryable)s::boolean" in NOSTR_FAIL_SQL
    assert "p_retry_at => %(retry_at)s::timestamptz" in NOSTR_PAUSE_BUDGET_SQL

    with pytest.raises(ValueError, match="only source.nostr.relay"):
        repository.lease(
            "worker-1",
            now=NOW,
            lease_for=timedelta(minutes=5),
            kinds={"source.youtube.discovery"},
        )


def test_enabled_nostr_health_uses_only_scoped_runtime_contracts() -> None:
    settings = Settings(
        _env_file=None,
        data_mode="live",
        nostr_supabase_db_url="postgresql://nostr.example.invalid/pokecrack",
        worker_id="nostr-collector-test",
        worker_role="nostr-collector",
        nostr_collection_enabled=True,
    )
    executor = RecordingExecutor([[{"ready": False}]])

    with pytest.raises(LiveCompositionError, match="dependencies"):
        write_health_heartbeat(settings, executor=executor)

    sql, params = executor.calls[0]
    assert params == {"worker_type": "nostr-collector"}
    assert "ingest.claim_nostr_relay_jobs_v1(text,integer)" in sql
    assert "ingest.enqueue_due_nostr_relay_jobs_v1(text)" in sql
    assert "ingest.heartbeat_nostr_relay_job_v1(uuid,text,bigint,integer)" in sql
    assert "ingest.fail_nostr_relay_job_v1(uuid,text,bigint,text,text,boolean)" in sql
    assert "ingest.pause_nostr_relay_job_v1(uuid,text,bigint,timestamptz)" in sql
    assert "ingest.upsert_nostr_worker_heartbeat_v1(text,text,jsonb)" in sql
    assert "ingest.begin_nostr_relay_job(uuid,text,bigint,text)" in sql
    assert "ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)" in sql
    assert "ingest.nostr_worker_runtime_ready_v1()" in sql
    assert "ingest.get_nostr_worker_policy_snapshot_v1()" in sql
    assert "FROM ingest.get_nostr_worker_policy_snapshot_v1() AS policies" in sql
    assert "FROM ingest.source_policies" not in sql
    assert "ingest.claim_jobs_v2" not in sql
    assert "ingest.heartbeat_job_v2" not in sql
    assert "ingest.fail_job_v2" not in sql
    assert "ingest.pause_job_for_budget_v2" not in sql
    assert "ingest.upsert_worker_heartbeat_v1" not in sql
    assert sql.count("policies.config - 'relay_key' - 'endpoint' - 'nip11_url'") == 1
    assert "degraded_missing_relay_specific_terms" in sql
    assert "wss://relay.primal.net/" in sql
    assert "wss://nos.lol/" in sql
    assert "wss://relay.nostr.net/" in sql
    assert "ingest.source_request_gates" in sql
    assert "ingest.nostr_relay_candidates" in sql
    assert "ingest.nostr_relay_observations" in sql
    assert "ingest.nostr_relay_checkpoints" in sql
    assert "ingest.nostr_relay_observations_id_seq" in sql
    assert "has_any_column_privilege" in sql
    assert "has_sequence_privilege" in sql


def test_nostr_health_uses_the_dedicated_worker_heartbeat_wrapper() -> None:
    settings = Settings(
        _env_file=None,
        data_mode="live",
        nostr_supabase_db_url="postgresql://nostr.example.invalid/pokecrack",
        worker_id="nostr-collector-test",
        worker_role="nostr-collector",
        nostr_collection_enabled=True,
    )
    executor = RecordingExecutor([[{"ready": True}], [{"last_seen_at": NOW}]])

    heartbeat = write_health_heartbeat(settings, executor=executor)

    assert heartbeat.worker_role is WorkerRole.NOSTR_COLLECTOR
    heartbeat_sql, heartbeat_params = executor.calls[1]
    assert "ingest.upsert_nostr_worker_heartbeat_v1" in heartbeat_sql
    assert "ingest.upsert_worker_heartbeat_v1" not in heartbeat_sql
    assert heartbeat_params["worker_id"] == "nostr-collector-test"
    assert set(json.loads(str(heartbeat_params["metadata"]))) == {
        "command",
        "data_mode",
        "max_concurrency",
        "role_ready",
    }


def test_nostr_enablement_freezes_cleanup_schedule() -> None:
    isolated = {
        "worker_id": "nostr-collector-test",
        "worker_role": "nostr-collector",
        "nostr_supabase_db_url": "postgresql://nostr.example.invalid/pokecrack",
    }
    with pytest.raises(ValidationError, match="NOSTR_COLLECTION_ENABLED.*SCHEDULE_CLEANUP"):
        Settings(
            _env_file=None,
            nostr_collection_enabled=True,
            schedule_cleanup="0 0 * * 0",
            **isolated,
        )


def test_generic_scheduler_ignores_legacy_nostr_schedule_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCHEDULE_NOSTR_COLLECTION", "not-a-cron")
    settings = Settings(
        _env_file=None,
        data_mode="live",
        supabase_db_url="postgresql://db.example.invalid/pokecrack",
        worker_id="scheduler-test",
        worker_role="scheduler",
    )

    entries = live_schedule_entries(settings)

    assert all(entry.job_type != NOSTR_RELAY_JOB_TYPE for entry in entries)
    cleanup = next(entry for entry in entries if entry.name == "cleanup")
    assert cleanup.catch_up_within == timedelta(hours=36)
    assert cleanup.catch_up_check_interval == timedelta(hours=1)
