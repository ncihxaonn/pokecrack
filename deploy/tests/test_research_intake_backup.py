"""Private reference backups are bounded and always restore with intake off."""

import runpy
import unittest

import test_backup_sanitizer as fixtures

MODULE = runpy.run_path(str(fixtures.SANITIZER))
SCHEMA = MODULE["RESEARCH_INTAKE_SCHEMA_SQL"]
COLUMNS = "url, report_group_sha256, conflicting, first_seen_at, last_seen_at, snapshot_sha256"
ROW = (b"https://example.com/opening\t" + b"a" * 64
       + b"\tt\t2026-09-09 00:00:00+00\t2026-09-09 01:00:00+00\t" + b"b" * 64)


def intake_dump(row=ROW):
    return (SCHEMA
            + fixtures.copy_block("ingest.research_intake_control", "singleton, enabled", b"t\tt")
            + fixtures.copy_block("ingest.research_intake_references", COLUMNS, *([row] if row else [])))


class ResearchIntakeBackupTests(unittest.TestCase):
    def run_dump(self, document):
        helper = fixtures.BackupSanitizerTests()
        return helper.run_sanitizer(helper.complete_dump() + document)

    def rejected(self, document):
        result = self.run_dump(document)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_restores_disabled_preserving_reference_and_conflict(self):
        for ownerless in (False, True):
            document = intake_dump()
            if ownerless:
                for owner in MODULE["RESEARCH_INTAKE_OWNER_STATEMENTS"]:
                    document = document.replace(owner + b"\n", b"")
            result = self.run_dump(document)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(ROW, result.stdout)
            self.assertIn(b"(singleton, enabled) FROM stdin;\nt\tf\n", result.stdout)
            self.assertNotIn(b"(singleton, enabled) FROM stdin;\nt\tt\n", result.stdout)

    def test_empty_queue_and_unicode_paths_are_valid(self):
        for row in (b"", ROW.replace(b"/opening", "/開封".encode())):
            result = self.run_dump(intake_dump(row))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_schema_and_copy_drift_fail_before_output(self):
        valid = intake_dump()
        variants = (
            valid.replace(SCHEMA, b""),
            SCHEMA,
            valid.replace(b"DEFAULT false", b"DEFAULT true"),
            valid.replace(b"url text NOT NULL,", b"url text NOT NULL, raw_html text,"),
            valid.replace(b"PRIMARY KEY (url)", b"UNIQUE (url)"),
            valid.replace(b"FORCE ROW LEVEL SECURITY", b"NO FORCE ROW LEVEL SECURITY"),
            valid.replace(b"OWNER TO postgres", b"OWNER TO service_role"),
            valid.replace(b"report_group_sha256, conflicting", b"raw_html, conflicting"),
            valid + b"CREATE POLICY exposed ON ingest.research_intake_references USING (true);\n",
            valid + b"ALTER TABLE ingest.research_intake_control ADD COLUMN raw_html text;\n",
            valid + fixtures.copy_block("ingest.research_intake_control", "singleton, enabled", b"t\tf"),
            valid.replace(b"t\tt\n", b""),
            valid.replace(b"t\tt\n", b"t\tt\nt\tf\n"),
            valid.replace(next(iter(MODULE["RESEARCH_INTAKE_OWNER_STATEMENTS"])) + b"\n", b""),
        )
        for index, document in enumerate(variants):
            with self.subTest(index=index):
                self.assertNotEqual(document, valid)
                self.rejected(document)

    def test_invalid_reference_fields_fail_closed(self):
        for row in (
            ROW.replace(b"https://", b"http://"),
            ROW.replace(b"example.com", b"127.0.0.1"),
            ROW.replace(b"example.com", b"example.internal"),
            ROW.replace(b"example.com", b"user:password@example.com"),
            ROW.replace(b"/opening", b"/opening?token=secret"),
            ROW.replace(b"/opening", b"/opening/"),
            ROW.replace(b"/opening", b"/opening\\nprivate"),
            ROW.replace(b"a" * 64, b"not-a-hash"),
            ROW.replace(b"\tt\t", b"\ttrue\t"),
            ROW.replace(b"2026-09-09 01:00:00+00", b"2026-09-08 01:00:00+00"),
            ROW.replace(b"+00", b"+10"),
            ROW + b"\n" + ROW,
        ):
            with self.subTest(row=row[:80]):
                self.rejected(intake_dump(row))

    def test_capacity_bound_and_non_copy_writes(self):
        rows = [ROW.replace(b"/opening", f"/opening-{i}".encode()) for i in range(10001)]
        self.rejected(intake_dump(b"\n".join(rows)))
        self.rejected(intake_dump() + b"INSERT INTO ingest.research_intake_control VALUES (true,true);\n")
        self.rejected(intake_dump() + b"ALTER\nTABLE ingest.research_intake_control DISABLE ROW LEVEL SECURITY;\n")


if __name__ == "__main__":
    unittest.main()
