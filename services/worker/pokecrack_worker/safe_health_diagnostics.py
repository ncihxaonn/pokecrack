"""Bounded, secret-free database diagnostics for failed worker deployments."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import datetime
from urllib.parse import parse_qsl, urlsplit

from pydantic import ValidationError

from pokecrack_worker import __version__, composition
from pokecrack_worker.config.settings import Settings

Diagnostic = dict[str, object]
_BROAD_WORKER_ROLES = frozenset(
    {
        composition.WorkerRole.COLLECTOR,
        composition.WorkerRole.SCHEDULER,
        composition.WorkerRole.WATCHDOG,
    }
)
_PRODUCTION_HOST = "aws-0-ap-northeast-1.pooler.supabase.com"
_PRODUCTION_PORT = 6543
_PRODUCTION_USERNAME = "pokecrack_worker.wohnphsxlquhhknuthrj"
_PRODUCTION_QUERY = {
    "application_name": "pokecrack-worker",
    "connect_timeout": "10",
    "sslmode": "verify-full",
    "sslrootcert": "/run/supabase-prod-ca-2021.crt",
}
_PROBE_TIMEOUT_SECONDS = 30
_ALLOWED_STAGES = frozenset(
    {"configuration", "dns", "tcp", "database", "dependencies", "heartbeat", "runtime"}
)
_ALLOWED_REASONS = frozenset(
    {
        "authentication_failed",
        "authorization_failed",
        "capacity_unavailable",
        "connection_unavailable",
        "contract_unavailable",
        "invalid_dsn",
        "invalid_runtime",
        "probe_failed",
        "probe_timed_out",
        "query_failed",
        "ready",
        "tls_failed",
        "unavailable",
        "unreachable",
        "validation_failed",
    }
)


def _dsn_and_dependency(
    settings: Settings,
    role: composition.WorkerRole,
) -> tuple[
    str,
    str,
    Mapping[str, object],
    str,
    Mapping[str, object],
]:
    metadata = json.dumps(
        {
            "command": "health",
            "data_mode": settings.data_mode.value,
            "max_concurrency": settings.worker_max_concurrency,
            "role_ready": composition.role_is_ready(role),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    heartbeat_params: dict[str, object] = {
        "worker_id": settings.worker_id,
        "version": __version__,
        "metadata": metadata,
    }
    if role not in _BROAD_WORKER_ROLES:
        raise ValueError("safe diagnostics support only the shared worker credential")
    assert settings.supabase_db_url is not None
    heartbeat_params["worker_type"] = role.value
    return (
        settings.supabase_db_url.get_secret_value(),
        composition.LIVE_ROLE_DEPENDENCIES_SQL,
        {
            "worker_type": role.value,
            "youtube_enabled": settings.youtube_collection_enabled,
            "bluesky_enabled": settings.bluesky_collection_enabled,
            "nostr_enabled": settings.nostr_collection_enabled,
            "mastodon_enabled": settings.mastodon_collection_enabled,
            "public_study_enabled": settings.public_study_collection_enabled,
        },
        composition.WORKER_HEARTBEAT_SQL,
        heartbeat_params,
    )


def _dns_probe(host: str, port: int) -> None:
    socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)


def _tcp_probe(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=5):
        pass


def _database_probe(
    dsn: str,
    dependency_sql: str,
    params: Mapping[str, object],
) -> bool:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, connect_timeout=10, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_catalog.set_config('statement_timeout', '30000', true)")
            cursor.execute(dependency_sql, params)
            row = cursor.fetchone()
        connection.rollback()
    return isinstance(row, Mapping) and row.get("ready") is True


def _heartbeat_probe(
    dsn: str,
    heartbeat_sql: str,
    params: Mapping[str, object],
) -> bool:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, connect_timeout=10, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_catalog.set_config('statement_timeout', '30000', true)")
            cursor.execute(heartbeat_sql, params)
            row = cursor.fetchone()
        # Exercise the exact heartbeat function but leave no durable diagnostic
        # write. A rollback also preserves the pre-release heartbeat timestamp.
        connection.rollback()
    return isinstance(row, Mapping) and isinstance(row.get("last_seen_at"), datetime)


def _database_failure_reason(error: BaseException) -> str:
    sqlstate = getattr(error, "sqlstate", None)
    message = str(error).casefold()
    if sqlstate in {"28000", "28P01"} or "password authentication failed" in message:
        return "authentication_failed"
    if sqlstate == "53300" or "too many clients" in message or "connection slots" in message:
        return "capacity_unavailable"
    if sqlstate == "42501" or "permission denied" in message:
        return "authorization_failed"
    if any(
        marker in message
        for marker in (
            "certificate verify failed",
            "root certificate",
            "ssl error",
            "sslmode",
            "tls",
        )
    ):
        return "tls_failed"
    if isinstance(error, (ConnectionError, TimeoutError, socket.gaierror)) or any(
        marker in message
        for marker in (
            "connection refused",
            "connection timed out",
            "timeout expired",
            "network is unreachable",
            "no route to host",
            "could not translate host name",
            "name or service not known",
        )
    ):
        return "connection_unavailable"
    return "query_failed"


def diagnose(
    settings: Settings,
    *,
    dns_probe: Callable[[str, int], None] = _dns_probe,
    tcp_probe: Callable[[str, int], None] = _tcp_probe,
    database_probe: Callable[[str, str, Mapping[str, object]], bool] = _database_probe,
    heartbeat_probe: Callable[[str, str, Mapping[str, object]], bool] = _heartbeat_probe,
) -> Diagnostic:
    """Return only fixed stages/reasons; never include a DSN or exception text."""

    try:
        role = composition.require_supported_role(settings)
        dsn, dependency_sql, params, heartbeat_sql, heartbeat_params = _dsn_and_dependency(
            settings, role
        )
        parsed = urlsplit(dsn)
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        query_names = [name for name, _value in query_pairs]
        query = dict(query_pairs)
        if (
            parsed.scheme != "postgresql"
            or parsed.hostname != _PRODUCTION_HOST
            or parsed.port != _PRODUCTION_PORT
            or parsed.username != _PRODUCTION_USERNAME
            or not parsed.password
            or parsed.path != "/postgres"
            or parsed.fragment
            or len(query_names) != len(set(query_names))
            or query != _PRODUCTION_QUERY
        ):
            return {"status": "failed", "stage": "configuration", "reason": "invalid_dsn"}
    except (AssertionError, ValueError, composition.LiveCompositionError):
        return {"status": "failed", "stage": "configuration", "reason": "invalid_runtime"}

    base: Diagnostic = {"worker_role": role.value}
    try:
        dns_probe(parsed.hostname, parsed.port)
    except Exception:
        return {**base, "status": "failed", "stage": "dns", "reason": "unavailable"}
    try:
        tcp_probe(parsed.hostname, parsed.port)
    except Exception:
        return {**base, "status": "failed", "stage": "tcp", "reason": "unreachable"}
    try:
        ready = database_probe(dsn, dependency_sql, params)
    except Exception as error:
        return {
            **base,
            "status": "failed",
            "stage": "database",
            "reason": _database_failure_reason(error),
        }
    if not ready:
        return {
            **base,
            "status": "failed",
            "stage": "dependencies",
            "reason": "contract_unavailable",
        }
    try:
        heartbeat_ready = heartbeat_probe(dsn, heartbeat_sql, heartbeat_params)
    except Exception as error:
        return {
            **base,
            "status": "failed",
            "stage": "heartbeat",
            "reason": _database_failure_reason(error),
        }
    if not heartbeat_ready:
        return {
            **base,
            "status": "failed",
            "stage": "heartbeat",
            "reason": "contract_unavailable",
        }
    return {**base, "status": "ok", "stage": "heartbeat", "reason": "ready"}


def render(payload: Diagnostic) -> str:
    """Serialize only the fixed token vocabulary consumed by deploy.sh."""

    fields = [
        f"status={payload['status']}",
        f"stage={payload['stage']}",
        f"reason={payload['reason']}",
    ]
    worker_role = payload.get("worker_role")
    if worker_role is not None:
        fields.append(f"worker_role={worker_role}")
    return " ".join(fields)


def _child_main() -> int:
    try:
        settings = Settings(_env_file=None)
        payload = diagnose(settings)
    except ValidationError:
        payload = {
            "status": "failed",
            "stage": "configuration",
            "reason": "validation_failed",
        }
    print(render(payload))
    return 0 if payload.get("status") == "ok" else 1


def _allowlisted_child_output(output: str, returncode: int) -> bool:
    if len(output) > 256 or "\n" in output or "\r" in output:
        return False
    fields = output.split(" ")
    if len(fields) not in {3, 4}:
        return False
    expected_names = ["status", "stage", "reason"]
    if len(fields) == 4:
        expected_names.append("worker_role")
    values: dict[str, str] = {}
    for field, expected_name in zip(fields, expected_names, strict=True):
        name, separator, value = field.partition("=")
        if name != expected_name or separator != "=" or not value:
            return False
        values[name] = value
    status = values["status"]
    if status not in {"failed", "ok"}:
        return False
    if values["stage"] not in _ALLOWED_STAGES or values["reason"] not in _ALLOWED_REASONS:
        return False
    role = values.get("worker_role")
    if role is not None and role not in {item.value for item in _BROAD_WORKER_ROLES}:
        return False
    return (status == "ok" and returncode == 0) or (status == "failed" and returncode == 1)


def _bounded_parent_main() -> int:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pokecrack_worker.safe_health_diagnostics", "--probe-child"],
            check=False,
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            start_new_session=True,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        print("status=failed stage=runtime reason=probe_timed_out")
        return 1
    output = completed.stdout.strip()
    if not _allowlisted_child_output(output, completed.returncode):
        print("status=failed stage=runtime reason=probe_failed")
        return 1
    print(output)
    return completed.returncode


def main() -> int:
    if sys.argv[1:] == ["--probe-child"]:
        return _child_main()
    if sys.argv[1:]:
        print("status=failed stage=runtime reason=probe_failed")
        return 1
    # DNS resolution and libpq execute only in this bounded child. If libc,
    # NSS, or libpq ignores its own timeout, subprocess.run kills and reaps the
    # whole probe before the outer Docker exec deadline.
    return _bounded_parent_main()


if __name__ == "__main__":
    raise SystemExit(main())
