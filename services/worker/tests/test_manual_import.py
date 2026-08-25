from __future__ import annotations

from pathlib import Path

from pokecrack_worker.collectors.manual_import import (
    import_csv_candidates,
    import_jsonl_candidates,
    import_opencli_candidates,
)
from pokecrack_worker.models import CollectorType

ROOT = Path(__file__).resolve().parents[3]


def test_csv_import_hashes_author_and_emits_the_standard_candidate_contract() -> None:
    items = import_csv_candidates(ROOT / "data" / "examples" / "manual-openings.csv")

    assert len(items) == 2
    first = items[0]
    assert first.collector is CollectorType.MANUAL_IMPORT
    assert first.platform == "manual"
    assert first.author_hash is not None and len(first.author_hash) == 64
    assert "fixture-author" not in first.model_dump_json()
    assert first.collector_version == "manual-csv-v1"
    assert first.source_policy_version == "1"


def test_jsonl_import_is_bounded_and_uses_manual_import_collector() -> None:
    items = import_jsonl_candidates(
        ROOT / "data" / "examples" / "manual-openings.jsonl", max_rows=10
    )

    assert len(items) == 2
    assert {item.collector for item in items} == {CollectorType.MANUAL_IMPORT}
    assert all(item.collector_version == "manual-jsonl-v1" for item in items)
    assert all(item.metadata["synthetic"] is True for item in items)


def test_opencli_json_import_preserves_authenticated_collector_boundary() -> None:
    items = import_opencli_candidates(ROOT / "data" / "examples" / "opencli.example.json")

    assert len(items) == 2
    assert {item.collector for item in items} == {CollectorType.OPENCLI_AUTHENTICATED}
    assert all(item.platform == "reddit" for item in items)
    assert all(item.author_hash for item in items)
    assert all("author" not in item.metadata for item in items)
    assert all(item.metadata["synthetic"] is True for item in items)
