from __future__ import annotations

import importlib.util
import copy
import json
from pathlib import Path
import unittest

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


class QuantityConsensusTests(unittest.TestCase):
    # The repository's script gate uses unittest discovery. Include the legacy
    # function-style tests in that gate as well as the new consensus regressions.
    def test_legacy_manifest_contracts(self):
        test_build_manifest_deduplicates_urls_and_keeps_unknown_geography()
        test_conflicting_url_is_quarantined_and_bad_groups_are_skipped()
        test_research_ledger_input_includes_seed_and_asia_facts()

    def record(self):
        value = group("https://example.com/original", country="AU", basis="opening_location")
        value["study_id"] = value.pop("study_ids")[0]
        for key in ("status", "conflicts", "statistics_eligible"):
            del value[key]
        return value

    def manifest(self, rows):
        source = {"version": 1, "country_reports": [], "asia_reports": [],
                  "global_batches": [{"version": 1, "studies": rows}]}
        return module.build_manifest(json.dumps(source).encode())

    def test_description_disagreements_keep_one_agreed_quantity(self):
        first = self.record()
        for field, value in (("set", "different-set"), ("product", "different-product"),
                             ("language", "fr"), ("method", "different-method")):
            second = {**first, field: value}
            with self.subTest(field=field):
                result = self.manifest([first, second])["candidates"]
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["pack_count"], 36)
                self.assertEqual(result[0]["country_code"], "AU")
                self.assertEqual(self.manifest([second, first])["candidates"], result)

    def test_geography_disagreement_preserves_count_as_unknown(self):
        first = self.record()
        for second in ({**first, "country": "NZ"},
                       {**first, "geography_basis": "publisher_country"},
                       {**first, "country": None, "geography_basis": "unknown"}):
            result = self.manifest([first, second])["candidates"]
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["pack_count"], 36)
            self.assertIsNone(result[0]["country_code"])
            self.assertEqual(result[0]["geography_basis"], "unknown")

    def test_hit_disagreement_never_creates_a_numerator(self):
        first = self.record()
        first["metrics"] = [{"category": "sir", "hits": 1, "unit": "packs_with_hit"}]
        second = copy.deepcopy(first)
        second["metrics"][0]["hits"] = 2
        result = self.manifest([first, second])["candidates"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pack_count"], 36)
        self.assertNotIn("metrics", result[0])

    def test_count_or_precision_disagreement_still_blocks_quantity(self):
        first = self.record()
        for second in ({**first, "packs": 72},
                       {**first, "pack_precision": "lower_bound"},
                       {**first, "packs": None, "pack_precision": "unknown"}):
            self.assertEqual(self.manifest([first, second])["candidates"], [])

    def test_native_box_reports_never_convert_to_packs(self):
        first = self.record()
        first.update(packs=None, pack_precision="unknown",
                     source_sample={"unit": "boxes", "count": 100, "precision": "exact_reported"})
        second = {**first, "product": "different-product"}
        self.assertEqual(self.manifest([first, second])["candidates"], [])

    def test_transitive_aliases_still_count_only_once(self):
        first = self.record()
        second = {**first, "urls": ["https://example.org/reprint"], "method": "translation"}
        third = {**second, "cohort_ids": ["rediscovered"], "set": "other-name"}
        result = self.manifest([first, second, third])["candidates"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pack_count"], 36)

    def test_strict_reference_view_and_input_are_unchanged(self):
        first = self.record()
        second = {**first, "set": "different-set"}
        rows = [first, second]
        before = copy.deepcopy(rows)
        raw = json.dumps({"version": 1, "studies": rows}).encode()
        strict = module.build_ledger(raw)["studies"][0]
        quantity = module.build_ledger(raw, quantity_only=True)["studies"][0]
        self.assertIsNone(strict["packs"])
        self.assertEqual(strict["conflicts"], ["set"])
        self.assertEqual(quantity["packs"], 36)
        self.assertEqual(quantity["reference_conflicts"], ["set"])
        self.assertEqual(quantity["conflicts"], [])
        self.assertEqual(quantity["set"], "unknown")
        self.assertEqual(quantity["metrics"], [])
        self.assertFalse(quantity["statistics_eligible"])
        self.assertEqual(rows, before)
