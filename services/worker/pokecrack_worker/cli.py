"""Typer entry point for the fixture-safe Pokecrack worker runtime."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import typer
from pydantic import ValidationError

from pokecrack_worker.collectors.manual_import import (
    ImportFormatError,
    import_csv_candidates,
    import_jsonl_candidates,
    import_opencli_candidates,
)
from pokecrack_worker.config.settings import DataMode, Settings
from pokecrack_worker.config.source_policy import (
    CollectorRoute,
    PolicyDeniedError,
    SourcePolicyRegistry,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"
EXAMPLES_DIR = PROJECT_ROOT / "data" / "examples"

app = typer.Typer(
    name="pokecrack-worker",
    no_args_is_help=True,
    help="Policy-gated Pokecrack collection, AI, jobs, and aggregation worker.",
)
aggregate_app = typer.Typer(no_args_is_help=True, help="Build aggregate statistics.")
collect_app = typer.Typer(no_args_is_help=True, help="Run official metadata collectors.")
sync_catalog_app = typer.Typer(no_args_is_help=True, help="Synchronize card catalogs.")
app.add_typer(aggregate_app, name="aggregate")
app.add_typer(collect_app, name="collect")
app.add_typer(sync_catalog_app, name="sync-catalog")

_QUEUE: list[dict[str, Any]] = []


def _settings() -> Settings:
    try:
        return Settings(_env_file=None)
    except ValidationError:
        _json(
            {
                "error": "invalid_configuration",
                "message": "validated runtime configuration is unavailable",
            },
            err=True,
        )
        raise typer.Exit(code=78) from None


def _require_fixture_service_mode() -> None:
    if _settings().data_mode is not DataMode.DEMO:
        _json(
            {
                "error": "unwired_live_service",
                "message": "production database-backed worker role wiring is not implemented",
            },
            err=True,
        )
        raise typer.Exit(code=78)


def _policies() -> SourcePolicyRegistry:
    return SourcePolicyRegistry.from_yaml(CONFIG_DIR / "sources.yaml")


def _json(payload: dict[str, Any], *, err: bool = False) -> None:
    typer.echo(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str),
        err=err,
    )


def _mutation(event: str, dry_run: bool, **values: Any) -> None:
    _json(
        {
            "event": event,
            "dry_run": dry_run,
            "mutated": False,
            **values,
        }
    )


def _safe_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _deny(error: PolicyDeniedError) -> None:
    _json(
        {
            "error": "source_policy_denied",
            "reason": error.event.reason,
            "domain": error.event.domain,
            "route": error.event.route,
        },
        err=True,
    )
    raise typer.Exit(code=2)


@app.command("health")
def health() -> None:
    """Report a no-side-effect runtime health snapshot."""

    settings = _settings()
    _json(
        {
            "status": "ok",
            "data_mode": settings.data_mode.value,
            "ai_provider": settings.ai_provider.value,
            "database": (
                "postgres_configured"
                if settings.supabase_db_url is not None
                else "in_memory_fixture"
            ),
            "network_calls": False,
        }
    )


@app.command("worker")
def worker(
    dry_run: bool = typer.Option(False, "--dry-run", help="Describe without claiming jobs."),
    once: bool = typer.Option(True, "--once/--forever", help="Process one fixture cycle."),
) -> None:
    """Run a worker claim/heartbeat cycle (one cycle by default)."""

    _require_fixture_service_mode()
    _mutation("worker_cycle", dry_run, once=once, processed=0, fixture=True)


@app.command("scheduler")
def scheduler(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not create scheduled jobs."),
) -> None:
    """Create due scheduler/watchdog/backup jobs."""

    _require_fixture_service_mode()
    _mutation("scheduler_cycle", dry_run, created=0, fixture=True)


@aggregate_app.command("all")
def aggregate_all(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not persist aggregates."),
) -> None:
    """Rebuild every idempotent aggregate scope."""

    _require_fixture_service_mode()
    _mutation("aggregate_all", dry_run, aggregates=0, fixture=True)


@collect_app.command("youtube")
def collect_youtube(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not enqueue metadata."),
) -> None:
    """Discover YouTube Data API metadata; never download full video."""

    _require_fixture_service_mode()
    settings = _settings()
    _mutation(
        "collect_youtube",
        dry_run,
        discovered=0,
        fixture=settings.youtube_api_key is None,
        live_boundary="YOUTUBE_API_KEY required for network discovery",
        media_download=False,
    )


@app.command("collect-source")
def collect_source(
    name: str = typer.Argument(..., help="Exact configured source domain."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate only; do not fetch."),
) -> None:
    """Collect one explicitly configured public source adapter."""

    _require_fixture_service_mode()
    source = name if "://" in name else f"https://{name}/"
    registry = _policies()
    resolved = registry.resolve(source)
    route = next(iter(sorted(resolved.routes, key=lambda item: item.value)), CollectorRoute.STATIC)
    try:
        policy = registry.require(source, route)
    except PolicyDeniedError as error:
        _deny(error)
    _mutation(
        "collect_source",
        dry_run,
        source=_safe_url(source),
        collector=policy.collector.value,
        adapter=policy.adapter,
        fetched=0,
        fixture=True,
    )


@app.command("enqueue-url")
def enqueue_url(
    url: str = typer.Argument(..., help="Policy-approved HTTP(S) source URL."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate only; do not enqueue."),
) -> None:
    """Enqueue one allowlisted source URL after policy authorization."""

    _require_fixture_service_mode()
    registry = _policies()
    try:
        resolved = registry.resolve(url)
    except ValueError:
        _json({"error": "invalid_source_url"}, err=True)
        raise typer.Exit(code=2) from None
    route = next(iter(sorted(resolved.routes, key=lambda item: item.value)), CollectorRoute.STATIC)
    try:
        policy = registry.require(url, route)
    except PolicyDeniedError as error:
        _deny(error)
    job_id: str | None = None
    if not dry_run:
        job_id = str(uuid4())
        _QUEUE.append(
            {
                "job_id": job_id,
                "kind": "collect_url",
                "status": "pending",
                "source_url": _safe_url(url),
                "collector": policy.collector.value,
            }
        )
    _mutation(
        "enqueue_url",
        dry_run,
        job_id=job_id,
        source=_safe_url(url),
        collector=policy.collector.value,
    )


def _import_command(kind: str, path: Path, dry_run: bool) -> None:
    _require_fixture_service_mode()
    if not path.is_file():
        _json({"error": "input_not_found", "kind": kind, "path": str(path)}, err=True)
        raise typer.Exit(code=2)
    try:
        if kind == "import_csv":
            candidates = import_csv_candidates(path)
        elif kind == "import_jsonl":
            candidates = import_jsonl_candidates(path)
        elif kind == "import_opencli":
            candidates = import_opencli_candidates(path)
        else:
            raise ValueError(f"unknown import kind: {kind}")
    except (ImportFormatError, OSError, UnicodeError) as error:
        _json({"error": "invalid_import", "kind": kind, "message": str(error)}, err=True)
        raise typer.Exit(code=2) from error
    _mutation(
        kind,
        dry_run,
        path=str(path),
        validated=len(candidates),
        imported=0 if dry_run else len(candidates),
        fixture=True,
    )


@app.command("import-csv")
def import_csv(
    path: Path = typer.Argument(EXAMPLES_DIR / "openings.example.csv"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without importing."),
) -> None:
    """Import bounded manual CSV observations."""

    _import_command("import_csv", path, dry_run)


@app.command("import-jsonl")
def import_jsonl(
    path: Path = typer.Argument(EXAMPLES_DIR / "sources.example.jsonl"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without importing."),
) -> None:
    """Import bounded manual JSONL observations."""

    _import_command("import_jsonl", path, dry_run)


@app.command("import-opencli")
def import_opencli(
    path: Path = typer.Argument(EXAMPLES_DIR / "opencli.example.json"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without importing."),
) -> None:
    """Import a bounded OpenCLI JSON export; no browser/login is started."""

    _import_command("import_opencli", path, dry_run)


@sync_catalog_app.command("tcgdex")
def sync_catalog_tcgdex(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not call or update catalog."),
) -> None:
    """Synchronize TCGdex catalog metadata with cache validators."""

    _require_fixture_service_mode()
    _mutation(
        "sync_catalog_tcgdex",
        dry_run,
        changed=False,
        fixture=True,
        live_boundary="TCGdex network access is explicit and policy-bound",
    )


@app.command("retry-failed")
def retry_failed(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not requeue failed jobs."),
) -> None:
    """Requeue retryable failed jobs without reviving dead jobs."""

    _require_fixture_service_mode()
    _mutation("retry_failed", dry_run, retried=0)


@app.command("cleanup")
def cleanup(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not remove expired data."),
) -> None:
    """Apply retention and stale-lease cleanup policies."""

    _require_fixture_service_mode()
    _mutation("cleanup", dry_run, removed=0)


@app.command("show-budget")
def show_budget() -> None:
    """Show configured AI budget caps without revealing credentials."""

    _require_fixture_service_mode()
    settings = _settings()
    _json(
        {
            "status": "available",
            "daily_budget_aud": str(settings.ai_daily_budget_aud),
            "monthly_budget_aud": str(settings.ai_monthly_soft_budget_aud),
            "daily_spend_aud": "0",
            "monthly_spend_aud": "0",
            "fixture": True,
        }
    )


@app.command("show-queue")
def show_queue() -> None:
    """Show redacted queue counts and fixture jobs."""

    _require_fixture_service_mode()
    _json(
        {
            "counts": {
                status: sum(job["status"] == status for job in _QUEUE)
                for status in ("pending", "running", "failed", "dead", "completed")
            },
            "jobs": _QUEUE,
            "total": len(_QUEUE),
        }
    )


@app.command("show-storage-usage")
def show_storage_usage() -> None:
    """Show fixture/free-tier storage threshold telemetry."""

    _require_fixture_service_mode()
    settings = _settings()
    _json(
        {
            "database_mb": 0,
            "storage_mb": 0,
            "monthly_egress_gb": 0,
            "database_warning_mb": settings.database_warning_mb,
            "database_critical_mb": settings.database_critical_mb,
            "storage_warning_mb": settings.storage_warning_mb,
            "storage_critical_mb": settings.storage_critical_mb,
            "measured_at": datetime.now(UTC).isoformat(),
            "fixture": True,
        }
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
