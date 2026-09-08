from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("global_research", ROOT / "scripts/global_research.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GlobalResearchTests(unittest.TestCase):
    def batch(self):
        row = json.loads((ROOT / "data/research/global-studies.json").read_text())["studies"][0]
        return module.validate_batch(json.dumps({"version": 1, "studies": [row]}).encode())

    def test_focus_rotation_is_worldwide(self):
        start = datetime(2026, 9, 8, tzinfo=timezone.utc)
        self.assertEqual([module.select_scope("auto", start + timedelta(hours=6*i))
                          for i in range(7)], list(module.SCOPES))
        self.assertEqual(module.select_scope("auto", start + timedelta(hours=42)), "global")

    def test_research_results_never_self_approve(self):
        row = self.batch()["studies"][0]
        self.assertIn("independent-review-pending", row["limitations"])
        self.assertIn("collector-policy-not-enabled", row["limitations"])
        self.assertIsNone(row["country"])

    def test_batch_limit(self):
        batch = self.batch()
        batch["studies"] *= 7
        with self.assertRaises(ValueError):
            module.validate_batch(json.dumps(batch).encode())

    def test_normalized_batch_must_fit_future_history_reader(self):
        batch = self.batch()
        batch["studies"][0]["limitations"] = []
        raw = json.dumps(batch).encode()
        with patch.object(module, "MAX_BYTES", len(raw) + 1):
            with self.assertRaises(ValueError):
                module.validate_batch(raw)

    def test_history_round_trip_and_bot_only(self):
        batch = self.batch()
        item = {"title": module.TITLE + module.fingerprint(batch),
                "body": module.issue_body(batch),
                "author": {"login": "app/github-actions", "is_bot": True}}
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([item]))):
            self.assertEqual(module.load_history(), batch["studies"])
        item["author"] = {"login": "ncihxaonn", "is_bot": False}
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([item]))):
            self.assertEqual(module.load_history(), [])

    def test_legacy_history_fingerprint_survives_native_sample_extension(self):
        batch = self.batch()
        batch["studies"][0].pop("source_sample", None)
        digest = module.fingerprint(batch)
        item = {"title": module.TITLE + digest, "body": module.issue_body(batch),
                "author": {"login": "app/github-actions", "is_bot": True}}
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([item]))):
            self.assertEqual(module.load_history(), batch["studies"])
        self.assertEqual(module.fingerprint(module.validate_batch(json.dumps(batch).encode())), digest)

    def test_new_schema_and_prompt_preserve_native_units(self):
        fields = module.schema()["properties"]["studies"]["items"]
        self.assertIn("source_sample", fields["required"])
        self.assertEqual(fields["properties"]["source_sample"]["properties"]["unit"]["enum"],
                         ["boxes", "cartons", "decks"])
        self.assertIn("Never multiply box contents into packs", module.prompt("asia"))

    def test_tampered_history_fails_closed(self):
        item = {"title": module.TITLE + "wrong", "body": module.issue_body(self.batch()),
                "author": {"login": "app/github-actions", "is_bot": True}}
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([item]))):
            with self.assertRaises(ValueError):
                module.load_history()

    def test_accumulation_retains_old_reports_and_skips_exact_replays(self):
        batch = self.batch()
        new, ledger = module.accumulate(batch, {"studies": []}, batch["studies"])
        self.assertEqual(new["studies"], [])
        self.assertEqual(ledger["distinct_report_groups"], 1)
        self.assertIsNone(ledger["verified_unique_packs"])

    def test_history_at_capacity_does_not_silently_truncate(self):
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([{}]*1000))):
            with self.assertRaises(ValueError):
                module.load_history()

    def test_no_rewrite_for_unchanged_batch(self):
        batch = self.batch()
        with patch.object(module, "load_history", return_value=batch["studies"]), \
                patch.object(module.subprocess, "run") as run:
            module.publish(batch, ROOT / "data/research/global-studies.json")
            run.assert_not_called()

    def test_workflow_is_main_only_and_has_no_production_db_credentials(self):
        workflow = (ROOT / ".github/workflows/global-research.yml").read_text()
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("global-ledger.json", workflow)
        self.assertNotIn("SUPABASE", workflow)
        self.assertNotIn("OPENAI_API_KEY", workflow)
        legacy = (ROOT / ".github/workflows/asia-research.yml").read_text()
        self.assertNotIn("cron:", legacy)


if __name__ == "__main__":
    unittest.main()
