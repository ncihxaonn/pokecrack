from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import SecretStr

from pokecrack_worker.collectors.official_api.tcgdex import APIResponse
from pokecrack_worker.collectors.official_api.youtube import YouTubeRequestStateUnknown
from pokecrack_worker.composition import (
    CLEANUP_JOB_TYPE,
    TCGDEX_SETS_JOB_TYPE,
    YOUTUBE_DISCOVERY_JOB_TYPE,
    LiveCompositionError,
    build_live_scheduler,
    build_live_worker_runtime,
    live_schedule_entries,
    require_worker_job_types,
    write_health_heartbeat,
)
from pokecrack_worker.config.registries import REQUIRED_YOUTUBE_QUERIES
from pokecrack_worker.config.settings import Settings
from pokecrack_worker.runtime import RuntimeStatus

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


class RecordingExecutor:
    def __init__(self, responses: Sequence[Sequence[Mapping[str, Any]]] = ()) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    def query(self, sql: str, params: Mapping[str, object]) -> Sequence[Mapping[str, Any]]:
        self.calls.append((sql, dict(params)))
        return self.responses.pop(0) if self.responses else ()


def _settings(role: str | None, **values: object) -> Settings:
    return Settings(
        _env_file=None,
        data_mode="live",
        supabase_db_url="postgresql://db.example.invalid/pokecrack",
        ai_provider="fixture",
        worker_id="worker-1",
        worker_role=role,
        worker_max_concurrency=1,
        **values,
    )


def _job_row(
    *,
    status: str,
    payload: Mapping[str, object] | None = None,
    locked: bool = True,
    job_type: str = CLEANUP_JOB_TYPE,
) -> dict[str, object]:
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "job_type": job_type,
        "payload": dict(payload or {}),
        "status": status,
        "priority": 10,
        "available_at": NOW,
        "attempts": 1,
        "max_attempts": (
            3 if job_type in {TCGDEX_SETS_JOB_TYPE, YOUTUBE_DISCOVERY_JOB_TYPE} else 5
        ),
        "lease_generation": 1,
        "locked_by": "worker-1" if locked else None,
        "locked_at": NOW if locked else None,
        "lock_expires_at": NOW + timedelta(minutes=5) if locked else None,
        "last_error_code": None,
        "last_error_message": None,
        "completed_at": NOW if status == "completed" else None,
        "dedupe_key": f"schedule:{job_type}:20260825T120000Z",
        "created_at": NOW,
        "updated_at": NOW,
    }


def _checkpoint_row(
    *,
    acquired: bool = True,
    retry_at: datetime | None = None,
    etag: str | None = None,
    content_sha256: str | None = None,
    item_count: int = 0,
    revision: int = 0,
) -> dict[str, object]:
    return {
        "acquired": acquired,
        "retry_at": retry_at,
        "etag": etag,
        "content_sha256": content_sha256,
        "item_count": item_count,
        "revision": revision,
    }


def test_live_health_probes_postgres_and_upserts_a_role_heartbeat() -> None:
    executor = RecordingExecutor([[{"ready": True}], [{"last_seen_at": NOW}]])

    heartbeat = write_health_heartbeat(_settings("watchdog"), executor=executor)

    assert heartbeat.worker_id == "worker-1"
    assert heartbeat.worker_role.value == "watchdog"
    assert heartbeat.last_seen_at == NOW
    assert len(executor.calls) == 2
    dependency_sql, dependency_params = executor.calls[0]
    assert "ingest.source_request_gates" in dependency_sql
    assert "ingest.claim_jobs_v2" in dependency_sql
    assert "ingest.heartbeat_job_v2" in dependency_sql
    assert "ingest.fail_job_v2" in dependency_sql
    assert "ingest.finalize_cleanup_job" in dependency_sql
    assert "ingest.upsert_worker_heartbeat_v1" in dependency_sql
    assert "ingest.pause_job_for_budget_v2" in dependency_sql
    assert "NOT has_table_privilege" in dependency_sql
    assert dependency_params == {"worker_type": "watchdog", "youtube_enabled": False}
    sql, params = executor.calls[1]
    assert "ingest.upsert_worker_heartbeat_v1" in sql
    assert "INSERT INTO ingest.worker_heartbeats" not in sql
    assert "UPDATE ingest.worker_heartbeats" not in sql
    assert params["worker_id"] == "worker-1"
    assert params["worker_type"] == "watchdog"
    assert json.loads(str(params["metadata"])) == {
        "command": "health",
        "data_mode": "live",
        "max_concurrency": 1,
        "role_ready": True,
    }
    assert "postgresql://" not in repr(executor.calls)


def test_collector_health_fails_before_heartbeat_when_policy_or_rpcs_are_unavailable() -> None:
    executor = RecordingExecutor([[{"ready": False}]])

    with pytest.raises(LiveCompositionError) as raised:
        write_health_heartbeat(_settings("collector"), executor=executor)

    assert raised.value.code == "live_dependencies_unavailable"
    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert "ingest.source_request_gates" in sql
    assert "ingest.claim_jobs_v2" in sql
    assert "ingest.heartbeat_job_v2" in sql
    assert "ingest.fail_job_v2" in sql
    assert "ingest.begin_tcgdex_sets_job" in sql
    assert "ingest.finalize_tcgdex_sets_job" in sql
    assert "tcgdex_catalog" in sql
    assert "has_function_privilege" in sql
    assert "policies.base_url = 'https://api.tcgdex.net/v2'" in sql
    assert "policies.min_delay_seconds = 10" in sql
    assert "policies.max_items_per_run = 1000" in sql
    assert "policies.expected_interval_seconds = 86400" in sql
    assert params == {"worker_type": "collector", "youtube_enabled": False}
    assert "INSERT INTO ingest.worker_heartbeats" not in sql


def test_enabled_youtube_health_requires_exact_rpc_policy_and_permissions() -> None:
    executor = RecordingExecutor([[{"ready": False}]])

    with pytest.raises(LiveCompositionError, match="dependencies"):
        write_health_heartbeat(_youtube_settings(), executor=executor)

    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert params == {"worker_type": "collector", "youtube_enabled": True}
    assert "ingest.begin_youtube_discovery_job" in sql
    assert "ingest.finalize_youtube_discovery_job" in sql
    assert "youtube_discovery" in sql
    assert "YouTube Global Discovery API" in sql
    assert "policies.max_pages_per_run = 1" in sql
    assert "policies.max_items_per_run = 25" in sql
    assert "policies.retention_days = 28" in sql
    assert "youtube-global-discovery-v1" in sql
    assert '"max_response_bytes":2097152' in sql
    assert "youtube-metadata-v1" not in sql
    assert "geography_status" not in sql
    assert "evidence_tier" not in sql
    assert "has_function_privilege" in sql


def test_enabled_youtube_scheduler_requires_the_shared_exact_dependencies() -> None:
    settings = _youtube_settings("scheduler")
    executor = RecordingExecutor([[{"ready": False}]])

    with pytest.raises(LiveCompositionError, match="dependencies"):
        write_health_heartbeat(settings, executor=executor)

    assert settings.youtube_api_key is None
    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert params == {"worker_type": "scheduler", "youtube_enabled": True}
    assert sql.startswith("WITH youtube_dependencies AS")
    assert sql.count("policies.source_key = 'youtube_discovery'") == 1
    assert sql.count("policies.retention_days = 28") == 1
    assert sql.count("ingest.begin_youtube_discovery_job(uuid,text,bigint)") == 2
    assert sql.count("ingest.finalize_youtube_discovery_job(uuid,text,bigint,jsonb)") == 2
    assert sql.count("(SELECT ready FROM youtube_dependencies)") == 2
    assert "policies.base_url = 'https://youtube.googleapis.com/youtube/v3'" in sql
    assert "policies.max_pages_per_run = 1" in sql
    assert "policies.max_items_per_run = 25" in sql
    assert "policies.expected_interval_seconds = 21600" in sql
    assert "youtube-global-discovery-v1" in sql
    assert "INSERT INTO ingest.worker_heartbeats" not in sql
    assert "YOUTUBE_API_KEY" not in repr(executor.calls)


def test_flag_off_scheduler_health_only_requires_enqueue_readiness() -> None:
    settings = _settings("scheduler")
    executor = RecordingExecutor([[{"ready": True}], [{"last_seen_at": NOW}]])

    heartbeat = write_health_heartbeat(settings, executor=executor)

    assert heartbeat.worker_role.value == "scheduler"
    assert settings.youtube_collection_enabled is False
    assert settings.youtube_api_key is None
    dependency_sql, dependency_params = executor.calls[0]
    scheduler_branch = dependency_sql[
        dependency_sql.index("WHEN 'scheduler'") : dependency_sql.index("WHEN 'watchdog'")
    ]
    assert dependency_params == {"worker_type": "scheduler", "youtube_enabled": False}
    assert "ingest.enqueue_scheduled_job_v1" in scheduler_branch
    assert "has_function_privilege" in scheduler_branch
    assert "NOT %(youtube_enabled)s::boolean" in scheduler_branch
    assert "OR (SELECT ready FROM youtube_dependencies)" in scheduler_branch
    assert "YOUTUBE_API_KEY" not in repr(executor.calls)


def test_live_health_refuses_unready_roles_before_writing_a_heartbeat() -> None:
    executor = RecordingExecutor([[{"last_seen_at": NOW}]])

    with pytest.raises(LiveCompositionError) as raised:
        write_health_heartbeat(_settings("ai-worker"), executor=executor)

    assert raised.value.code == "worker_role_not_ready"
    assert executor.calls == []


@pytest.mark.parametrize("role", (None, "unknown", "ai-worker", "aggregator"))
def test_live_worker_roles_without_safe_handlers_fail_closed(role: str | None) -> None:
    expected = "worker_role_not_ready" if role in {"ai-worker", "aggregator"} else None

    with pytest.raises(LiveCompositionError) as raised:
        require_worker_job_types(_settings(role))

    if expected is not None:
        assert raised.value.code == expected
    else:
        assert raised.value.code in {"worker_role_missing", "unsupported_worker_role"}


def test_watchdog_runtime_claims_only_the_cleanup_job_type() -> None:
    executor = RecordingExecutor()
    runtime = build_live_worker_runtime(_settings("watchdog"), executor=executor, clock=lambda: NOW)

    result = runtime.run_once()

    assert result.status is RuntimeStatus.IDLE
    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert "ingest.claim_jobs_v2" in sql
    assert params["kinds"] == [CLEANUP_JOB_TYPE]


def test_live_worker_dry_run_never_touches_the_database() -> None:
    executor = RecordingExecutor()
    runtime = build_live_worker_runtime(_settings("watchdog"), executor=executor, clock=lambda: NOW)

    result = runtime.run(once=False, dry_run=True)

    assert result.results[0].status is RuntimeStatus.DRY_RUN
    assert executor.calls == []


class RecordingTCGdexTransport:
    def __init__(self, response: APIResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def get(self, url: str, *, headers: dict[str, str], timeout_seconds: float) -> APIResponse:
        self.calls.append((url, headers, timeout_seconds))
        return self.response


class RecordingYouTubeTransport:
    def __init__(self, responses: Sequence[APIResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str], float]] = []

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


TCGDEX_BODY = b'[{"id":"sv1","name":"Scarlet & Violet","cardCount":{"total":258,"official":198}}]'
YOUTUBE_SEARCH_BODY = json.dumps(
    {
        "items": [
            {
                "id": {"kind": "youtube#video", "videoId": "dQw4w9WgXcQ"},
                "snippet": {
                    "publishedAt": "2026-08-24T08:00:00Z",
                    "channelId": "UC-private-fixture",
                    "title": "Pokemon ETB opening",
                    "description": "Elite Trainer Box, batch code: AB-123",
                },
            }
        ]
    }
).encode()


def _youtube_settings(role: str = "collector") -> Settings:
    values: dict[str, object] = {"youtube_collection_enabled": True}
    if role != "scheduler":
        values["youtube_api_key"] = "fixture-youtube-secret"
    return _settings(role, **values)


def test_collector_runs_only_the_fenced_tcgdex_sets_pipeline() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running", job_type=TCGDEX_SETS_JOB_TYPE)],
            [_checkpoint_row()],
            [_job_row(status="completed", locked=False, job_type=TCGDEX_SETS_JOB_TYPE)],
        ]
    )
    transport = RecordingTCGdexTransport(APIResponse(200, {"etag": '"v1"'}, TCGDEX_BODY))
    runtime = build_live_worker_runtime(
        _settings("collector"),
        executor=executor,
        clock=lambda: NOW,
        tcgdex_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.COMPLETED
    assert result.job_type == TCGDEX_SETS_JOB_TYPE
    assert len(executor.calls) == 3
    assert executor.calls[0][1]["kinds"] == [TCGDEX_SETS_JOB_TYPE]
    assert "ingest.begin_tcgdex_sets_job" in executor.calls[1][0]
    finalizer_sql, finalizer_params = executor.calls[2]
    assert "ingest.finalize_tcgdex_sets_job" in finalizer_sql
    persisted = json.loads(str(finalizer_params["result"]))
    assert persisted == {
        "content_sha256": persisted["content_sha256"],
        "etag": '"v1"',
        "expected_revision": 0,
        "outcome": "changed",
        "sets": [
            {
                "card_count_official": 198,
                "card_count_total": 258,
                "id": "sv1",
                "name": "Scarlet & Violet",
            }
        ],
        "version": 1,
    }
    assert len(persisted["content_sha256"]) == 64
    assert len(transport.calls) == 1


def test_enabled_collector_runs_fenced_global_youtube_activity_pipeline() -> None:
    executor = RecordingExecutor(
        [
            [
                _job_row(
                    status="running",
                    payload={"query_name": "pokemon-tcg-etb-opening"},
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ],
            [{"acquired": True, "retry_at": None}],
            [
                _job_row(
                    status="completed",
                    payload={"query_name": "pokemon-tcg-etb-opening"},
                    locked=False,
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ],
        ]
    )
    transport = RecordingYouTubeTransport([APIResponse(200, {}, YOUTUBE_SEARCH_BODY)])
    runtime = build_live_worker_runtime(
        _youtube_settings(),
        executor=executor,
        clock=lambda: NOW,
        youtube_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.COMPLETED
    assert executor.calls[0][1]["kinds"] == [
        TCGDEX_SETS_JOB_TYPE,
        YOUTUBE_DISCOVERY_JOB_TYPE,
    ]
    assert "ingest.begin_youtube_discovery_job" in executor.calls[1][0]
    assert len(transport.calls) == 1
    assert transport.calls[0][0].endswith("/search")
    assert all("key" not in params for _url, params, _timeout in transport.calls)
    assert transport.calls[0][1]["q"] == "Pokemon TCG ETB opening"
    assert transport.calls[0][1]["relevanceLanguage"] == "en"
    assert transport.calls[0][1]["fields"] == ("items(id(kind,videoId),snippet(publishedAt,title))")
    assert "regionCode" not in transport.calls[0][1]
    assert transport.calls[0][2] == 30.0
    finalizer_sql, finalizer_params = executor.calls[2]
    assert "ingest.finalize_youtube_discovery_job" in finalizer_sql
    persisted = json.loads(str(finalizer_params["result"]))
    assert persisted["query_name"] == "pokemon-tcg-etb-opening"
    assert len(persisted["items"]) == 1
    item = persisted["items"][0]
    assert item["collector_version"] == "youtube-global-discovery-v1"
    assert item["source_policy_version"] == "youtube-global-discovery-v1"
    assert item["title"] == "Pokemon ETB opening"
    assert item["published_at"] == "2026-08-24T08:00:00Z"
    assert set(item) == {
        "external_id",
        "source_url",
        "title",
        "published_at",
        "collector_version",
        "source_policy_version",
    }
    serialized = json.dumps(persisted)
    assert "UC-private-fixture" not in serialized
    assert "must-not-persist" not in serialized
    assert "Elite Trainer Box, batch code: AB-123" not in serialized
    assert "fixture-youtube-secret" not in repr(executor.calls + transport.calls)


@pytest.mark.parametrize(
    "payload",
    (
        {},
        {"query_name": "not-approved"},
        {"query_name": "pokemon-tcg-etb-opening", "region_code": "AU"},
    ),
)
def test_youtube_job_payload_cannot_expand_query_or_geography_scope(
    payload: Mapping[str, object],
) -> None:
    executor = RecordingExecutor(
        [
            [
                _job_row(
                    status="running",
                    payload=payload,
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ],
            [
                _job_row(
                    status="dead",
                    payload=payload,
                    locked=False,
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ],
        ]
    )
    transport = RecordingYouTubeTransport([])
    runtime = build_live_worker_runtime(
        _youtube_settings(),
        executor=executor,
        clock=lambda: NOW,
        youtube_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.FAILED
    assert result.error_code == "ValueError"
    assert len(executor.calls) == 2
    assert "ingest.begin_youtube_discovery_job" not in executor.calls[1][0]
    assert transport.calls == []


def test_busy_youtube_request_gate_defers_before_network_access() -> None:
    retry_at = NOW + timedelta(seconds=2)
    payload = {"query_name": "pokemon-tcg-pack-opening"}
    executor = RecordingExecutor(
        [
            [
                _job_row(
                    status="running",
                    payload=payload,
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ],
            [{"acquired": False, "retry_at": retry_at}],
            [
                _job_row(
                    status="pending",
                    payload=payload,
                    locked=False,
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ],
        ]
    )
    transport = RecordingYouTubeTransport([])
    runtime = build_live_worker_runtime(
        _youtube_settings(),
        executor=executor,
        clock=lambda: NOW,
        youtube_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.DEFERRED
    assert result.error_code == "youtube_request_deferred"
    assert transport.calls == []
    assert "ingest.pause_job_for_budget_v2" in executor.calls[2][0]
    assert "UPDATE ingest.jobs" not in executor.calls[2][0]


@pytest.mark.parametrize(
    ("response", "error_code", "retryable"),
    (
        (APIResponse(200, {}, b"not-json"), "invalid_response", False),
        (APIResponse(429, {}, b"quota"), "http_error", True),
    ),
)
def test_youtube_response_failures_keep_typed_retry_disposition(
    response: APIResponse,
    error_code: str,
    retryable: bool,
) -> None:
    payload = {"query_name": "pokemon-tcg-pack-opening"}
    executor = RecordingExecutor(
        [
            [
                _job_row(
                    status="running",
                    payload=payload,
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ],
            [{"acquired": True, "retry_at": None}],
            [
                _job_row(
                    status="pending" if retryable else "dead",
                    payload=payload,
                    locked=False,
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ],
        ]
    )
    runtime = build_live_worker_runtime(
        _youtube_settings(),
        executor=executor,
        clock=lambda: NOW,
        youtube_transport=RecordingYouTubeTransport([response]),
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.FAILED
    assert result.error_code == error_code
    fail_sql, fail_params = executor.calls[2]
    assert "ingest.fail_job_v2" in fail_sql
    assert fail_params["error_code"] == error_code
    assert fail_params["retryable"] is retryable


def test_unreaped_youtube_request_is_fatal_and_leaves_request_gate_fenced() -> None:
    class UnknownStateTransport:
        def get(self, *_args: object, **_kwargs: object) -> APIResponse:
            raise YouTubeRequestStateUnknown()

    payload = {"query_name": "pokemon-tcg-pack-opening"}
    executor = RecordingExecutor(
        [
            [
                _job_row(
                    status="running",
                    payload=payload,
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ],
            [{"acquired": True, "retry_at": None}],
        ]
    )
    runtime = build_live_worker_runtime(
        _youtube_settings(),
        executor=executor,
        clock=lambda: NOW,
        youtube_transport=UnknownStateTransport(),
    )

    with pytest.raises(YouTubeRequestStateUnknown):
        runtime.run_once()

    assert len(executor.calls) == 2
    assert "ingest.begin_youtube_discovery_job" in executor.calls[1][0]
    assert all("ingest.fail_job_v2" not in sql for sql, _params in executor.calls)
    assert all(
        "ingest.finalize_youtube_discovery_job" not in sql for sql, _params in executor.calls
    )


def test_stale_youtube_finalizer_cannot_persist_discovered_metadata() -> None:
    payload = {"query_name": "pokemon-tcg-etb-opening"}
    executor = RecordingExecutor(
        [
            [
                _job_row(
                    status="running",
                    payload=payload,
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ],
            [{"acquired": True, "retry_at": None}],
            [],
        ]
    )
    transport = RecordingYouTubeTransport([APIResponse(200, {}, YOUTUBE_SEARCH_BODY)])
    runtime = build_live_worker_runtime(
        _youtube_settings(),
        executor=executor,
        clock=lambda: NOW,
        youtube_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.LEASE_LOST
    assert len(transport.calls) == 1
    assert "ingest.finalize_youtube_discovery_job" in executor.calls[2][0]
    assert all("INSERT INTO ingest.source_items" not in sql for sql, _params in executor.calls)


def test_stale_tcgdex_preflight_blocks_the_network_request() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running", job_type=TCGDEX_SETS_JOB_TYPE)],
            [],
        ]
    )
    transport = RecordingTCGdexTransport(APIResponse(200, {}, TCGDEX_BODY))
    runtime = build_live_worker_runtime(
        _settings("collector"),
        executor=executor,
        clock=lambda: NOW,
        tcgdex_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.LEASE_LOST
    assert len(executor.calls) == 2
    assert "ingest.begin_tcgdex_sets_job" in executor.calls[1][0]
    assert transport.calls == []


def test_database_policy_rejection_blocks_tcgdex_before_network_access() -> None:
    class PolicyRejectedExecutor(RecordingExecutor):
        def query(self, sql: str, params: Mapping[str, object]) -> Sequence[Mapping[str, Any]]:
            self.calls.append((sql, dict(params)))
            if "ingest.claim_jobs_v2" in sql:
                return [_job_row(status="running", job_type=TCGDEX_SETS_JOB_TYPE)]
            if "ingest.begin_tcgdex_sets_job" in sql:
                raise RuntimeError("TCGdex source policy is disabled")
            return [_job_row(status="pending", locked=False, job_type=TCGDEX_SETS_JOB_TYPE)]

    executor = PolicyRejectedExecutor()
    transport = RecordingTCGdexTransport(APIResponse(200, {}, TCGDEX_BODY))
    runtime = build_live_worker_runtime(
        _settings("collector"),
        executor=executor,
        clock=lambda: NOW,
        tcgdex_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.FAILED
    assert result.error_code == "RuntimeError"
    assert transport.calls == []
    assert len(executor.calls) == 3
    assert "ingest.fail_job_v2" in executor.calls[2][0]


def test_invalid_tcgdex_response_is_dead_lettered_without_blind_retries() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running", job_type=TCGDEX_SETS_JOB_TYPE)],
            [_checkpoint_row()],
            [_job_row(status="dead", locked=False, job_type=TCGDEX_SETS_JOB_TYPE)],
        ]
    )
    transport = RecordingTCGdexTransport(APIResponse(200, {}, b"not-json"))
    runtime = build_live_worker_runtime(
        _settings("collector"),
        executor=executor,
        clock=lambda: NOW,
        tcgdex_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.FAILED
    assert result.error_code == "invalid_response"
    fail_sql, fail_params = executor.calls[2]
    assert "ingest.fail_job_v2" in fail_sql
    assert fail_params["error_code"] == "invalid_response"
    assert fail_params["retryable"] is False


def test_busy_tcgdex_request_gate_defers_without_network_or_consuming_an_attempt() -> None:
    retry_at = NOW + timedelta(seconds=10)
    executor = RecordingExecutor(
        [
            [_job_row(status="running", job_type=TCGDEX_SETS_JOB_TYPE)],
            [_checkpoint_row(acquired=False, retry_at=retry_at)],
            [_job_row(status="pending", locked=False, job_type=TCGDEX_SETS_JOB_TYPE)],
        ]
    )
    transport = RecordingTCGdexTransport(APIResponse(200, {}, TCGDEX_BODY))
    runtime = build_live_worker_runtime(
        _settings("collector"),
        executor=executor,
        clock=lambda: NOW,
        tcgdex_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.DEFERRED
    assert result.error_code == "tcgdex_request_deferred"
    assert transport.calls == []
    pause_sql, pause_params = executor.calls[2]
    assert "ingest.pause_job_for_budget_v2" in pause_sql
    assert "UPDATE ingest.jobs" not in pause_sql
    assert pause_params["retry_at"] == retry_at


def test_tcgdex_finalizer_rejection_is_failed_without_ending_the_worker_loop() -> None:
    class RejectingFinalizerExecutor(RecordingExecutor):
        def query(self, sql: str, params: Mapping[str, object]) -> Sequence[Mapping[str, Any]]:
            self.calls.append((sql, dict(params)))
            if "ingest.claim_jobs_v2" in sql:
                return [_job_row(status="running", job_type=TCGDEX_SETS_JOB_TYPE)]
            if "ingest.begin_tcgdex_sets_job" in sql:
                return [_checkpoint_row()]
            if "ingest.finalize_tcgdex_sets_job" in sql:
                raise RuntimeError("policy changed during finalization")
            return [_job_row(status="pending", locked=False, job_type=TCGDEX_SETS_JOB_TYPE)]

    executor = RejectingFinalizerExecutor()
    transport = RecordingTCGdexTransport(APIResponse(200, {"etag": '"v1"'}, TCGDEX_BODY))
    runtime = build_live_worker_runtime(
        _settings("collector"),
        executor=executor,
        clock=lambda: NOW,
        tcgdex_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.FAILED
    assert result.error_code == "RuntimeError"
    assert len(executor.calls) == 4
    assert "ingest.finalize_tcgdex_sets_job" in executor.calls[2][0]
    assert "ingest.fail_job_v2" in executor.calls[3][0]


def test_tcgdex_304_uses_the_persisted_validator_and_atomic_finalizer() -> None:
    existing_hash = "a" * 64
    executor = RecordingExecutor(
        [
            [_job_row(status="running", job_type=TCGDEX_SETS_JOB_TYPE)],
            [
                _checkpoint_row(
                    etag='"v1"',
                    content_sha256=existing_hash,
                    item_count=218,
                    revision=7,
                )
            ],
            [_job_row(status="completed", locked=False, job_type=TCGDEX_SETS_JOB_TYPE)],
        ]
    )
    transport = RecordingTCGdexTransport(APIResponse(304, {"etag": '"v1"'}, b""))
    runtime = build_live_worker_runtime(
        _settings("collector"),
        executor=executor,
        clock=lambda: NOW,
        tcgdex_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.COMPLETED
    assert transport.calls[0][1]["If-None-Match"] == '"v1"'
    persisted = json.loads(str(executor.calls[2][1]["result"]))
    assert persisted["outcome"] == "not_modified"
    assert persisted["expected_revision"] == 7
    assert persisted["content_sha256"] == existing_hash
    assert persisted["sets"] == []


def test_stale_tcgdex_finalizer_cannot_persist_after_the_get() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running", job_type=TCGDEX_SETS_JOB_TYPE)],
            [_checkpoint_row()],
            [],
        ]
    )
    transport = RecordingTCGdexTransport(APIResponse(200, {"etag": '"v1"'}, TCGDEX_BODY))
    runtime = build_live_worker_runtime(
        _settings("collector"),
        executor=executor,
        clock=lambda: NOW,
        tcgdex_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.LEASE_LOST
    assert len(transport.calls) == 1
    assert "ingest.finalize_tcgdex_sets_job" in executor.calls[2][0]
    assert all("INSERT INTO catalog.sets" not in sql for sql, _ in executor.calls)


def test_tcgdex_job_payload_cannot_change_the_fixed_endpoint_or_scope() -> None:
    executor = RecordingExecutor(
        [
            [
                _job_row(
                    status="running",
                    payload={"language": "ja"},
                    job_type=TCGDEX_SETS_JOB_TYPE,
                )
            ],
            [
                _job_row(
                    status="pending",
                    payload={"language": "ja"},
                    locked=False,
                    job_type=TCGDEX_SETS_JOB_TYPE,
                )
            ],
        ]
    )
    transport = RecordingTCGdexTransport(APIResponse(200, {}, TCGDEX_BODY))
    runtime = build_live_worker_runtime(
        _settings("collector"),
        executor=executor,
        clock=lambda: NOW,
        tcgdex_transport=transport,
    )

    result = runtime.run_once()

    assert result.status is RuntimeStatus.FAILED
    assert result.error_code == "ValueError"
    assert transport.calls == []
    assert "ingest.begin_tcgdex_sets_job" not in executor.calls[1][0]


def test_watchdog_cleanup_handler_uses_one_fenced_atomic_finalizer() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running")],
            [_job_row(status="completed", locked=False)],
        ]
    )
    runtime = build_live_worker_runtime(_settings("watchdog"), executor=executor, clock=lambda: NOW)

    result = runtime.run_once()

    assert result.status is RuntimeStatus.COMPLETED
    assert result.job_type == CLEANUP_JOB_TYPE
    assert len(executor.calls) == 2
    assert "ingest.claim_jobs_v2" in executor.calls[0][0]
    finalizer_sql, finalizer_params = executor.calls[1]
    assert "ingest.finalize_cleanup_job" in finalizer_sql
    assert "ingest.prune_expired_ephemera()" not in finalizer_sql
    assert "SET status = 'completed'" not in finalizer_sql
    assert finalizer_params == {
        "job_id": "00000000-0000-0000-0000-000000000001",
        "worker_id": "worker-1",
        "lease_generation": 1,
    }


def test_stale_cleanup_finalizer_returns_lease_lost_without_an_unfenced_effect() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running")],
            [],
        ]
    )
    runtime = build_live_worker_runtime(_settings("watchdog"), executor=executor, clock=lambda: NOW)

    result = runtime.run_once()

    assert result.status is RuntimeStatus.LEASE_LOST
    assert len(executor.calls) == 2
    assert "ingest.finalize_cleanup_job" in executor.calls[1][0]
    assert all("ingest.prune_expired_ephemera()" not in sql for sql, _ in executor.calls)


def test_cleanup_handler_rejects_payloads_instead_of_expanding_its_authority() -> None:
    executor = RecordingExecutor(
        [
            [_job_row(status="running", payload={"cutoff": "tomorrow"})],
            [_job_row(status="pending", payload={"cutoff": "tomorrow"}, locked=False)],
        ]
    )
    runtime = build_live_worker_runtime(_settings("watchdog"), executor=executor, clock=lambda: NOW)

    result = runtime.run_once()

    assert result.status is RuntimeStatus.FAILED
    assert result.error_code == "ValueError"
    assert len(executor.calls) == 2
    assert "ingest.prune_expired_ephemera" not in executor.calls[1][0]
    assert "ingest.finalize_cleanup_job" not in executor.calls[1][0]
    assert "ingest.fail_job_v2" in executor.calls[1][0]


def test_live_scheduler_enqueues_cleanup_through_the_durable_slot_rpc() -> None:
    executor = RecordingExecutor([[_job_row(status="pending", locked=False)]])
    settings = _settings(
        "scheduler",
        schedule_cleanup="* * * * *",
        schedule_catalog_sync="0 0 31 2 *",
    )

    result = build_live_scheduler(settings, executor=executor).run_due(now=NOW)

    assert result.due_names == ("cleanup",)
    assert result.created == 1
    assert len(executor.calls) == 1
    sql, params = executor.calls[0]
    assert "ingest.enqueue_scheduled_job_v1" in sql
    assert params["kind"] == CLEANUP_JOB_TYPE
    assert params["schedule_name"] == "cleanup"
    assert params["scheduled_for"] == NOW


def test_live_scheduler_registers_the_daily_tcgdex_sets_job() -> None:
    catalog_time = NOW.replace(hour=2)
    executor = RecordingExecutor(
        [[_job_row(status="pending", locked=False, job_type=TCGDEX_SETS_JOB_TYPE)]]
    )
    settings = _settings("scheduler")

    result = build_live_scheduler(settings, executor=executor).run_due(now=catalog_time)

    assert result.due_names == ("catalog_sync",)
    assert result.created == 1
    sql, params = executor.calls[0]
    assert "ingest.enqueue_scheduled_job_v1" in sql
    assert params["schedule_name"] == "catalog_sync"
    assert params["scheduled_for"] == catalog_time
    assert params["kind"] == TCGDEX_SETS_JOB_TYPE
    assert params["payload"] == "{}"
    assert params["priority"] == 20
    assert params["max_attempts"] == 3


def test_scheduler_flag_registers_exactly_five_global_queries_without_receiving_key() -> None:
    settings = _settings(
        "scheduler",
        youtube_collection_enabled=True,
        schedule_catalog_sync="0 0 31 2 *",
    )
    expected_names = [name for name, _query in REQUIRED_YOUTUBE_QUERIES]
    executor = RecordingExecutor(
        [
            [
                _job_row(
                    status="pending",
                    payload={"query_name": name},
                    locked=False,
                    job_type=YOUTUBE_DISCOVERY_JOB_TYPE,
                )
            ]
            for name in expected_names
        ]
    )

    youtube_slot = NOW.replace(hour=0)
    result = build_live_scheduler(settings, executor=executor).run_due(now=youtube_slot)

    assert settings.youtube_api_key is None
    assert result.created == 5
    assert result.due_names == tuple(f"youtube_{name}" for name in expected_names)
    assert len(executor.calls) == 5
    assert [json.loads(str(params["payload"])) for _sql, params in executor.calls] == [
        {"query_name": name} for name in expected_names
    ]
    assert all(params["kind"] == YOUTUBE_DISCOVERY_JOB_TYPE for _sql, params in executor.calls)
    assert all(params["max_attempts"] == 3 for _sql, params in executor.calls)


def test_enabled_youtube_cleanup_has_a_bounded_restart_catch_up_margin() -> None:
    entries = live_schedule_entries(_youtube_settings("scheduler"))
    cleanup = next(entry for entry in entries if entry.name == "cleanup")
    missed_slot = NOW.replace(hour=3, minute=30)

    assert cleanup.catch_up_within == timedelta(hours=12)
    assert cleanup.catch_up_check_interval == timedelta(hours=1)
    assert cleanup.slot(NOW) == missed_slot
    assert cleanup.slot(missed_slot + timedelta(hours=12, minutes=1)) is None


def test_scheduler_flag_off_registers_no_youtube_jobs() -> None:
    entries = live_schedule_entries(_settings("scheduler"))

    assert all(entry.job_type != YOUTUBE_DISCOVERY_JOB_TYPE for entry in entries)


def test_live_scheduler_validates_even_unwired_cron_configuration() -> None:
    settings = _settings("scheduler", schedule_public_collection="not-a-cron")

    with pytest.raises(ValueError, match="five fields"):
        live_schedule_entries(settings)
