from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import global_studies
import research_intake as module


class ResearchIntakeTests(unittest.TestCase):
    def snapshot(self):
        raw = (ROOT / "data/research/global-studies.json").read_bytes()
        return {"production_admitted": False, "ledger": global_studies.build_ledger(raw)}

    def raw(self, snapshot=None):
        return json.dumps(snapshot or self.snapshot(), sort_keys=True).encode()

    def test_real_reference_seed_builds_count_free_deterministic_manifest(self):
        raw = self.raw()
        output = module.build_manifest(raw)
        self.assertEqual(output, module.build_manifest(raw))
        self.assertEqual(output["snapshot_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertGreater(len(output["references"]), 0)
        for item in output["references"]:
            self.assertEqual(set(item), {"url", "report_group_sha256", "conflicting"})
        for forbidden in ("packs", "country", "metrics", "approved", "html"):
            self.assertNotIn(forbidden, output)

    def test_normalization_matches_canonical_research_ledger(self):
        for url in ("https://EXAMPLE.com/study/", "https://example.com", "https://example.com/開封/",
                    "https://www.reddit.com/r/PokemonTCG/comments/abc123/title/"):
            self.assertEqual(module.reference_url(url), global_studies.reference_url(url))

    def test_conflicting_reports_stay_flagged_and_share_one_group_identity(self):
        snapshot = self.snapshot()
        snapshot["ledger"]["studies"] = [snapshot["ledger"]["studies"][0]]
        group = snapshot["ledger"]["studies"][0]
        group.update(status="conflicting_reports", conflicts=["packs"])
        group["urls"] = ["https://example.com/a", "https://example.com/b"]
        refs = module.build_manifest(self.raw(snapshot))["references"]
        self.assertTrue(all(item["conflicting"] for item in refs))
        self.assertEqual(len({item["report_group_sha256"] for item in refs}), 1)

    def test_invalid_or_self_approved_snapshots_fail_closed(self):
        for mutate in (
            lambda s: s.update(production_admitted=True),
            lambda s: s["ledger"].update(verified_unique_packs=1000),
            lambda s: s["ledger"].update(layer="production"),
            lambda s: s["ledger"]["studies"][0].update(statistics_eligible=True),
            lambda s: s["ledger"]["studies"][0].update(status="conflicting_reports"),
            lambda s: s["ledger"]["studies"][0].update(urls=["https://127.0.0.1/private"]),
            lambda s: s["ledger"]["studies"].append(copy.deepcopy(s["ledger"]["studies"][0])),
        ):
            snapshot = self.snapshot()
            mutate(snapshot)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                module.build_manifest(self.raw(snapshot))

    def test_workflow_bridges_only_after_validated_publication_and_artifact(self):
        workflow = (ROOT / ".github/workflows/country-research.yml").read_text()
        self.assertLess(workflow.index("--publish"), workflow.index("scripts/research_intake.py"))
        self.assertLess(workflow.index("country-research-ledger-"), workflow.index("scripts/research_intake.py"))
        self.assertIn("vars.COUNTRY_RESEARCH_INTAKE_ENABLED == 'true'", workflow)
        self.assertIn("bash /home/codex/pokecrack/deploy/scripts/import-research-intake.sh", workflow)
        self.assertNotIn("SUPABASE", workflow)
        self.assertNotIn("OPENAI_API_KEY", workflow)
        self.assertNotIn("--prod", workflow)


if __name__ == "__main__":
    unittest.main()
