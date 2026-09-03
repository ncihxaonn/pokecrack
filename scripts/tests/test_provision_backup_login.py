from __future__ import annotations

import unittest

from scripts import provision_backup_login as provision


class BackupLoginProvisioningTests(unittest.TestCase):
    def test_contract_creates_non_inheriting_limited_login(self) -> None:
        sql = provision.build_provision_sql("a" * 64)
        lowered = sql.lower()
        self.assertIn("create role pokecrack_backup_login", lowered)
        self.assertIn("noinherit", lowered)
        self.assertIn("nosuperuser nocreatedb nocreaterole", lowered)
        self.assertIn("nobypassrls", lowered)
        self.assertIn("connection limit 2", lowered)
        self.assertIn(
            "grant service_role to pokecrack_backup_login with inherit false, set true",
            lowered,
        )
        self.assertIn(
            "grant maintain on table ingest.source_request_gates to pokecrack_backup_login",
            lowered,
        )
        self.assertIn(
            "revoke all on table ingest.source_request_gates from pokecrack_backup_login",
            lowered,
        )
        self.assertIn(
            "revoke all on table ingest.source_request_gates from service_role",
            lowered,
        )
        self.assertIn("alter default privileges for role postgres", lowered)

    def test_contract_rejects_short_or_ambiguous_passwords(self) -> None:
        with self.assertRaises(provision.MigrationRunnerError):
            provision.build_provision_sql("short")
        with self.assertRaises(provision.MigrationRunnerError):
            provision.build_provision_sql("a" * 64 + "'")

    def test_contract_does_not_use_owner_or_bypass_rls_authority(self) -> None:
        sql = provision.build_provision_sql("b" * 64).lower()
        self.assertNotIn("superuser", sql.replace("nosuperuser", ""))
        self.assertNotIn("bypassrls", sql.replace("nobypassrls", ""))
        self.assertNotIn("alter role", sql)


if __name__ == "__main__":
    unittest.main()
