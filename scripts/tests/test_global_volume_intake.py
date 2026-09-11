from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("global_volume_intake", ROOT / "scripts/global_volume_intake.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def group(url: str, *, country: str | None = "AU", basis: str = "product_market") -> dict:
    return {
        "study_ids": ["study-one"],
        "cohort_ids": ["cohort-one"],
        "urls": [url],
        "set": "sample-set",
        "language": "en",
        "product": "booster_box",
        "country": country,
        "geography_basis": basis,
        "packs": 36,
        "pack_precision": "exact_reported",
        "method": "reported-opening",
        "metrics": [],
        "limitations": [],
        "conflicts": [],
        "status": "reported_not_independently_audited",
        "statistics_eligible": False,
    }


def test_build_manifest_deduplicates_urls_and_keeps_unknown_geography() -> None:
    snapshot = {
        "ledger": {
            "studies": [
                group("https://example.com/a"),
                group("https://example.com/b", country=None, basis="unknown"),
            ]
        }
    }
    result = module.build_manifest(json.dumps(snapshot).encode())
    assert [item["url"] for item in result["candidates"]] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert result["candidates"][1]["country_code"] is None


def test_conflicting_url_is_quarantined_and_bad_groups_are_skipped() -> None:
    first = group("https://example.com/same")
    second = {**group("https://example.com/same"), "packs": 72}
    bad = {**group("https://example.com/bad"), "conflicts": ["packs"], "status": "conflicting_reports"}
    result = module.build_manifest(
        json.dumps({"ledger": {"studies": [first, second, bad]}}).encode()
    )
    assert result["candidates"] == []


def test_research_ledger_input_includes_seed_and_asia_facts() -> None:
    ledger = {
        "version": 1,
        "country_reports": [],
        "global_batches": [],
        "asia_reports": [
            {
                "country": "ID",
                "candidates": [
                    {
                        "source_url": "https://example.com/asia",
                        "pack_count": 80,
                        "geography_basis": "product_market",
                    }
                ],
            }
        ],
    }
    seed_group = group("https://example.com/seed")
    seed = {
        "version": 1,
        "studies": [
            {
                "study_id": seed_group["study_ids"][0],
                "cohort_ids": seed_group["cohort_ids"],
                "urls": seed_group["urls"],
                "set": seed_group["set"],
                "language": seed_group["language"],
                "product": seed_group["product"],
                "country": seed_group["country"],
                "geography_basis": seed_group["geography_basis"],
                "packs": seed_group["packs"],
                "pack_precision": seed_group["pack_precision"],
                "method": seed_group["method"],
                "metrics": seed_group["metrics"],
                "limitations": seed_group["limitations"],
            }
        ],
    }
    result = module.build_manifest(
        json.dumps(ledger).encode(), seed_raw=json.dumps(seed).encode()
    )
    assert {item["url"] for item in result["candidates"]} == {
        "https://example.com/asia",
        "https://example.com/seed",
    }
    assert any(item["country_code"] == "ID" for item in result["candidates"])
