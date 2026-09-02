"""Static contracts for the local authorized-opening operator boundary."""

from __future__ import annotations

import unittest
from pathlib import Path


SUPABASE_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    SUPABASE_ROOT / "migrations/20260922000000_authorized_opening_operator.sql"
).read_text(encoding="utf-8")
OPERATOR = (
    SUPABASE_ROOT.parent
    / "services/worker/pokecrack_worker/authorized_opening_operator.py"
).read_text(encoding="utf-8")
CLI = (
    SUPABASE_ROOT.parent / "services/worker/pokecrack_worker/cli.py"
).read_text(encoding="utf-8")
ENV_EXAMPLE = (SUPABASE_ROOT.parent / ".env.example").read_text(encoding="utf-8")
DOCS = (
    SUPABASE_ROOT.parent / "docs/AUTHORIZED_OPENING_OPERATOR.md"
).read_text(encoding="utf-8")


class AuthorizedOpeningOperatorContractTests(unittest.TestCase):
    def test_forward_migration_declares_distinct_submitter_role_and_acl(self) -> None:
        lowered = MIGRATION.casefold()
        compact = " ".join(lowered.split())
        self.assertEqual(lowered.count("begin;"), 1)
        self.assertEqual(lowered.count("commit;"), 1)
        self.assertIn("create role pokecrack_authorized_opening_submitter", lowered)
        self.assertIn("nologin noinherit", lowered)
        self.assertIn("pokecrack_authorized_opening_submitter_login", lowered)
        self.assertIn("login.rolconnlimit = 2", lowered)
        self.assertIn("grant usage on schema ingest to pokecrack_authorized_opening_submitter", compact)
        self.assertIn(
            "grant execute on function ingest.submit_authorized_opening_v1(jsonb)\n  to pokecrack_authorized_opening_submitter",
            lowered,
        )
        self.assertIn("with admin true, inherit false, set false", lowered)
        self.assertIn("role_has_dangerous_memberships", lowered)
        self.assertIn("submitter_has_dangerous_memberships", lowered)
        self.assertIn("not login.rolinherit", lowered)
        self.assertIn("not login.rolbypassrls", lowered)
        self.assertIn("has_sequence_privilege", lowered)
        self.assertIn("aclexplode", lowered)
        self.assertIn("dedicated authorized opening submitter login has direct application privileges", lowered)
        self.assertNotIn("grant insert on table ingest", lowered)
        self.assertNotIn("grant update on table ingest", lowered)
        self.assertNotIn("grant delete on table ingest", lowered)
        self.assertNotIn("create table", lowered)

    def test_operator_uses_only_reviewed_rpc_names_and_fixed_input_boundary(self) -> None:
        lowered = OPERATOR.casefold()
        self.assertIn("max_envelope_bytes = 16_384", lowered)
        self.assertIn("envelope_file_mode = 0o600", lowered)
        self.assertIn("o_nofollow", lowered)
        self.assertIn("o_nonblock", lowered)
        self.assertIn("object_pairs_hook", lowered)
        self.assertIn("parse_constant", lowered)
        self.assertIn("discovery_platform != \"direct\"", lowered)
        self.assertIn("social_derived_rejected", lowered)
        self.assertIn("authorized_opening_submitter_db_url", lowered)
        self.assertIn("authorized_opening_reviewer_db_url", lowered)
        self.assertIn("-c role=", lowered)
        self.assertNotIn("supabase_db_url", lowered)
        self.assertIn("ingest.submit_authorized_opening_v1", lowered)
        self.assertIn("ingest.list_authorized_opening_reviews_v1", lowered)
        self.assertIn("ingest.review_authorized_opening_v1", lowered)
        self.assertIn("ingest.retract_authorized_opening_v1", lowered)
        self.assertNotIn("insert into", lowered)
        self.assertNotIn("update ingest", lowered)
        self.assertNotIn("delete from", lowered)
        self.assertNotIn("evidence text", lowered)

    def test_cli_and_docs_keep_operator_and_reviewer_paths_explicit(self) -> None:
        self.assertIn('app.add_typer(authorized_opening_app, name="authorized-opening")', CLI)
        for command in ("submit", "list-reviews", "review", "retract"):
            self.assertIn(f'@authorized_opening_app.command("{command}")', CLI)
        for variable in (
            "AUTHORIZED_OPENING_SUBMITTER_DB_URL",
            "AUTHORIZED_OPENING_REVIEWER_DB_URL",
        ):
            self.assertIn(variable, ENV_EXAMPLE)
            self.assertIn(variable, DOCS)
        self.assertIn("mode `0600`", DOCS)
        self.assertIn("social discovery", DOCS.casefold())
        self.assertIn("never falls back to `SUPABASE_DB_URL`", DOCS)
        self.assertIn("auto-approval path", DOCS.casefold())


if __name__ == "__main__":
    unittest.main()
