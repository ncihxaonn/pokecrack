from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import research_ledger as module


class ResearchLedgerTests(unittest.TestCase):
    def test_round_trip_keeps_all_three_research_collections(self):
        ledger = module.empty_ledger()
        country = {"campaign": "country", "sweep": 1, "targets": ["MY"], "results": []}
        batch = {"version": 1, "studies": []}
        asia = {"country": "VN", "candidates": []}
        self.assertTrue(module.append_unique(ledger, "country_reports", country))
        self.assertTrue(module.append_unique(ledger, "global_batches", batch))
        self.assertTrue(module.upsert_asia_report(ledger, asia))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            module.save(ledger, path)
            self.assertEqual(module.load(path), ledger)

    def test_duplicate_entries_are_not_appended_and_asia_is_upserted(self):
        ledger = module.empty_ledger()
        report = {"country": "VN", "candidates": []}
        self.assertTrue(module.upsert_asia_report(ledger, report))
        self.assertFalse(module.upsert_asia_report(ledger, report))
        self.assertEqual(len(ledger["asia_reports"]), 1)
        batch = {"version": 1, "studies": []}
        self.assertTrue(module.append_unique(ledger, "global_batches", batch))
        self.assertFalse(module.append_unique(ledger, "global_batches", batch))
        self.assertEqual(len(ledger["global_batches"]), 1)

    def test_invalid_shape_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_research_ledger"):
                module.load(path)


if __name__ == "__main__":
    unittest.main()
