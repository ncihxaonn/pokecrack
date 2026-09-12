from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("asia_research", ROOT / "scripts/asia_research.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AsiaResearchTests(unittest.TestCase):
    def test_research_output_budget_defaults_and_explicit_larger_limit(self):
        for size, kwargs, accepted in ((16384, {}, True), (16385, {}, False),
                                      (96 * 1024, {"max_bytes": 96 * 1024}, True),
                                      (96 * 1024 + 1, {"max_bytes": 96 * 1024}, False)):
            with self.subTest(size=size, kwargs=kwargs), patch.object(module.subprocess, "Popen") as popen:
                process = popen.return_value.__enter__.return_value
                process.returncode = 0
                def write_output(*args, **unused):
                    command = popen.call_args.args[0]
                    Path(command[command.index("-o") + 1]).write_bytes(b"x" * size)
                process.communicate.side_effect = write_output
                if accepted:
                    self.assertEqual(len(module.research_document("test", {}, **kwargs)), size)
                else:
                    with self.assertRaisesRegex(ValueError, "invalid_report"):
                        module.research_document("test", {}, **kwargs)
        for value in (True, 0, -1, 96 * 1024 + 1, "98304"):
            with self.subTest(value=value), patch.object(module.subprocess, "Popen") as popen:
                with self.assertRaises(ValueError):
                    module.research_document("test", {}, max_bytes=value)
                popen.assert_not_called()

    def example(self):
        return {"country": "VN", "candidates": [{
            "source_url": "https://example.com/opening", "supporting_url": None,
            "pack_count": None, "observed_on": None, "geography_basis": "unknown",
            "missing_checks": [],
        }]}

    def test_round_robin_visits_each_region_without_blocking_on_one(self):
        start = datetime(2026, 9, 8, tzinfo=timezone.utc)
        self.assertEqual([module.select_country("auto", start + timedelta(hours=6*i))
                          for i in range(6)], list(module.COUNTRIES))
        self.assertEqual(module.select_country("auto", start + timedelta(hours=36)), "VN")
        self.assertEqual(module.select_country("MY", start), "MY")

    def test_wrong_country_and_unknown_fields_fail_closed(self):
        with self.assertRaises(ValueError):
            module.validate(json.dumps(self.example()).encode(), "ID")
        data = self.example()
        data["secret"] = "must not be retained"
        with self.assertRaises(ValueError):
            module.validate(json.dumps(data).encode(), "VN")

    def test_discovery_never_self_approves_missing_evidence_or_rights(self):
        data = module.validate(json.dumps(self.example()).encode(), "VN")
        self.assertEqual(data["candidates"][0]["missing_checks"], [
            "geography", "independent_review", "pack_count", "publication_date",
            "source_access", "source_rights"])
        self.assertEqual(data["country"], "VN")
        self.assertIn("source_access", data["candidates"][0]["missing_checks"])

    def test_unsafe_urls_are_rejected(self):
        for url in ["http://example.com/a", "https://localhost/a", "https://127.0.0.1/a",
                    "https://example.com/a?token=secret", "https://user:pass@example.com/a",
                    "https://example.com/a\n@owner", "https://example.com/[bad]",
                    "https://www.youtube.com/watch?v=abc", "https://youtu.be/abc"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                module.public_url(url)

    def test_invalid_denominators_and_dates_fail(self):
        for field, value in [("pack_count", True), ("pack_count", -1),
                             ("observed_on", "2026-02-31"), ("missing_checks", ["approved"])]:
            data = self.example()
            data["candidates"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                module.validate(json.dumps(data).encode(), "VN")

    def test_duplicate_and_oversized_results_fail(self):
        data = self.example()
        data["candidates"] *= 2
        with self.assertRaises(ValueError):
            module.validate(json.dumps(data).encode(), "VN")
        with self.assertRaises(ValueError):
            module.validate(b" " * 16385, "VN")

    def test_publish_writes_to_the_unified_ledger(self):
        data = module.validate(json.dumps(self.example()).encode(), "VN")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({
                "version": 1, "country_reports": [],
                "global_batches": [], "asia_reports": []
            }), encoding="utf-8")
            module.publish(data, path)
            saved = json.loads(path.read_text())
            self.assertEqual(saved["asia_reports"], [data])

    def test_publish_upserts_the_same_asia_country(self):
        data = module.validate(json.dumps(self.example()).encode(), "VN")
        previous = {**data, "candidates": []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({
                "version": 1, "country_reports": [],
                "global_batches": [], "asia_reports": [previous]
            }), encoding="utf-8")
            module.publish(data, path)
            saved = json.loads(path.read_text())
            self.assertEqual(saved["asia_reports"], [data])

    def test_unchanged_asia_report_is_not_written_again(self):
        data = module.validate(json.dumps(self.example()).encode(), "VN")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({
                "version": 1, "country_reports": [],
                "global_batches": [], "asia_reports": [data]
            }), encoding="utf-8")
            with patch.object(module, "save_research_ledger") as save:
                module.publish(data, path)
                save.assert_not_called()

    def test_workflow_is_main_only_sequential_and_has_no_db_secret(self):
        source = (ROOT / ".github/workflows/asia-research.yml").read_text()
        self.assertIn("github.ref == 'refs/heads/main'", source)
        self.assertIn("cancel-in-progress: false", source)
        self.assertIn("contents: write", source)
        self.assertIn("pull-requests: write", source)
        self.assertIn("group: pokecrack-research-ledger", source)
        self.assertIn("queue_research_ledger.py", source)
        self.assertNotIn("issues: write", source)
        self.assertNotIn("SUPABASE", source)
        self.assertNotIn("OPENAI_API_KEY", source)
        self.assertNotIn("self-hosted", source)


if __name__ == "__main__":
    unittest.main()
