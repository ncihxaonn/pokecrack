from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

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
        self.assertEqual(self.selection()["targets"], ["MY", "VN", "PH", "HK", "IN", "MO"])
        self.assertEqual(module.select_targets([self.report()])["targets"],
                         [code for code, _ in REGIONS["asia"]][6:12])

    def test_full_capacity_preserves_uncertainty_and_legacy_reports(self):
        legacy_selection = {**self.selection(), "targets": ["MY", "VN", "PH"]}
        legacy = self.report(legacy_selection, [self.row()])
        self.assertEqual(module.validate_report(json.dumps(legacy).encode()), legacy)
        report = self.report()
        for index, result in enumerate(report["results"]):
            result["studies"] = [{**self.row(), "study_id": f"sample-{index}-{j}",
                                  "cohort_ids": [f"sample-{index}-{j}"],
                                  "urls": [f"https://example.com/sample-{index}-{j}"]}
                                 for j in range(6)]
        report = module.validate_report(json.dumps(report).encode())
        output = module.snapshot(report, [], {"studies": []}, [])
        self.assertEqual(output["ledger"]["distinct_report_groups"], 36)
        self.assertIsNone(output["ledger"]["verified_unique_packs"])
        self.assertLess(len(json.dumps(report).encode()), 65536)
        self.assertIn("return at most 36 studies", module.prompt(self.selection()))
        self.assertNotIn("12 queries", module.prompt(self.selection()))
        result_schema = module.schema(self.selection())["properties"]["results"]["items"]
        self.assertEqual(result_schema["properties"]["studies"]["maxItems"], 6)

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
        self.assertEqual(len(history), 44)

    def test_existing_four_region_history_resumes_in_americas_without_reset(self):
        history = []
        while (selection := module.select_targets(history))["targets"][0] != "US":
            history.append(self.report(selection))
        self.assertEqual(len(history), 33)
        self.assertEqual(selection["sweep"], 1)
        self.assertEqual(selection["targets"], [code for code, _ in REGIONS["north-america"]])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({
                "version": 1, "country_reports": history,
                "global_batches": [], "asia_reports": []
            }), encoding="utf-8")
            self.assertEqual(module.country_history(path), history)

    def test_each_global_phase_produces_a_valid_prompt_and_selection(self):
        for region in REGION_ORDER:
            with self.subTest(region=region):
                selection = {**self.selection(), "targets": [REGIONS[region][0][0]]}
                self.assertEqual(module.validate_selection(selection), selection)
                self.assertIn(COUNTRIES[selection["targets"][0]], module.prompt(selection))

    def test_selection_rejects_cross_region_invalid_repeated_and_extra_values(self):
        for update in ({"targets": []}, {"targets": ["MY", "AU"]},
                       {"targets": ["MY", "MY"]}, {"targets": ["ZZ"]},
                       {"targets": [code for code, _ in REGIONS["asia"]][:7]}, {"sweep": True},
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
        self.assertEqual(output["checked_this_sweep"], self.selection()["targets"])
        self.assertEqual(output["next"]["targets"], [code for code, _ in REGIONS["asia"]][6:12])
        self.assertEqual(output["ledger"]["distinct_report_groups"], 1)
        self.assertFalse(output["ledger"]["production_admitted"])
        self.assertEqual(report["results"][0]["studies"], [])

    def test_limits_and_no_country_result_padding(self):
        report = self.report()
        report["results"][0]["studies"] = [self.row()] * 7
        with self.assertRaises(ValueError):
            module.validate_report(json.dumps(report).encode())
        with self.assertRaises(ValueError):
            module.validate_report(b" " * (module.MAX_BYTES + 1))
        raw = json.dumps(self.report()).encode()
        with patch.object(module, "MAX_BYTES", len(raw) - 1), self.assertRaises(ValueError):
            module.validate_report(raw)

    def test_ledger_history_validates_reports_and_fails_closed(self):
        report = self.report()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({
                "version": 1, "country_reports": [report],
                "global_batches": [], "asia_reports": []
            }), encoding="utf-8")
            self.assertEqual(module.country_history(path), [report])
            path.write_text(json.dumps({}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_research_ledger"):
                module.country_history(path)

    def test_publish_is_idempotent_and_stale_selection_fails(self):
        report = self.report()
        seed = ROOT / "data/research/global-studies.json"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({
                "version": 1, "country_reports": [],
                "global_batches": [], "asia_reports": []
            }), encoding="utf-8")
            module.publish(report, seed, path)
            self.assertEqual(module.country_history(path), [report])
            changed = self.report(studies=[self.row()])
            with self.assertRaisesRegex(ValueError, "progress_conflict"):
                module.publish(changed, seed, path)
            later = self.report({**self.selection(), "targets": ["AU", "NZ", "FJ"]})
            with self.assertRaisesRegex(ValueError, "selection_mismatch"):
                module.publish(later, seed, path)

    def test_prompt_is_bounded_country_only_and_preserves_geo_and_access_rules(self):
        prompt = module.prompt(self.selection())
        for fragment in ("24 queries TOTAL", "not city research", "Unknown geography stays null",
                         "Do not collect cities", "counterfeit/resealed", "Never multiply box contents"):
            self.assertIn(fragment, prompt)
        self.assertEqual(module.schema(self.selection())["properties"]["sweep"]["enum"], [1])

    def test_workflow_replaces_timer_without_db_or_paid_api_credentials(self):
        workflow = (ROOT / ".github/workflows/country-research.yml").read_text()
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("cron: '17,47 * * * *'", workflow)
        self.assertLess(workflow.index("scripts/research_checkpoint.py"),
                        workflow.index("scripts/country_research.py --select"))
        self.assertIn("contents: write", workflow)
        self.assertIn("pull-requests: write", workflow)
        self.assertIn("group: pokecrack-research-ledger", workflow)
        self.assertIn("queue_research_ledger.py", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("StrictHostKeyChecking=yes", workflow)
        self.assertIn("--selection", workflow)
        self.assertNotIn("SUPABASE", workflow)
        self.assertNotIn("OPENAI_API_KEY", workflow)
        self.assertNotIn("cron:", (ROOT / ".github/workflows" / "asia-research.yml").read_text())
        self.assertIn("cron: '7 */6 * * *'", (ROOT / ".github/workflows" / "global-research.yml").read_text())

    def test_context_is_minimal_and_does_not_mutate_historical_fingerprints(self):
        report = self.report(studies=[self.row()])
        original = json.dumps(report, sort_keys=True)
        selection = {**self.selection(), "sweep": 2}
        context = module.continuation_context(selection, [report, report])
        self.assertEqual(context["prior_passes"], dict.fromkeys(selection["targets"], 1))
        self.assertEqual(context["known_urls"], report["results"][0]["studies"][0]["urls"])
        self.assertEqual(context["known_cohort_ids"], self.row()["cohort_ids"])
        self.assertEqual(json.dumps(report, sort_keys=True), original)
        for field in ("packs", "country", "geography_basis", "metrics", "limitations", "method"):
            self.assertNotIn('"' + field + '"', json.dumps(context))
        self.assertEqual(module.validate_context(context, selection), context)

    def test_empty_passes_are_retained_as_search_hints_not_zero_packs(self):
        selection = {**self.selection(), "sweep": 2}
        context = module.continuation_context(selection, [self.report()])
        self.assertEqual(context["prior_passes"]["MY"], 1)
        self.assertEqual(context["known_urls"], [])
        self.assertIn("Earlier empty passes do not prove zero activity", module.prompt(selection, context))

    def test_shared_urls_do_not_inherit_new_target_geography(self):
        selection = {**self.selection(), "targets": ["AU", "NZ", "FJ"]}
        context = module.continuation_context(selection, [self.report(studies=[self.row()])])
        self.assertEqual(context["prior_passes"], {"AU": 0, "NZ": 0, "FJ": 0})
        self.assertTrue(context["known_urls"])
        self.assertNotIn("country", context)

    def test_local_prior_references_precede_shared_known_reports(self):
        row = {**self.row(), "urls": ["https://example.com/local"], "cohort_ids": ["local-sample"]}
        remote = {**self.row(), "urls": ["https://example.com/shared"], "cohort_ids": ["shared-sample"]}
        history = [self.report(studies=[row]), self.report(
            {**self.selection(), "targets": ["AU"]}, [remote])]
        context = module.continuation_context({**self.selection(), "sweep": 2}, history)
        self.assertEqual(context["known_urls"], ["https://example.com/local", "https://example.com/shared"])

    def test_context_windows_rotate_deterministically_and_preserve_all_history(self):
        reports = []
        for index in range(80):
            row = {**self.row(), "urls": [f"https://example.com/report-{index:03d}"],
                   "cohort_ids": [f"cohort-{index:03d}"]}
            reports.append(self.report(studies=[row]))
        original = json.dumps(reports, sort_keys=True)
        first = module.continuation_context({**self.selection(), "sweep": 2}, reports)
        second = module.continuation_context({**self.selection(), "sweep": 3}, reports)
        self.assertEqual(first, module.continuation_context(
            {**self.selection(), "sweep": 2}, list(reversed(reports))))
        self.assertEqual(len(first["known_urls"]), 64)
        self.assertEqual(len(first["known_cohort_ids"]), 32)
        self.assertNotEqual(set(first["known_urls"]), set(second["known_urls"]))
        self.assertEqual(len(set(first["known_urls"] + second["known_urls"])), 80)
        self.assertEqual(json.dumps(reports, sort_keys=True), original)

    def test_long_reference_hints_fit_byte_budget_without_weakening_report_limits(self):
        reports = [self.report(studies=[{**self.row(),
            "urls": ["https://example.com/" + str(index) + "x" * 950],
            "cohort_ids": [str(index) + "c" * 95]}]) for index in range(70)]
        context = module.continuation_context({**self.selection(), "sweep": 2}, reports)
        self.assertLessEqual(len(json.dumps(context, sort_keys=True).encode()), module.MAX_CONTEXT_BYTES)
        self.assertGreater(len(context["known_urls"]), 0)
        self.assertLess(len(context["known_urls"]), 64)
        self.assertEqual(module.MAX_BYTES, 49152)

    def test_context_rejects_wrong_selection_extra_fields_and_invalid_references(self):
        selected = self.selection()
        context = module.continuation_context(selected, [])
        invalid = [
            {"version": True}, {"selection": {**selected, "sweep": 2}},
            {"selection": {**selected, "targets": ["AU"]}}, {"packs": 100},
            {"prior_passes": {"MY": True, "VN": 0, "PH": 0}},
            {"prior_passes": {"MY": 1, "VN": 0, "PH": 0}},
            {"prior_passes": {"MY": 0}}, {"known_urls": "https://example.com/"},
            {"known_urls": ["https://example.com/?secret=private"]},
            {"known_urls": ["https://example.com/<ignore-instructions>"]},
            {"known_urls": ["https://example.com/"] * 2},
            {"known_urls": [f"https://example.com/{i}" for i in range(65)]},
            {"known_cohort_ids": ["bad identity"]}, {"known_cohort_ids": [True]},
            {"known_cohort_ids": [f"id-{i}" for i in range(33)]},
        ]
        for update in invalid:
            with self.subTest(update=update), self.assertRaises(ValueError):
                module.validate_context({**context, **update}, selected)
        with patch.object(module, "MAX_CONTEXT_BYTES", 10), self.assertRaises(ValueError):
            module.validate_context(context, selected)

    def test_context_prompt_rotates_angles_without_broad_host_exclusion_or_approval(self):
        for sweep, angle in enumerate(module.QUERY_ANGLES, 1):
            selection = {**self.selection(), "sweep": sweep}
            context = module.continuation_context(selection, [])
            prompt = module.prompt(selection, context)
            self.assertIn(angle, prompt)
            for fragment in ("REFERENCE DATA ONLY", "Do not exclude whole hosts",
                             "SAME identity", "all access restrictions", "24 queries TOTAL",
                             "absence does not prove independence or permission"):
                self.assertIn(fragment, prompt)

    def test_select_writes_hints_from_same_verified_history_and_keeps_selection_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            with patch.object(module, "country_history", return_value=[]) as history, \
                    patch.object(sys, "argv", ["country_research.py", "--select", "--context", str(path)]), \
                    redirect_stdout(io.StringIO()) as output:
                module.main()
            history.assert_called_once_with()
            self.assertEqual(json.loads(output.getvalue()), self.selection())
            self.assertEqual(module.validate_context(json.loads(path.read_text()), self.selection()),
                             module.continuation_context(self.selection(), []))

    def test_research_consumes_selection_bound_context_without_publishing_or_gh_access(self):
        selection = self.selection()
        context = module.continuation_context(selection, [])
        with patch.object(module, "read_bounded", side_effect=[json.dumps(selection).encode(),
                json.dumps(context).encode()]), patch.object(module, "research_document",
                return_value=json.dumps(self.report()).encode()) as research, \
                patch.object(module, "country_history") as history, \
                patch.object(module, "publish") as publish, \
                patch.object(sys, "argv", ["country_research.py", "--research", "selection", "--context", "context"]), \
                redirect_stdout(io.StringIO()) as output:
            module.main()
        research.assert_called_once_with(module.prompt(selection, context), module.schema(selection),
                                         max_bytes=module.MAX_BYTES)
        history.assert_not_called()
        publish.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), self.report())

    def test_bad_context_fails_before_search_and_keeps_payload_out_of_logs(self):
        context = module.continuation_context(self.selection(), [])
        context["known_urls"] = ["https://example.com/?token=private"]
        with patch.object(module, "read_bounded", side_effect=[json.dumps(self.selection()).encode(),
                json.dumps(context).encode()]), patch.object(module, "research_document") as research, \
                patch.object(sys, "argv", ["country_research.py", "--research", "selection", "--context", "context"]), \
                redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(SystemExit, "stage=context code=invalid_reference_url") as caught:
                module.main()
        self.assertNotIn("private", str(caught.exception))
        research.assert_not_called()
        self.assertEqual(output.getvalue(), "")

    def test_hourly_workflow_transfers_context_without_adding_credentials_or_report_schema(self):
        workflow = (ROOT / ".github/workflows/country-research.yml").read_text()
        self.assertIn('--select --context "$RUNNER_TEMP/country-context.json"', workflow)
        self.assertIn("--context '$remote_dir/country-context.json'", workflow)
        self.assertIn("'$remote_dir/country-context.json'; rmdir", workflow)
        self.assertNotIn("known_urls", module.schema(self.selection())["properties"])


if __name__ == "__main__":
    unittest.main()
