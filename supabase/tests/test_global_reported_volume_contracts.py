from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "migrations/20261029000000_global_reported_volume.sql").read_text()
DATABASE_TYPES = (ROOT / "types/database.ts").read_text()


class GlobalReportedVolumeContractTests(unittest.TestCase):
    def test_migration_is_forward_only_and_keeps_the_volume_lane_separate(self) -> None:
        lowered = MIGRATION.casefold()
        self.assertEqual(lowered.count("begin;"), 1)
        self.assertEqual(lowered.count("commit;"), 1)
        self.assertIn("create table ingest.global_volume_candidates", lowered)
        self.assertIn("create table ingest.global_volume_observations", lowered)
        self.assertIn("state in ('reported', 'checking', 'verified', 'rejected', 'conflicting')", lowered)
        self.assertIn("pack_count integer not null check (pack_count between 1 and 100000000)", lowered)
        self.assertIn("alter table ingest.global_volume_candidates force row level security", lowered)
        self.assertIn("alter table ingest.global_volume_observations force row level security", lowered)
        self.assertIn("no hit-rate numerator or inference", lowered)
        self.assertIn("source_redirected", lowered)
        self.assertIn("source_challenged", lowered)
        self.assertNotIn("drop table", lowered)
        self.assertNotIn("truncate", lowered)

    def test_public_projection_has_explicit_known_and_unknown_paths(self) -> None:
        self.assertIn("ingest.global_volume_public_rows_v1()", MIGRATION)
        self.assertIn("where candidates.country_code is not null", MIGRATION)
        self.assertIn("where c.country_code is null", MIGRATION)
        self.assertIn("case when rows.reported_volume then jsonb_build_object", MIGRATION)
        self.assertIn("'reportedVolume', true", MIGRATION)
        self.assertIn("'unknownLocation',unknown_location", MIGRATION)

    def test_generated_types_include_the_three_worker_rpcs_and_private_tables(self) -> None:
        for name in (
            "global_volume_candidates",
            "global_volume_observations",
            "claim_global_volume_candidates_v1",
            "finalize_global_volume_candidate_v1",
            "global_volume_public_rows_v1",
            "import_global_volume_intake_v1",
        ):
            self.assertIn(name, DATABASE_TYPES)


if __name__ == "__main__":
    unittest.main()
