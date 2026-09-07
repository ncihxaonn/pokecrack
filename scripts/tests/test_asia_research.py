from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("asia_research", ROOT / "scripts/asia_research.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AsiaResearchTests(unittest.TestCase):
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
        self.assertIn("尚未上线", module.issue_body(data))

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

    def test_unchanged_bot_issue_is_not_written_again(self):
        data = module.validate(json.dumps(self.example()).encode(), "VN")
        issue = {"number": 42, "title": "[Asia research] VN — Vietnam",
                 "author": {"login": "github-actions[bot]"}, "state": "OPEN",
                 "body": module.issue_body(data)}
        with patch.object(module.subprocess, "run", return_value=Mock(
            stdout=json.dumps([issue]))) as run:
            module.publish(data)
        self.assertEqual(run.call_count, 1)

    def test_user_issue_cannot_be_overwritten(self):
        data = module.validate(json.dumps(self.example()).encode(), "VN")
        issue = {"number": 42, "title": "[Asia research] VN — Vietnam",
                 "author": {"login": "ncihxaonn"}, "state": "OPEN",
                 "body": module.issue_body(data)}
        with patch.object(module.subprocess, "run", side_effect=[
            Mock(stdout=json.dumps([issue])), Mock()]) as run:
            module.publish(data)
        self.assertEqual(run.call_args_list[1].args[0][1:3], ["issue", "create"])

    def test_workflow_is_main_only_sequential_and_has_no_db_secret(self):
        source = (ROOT / ".github/workflows/asia-research.yml").read_text()
        self.assertIn("github.ref == 'refs/heads/main'", source)
        self.assertIn("cancel-in-progress: false", source)
        self.assertNotIn("SUPABASE", source)
        self.assertNotIn("OPENAI_API_KEY", source)
        self.assertNotIn("self-hosted", source)


if __name__ == "__main__":
    unittest.main()
