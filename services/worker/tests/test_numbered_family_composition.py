"""Optional publisher scheduling and exact shared-job dispatch, without HTTP."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from pokecrack_worker import numbered_families, source_families
from pokecrack_worker.composition import (
    LiveCompositionError,
    build_live_worker_runtime,
    live_schedule_entries,
    require_worker_job_types,
    write_health_heartbeat,
)
from pokecrack_worker.config.settings import Settings
from pokecrack_worker.jobs.models import CompletionEffect, Job
from pokecrack_worker.jobs.postgres import PostgresJobRepository

NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)


class DB:
    def __init__(self):
        self.calls = []

    def query(self, sql, params):
        self.calls.append((sql, params))
        return []


def settings(enabled=True):
    return Settings(
        _env_file=None,
        data_mode="live",
        worker_role="collector",
        supabase_db_url="postgresql://example.invalid/test",
        public_study_collection_enabled=True,
        source_family_collection_enabled=True,
        numbered_family_collection_enabled=enabled,
        scrapling_enabled=True,
    )


@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_exact_dispatch_and_schedule(monkeypatch, approved, enabled):
    monkeypatch.setattr(
        source_families, "POLICY", replace(source_families.POLICY, approved=approved)
    )
    calls = []

    def factory(name, effect):
        def make(*args, **kwargs):
            def handler(job):
                calls.append(name)
                return effect

            return handler

        return make

    monkeypatch.setattr(
        numbered_families,
        "make_handler",
        factory("numbered", CompletionEffect.FINALIZE_NUMBERED_FAMILY),
    )
    monkeypatch.setattr(
        source_families,
        "make_handler",
        factory("existing", CompletionEffect.FINALIZE_NUMBERED_FAMILY),
    )
    config = settings(enabled)
    runtime = build_live_worker_runtime(config, executor=DB())
    assert tuple(runtime.handlers) == require_worker_job_types(config)
    schedules = live_schedule_entries(config.model_copy(update={"worker_role": "scheduler"}))
    numbered = [
        entry for entry in schedules if entry.payload == {"family": numbered_families.FAMILY}
    ]
    assert len(numbered) == int(enabled)
    if enabled:
        assert numbered[0].slot(NOW + timedelta(minutes=7)) == NOW + timedelta(minutes=5)
        assert numbered[0].max_attempts == 1
    if not (enabled or approved):
        assert numbered_families.JOB_TYPE not in runtime.handlers
        return
    dispatch = runtime.handlers[numbered_families.JOB_TYPE]
    for family, allowed, name in [
        (numbered_families.FAMILY, enabled, "numbered"),
        (source_families.FAMILY, approved, "existing"),
    ]:
        job = Job("test", numbered_families.JOB_TYPE, {"family": family}, is_demo=False)
        if allowed:
            dispatch(job)
            assert calls[-1] == name
        else:
            with pytest.raises(ValueError, match="dispatch_scope"):
                dispatch(job)
    for payload in [
        {},
        {"family": []},
        {"family": "foreign"},
        {"family": numbered_families.FAMILY, "url": "x"},
    ]:
        before = len(calls)
        with pytest.raises(ValueError, match="dispatch_scope"):
            dispatch(Job("test", numbered_families.JOB_TYPE, payload, is_demo=False))
        assert len(calls) == before


@pytest.mark.parametrize(
    "family,rpc",
    [
        ("kozaru-numbered", "enqueue_numbered_family_v1"),
        ("pokesup-enumerated", "enqueue_source_family_v1"),
    ],
)
def test_enqueue_selects_fixed_rpc(family, rpc):
    db = DB()
    result = PostgresJobRepository(db).enqueue_scheduled(
        numbered_families.JOB_TYPE,
        {"family": family},
        schedule_name="test",
        scheduled_for=NOW,
        now=NOW,
    )
    assert result is None
    assert db.calls == [(f"SELECT * FROM ingest.{rpc}(%(slot)s)", {"slot": NOW})]


def test_numbered_flag_requires_parent_flag():
    with pytest.raises(ValueError, match="requires SOURCE_FAMILY"):
        Settings(_env_file=None, numbered_family_collection_enabled=True)


@pytest.mark.parametrize("ready", [False, True])
def test_optional_publisher_pause_does_not_stop_shared_worker(ready):
    class HealthDB(DB):
        def query(self, sql, params):
            self.calls.append((sql, params))
            if "numbered_family_ready_v1" in sql:
                return [{"ready": ready}]
            if len(self.calls) == 4:
                return [{"last_seen_at": NOW}]
            return [{"ready": True}]

    db = HealthDB()
    assert write_health_heartbeat(settings(), executor=db).last_seen_at == NOW
    assert len(db.calls) == 4


@pytest.mark.parametrize(
    "rows", [[], [{}], [{"ready": None}], [{"ready": 0}], [{"ready": False}, {"ready": True}]]
)
def test_missing_numbered_contract_fails_before_heartbeat(rows):
    class HealthDB(DB):
        def query(self, sql, params):
            self.calls.append((sql, params))
            if "numbered_family_ready_v1" in sql:
                return rows
            return [{"ready": True}]

    db = HealthDB()
    with pytest.raises(LiveCompositionError, match="numbered-family runtime contract"):
        write_health_heartbeat(settings(), executor=db)
    assert len(db.calls) == 3
