"""Retain minimal family identity, never run payloads or restored enablement."""

import unittest
import runpy

import test_backup_sanitizer as fixtures

FAMILY_SCHEMA = runpy.run_path(str(fixtures.SANITIZER))["SOURCE_FAMILY_SCHEMA_SQL"]


def family_dump() -> bytes:
    rows = [
        (
            "source_family_candidates",
            "url, state, discovered_at, checked_at, reason",
            b"https://pokesup.com/blog/unboxing-m2/\tadmitted\t2026-09-09 00:00:00+00\t2026-09-09 00:00:00+00\tvalid",
        ),
        (
            "source_family_admissions",
            "url, policy_version, post_id, product, opening_ordinal, published_at, verified_at, resource_sha256, video_sha256, pack_count",
            b"https://pokesup.com/blog/unboxing-m2/\tpokesup-enumerated-v1\t462\tm2\t1\t2025-09-30 10:44:54+00\t2026-09-09 00:00:00+00\t"
            + b"a" * 64
            + b"\t\\N\t30",
        ),
        ("source_family_tombstones", "url_sha256, reason", b"b" * 64 + b"\tretracted"),
        (
            "source_family_identity_keys",
            "identity_sha256, url_sha256",
            b"c" * 64 + b"\t" + b"d" * 64,
        ),
        (
            "source_family_clock",
            "singleton, discovered_at",
            b"t\t2026-09-09 00:00:00+00",
        ),
        (
            "source_family_control",
            "singleton, enabled, policy_version",
            b"t\tt\tpokesup-enumerated-v1",
        ),
    ]
    return FAMILY_SCHEMA + b"".join(
        fixtures.copy_block("ingest." + name, columns, row)
        for name, columns, row in rows
    )


class SourceFamilyBackupTests(unittest.TestCase):
    def test_schema_drift_missing_constraints_and_extra_columns_fail_closed(
        self,
    ) -> None:
        helper = fixtures.BackupSanitizerTests()
        valid = family_dump()
        variants = [
            valid.replace(b"pack_count integer NOT NULL", b"pack_count text NOT NULL"),
            valid.replace(
                b"pack_count integer NOT NULL,",
                b"raw_html text, pack_count integer NOT NULL,",
            ),
            valid.replace(b"CHECK ((pack_count = 30))", b"CHECK ((pack_count > 0))"),
            valid.replace(b"DEFAULT false NOT NULL", b"DEFAULT true NOT NULL"),
            valid.replace(b"PRIMARY KEY (singleton)", b"UNIQUE (singleton)"),
            valid.replace(b"FORCE ROW LEVEL SECURITY", b"NO FORCE ROW LEVEL SECURITY"),
            valid.replace(b"OWNER TO postgres", b"OWNER TO service_role"),
            valid.replace(b"'m5'::text", b"'M5'::text"),
            valid.replace(
                b"ALTER TABLE ingest.source_family_clock ENABLE ROW LEVEL SECURITY;\n",
                b"",
            ),
            valid
            + b"ALTER TABLE ingest.source_family_clock ADD COLUMN raw_html text;\n",
            valid
            + b"CREATE POLICY exposed ON ingest.source_family_clock USING (true);\n",
            valid.replace(FAMILY_SCHEMA, b""),
        ]
        for index, bad in enumerate(variants):
            with self.subTest(index=index):
                self.assertNotEqual(bad, valid)
                result = helper.run_sanitizer(helper.complete_dump() + bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_missing_or_duplicate_singleton_rows_fail_closed(self) -> None:
        helper = fixtures.BackupSanitizerTests()
        for row in (
            b"t\t2026-09-09 00:00:00+00\n",
            b"t\tt\tpokesup-enumerated-v1\n",
        ):
            for replacement in (b"", row + row):
                with self.subTest(row=row, replacement=replacement):
                    family = family_dump()
                    self.assertEqual(family.count(row), 1)
                    result = helper.run_sanitizer(
                        helper.complete_dump() + family.replace(row, replacement)
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")

    def test_restore_preserves_identity_but_disables_collection(self) -> None:
        helper = fixtures.BackupSanitizerTests()
        result = helper.run_sanitizer(helper.complete_dump() + family_dump())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"t\tf\tpokesup-enumerated-v1", result.stdout)
        self.assertNotIn(b"t\tt\tpokesup-enumerated-v1", result.stdout)
        self.assertIn(b"b" * 64 + b"\tretracted", result.stdout)
        self.assertIn(b"2025-09-30 10:44:54+00", result.stdout)

    def test_raw_extra_fields_and_partial_ledgers_fail_closed(self) -> None:
        helper = fixtures.BackupSanitizerTests()
        family = family_dump()
        for bad in [
            family.replace(b"462\tm2", b"private-payload\tm2"),
            family.replace(b"url_sha256, reason", b"url_sha256, raw_html"),
            family.replace(b"ingest.source_family_tombstones", b"ingest.other_table"),
            family + fixtures.copy_block("ingest.source_family_runs", "result", b"raw"),
            family
            + fixtures.copy_block(
                "ingest.source_family_control",
                "singleton, enabled, policy_version",
                b"t\tf\tpokesup-enumerated-v1",
            ),
        ]:
            with self.subTest(bad=bad[-100:]):
                result = helper.run_sanitizer(helper.complete_dump() + bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
