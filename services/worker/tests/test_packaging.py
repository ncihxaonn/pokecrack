from __future__ import annotations

import tomllib
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1]
ROOT = WORKER.parents[1]


def test_worker_manifest_container_and_required_package_layout_exist() -> None:
    manifest = tomllib.loads((WORKER / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = " ".join(manifest["project"]["dependencies"]).casefold()
    dev = " ".join(manifest["project"]["optional-dependencies"]["dev"]).casefold()

    for runtime in (
        "coincurve",
        "httpx",
        "psycopg",
        "pydantic-settings",
        "pyyaml",
        "structlog",
        "typer",
        "websockets",
    ):
        assert runtime in dependencies
    for tool in ("pytest", "ruff", "mypy", "types-pyyaml"):
        assert tool in dev

    dockerfile = (WORKER / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in dockerfile
    assert "pokecrack-worker health" in dockerfile
    assert "USER pokecrack" in dockerfile

    for package in (
        "collectors/official_api",
        "collectors/scrapling/adapters",
        "collectors/manual_import",
        "catalog",
        "jobs",
        "statistics",
        "aggregation",
        "db",
    ):
        assert (WORKER / "pokecrack_worker" / package / "__init__.py").is_file()
