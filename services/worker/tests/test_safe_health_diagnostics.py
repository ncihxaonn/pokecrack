from __future__ import annotations

import pytest

from pokecrack_worker.config.settings import Settings
from pokecrack_worker.safe_health_diagnostics import (
    _database_failure_reason,
    diagnose,
    render,
)


def live_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "data_mode": "live",
        "supabase_db_url": (
            "postgresql://pokecrack_worker.wohnphsxlquhhknuthrj:do-not-log@"
            "aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?"
            "sslmode=verify-full&sslrootcert=%2Frun%2Fsupabase-prod-ca-2021.crt&"
            "connect_timeout=10&application_name=pokecrack-worker"
        ),
        "worker_id": "collector-1",
        "worker_role": "collector",
        "worker_max_concurrency": 1,
        "ai_provider": "fixture",
        "public_study_collection_enabled": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_success_reports_only_fixed_safe_fields() -> None:
    payload = diagnose(
        live_settings(),
        dns_probe=lambda _host, _port: None,
        tcp_probe=lambda _host, _port: None,
        database_probe=lambda _dsn, _sql, _params: True,
        heartbeat_probe=lambda _dsn, _sql, _params: True,
    )

    assert payload == {
        "worker_role": "collector",
        "status": "ok",
        "stage": "heartbeat",
        "reason": "ready",
    }


def test_database_exception_is_classified_without_leaking_contents() -> None:
    def fail(_dsn: str, _sql: str, _params: object) -> bool:
        raise RuntimeError(
            "password authentication failed for postgresql://user:do-not-log@db.example"
        )

    payload = diagnose(
        live_settings(),
        dns_probe=lambda _host, _port: None,
        tcp_probe=lambda _host, _port: None,
        database_probe=fail,
        heartbeat_probe=lambda _dsn, _sql, _params: True,
    )

    encoded = render(payload)
    assert payload == {
        "worker_role": "collector",
        "status": "failed",
        "stage": "database",
        "reason": "authentication_failed",
    }
    assert "do-not-log" not in encoded
    assert "postgresql://" not in encoded


@pytest.mark.parametrize(
    "database_url",
    (
        "postgresql://worker:secret@db.example.invalid:6543/postgres",
        "postgresql://worker:secret@db.example.invalid:6543/postgres?sslmode=disable",
        "postgresql://worker:secret@db.example.invalid:6543/postgres?sslmode=prefer",
        "postgresql://worker:secret@db.example.invalid:6543/postgres?sslmode=require",
        "postgresql://worker:secret@db.example.invalid:6543/postgres?sslmode=verify-ca",
        "postgresql://worker:@db.example.invalid:6543/postgres?sslmode=require",
        (
            "postgresql://pokecrack_worker.wohnphsxlquhhknuthrj:secret@"
            "aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?"
            "sslmode=require&sslrootcert=%2Frun%2Fsupabase-prod-ca-2021.crt&"
            "connect_timeout=10&application_name=pokecrack-worker"
        ),
        (
            "postgresql://pokecrack_worker.wohnphsxlquhhknuthrj:secret@"
            "aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?"
            "sslmode=verify-ca&sslrootcert=%2Frun%2Fsupabase-prod-ca-2021.crt&"
            "connect_timeout=10&application_name=pokecrack-worker"
        ),
        (
            "postgresql://worker:secret@db.example.invalid:6543/postgres?"
            "sslmode=require&sslmode=verify-full"
        ),
        (
            "postgresql://pokecrack_worker.wohnphsxlquhhknuthrj:secret@"
            "aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?"
            "sslmode=verify-full&sslrootcert=%2Ftmp%2Funreviewed.crt&"
            "connect_timeout=10&application_name=pokecrack-worker"
        ),
        (
            "postgresql://pokecrack_worker.wohnphsxlquhhknuthrj:secret@"
            "aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres?"
            "sslmode=verify-full&sslrootcert=%2Frun%2Fsupabase-prod-ca-2021.crt&"
            "connect_timeout=10&application_name=pokecrack-worker&options=unreviewed"
        ),
    ),
)
def test_insecure_or_ambiguous_tls_is_rejected_before_network(
    database_url: str,
) -> None:
    calls: list[str] = []

    def unexpected(*_args: object) -> None:
        calls.append("network")

    payload = diagnose(
        live_settings(supabase_db_url=database_url),
        dns_probe=unexpected,
        tcp_probe=unexpected,
        database_probe=unexpected,
        heartbeat_probe=unexpected,
    )

    assert payload == {
        "status": "failed",
        "stage": "configuration",
        "reason": "invalid_dsn",
    }
    assert calls == []


@pytest.mark.parametrize(
    ("error", "reason"),
    (
        (RuntimeError("root certificate file is unavailable"), "tls_failed"),
        (RuntimeError("too many clients already"), "capacity_unavailable"),
        (RuntimeError("permission denied"), "authorization_failed"),
        (TimeoutError("secret timeout"), "connection_unavailable"),
        (RuntimeError("opaque secret"), "query_failed"),
    ),
)
def test_database_failure_reasons_are_bounded(error: BaseException, reason: str) -> None:
    assert _database_failure_reason(error) == reason


def test_dependency_failure_does_not_write_or_claim_health() -> None:
    calls: list[str] = []
    heartbeat_calls: list[str] = []

    def probe(_dsn: str, sql: str, _params: object) -> bool:
        calls.append(sql)
        return False

    payload = diagnose(
        live_settings(worker_role="watchdog", worker_id="watchdog-1"),
        dns_probe=lambda _host, _port: None,
        tcp_probe=lambda _host, _port: None,
        database_probe=probe,
        heartbeat_probe=lambda _dsn, sql, _params: heartbeat_calls.append(sql) or True,
    )

    assert payload["stage"] == "dependencies"
    assert payload["reason"] == "contract_unavailable"
    assert len(calls) == 1
    assert "FROM ingest.upsert_worker_heartbeat_v1(" not in calls[0]
    assert heartbeat_calls == []


def test_heartbeat_failure_is_distinct_and_secret_free() -> None:
    def fail(_dsn: str, _sql: str, _params: object) -> bool:
        raise RuntimeError("permission denied for secret do-not-log")

    payload = diagnose(
        live_settings(worker_role="scheduler", worker_id="scheduler-1"),
        dns_probe=lambda _host, _port: None,
        tcp_probe=lambda _host, _port: None,
        database_probe=lambda _dsn, _sql, _params: True,
        heartbeat_probe=fail,
    )

    assert payload == {
        "worker_role": "scheduler",
        "status": "failed",
        "stage": "heartbeat",
        "reason": "authorization_failed",
    }
    assert "do-not-log" not in render(payload)
