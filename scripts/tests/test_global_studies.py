from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("global_studies", ROOT / "scripts/global_studies.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GlobalStudiesTests(unittest.TestCase):
    def sample(self):
        return {"study_id": "opening-one", "cohort_ids": ["original-opening"],
                "urls": ["https://example.com/opening"], "set": "test-set",
                "language": "en", "product": "booster-box", "country": None,
                "geography_basis": "unknown", "packs": 36,
                "pack_precision": "exact_reported", "method": "complete-opening",
                "metrics": [{"category": "sir", "hits": 2, "unit": "cards"}],
                "limitations": []}

    def build(self, rows):
        return module.build_ledger(json.dumps({"version": 1, "studies": rows}).encode())

    def test_repost_counts_once_and_is_not_automatically_admitted(self):
        a = self.sample()
        b = copy.deepcopy(a)
        b.update(study_id="translated-report", urls=["https://example.org/translation"])
        result = self.build([a, b])
        self.assertEqual(result["distinct_report_groups"], 1)
        self.assertEqual(result["studies"][0]["packs"], 36)
        self.assertEqual(result["studies"][0]["metrics"][0]["hits"], 2)
        self.assertFalse(result["studies"][0]["statistics_eligible"])
        self.assertIsNone(result["verified_unique_packs"])

    def test_shared_url_and_transitive_aliases_deduplicate(self):
        a = self.sample()
        b = copy.deepcopy(a)
        b.update(study_id="second", cohort_ids=["other-cohort"])
        c = copy.deepcopy(b)
        c.update(study_id="third", urls=["https://example.net/third"])
        self.assertEqual(self.build([a, b, c])["distinct_report_groups"], 1)

    def test_reddit_post_slug_alias_preserves_original_records(self):
        a = self.sample()
        a["urls"] = ["https://www.reddit.com/r/PokemonTCG/comments/qqpiol/"]
        b = copy.deepcopy(a)
        b.update(study_id="rediscovery", cohort_ids=["different-generated-cohort"],
                 urls=["https://www.reddit.com/r/PokemonTCG/comments/qqpiol/title_slug"])
        before = module.validate_record(b)
        result = self.build([a, b])
        self.assertEqual(result["distinct_report_groups"], 1)
        self.assertEqual(result["studies"][0]["packs"], 36)
        self.assertEqual(len(result["studies"][0]["urls"]), 2)
        self.assertEqual(before, module.validate_record(b))
        self.assertEqual(before["urls"], b["urls"])
        self.assertEqual(result, self.build([b, a]))

    def test_reddit_alias_does_not_merge_comments_other_posts_or_lookalike_hosts(self):
        a = self.sample()
        a["urls"] = ["https://www.reddit.com/r/PokemonTCG/comments/qqpiol"]
        for url in (
            "https://www.reddit.com/r/PokemonTCG/comments/qqpiol/title/commentid",
            "https://www.reddit.com/r/PokemonTCG/comments/otherid/title",
            "https://www.reddit.com.example.com/r/PokemonTCG/comments/qqpiol/title",
            "https://example.com/r/PokemonTCG/comments/qqpiol/title",
        ):
            b = copy.deepcopy(a)
            b.update(study_id="other", cohort_ids=["other"], urls=[url])
            with self.subTest(url=url):
                self.assertEqual(self.build([a, b])["distinct_report_groups"], 2)

    def test_reddit_alias_conflicts_are_quarantined_not_added(self):
        a = self.sample()
        a["urls"] = ["https://www.reddit.com/r/PokemonTCG/comments/qqpiol"]
        b = copy.deepcopy(a)
        b.update(cohort_ids=["different"], packs=72,
                 urls=["https://old.reddit.com/comments/qqpiol/title"])
        result = self.build([a, b])
        self.assertEqual(result["distinct_report_groups"], 1)
        self.assertEqual(result["studies"][0]["status"], "conflicting_reports")
        self.assertIsNone(result["studies"][0]["packs"])

    def test_reddit_shortlinks_and_new_frontend_share_post_identity(self):
        a = self.sample()
        a["urls"] = ["https://www.reddit.com/r/PokemonTCG/comments/qqpiol"]
        for url in ("https://redd.it/qqpiol", "https://redd.it/qqpiol/",
                    "https://new.reddit.com/r/PokemonTCG/comments/qqpiol/title",
                    "https://np.reddit.com/r/PokemonTCG/comments/qqpiol/title",
                    "https://m.reddit.com/r/PokemonTCG/comments/qqpiol/title",
                    "https://sh.reddit.com/r/PokemonTCG/comments/qqpiol/title",
                    "https://de.reddit.com/r/PokemonTCG/comments/qqpiol/title",
                    "https://www.reddit.com/gallery/qqpiol"):
            b = copy.deepcopy(a)
            b.update(cohort_ids=["different"], urls=[url])
            with self.subTest(url=url):
                self.assertEqual(self.build([a, b])["distinct_report_groups"], 1)
        for url in ("https://i.redd.it/qqpiol", "https://v.redd.it/qqpiol",
                    "https://redd.it/qqpiol/comment", "https://redd.it.example.com/qqpiol",
                    "https://notreddit.com/gallery/qqpiol",
                    "https://reddit.com.example.com/gallery/qqpiol",
                    "https://www.reddit.com/gallery/qqpiol/another"):
            self.assertIsNone(module.report_alias_key(url))

    def test_conflicting_denominator_quarantines_component(self):
        a = self.sample()
        b = copy.deepcopy(a)
        b["packs"] = 72
        row = self.build([a, b])["studies"][0]
        self.assertEqual(row["status"], "conflicting_reports")
        self.assertIsNone(row["packs"])
        self.assertEqual(row["pack_precision"], "unknown")
        self.assertEqual(row["metrics"], [])

    def test_conflicting_hits_not_last_wins(self):
        a = self.sample()
        b = copy.deepcopy(a)
        b["metrics"][0]["hits"] = 3
        self.assertEqual(self.build([a, b])["studies"][0]["metrics"], [])

    def test_identical_counts_alone_do_not_merge_independent_cohorts(self):
        a = self.sample()
        b = copy.deepcopy(a)
        b.update(study_id="second", cohort_ids=["second"], urls=["https://example.org/two"])
        self.assertEqual(self.build([a, b])["distinct_report_groups"], 2)

    def test_unknown_country_is_preserved(self):
        self.assertIsNone(self.build([self.sample()])["studies"][0]["country"])

    def test_generated_study_slug_collision_does_not_merge_samples(self):
        a = self.sample()
        b = copy.deepcopy(a)
        b.update(cohort_ids=["different-original"], urls=["https://example.org/other"], packs=72)
        result = self.build([a, b])
        self.assertEqual(result["distinct_report_groups"], 2)
        self.assertEqual(sorted(row["packs"] for row in result["studies"]), [36, 72])
        self.assertEqual(result, self.build([b, a]))

    def test_precision_boolean_negative_and_unknown_fields_rejected(self):
        for field, value in [("packs", True), ("packs", -1), ("packs", 0),
                             ("pack_precision", "lower_bound"), ("country", "US"),
                             ("secret", "not-allowed")]:
            a = self.sample()
            a[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.build([a])

    def test_card_yield_not_pack_probability(self):
        a = self.sample()
        a["metrics"][0]["hits"] = 40
        self.assertEqual(self.build([a])["studies"][0]["metrics"][0]["unit"], "cards")
        a["metrics"][0]["unit"] = "packs_with_hit"
        with self.assertRaises(ValueError):
            self.build([a])

    def test_nonexact_denominator_can_be_kept_without_metrics(self):
        a = self.sample()
        a.update(pack_precision="lower_bound", metrics=[])
        self.assertEqual(self.build([a])["studies"][0]["pack_precision"], "lower_bound")

    def test_reference_urls_no_credentials_or_query(self):
        for url in ["https://u:p@example.com/a", "https://example.com/a?token=secret",
                    "http://example.com", "https://localhost/a", "https://127.0.0.1/a"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                module.reference_url(url)

    def test_order_independent_and_trailing_slash_alias(self):
        a = self.sample()
        b = copy.deepcopy(a)
        b["urls"] = ["https://example.com/opening/"]
        self.assertEqual(self.build([a, b]), self.build([b, a]))

    def test_real_catalog_is_reference_only_and_no_fabricated_total(self):
        data = module.build_ledger((ROOT / "data/research/global-studies.json").read_bytes())
        self.assertEqual(data["input_reports"], 15)
        self.assertEqual(data["distinct_report_groups"], 14)
        self.assertFalse(data["production_admitted"])
        self.assertIsNone(data["verified_unique_packs"])
        self.assertEqual(
            {row["country"] for row in data["studies"] if row["country"] is not None},
            {"CN", "ES", "FR"},
        )

    def test_real_same_page_disagreement_is_one_quarantined_cohort(self):
        data = module.build_ledger((ROOT / "data/research/global-studies.json").read_bytes())
        row = next(row for row in data["studies"]
                   if "codedyellow-crown-zenith-results-50" in row["study_ids"])
        self.assertEqual(len(row["study_ids"]), 2)
        self.assertEqual(len(row["urls"]), 1)
        self.assertEqual(row["status"], "conflicting_reports")
        self.assertEqual(row["conflicts"], ["metric:source-reported-art-hit-packs"])
        self.assertIsNone(row["packs"])
        self.assertEqual(row["metrics"], [])

    def test_new_reference_units_do_not_invent_rarity_or_opening_country(self):
        data = module.build_ledger((ROOT / "data/research/global-studies.json").read_bytes())
        rows = {row["study_ids"][0]: row for row in data["studies"]}
        go = rows["codedyellow-pokemon-go-38"]
        self.assertEqual(go["packs"], 38)
        self.assertEqual(go["metrics"], [{"category": "source-art-radiant-or-peelable-ditto",
                                        "hits": 12, "unit": "packs_with_hit"}])
        self.assertIsNone(go["country"])
        self.assertIsNone(go["language"])
        paradigm = rows["nanjakorya-paradigm-trigger-100"]
        self.assertEqual(paradigm["packs"], 100)
        self.assertEqual({m["category"]: m["hits"] for m in paradigm["metrics"]},
                         {"rr": 14, "rrr": 7, "sr": 1, "hr": 2})
        self.assertTrue(all(m["unit"] == "cards" for m in paradigm["metrics"]))
        self.assertFalse(paradigm["statistics_eligible"])

    def test_large_publisher_samples_are_bounds_not_reconstructed_counts(self):
        data = module.build_ledger((ROOT / "data/research/global-studies.json").read_bytes())
        rows = {row["study_ids"][0]: row for row in data["studies"]}
        for study, bound in [("tcgplayer-perfect-order-2026", 3500),
                             ("tcgplayer-destined-rivals-2025", 8000)]:
            self.assertEqual(rows[study]["packs"], bound)
            self.assertEqual(rows[study]["pack_precision"], "lower_bound")
            self.assertEqual(rows[study]["metrics"], [])
        japanese = rows["nanjakorya-star-birth-100"]
        self.assertEqual(japanese["packs"], 100)
        self.assertEqual({m["category"]: m["hits"] for m in japanese["metrics"]},
                         {"rr": 16, "rrr": 6, "sr": 4, "hr": 1})
        self.assertTrue(all(m["unit"] == "cards" for m in japanese["metrics"]))

    def native(self):
        row = self.sample()
        row.update(packs=None, pack_precision="unknown", metrics=[],
                   source_sample={"unit": "boxes", "count": 1000,
                                  "precision": "approximate_reported"})
        return row

    def test_native_units_never_become_packs_or_statistics(self):
        row = self.build([self.native()])["studies"][0]
        self.assertEqual(row["source_sample"], self.native()["source_sample"])
        self.assertIsNone(row["packs"])
        self.assertEqual(row["metrics"], [])
        self.assertFalse(row["statistics_eligible"])
        candidate = next(row for row in json.loads(
            (ROOT / "data/research/global-studies.json").read_text())["studies"]
            if row["study_id"] == "pokemon-infomation-battle-partners-2026")
        self.assertEqual(candidate["source_sample"], self.native()["source_sample"])
        self.assertIsNone(candidate["packs"])

    def test_native_validation_rejects_conversion_and_invalid_samples(self):
        for field, value in [("unit", "packs"), ("unit", "videos"), ("count", True),
                             ("count", 0), ("precision", "inferred"), ("extra", 1)]:
            row = self.native()
            row["source_sample"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.build([row])
        row = self.native()
        row.update(packs=30000, pack_precision="exact_reported")
        with self.assertRaises(ValueError):
            self.build([row])

    def test_native_conflict_quarantines_and_unknown_is_not_conflict(self):
        a = self.native()
        for field, value in [("count", 800), ("unit", "decks"),
                             ("precision", "exact_reported")]:
            b = copy.deepcopy(a)
            b["source_sample"][field] = value
            row = self.build([a, b])["studies"][0]
            self.assertIn("source_sample", row["conflicts"])
            self.assertIsNone(row["source_sample"])
            self.assertEqual(self.build([a, b]), self.build([b, a]))
        b = copy.deepcopy(a)
        del b["source_sample"]
        self.assertEqual(self.build([a, b])["studies"][0]["source_sample"], a["source_sample"])
        b["source_sample"] = None
        self.assertEqual(self.build([a, b])["studies"][0]["conflicts"], [])
        b["set"] = "different-set"
        self.assertIsNone(self.build([a, b])["studies"][0]["source_sample"])

    def test_legacy_shape_is_unchanged(self):
        row = self.sample()
        self.assertNotIn("source_sample", module.validate_record(row))


if __name__ == "__main__":
    unittest.main()
