from __future__ import annotations

import json
from pathlib import Path

from pokecrack_worker.collectors.manual_import import (
    import_csv_candidates,
    import_jsonl_candidates,
    import_opencli_candidates,
)
from pokecrack_worker.extraction.models import ExtractorOutput
from pokecrack_worker.validation.models import ValidatorOutput

ROOT = Path(__file__).resolve().parents[3]
WORKER = Path(__file__).resolve().parents[1]


def test_exact_example_import_files_exist_and_are_clearly_synthetic() -> None:
    csv_items = import_csv_candidates(ROOT / "data/examples/openings.example.csv")
    jsonl_items = import_jsonl_candidates(ROOT / "data/examples/sources.example.jsonl")
    opencli_items = import_opencli_candidates(ROOT / "data/examples/opencli.example.json")

    assert csv_items and jsonl_items and opencli_items
    assert all(
        item.metadata.get("synthetic") is True
        for item in (*csv_items, *jsonl_items, *opencli_items)
    )
    assert all(
        "synthetic" in ((item.title or "") + (item.text or "")).casefold()
        for item in (*csv_items, *jsonl_items, *opencli_items)
    )


def test_worker_fixtures_are_bounded_synthetic_and_schema_valid() -> None:
    fixtures = WORKER / "fixtures"
    expected = {
        "extractor.example.json",
        "validator.example.json",
        "escalation.example.json",
        "opencli.example.json",
        "collector.example.html",
        "tcgdex.example.json",
        "youtube.example.json",
    }
    assert expected <= {path.name for path in fixtures.iterdir()}
    assert all(path.stat().st_size < 100_000 for path in fixtures.iterdir() if path.is_file())

    extractor = json.loads((fixtures / "extractor.example.json").read_text())
    validator = json.loads((fixtures / "validator.example.json").read_text())
    ExtractorOutput.from_mapping(extractor)
    ValidatorOutput.from_mapping(validator)
    assert "synthetic" in (fixtures / "collector.example.html").read_text().casefold()
