"""Static cross-layer contracts for the authorized-opening review boundary."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


SUPABASE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SUPABASE_ROOT.parent
MIGRATION = (
    SUPABASE_ROOT / "migrations/20260911000000_authorized_opening_review.sql"
).read_text()
DATABASE_TYPES = (SUPABASE_ROOT / "types/database.ts").read_text()
WORKER_ISO_PATH = Path("services/worker/pokecrack_worker/authorized_openings/iso_codes.py")
WORKER_COMMIT = "e2f247f3b1da19af6748d8fb5b874ffdcccf6119"


def _worker_iso_source() -> str | None:
    local_path = REPOSITORY_ROOT / WORKER_ISO_PATH
    if local_path.exists():
        return local_path.read_text()
    result = subprocess.run(
        ["git", "show", f"{WORKER_COMMIT}:{WORKER_ISO_PATH.as_posix()}"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


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


def _worker_country_rows(source: str) -> dict[str, str]:
    match = re.search(
        r"_CANONICAL_COUNTRY_ROWS\s*=\s*\"\"\"(.*?)\"\"\"",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError("worker is missing _CANONICAL_COUNTRY_ROWS")
    rows: dict[str, str] = {}
    for line in match.group(1).strip().splitlines():
        code, name = line.split(r"\t", maxsplit=1)
        rows[code] = name
    return rows


class AuthorizedOpeningContractTests(unittest.TestCase):
    def test_database_and_worker_share_exact_iso_country_names(self) -> None:
        worker_source = _worker_iso_source()
        if worker_source is None:
            self.skipTest("authorized-opening worker contract is not present in this checkout")
        database_rows = _migration_country_rows()
        worker_rows = _worker_country_rows(worker_source)
        self.assertEqual(len(database_rows), 249)
        self.assertEqual(len(worker_rows), 249)
        self.assertEqual(database_rows, worker_rows)

    def test_migration_exposes_only_the_approved_rpc_acl(self) -> None:
        lowered = MIGRATION.casefold()
        self.assertEqual(lowered.count("begin;"), 1)
        self.assertEqual(lowered.count("commit;"), 1)
        self.assertIn("create role pokecrack_authorized_opening_reviewer", lowered)
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
            ("public.get_public_dashboard_snapshot_v4()", "public.get_public_dashboard_snapshot_v4()"),
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
        self.assertIn(
            "grant execute on function public.get_public_dashboard_snapshot_v4()\n  to anon, authenticated",
            lowered,
        )
        self.assertNotIn(
            "grant execute on function ingest.submit_authorized_opening_v1(jsonb)\n  to pokecrack_authorized_opening_reviewer",
            lowered,
        )
        self.assertNotIn(
            "grant execute on function public.get_public_dashboard_snapshot_v4()\n  to service_role",
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

    def test_generated_types_track_the_worker_rpc_tuples(self) -> None:
        for type_name in (
            "authorized_opening_submissions:",
            "authorized_opening_review_events:",
            "authorized_opening_observations:",
            "authorized_opening_retractions:",
            "submit_authorized_opening_v1:",
            "list_authorized_opening_reviews_v1:",
            "review_authorized_opening_v1:",
            "retract_authorized_opening_v1:",
            "get_public_dashboard_snapshot_v4:",
        ):
            self.assertIn(type_name, DATABASE_TYPES)
        self.assertIn("country_name: string;", DATABASE_TYPES)
        self.assertIn("requested_reason_code: string;", DATABASE_TYPES)
        self.assertIn("requested_reason_code text", MIGRATION)

    def test_public_projection_keeps_rates_and_private_fields_withheld(self) -> None:
        public_start = MIGRATION.index(
            "create or replace function public.get_public_dashboard_snapshot_v4()"
        )
        public_end = MIGRATION.index(
            "alter function public.get_public_dashboard_snapshot_v4()"
        )
        public_body = MIGRATION[public_start:public_end].casefold()
        for key in (
            "'packsobserved'",
            "'openings'",
            "'independentsources'",
            "'state'",
            "'samplenote'",
        ):
            self.assertIn(key, public_body)
        self.assertNotIn("'source_identity_sha256'", public_body)
        self.assertNotIn("'authorization_reference_sha256'", public_body)
        self.assertNotIn("'evidence_sha256'", public_body)
        self.assertNotIn("'provenance_dedupe_sha256'", public_body)
        self.assertNotIn("'reviewer_reference_sha256'", public_body)
        self.assertNotIn("'qualifying_hit_pack_count'", public_body)
        snapshot_start = public_body.index("\nsnapshot as (")
        snapshot_body = public_body[snapshot_start:]
        self.assertIn("jsonb_build_object(", snapshot_body)
        self.assertIn("'schemaversion', '2.0.0'", snapshot_body)
        self.assertIn("'catalog', catalog.value", snapshot_body)
        self.assertNotIn("base.value", snapshot_body)
        self.assertNotIn("'admin'", public_body)


if __name__ == "__main__":
    unittest.main()
