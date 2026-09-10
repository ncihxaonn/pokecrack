"""Numbered opening facts survive backup; runtime state does not."""

import hashlib
import runpy
import unittest

import test_backup_sanitizer as fixtures

MODULE = runpy.run_path(str(fixtures.SANITIZER))
SCHEMA = MODULE["NUMBERED_FAMILY_SCHEMA_SQL"]
URL = b"https://www.kozaru02.com/entry/synthetic-report"
DATE = b"2026-09-10 00:00:00+00"
RESOURCES = b"{" + b",".join(hashlib.sha256(str(n).encode()).hexdigest().encode() for n in range(10)) + b"}"
CONTROL = b"t\tt\tkozaru-numbered-v1\t" + DATE + b"\t" + DATE + b"\t00000000-0000-4000-8000-000000000001\t1\t" + DATE


def numbered_dump():
    rows = {
        "numbered_family_candidates": URL + b"\tadmitted\t" + DATE + b"\t" + DATE,
        "numbered_family_admissions": URL + b"\tkozaru-numbered-v1\t" + DATE + b"\t" + DATE + b"\t10\t" + b"a" * 64 + b"\t" + RESOURCES,
        "numbered_family_control": CONTROL,
        "numbered_family_identity_keys": b"b" * 64 + b"\t" + b"c" * 64,
    }
    return SCHEMA + b"".join(fixtures.copy_block(
        ".".join(table), ", ".join(columns), rows[table[1]],
    ) for table, columns in MODULE["NUMBERED_FAMILY_COLUMNS"].items())


class NumberedFamilyBackupTests(unittest.TestCase):
    def run_dump(self, document):
        helper = fixtures.BackupSanitizerTests()
        return helper.run_sanitizer(helper.complete_dump() + document)

    def test_facts_and_identity_retained_but_restore_is_inert(self):
        ownerless = numbered_dump()
        for statement in MODULE["NUMBERED_FAMILY_STATEMENTS"] - MODULE["NUMBERED_FAMILY_OWNERLESS"]:
            ownerless = ownerless.replace(statement + b"\n", b"")
        for document in [numbered_dump(), ownerless]:
            result = self.run_dump(document)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(URL, result.stdout)
            self.assertIn(RESOURCES, result.stdout)
            self.assertIn(b"b" * 64 + b"\t" + b"c" * 64, result.stdout)
            self.assertNotIn(CONTROL, result.stdout)
            self.assertIn(b"t\tf\tkozaru-numbered-v1\t\\N\t-infinity\t\\N\t\\N\t\\N", result.stdout)

    def test_invalid_facts_and_schema_never_emit_partial_backup(self):
        original = numbered_dump()
        for invalid in [
            original.replace(b"\t10\t", b"\t11\t"),
            original.replace(URL, b"https://foreign.example/entry/a"),
            original.replace(RESOURCES, b"{raw body}"),
            original.replace(RESOURCES, b"{" + b",".join([b"a" * 64] * 10) + b"}"),
            original.replace(b"FORCE ROW LEVEL SECURITY", b"NO FORCE ROW LEVEL SECURITY", 1),
            original + fixtures.copy_block("ingest.numbered_family_runs", "result", b"private body"),
            original + fixtures.copy_block("ingest.numbered_family_control", ", ".join(MODULE["NUMBERED_FAMILY_COLUMNS"][("ingest", "numbered_family_control")]), CONTROL),
            original.replace(SCHEMA, b""),
            SCHEMA,
        ]:
            with self.subTest(invalid=hashlib.sha256(invalid).hexdigest()):
                result = self.run_dump(invalid)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_retractions_retained(self):
        result = self.run_dump(numbered_dump().replace(b"\tadmitted\t", b"\tretracted\t"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"\tretracted\t", result.stdout)


if __name__ == "__main__":
    unittest.main()
