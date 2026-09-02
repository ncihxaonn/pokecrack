"""Static cross-layer contracts for the authorized-opening review boundary."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


SUPABASE_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    SUPABASE_ROOT / "migrations/20260918000000_authorized_opening_review.sql"
).read_text()
DATABASE_TYPES = (SUPABASE_ROOT / "types/database.ts").read_text()


def _migration_country_rows() -> dict[str, str]:
    match = re.search(
        r"from\s*\(\s*values\s*(.*?)\n\)\s*as canonical\(code, country_name\)",
        MIGRATION,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise AssertionError("migration is missing the canonical country-name values")
    rows = re.findall(r"\('([A-Z]{2})', '((?:[^']|'')*)'\)", match.group(1))
    return {code: name.replace("''", "'") for code, name in rows}


class AuthorizedOpeningContractTests(unittest.TestCase):
    def test_migration_has_the_trusted_iso_country_catalogue(self) -> None:
        database_rows = _migration_country_rows()
        self.assertEqual(len(database_rows), 249)
        self.assertEqual(database_rows["AU"], "Australia")
        self.assertEqual(database_rows["JP"], "Japan")
        self.assertEqual(database_rows["US"], "United States")

    def test_migration_exposes_only_the_approved_rpc_acl(self) -> None:
        lowered = MIGRATION.casefold()
        compact = " ".join(lowered.split())
        self.assertEqual(lowered.count("begin;"), 1)
        self.assertEqual(lowered.count("commit;"), 1)
        self.assertIn("create role pokecrack_authorized_opening_reviewer", lowered)
        self.assertIn(
            "grant pokecrack_authorized_opening_reviewer\n        to postgres\n"
            "        with admin true, inherit false, set false",
            lowered,
        )
        self.assertIn("<<submit_contract>>", lowered)
        self.assertIn("nologin noinherit", lowered)
        self.assertIn("role_is_exact", lowered)
        self.assertIn("role_has_dangerous_memberships", lowered)
        self.assertIn("role_membership_count", lowered)
        self.assertIn("role_creator_membership_count", lowered)
        self.assertIn("role_dedicated_login_count", lowered)
        self.assertIn("role_has_invalid_membership", lowered)
        self.assertIn("reviewer_login_oid", lowered)
        self.assertIn("memberships.member = reviewer_oid", lowered)
        self.assertIn("memberships.roleid = reviewer_oid", lowered)
        self.assertIn("memberships.inherit_option", lowered)
        self.assertIn("login.rolcanlogin", lowered)
        self.assertIn("connection limit -1", lowered)
        self.assertIn(
            "existing authorized opening reviewer role is not the reviewed isolated contract",
            lowered,
        )
        self.assertIn("alter table catalog.iso_alpha2_codes", lowered)
        self.assertIn("trusted iso alpha-2 code/name catalogue must contain exactly 249 rows", lowered)
        self.assertIn("tcgdexsetid must identify a current live non-demo tcgdex set", lowered)
        self.assertIn("for update", lowered)
        self.assertIn("expires_at", lowered)
        self.assertIn("create unique index authorized_opening_submissions_provenance_uidx", lowered)
        self.assertIn("create unique index authorized_opening_observations_source_fact_uidx", lowered)
        self.assertIn("authorized_opening_review_events_immutable", lowered)
        self.assertIn("authorized_opening_observations_immutable", lowered)
        self.assertIn("authorized_opening_retractions_immutable", lowered)
        self.assertIn("discovery_platform is not null", lowered)
        self.assertIn("reviewer_reference_sha256 is not null", lowered)
        for table_name in (
            "authorized_opening_submissions",
            "authorized_opening_review_events",
            "authorized_opening_observations",
            "authorized_opening_retractions",
        ):
            self.assertIn(
                f"alter table ingest.{table_name} enable row level security",
                compact,
            )
            self.assertIn(
                f"alter table ingest.{table_name} force row level security",
                compact,
            )
            self.assertIn(
                f"revoke all on table ingest.{table_name}",
                compact,
            )
            self.assertIn(
                f"grant select on table ingest.{table_name} to service_role",
                compact,
            )
        self.assertIn(
            "grant usage on schema ingest to pokecrack_authorized_opening_reviewer",
            compact,
        )
        self.assertNotIn("create table public.authorized_opening", lowered)
        self.assertNotIn("grant insert on table ingest.authorized_opening", lowered)
        self.assertNotIn("grant update on table ingest.authorized_opening", lowered)
        self.assertNotIn("grant delete on table ingest.authorized_opening", lowered)

        expected_functions = (
            (
                "ingest.submit_authorized_opening_v1(",
                "ingest.submit_authorized_opening_v1(jsonb)",
            ),
            (
                "ingest.list_authorized_opening_reviews_v1(",
                "ingest.list_authorized_opening_reviews_v1(text, integer)",
            ),
            (
                "ingest.review_authorized_opening_v1(",
                "ingest.review_authorized_opening_v1(uuid, bigint, text, text, text)",
            ),
            (
                "ingest.retract_authorized_opening_v1(",
                "ingest.retract_authorized_opening_v1(uuid, text, text)",
            ),
        )
        for creation_name, function_name in expected_functions:
            function_start = lowered.find(f"create or replace function {creation_name}")
            self.assertGreaterEqual(function_start, 0, creation_name)
            function_end = lowered.find("alter function", function_start)
            self.assertGreater(function_end, function_start, creation_name)
            body = lowered[function_start:function_end]
            self.assertIn("security definer", body, creation_name)
            self.assertIn("set search_path = pg_catalog", body, creation_name)
            self.assertIn(f"alter function {function_name}", lowered[function_end:], function_name)

        self.assertIn(
            "grant execute on function ingest.submit_authorized_opening_v1(jsonb)\n  to service_role",
            lowered,
        )
        for _, function_name in expected_functions[1:4]:
            self.assertIn(f"grant execute on function {function_name}\n  to pokecrack_authorized_opening_reviewer", lowered)
        self.assertNotIn(
            "grant execute on function ingest.submit_authorized_opening_v1(jsonb)\n  to pokecrack_authorized_opening_reviewer",
            lowered,
        )
        self.assertIn("has_schema_privilege(", lowered)
        self.assertIn("'ingest', 'usage'", lowered)
        self.assertIn("'ingest', 'create'", lowered)
        self.assertIn("has_table_privilege(", lowered)
        self.assertIn("has_any_column_privilege(", lowered)
        self.assertIn("has_sequence_privilege(", lowered)
        self.assertIn("aclexplode(", lowered)
        self.assertIn("is_grantable", lowered)
        self.assertIn("expected_review_functions", lowered)
        self.assertIn("reviewer_creator_membership_count", lowered)
        self.assertIn("memberships.member = 'postgres'::regrole", lowered)
        self.assertIn("not memberships.inherit_option", lowered)
        self.assertIn("not memberships.set_option", lowered)
        self.assertIn("dedicated reviewer login has direct application privileges", lowered)
        self.assertIn("owns an application object", lowered)

    def test_generated_types_track_the_reviewer_rpc_tuples(self) -> None:
        for type_name in (
            "authorized_opening_submissions:",
            "authorized_opening_review_events:",
            "authorized_opening_observations:",
            "authorized_opening_retractions:",
            "submit_authorized_opening_v1:",
            "list_authorized_opening_reviews_v1:",
            "review_authorized_opening_v1:",
            "retract_authorized_opening_v1:",
        ):
            self.assertIn(type_name, DATABASE_TYPES)
        self.assertIn("country_name: string;", DATABASE_TYPES)
        self.assertIn("requested_reason_code: string;", DATABASE_TYPES)
        self.assertIn("requested_reason_code text", MIGRATION)

if __name__ == "__main__":
    unittest.main()
