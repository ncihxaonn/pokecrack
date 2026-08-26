from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_migration_safety import audit_migrations, scan_destructive_statements


class MigrationSafetyTests(unittest.TestCase):
    def _workspace(self, root: Path) -> tuple[Path, Path, Path]:
        migrations = root / "migrations"
        migrations.mkdir()
        applied = root / "applied.txt"
        applied.write_text("", encoding="utf-8")
        allowlist = root / "allowlist.json"
        allowlist.write_text(
            json.dumps({"version": 1, "reviewed_deletes": []}),
            encoding="utf-8",
        )
        return migrations, applied, allowlist

    def _allow_delete(self, allowlist: Path, migration: str, sql: str) -> None:
        statement = scan_destructive_statements(sql)[0]
        allowlist.write_text(
            json.dumps(
                {
                    "version": 1,
                    "reviewed_deletes": [
                        {
                            "migration": migration,
                            "statement_sha256": statement.fingerprint,
                            "reason": "Reviewed bounded cleanup inside an audited function.",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_only_unapplied_migrations_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            migrations, applied, allowlist = self._workspace(Path(temporary))
            name = "20260101000000_existing.sql"
            (migrations / name).write_text(
                "delete from private.old_rows;\n", encoding="utf-8"
            )
            applied.write_text("20260101000000\n", encoding="utf-8")

            result = audit_migrations(migrations, applied, allowlist)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.pending, ())

    def test_pending_delete_requires_an_exact_reasoned_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            migrations, applied, allowlist = self._workspace(Path(temporary))
            name = "20260101000001_cleanup.sql"
            sql = "delete from private.expired_rows where expires_at < now();\n"
            (migrations / name).write_text(sql, encoding="utf-8")

            rejected = audit_migrations(migrations, applied, allowlist)
            self._allow_delete(allowlist, name, sql)
            accepted = audit_migrations(migrations, applied, allowlist)

        self.assertFalse(rejected.ok)
        self.assertIn("requires an audited allowlist", rejected.errors[0])
        self.assertTrue(accepted.ok, accepted.errors)
        self.assertEqual(accepted.reviewed_deletes, 1)

    def test_mutating_a_reviewed_delete_invalidates_the_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            migrations, applied, allowlist = self._workspace(Path(temporary))
            name = "20260101000001_cleanup.sql"
            sql = "delete from private.expired_rows where expires_at < now();\n"
            path = migrations / name
            path.write_text(sql, encoding="utf-8")
            self._allow_delete(allowlist, name, sql)
            path.write_text("delete from private.all_rows;\n", encoding="utf-8")

            result = audit_migrations(migrations, applied, allowlist)

        self.assertFalse(result.ok)
        self.assertTrue(any("no longer matches" in error for error in result.errors))
        self.assertTrue(
            any("requires an audited allowlist" in error for error in result.errors)
        )

    def test_drop_and_truncate_are_never_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            migrations, applied, allowlist = self._workspace(Path(temporary))
            (migrations / "20260101000001_bad.sql").write_text(
                "drop table private.records;\ntruncate table private.other_records;\n",
                encoding="utf-8",
            )

            result = audit_migrations(migrations, applied, allowlist)

        self.assertFalse(result.ok)
        self.assertTrue(any("DROP is forbidden" in error for error in result.errors))
        self.assertTrue(
            any("TRUNCATE is forbidden" in error for error in result.errors)
        )

    def test_comments_do_not_trigger_the_gate(self) -> None:
        source = "-- delete from ignored;\n/* drop table ignored; */\nselect 1;\n"
        self.assertEqual(scan_destructive_statements(source), ())

    def test_comment_markers_inside_quotes_do_not_hide_later_statements(self) -> None:
        source = (
            "select '-- not a comment'; delete from private.expired_rows where id = 1;"
        )

        statements = scan_destructive_statements(source)

        self.assertEqual(len(statements), 1)
        self.assertEqual(statements[0].kind, "delete")

    def test_semicolons_inside_values_do_not_truncate_the_fingerprint(self) -> None:
        first = scan_destructive_statements(
            "delete from private.rows where marker = ';' and id = 1;"
        )[0]
        second = scan_destructive_statements(
            "delete from private.rows where marker = ';' and id = 2;"
        )[0]

        self.assertNotEqual(first.fingerprint, second.fingerprint)
        self.assertTrue(first.normalized.endswith("and id = 1;"))

    def test_remote_history_missing_locally_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            migrations, applied, allowlist = self._workspace(Path(temporary))
            applied.write_text("20260101000009\n", encoding="utf-8")

            result = audit_migrations(migrations, applied, allowlist)

        self.assertFalse(result.ok)
        self.assertTrue(any("missing locally" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
