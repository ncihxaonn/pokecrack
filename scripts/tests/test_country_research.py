from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import country_research as module
from country_targets import COUNTRIES, COUNTRY_REGION, REGION_ORDER, REGIONS


class CountryResearchTests(unittest.TestCase):
    def selection(self):
        return module.select_targets([])

    def report(self, selection=None, studies=None):
        selection = selection or self.selection()
        result = {**selection, "results": [{"target": code, "studies": studies or []}
                                           for code in selection["targets"]]}
        return module.validate_report(json.dumps(result).encode(), selection)

    def row(self):
        seed = json.loads((ROOT / "data/research/global-studies.json").read_text())
        return seed["studies"][0]

    def issue(self, report):
        return {"title": module.TITLE + module.fingerprint(report),
                "body": module.issue_body(report),
                "author": {"login": "app/github-actions", "is_bot": True}}

    def test_complete_country_area_inventory_no_cities_or_duplicate_codes(self):
        self.assertEqual(REGION_ORDER, ("asia", "oceania", "europe", "africa", "north-america", "latin-america", "antarctica"))
        self.assertEqual([len(REGIONS[key]) for key in REGION_ORDER], [51, 29, 51, 60, 5, 52, 1])
        self.assertEqual(len(COUNTRIES), 249)
        iso = set(json.loads((ROOT / "apps/web/src/data/iso-alpha2.json").read_text()))
        self.assertEqual(set(COUNTRIES), iso)
        self.assertEqual(sum(map(len, REGIONS.values())), len(COUNTRIES))
        self.assertEqual(COUNTRY_REGION["TR"], "asia")
        self.assertEqual(COUNTRY_REGION["RU"], "europe")
        self.assertEqual(COUNTRY_REGION["AU"], "oceania")
        self.assertEqual(COUNTRY_REGION["TW"], "asia")
        self.assertNotIn("Sydney", COUNTRIES.values())

    def test_missing_asia_targets_are_first(self):
        self.assertEqual(self.selection()["targets"], ["MY", "VN", "PH"])
        self.assertEqual(module.select_targets([self.report()])["targets"], ["HK", "IN", "MO"])

    def test_progress_is_success_evidence_not_wall_clock(self):
        self.assertEqual(module.select_targets([]), module.select_targets([]))
        with patch.object(module, "research_document", side_effect=ValueError("research_timeout")), \
                patch.object(module, "read_bounded", return_value=json.dumps(self.selection()).encode()), \
                patch.object(sys, "argv", ["country_research.py", "--research", "selection"]), \
                patch.object(module, "publish") as publish, redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(SystemExit, "stage=research code=research_timeout"):
                module.main()
            publish.assert_not_called()
            self.assertEqual(output.getvalue(), "")

    def test_all_countries_precede_next_continent_and_then_next_sweep(self):
        history = []
        observed = []
        while (selection := module.select_targets(history))["sweep"] == 1:
            self.assertEqual(len({COUNTRY_REGION[code] for code in selection["targets"]}), 1)
            observed.extend(selection["targets"])
            history.append(self.report(selection))
        self.assertEqual(observed, list(COUNTRIES))
        self.assertEqual(selection, {**self.selection(), "sweep": 2})
        self.assertEqual(len(history), 85)

    def test_existing_four_region_history_resumes_in_americas_without_reset(self):
        history = []
        while (selection := module.select_targets(history))["targets"][0] != "US":
            history.append(self.report(selection))
        self.assertEqual(len(history), 64)
        self.assertEqual(selection["sweep"], 1)
        self.assertEqual(selection["targets"], ["US", "CA", "BM"])
        # Old report fingerprints and the campaign marker remain stable.
        with patch.object(module.subprocess, "run", return_value=Mock(
                stdout=json.dumps([self.issue(report) for report in history]))):
            self.assertEqual(module.country_history(), history)

    def test_each_global_phase_produces_a_valid_prompt_and_selection(self):
        for region in REGION_ORDER:
            with self.subTest(region=region):
                selection = {**self.selection(), "targets": [REGIONS[region][0][0]]}
                self.assertEqual(module.validate_selection(selection), selection)
                self.assertIn(COUNTRIES[selection["targets"][0]], module.prompt(selection))

    def test_selection_rejects_cross_region_invalid_repeated_and_extra_values(self):
        for update in ({"targets": []}, {"targets": ["MY", "AU"]},
                       {"targets": ["MY", "MY"]}, {"targets": ["ZZ"]},
                       {"targets": ["MY", "VN", "PH", "HK"]}, {"sweep": True},
                       {"sweep": 0}, {"sweep": 101}, {"campaign": "untrusted"}, {"city": "x"}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                module.validate_selection({**self.selection(), **update})

    def test_report_requires_each_selected_country_exactly_once(self):
        report = self.report()
        for results in ([], report["results"][:2], [report["results"][0]] * 3,
                        [*report["results"][:2], {"target": "AU", "studies": []}]):
            with self.subTest(results=results), self.assertRaises(ValueError):
                module.validate_report(json.dumps({**report, "results": results}).encode())
        with self.assertRaisesRegex(ValueError, "selection_mismatch"):
            module.validate_report(json.dumps(report).encode(), {**self.selection(), "sweep": 2})

    def test_studies_do_not_inherit_search_country_or_self_approve(self):
        report = self.report(studies=[self.row()])
        for item in report["results"]:
            self.assertIsNone(item["studies"][0]["country"])
            self.assertEqual(item["studies"][0]["geography_basis"], "unknown")
            self.assertIn("independent-review-pending", item["studies"][0]["limitations"])
        output = module.snapshot(report, [], {"studies": []}, [])
        self.assertEqual(output["ledger"]["distinct_report_groups"], 1)
        self.assertEqual(output["ledger"]["input_reports"], 1)
        self.assertIsNone(output["ledger"]["verified_unique_packs"])
        self.assertFalse(output["production_admitted"])

    def test_empty_reports_advance_research_only_and_keep_existing_global_evidence(self):
        report = self.report()
        output = module.snapshot(report, [], {"studies": [self.row()]}, [])
        self.assertEqual(output["checked_this_sweep"], ["MY", "VN", "PH"])
        self.assertEqual(output["next"]["targets"], ["HK", "IN", "MO"])
        self.assertEqual(output["ledger"]["distinct_report_groups"], 1)
        self.assertFalse(output["ledger"]["production_admitted"])
        self.assertIn("never zero activity", module.issue_body(report))

    def test_limits_and_no_country_result_padding(self):
        report = self.report()
        report["results"][0]["studies"] = [self.row()] * 3
        with self.assertRaises(ValueError):
            module.validate_report(json.dumps(report).encode())
        with self.assertRaises(ValueError):
            module.validate_report(b" " * (module.MAX_BYTES + 1))
        raw = json.dumps(self.report()).encode()
        with patch.object(module, "MAX_BYTES", len(raw) - 1), self.assertRaises(ValueError):
            module.validate_report(raw)

    def test_bot_owned_history_only_and_fingerprint_integrity(self):
        report = self.report()
        issue = self.issue(report)
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([issue]))):
            self.assertEqual(module.country_history(), [report])
        issue["author"] = {"login": "ncihxaonn", "is_bot": False}
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([issue]))):
            self.assertEqual(module.country_history(), [])
        issue = {**self.issue(report), "title": module.TITLE + "tampered"}
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([issue]))), \
                self.assertRaisesRegex(ValueError, "fingerprint"):
            module.country_history()

    def test_history_capacity_fails_without_silently_skipping_targets(self):
        with patch.object(module.subprocess, "run", return_value=Mock(stdout=json.dumps([{}] * 1000))), \
                self.assertRaisesRegex(ValueError, "capacity"):
            module.country_history()

    def test_publish_retry_is_idempotent_and_stale_selection_fails(self):
        report = self.report()
        seed = ROOT / "data/research/global-studies.json"
        with patch.object(module, "country_history", return_value=[report]), \
                patch.object(module, "load_history", return_value=[]), \
                patch.object(module.subprocess, "run") as run:
            module.publish(report, seed)
            run.assert_not_called()
            changed = self.report(studies=[self.row()])
            with self.assertRaisesRegex(ValueError, "progress_conflict"):
                module.publish(changed, seed)
            run.assert_not_called()
        later = self.report({**self.selection(), "targets": ["AU", "NZ", "FJ"]})
        with patch.object(module, "country_history", return_value=[]), \
                patch.object(module, "load_history", return_value=[]), \
                patch.object(module.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "selection_mismatch"):
                module.publish(later, seed)
            run.assert_not_called()

    def test_prompt_is_bounded_country_only_and_preserves_geo_and_access_rules(self):
        prompt = module.prompt(self.selection())
        for fragment in ("12 queries TOTAL", "not city research", "Unknown geography stays null",
                         "Do not collect cities", "counterfeit/resealed", "Never multiply box contents"):
            self.assertIn(fragment, prompt)
        self.assertEqual(module.schema(self.selection())["properties"]["sweep"]["enum"], [1])

    def test_workflow_replaces_timer_without_db_or_paid_api_credentials(self):
        workflow = (ROOT / ".github/workflows/country-research.yml").read_text()
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("cron: '17 * * * *'", workflow)
        self.assertIn("group: pokecrack-global-research", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("StrictHostKeyChecking=yes", workflow)
        self.assertIn("--selection", workflow)
        self.assertNotIn("SUPABASE", workflow)
        self.assertNotIn("OPENAI_API_KEY", workflow)
        for legacy in ("asia-research.yml", "global-research.yml"):
            self.assertNotIn("cron:", (ROOT / ".github/workflows" / legacy).read_text())


if __name__ == "__main__":
    unittest.main()
