from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import run_supabase_migrations as runner


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.payload


class _API:
    def __init__(self, columns: list[str]) -> None:
        self.columns = columns

    def query(self, sql: str) -> object:
        if sql == runner.LEDGER_COLUMNS_SQL:
            return [{"column_name": column} for column in self.columns]
        raise AssertionError(sql)


class _Opener:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.requests: list[object] = []

    def open(self, request: object, *, timeout: float) -> _Response:
        self.requests.append((request, timeout))
        return _Response(self.payload)


class SupabaseMigrationRunnerTests(unittest.TestCase):
    def test_management_api_request_keeps_token_out_of_query_payload(self) -> None:
        token = "sbp_fixture_owner_token_123456"
        project_ref = "a" * 20
        opener = _Opener([{"ok": True}])
        with patch.object(
            runner.urllib.request,
            "build_opener",
            return_value=opener,
        ) as build_opener:
            api = runner.SupabaseManagementAPI(token=token, project_ref=project_ref)
            response = api.query("select 1")

        request, timeout = opener.requests[0]
        self.assertEqual(response, [{"ok": True}])
        self.assertEqual(timeout, 60.0)
        self.assertNotIn(token.encode("utf-8"), request.data or b"")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {token}")
        self.assertNotIn(token, repr(response))
        redirect_handler = build_opener.call_args.args[0]
        self.assertIsInstance(redirect_handler, runner._RejectRedirects)
        self.assertIsNone(
            redirect_handler.redirect_request(
                request,
                object(),
                302,
                "Found",
                {"Location": "https://evil.example.invalid/steal"},
                "https://evil.example.invalid/steal",
            )
        )

    def test_ledger_shape_is_the_supabase_version_statements_name_contract(self) -> None:
        runner._check_ledger_shape(_API(["version", "statements", "name"]))
        with self.assertRaises(runner.MigrationRunnerError):
            runner._check_ledger_shape(_API(["version", "name", "statements"]))

    def test_apply_sql_retains_source_in_the_ledger_without_a_database_url(self) -> None:
        source = "begin;\nselect 'fixture';\ncommit;\n"
        body = runner._transaction_body(source, filename="20260909000000_fixture.sql")
        statement = runner._apply_sql(
            source=source,
            body=body,
            version="20260909000000",
            name="fixture",
        )
        self.assertIn("begin;", statement)
        self.assertIn("insert into supabase_migrations.schema_migrations", statement)
        self.assertIn("20260909000000", statement)
        self.assertNotIn("SUPABASE_DB_URL", statement)
        self.assertNotIn("fixture-secret", statement)

    def test_migration_file_validation_rejects_symlink_and_bad_transaction_shape(self) -> None:
        with self.assertRaises(runner.MigrationRunnerError):
            runner._transaction_body(
                "begin;\nselect 1;\ncommit;\nrollback;\n",
                filename="fixture.sql",
            )
        with self.assertRaises(runner.MigrationRunnerError):
            runner._transaction_body("select 1;\n", filename="fixture.sql")

    def test_transaction_lexer_rejects_every_top_level_transaction_control_alias(self) -> None:
        controls = (
            "begin transaction;",
            "start transaction;",
            "end;",
            "abort;",
            "commit and chain;",
            "rollback to savepoint fixture;",
            "savepoint fixture;",
            "release savepoint fixture;",
            "prepare transaction 'fixture';",
            "set transaction isolation level serializable;",
            "commit;\nbegin;",
        )
        for control in controls:
            with self.subTest(control=control), self.assertRaises(runner.MigrationRunnerError):
                runner._transaction_body(
                    f"begin;\n{control}\ncommit;\n",
                    filename="fixture.sql",
                )

    def test_transaction_lexer_ignores_plpgsql_begin_inside_dollar_quotes(self) -> None:
        source = """begin;
create function fixture() returns void
language plpgsql
as $$
begin;
  perform 1;
end;
$$;
commit;
"""
        body = runner._transaction_body(source, filename="fixture.sql")
        self.assertIn("begin;", body)
        self.assertIn("perform 1;", body)

        for migration_name in (
            "20260906000000_nostr_multi_relay_discovery.sql",
            "20260909000000_nostr_cleanup_capacity.sql",
            "20260910000000_nostr_worker_role_isolation.sql",
            "20260921000000_bluesky_worker_role_isolation.sql",
            "20260926000000_bluesky_generic_queue_guard.sql",
        ):
            with self.subTest(migration=migration_name):
                source = Path("supabase/migrations", migration_name).read_text()
                self.assertTrue(
                    runner._transaction_body(source, filename=migration_name)
                )

    def test_transaction_lexer_does_not_hide_commit_after_ordinary_backslash_string(self) -> None:
        source = """begin;
select 'x\\';
commit;
select E'a\\'b';
commit;
"""
        with self.assertRaises(runner.MigrationRunnerError):
            runner._transaction_body(source, filename="fixture.sql")

    def test_transaction_lexer_rejects_changes_to_string_lexing_mode(self) -> None:
        for statement in (
            "set standard_conforming_strings = off;",
            "set local standard_conforming_strings = on;",
            "reset standard_conforming_strings;",
        ):
            with self.subTest(statement=statement), self.assertRaises(
                runner.MigrationRunnerError
            ):
                runner._transaction_body(
                    f"begin;\n{statement}\nselect 1;\ncommit;\n",
                    filename="fixture.sql",
                )


if __name__ == "__main__":
    unittest.main()
