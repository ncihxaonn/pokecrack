"""Retain minimal family identity, never run payloads or restored enablement."""

import unittest
import runpy

import test_backup_sanitizer as fixtures

SANITIZER_MODULE = runpy.run_path(str(fixtures.SANITIZER))
FAMILY_SCHEMA = SANITIZER_MODULE["SOURCE_FAMILY_SCHEMA_SQL"]
OWNER_SQL = (
    b"\n".join(sorted(SANITIZER_MODULE["SOURCE_FAMILY_OWNER_STATEMENTS"])) + b"\n"
)


def without_owners(document: bytes) -> bytes:
    for statement in SANITIZER_MODULE["SOURCE_FAMILY_OWNER_STATEMENTS"]:
        document = document.replace(statement + b"\n", b"")
    return document


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
    def test_variable_layouts_preserve_exact_counts_and_restore_disabled(self) -> None:
        helper = fixtures.BackupSanitizerTests()
        for product, count in ((b"sv11b", b"20"), (b"sv11w", b"20"), (b"sv2a", b"20"),
                               (b"sv8a", b"10"), (b"sv9", b"30"), (b"sv9a", b"30")):
            with self.subTest(product=product):
                document = family_dump().replace(
                    FAMILY_SCHEMA, SANITIZER_MODULE["SOURCE_FAMILY_VARIABLE_SCHEMA_SQL"]
                ).replace(b"unboxing-m2", b"unboxing-" + product).replace(
                    b"462\tm2\t", b"462\t" + product + b"\t"
                ).replace(b"\t\\N\t30\n", b"\t\\N\t" + count + b"\n")
                for value in (document, without_owners(document)):
                    result = helper.run_sanitizer(helper.complete_dump() + value)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(b"\t\\N\t" + count + b"\n", result.stdout)
                    self.assertIn(b"t\tf\tpokesup-enumerated-v1", result.stdout)
                wrong = document.replace(b"\t\\N\t" + count + b"\n",
                                         b"\t\\N\t" + (b"20" if count != b"20" else b"30") + b"\n")
                result = helper.run_sanitizer(helper.complete_dump() + wrong)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                old_shape = document.replace(SANITIZER_MODULE["SOURCE_FAMILY_VARIABLE_SCHEMA_SQL"], FAMILY_SCHEMA)
                self.assertNotEqual(helper.run_sanitizer(helper.complete_dump() + old_shape).returncode, 0)

    def test_historical_sv8_retains_facts_and_restores_disabled(self) -> None:
        helper = fixtures.BackupSanitizerTests()
        historical = family_dump().replace(b"unboxing-m2", b"unboxing-sv8").replace(
            b"462\tm2", b"120\tsv8"
        ).replace(b"2025-09-30 10:44:54+00", b"2024-10-18 16:10:30+00")
        result = helper.run_sanitizer(helper.complete_dump() + historical)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"120\tsv8\t1\t2024-10-18 16:10:30+00", result.stdout)
        self.assertIn(b"t\tf\tpokesup-enumerated-v1", result.stdout)
        self.assertNotIn(b"t\tt\tpokesup-enumerated-v1", result.stdout)
        for product in (b"sv7", b"sv8a", b"sv8-2", b"SV8"):
            with self.subTest(product=product):
                bad = historical.replace(b"120\tsv8\t", b"120\t" + product + b"\t")
                rejected = helper.run_sanitizer(helper.complete_dump() + bad)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertEqual(rejected.stdout, b"")

    def test_managed_no_owner_dump_is_complete_and_restores_disabled(self) -> None:
        self.assertEqual(len(SANITIZER_MODULE["SOURCE_FAMILY_OWNER_STATEMENTS"]), 7)
        self.assertEqual(OWNER_SQL.count(b" OWNER TO postgres;"), 7)
        helper = fixtures.BackupSanitizerTests()
        document = without_owners(family_dump())
        self.assertNotIn(b" OWNER TO ", document)
        result = helper.run_sanitizer(helper.complete_dump() + document)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"t\tf\tpokesup-enumerated-v1", result.stdout)

    def test_partial_or_wrong_owner_sets_fail_closed(self) -> None:
        helper = fixtures.BackupSanitizerTests()
        ownerless = without_owners(family_dump())
        for extra in (
            b"ALTER TABLE ingest.source_family_control OWNER TO postgres;\n",
            OWNER_SQL.replace(b"OWNER TO postgres", b"OWNER TO service_role"),
        ):
            with self.subTest(extra=extra[:80]):
                result = helper.run_sanitizer(
                    helper.complete_dump() + ownerless + extra
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_other_table_constraints_do_not_impersonate_family_ddl(self) -> None:
        helper = fixtures.BackupSanitizerTests()
        jobs = b"""CREATE TABLE ingest.jobs (
  id uuid NOT NULL,
  payload jsonb,
  CONSTRAINT jobs_source_family_payload_check CHECK (payload IS NOT NULL)
);
"""
        result = helper.run_sanitizer(
            helper.complete_dump() + jobs + without_owners(family_dump())
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(jobs, result.stdout)

    def test_family_detector_uses_relation_position(self) -> None:
        detector = SANITIZER_MODULE["SOURCE_FAMILY_DDL"]
        for statement in (
            b'CREATE TABLE "ingest"."source_family_control" (x text);',
            b"ALTER TABLE ONLY ingest.source_family_control NO FORCE ROW LEVEL SECURITY;",
            b"CREATE INDEX arbitrary ON ingest.source_family_control (singleton);",
            b'CREATE POLICY arbitrary\n ON "ingest"."source_family_control" USING (true);',
            b"DROP TABLE IF EXISTS ingest.source_family_control;",
            b"DROP TABLE ingest.other, ingest.source_family_control;",
        ):
            with self.subTest(statement=statement):
                self.assertIsNotNone(detector.match(statement))
        self.assertIsNone(
            detector.match(
                b"CREATE TABLE ingest.jobs (CONSTRAINT source_family_name CHECK (true));"
            )
        )

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
