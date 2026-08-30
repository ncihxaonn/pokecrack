from __future__ import annotations

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

from pokecrack_worker.collectors.official_api.bluesky import (
    BLUESKY_JETSTREAM_URL,
    BLUESKY_MAX_EVENTS,
    BLUESKY_MAX_MESSAGE_BYTES,
    BLUESKY_MAX_STREAM_BYTES,
    BLUESKY_POLICY_URL,
    BLUESKY_STREAM_WINDOW_SECONDS,
    BLUESKY_SUBPROTOCOL,
    BlueskyConsumerTooSlowError,
    BlueskyCursorTooOldError,
    BlueskyInvalidMessage,
    BlueskyJetstreamCollector,
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
    BlueskyJetstreamCompletion,
    BlueskySourceItemWrite,
    JobStatus,
    PostgresJobRepository,
)
from pokecrack_worker.jobs.postgres import FINALIZE_BLUESKY_JETSTREAM_SQL

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
) -> bytes:
    payload: dict[str, object] = {
        "$type": "network.bsky.jetstream.subscribeEvents#commit",
        "seq": seq,
        "did": DID,
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
            "createdAt": "2026-08-30T11:59:00Z",
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
                "keywords": [
                    {"name": "pokemon", "keyword": "Pokemon", "group": "identity"}
                ],
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
        "stream_window_seconds": 40,
        "subprotocol": BLUESKY_SUBPROTOCOL,
    }
    assert "policies.config = '{" in LIVE_ROLE_DEPENDENCIES_SQL
    assert '"subprotocol":"xrpc.v1.json"' in LIVE_ROLE_DEPENDENCIES_SQL


def test_parser_validates_v2_envelope_time_and_operations() -> None:
    event = parse_jetstream_message(_frame(42, operation="update"))
    assert event is not None
    assert event.seq == 42
    assert event.did == DID
    assert event.operation == "update"
    assert event.time == datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    assert event.record is not None
    assert event.record["text"] == "Pokemon TCG opening"

    deletion = parse_jetstream_message(_frame(43, operation="delete", rkey="post2"))
    assert deletion is not None
    assert deletion.record is None
    assert deletion.operation == "delete"

    assert parse_jetstream_message(_frame(44, collection="app.bsky.feed.like")) is None
    with pytest.raises(BlueskyInvalidMessage):
        parse_jetstream_message(b"x" * (BLUESKY_MAX_MESSAGE_BYTES + 1))
    with pytest.raises(Exception, match="bluesky_time_invalid"):
        parse_jetstream_message(_frame(45, time="1700000000"))
    with pytest.raises(BlueskyConsumerTooSlowError):
        parse_jetstream_message(_error_frame("ConsumerTooSlow"))
    with pytest.raises(BlueskyCursorTooOldError):
        parse_jetstream_message(_error_frame("CursorTooOld"))


def test_collector_is_bounded_idempotent_and_advances_cursor_for_nonmatches() -> None:
    messages = (
        _frame(1, text="just opening"),
        _frame(2, text="Pokemon TCG!\r\x00opening"),
        _frame(3, operation="update", text="Pokemon TCG updated"),
        _frame(3, operation="update", text="Pokemon TCG duplicate"),
        _frame(4, rkey="post2", text="Pokemon TCG second"),
        _frame(5, operation="delete", rkey="post2"),
    )
    transport = RecordingTransport(messages)
    collector = BlueskyJetstreamCollector(transport=transport, keywords=_registry())

    result = collector.collect()

    assert result.start_cursor is None
    assert result.end_cursor == 5
    assert result.events_seen == len(messages)
    assert result.bytes_seen == sum(map(len, messages))
    assert [item.cursor for item in result.candidates] == [3]
    assert result.candidates[0].at_uri.endswith("/post1")
    assert result.candidates[0].text_excerpt == "Pokemon TCG updated"
    assert result.candidates[0].record_sha256.isascii()
    assert len(result.candidates[0].record_sha256) == 64
    assert [(item.at_uri, item.cursor) for item in result.deletions] == [
        (f"at://{DID}/{BLUESKY_POST_COLLECTION}/post2", 5)
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
        transport=RecordingTransport((_frame(5, text="Pokemon TCG later"), _frame(6))),
        keywords=_registry(),
    )
    resumed = inclusive.collect(start_cursor=5)
    assert resumed.end_cursor == 6
    assert resumed.events_seen == 2
    assert resumed.candidates[0].cursor == 6


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


def test_bluesky_enablement_keeps_schedule_fixed() -> None:
    with pytest.raises(ValidationError, match="SCHEDULE_BLUESKY_COLLECTION"):
        Settings(
            _env_file=None,
            bluesky_collection_enabled=True,
            schedule_bluesky_collection="*/5 * * * *",
        )
