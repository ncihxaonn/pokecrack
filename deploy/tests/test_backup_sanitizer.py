from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SANITIZER = REPOSITORY_ROOT / "deploy" / "lib" / "sanitize_plain_backup.py"

YOUTUBE_POLICY = "11111111-1111-4111-8111-111111111111"
OTHER_POLICY = "22222222-2222-4222-8222-222222222222"
TCGDEX_POLICY = "44444444-4444-4444-8444-444444444444"
WRONG_POLICY = "33333333-3333-4333-8333-333333333333"
YOUTUBE_ITEM = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_ITEM = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
FIRST_VIDEO = "AbCdEfGhI_1"
SECOND_VIDEO = "ZyXwVuTsR-2"
GATE_CREATE_COMMON = b"""CREATE TABLE ingest.source_request_gates (
    source_key text NOT NULL,
    owner_job_id uuid,
    owner_lease_generation bigint,
    acquired_at timestamp with time zone,
    active_until timestamp with time zone,
    CONSTRAINT source_request_gates_owner_check CHECK ((((owner_job_id IS NULL) AND (owner_lease_generation IS NULL) AND (acquired_at IS NULL) AND (active_until IS NULL)) OR ((owner_job_id IS NOT NULL) AND (owner_lease_generation >= 1) AND (acquired_at IS NOT NULL) AND (active_until > acquired_at)))),
    {source_constraint}
);
"""
GATE_POST_DATA = b"""ALTER TABLE ONLY ingest.source_request_gates FORCE ROW LEVEL SECURITY;
ALTER TABLE ONLY ingest.source_request_gates
    ADD CONSTRAINT source_request_gates_pkey PRIMARY KEY (source_key);
ALTER TABLE ingest.source_request_gates ENABLE ROW LEVEL SECURITY;
"""
GATE_ENABLE_RLS = b"ALTER TABLE ingest.source_request_gates ENABLE ROW LEVEL SECURITY;\n"
PRE_YOUTUBE_GATE_DDL = GATE_CREATE_COMMON.replace(
    b"{source_constraint}",
    b"CONSTRAINT source_request_gates_source_check CHECK ((source_key = 'tcgdex_catalog'::text))",
) + GATE_POST_DATA
GATE_DDL = GATE_CREATE_COMMON.replace(
    b"{source_constraint}",
    b"CONSTRAINT source_request_gates_source_check CHECK ((source_key ~ '^[a-z0-9][a-z0-9_-]{0,62}$'::text))",
) + GATE_POST_DATA
QUOTED_GATE_DDL = GATE_DDL.replace(
    b"ingest.source_request_gates", b'"ingest"."source_request_gates"'
).replace(b"\n", b"\r\n")
POST_YOUTUBE_GATE_SEED = (
    b"\n-- Canonical idle request gates; live lease ownership is not retained.\n"
    b"COPY ingest.source_request_gates (source_key) FROM stdin;\n"
    b"tcgdex_catalog\n"
    b"youtube_discovery\n"
    b"\\.\n\n"
)


def copy_block(table: str, columns: str, *rows: bytes, crlf: bool = False) -> bytes:
    newline = b"\r\n" if crlf else b"\n"
    header = f"COPY {table} ({columns}) FROM stdin;".encode()
    return newline.join((header, *rows, b"\\.")) + newline


class BackupSanitizerTests(unittest.TestCase):
    def run_sanitizer(
        self,
        dump: bytes,
        *,
        source_policies: str = "present",
        youtube_discoveries: str = "present",
        policy_id: str | None = YOUTUBE_POLICY,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        command = [
            "python3",
            str(SANITIZER),
            "--source-policies",
            source_policies,
            "--youtube-discoveries",
            youtube_discoveries,
        ]
        if policy_id is not None:
            command.extend(("--youtube-policy-id", policy_id))
        return subprocess.run(
            command,
            input=dump,
            check=False,
            capture_output=True,
            env=environment,
        )

    def complete_dump(
        self,
        *,
        quoted: bool = False,
        cache_first: bool = False,
    ) -> bytes:
        if quoted:
            gate_ddl = QUOTED_GATE_DDL
            cache_ddl = (
                b'CREATE UNLOGGED TABLE "ingest"."youtube_discoveries" (\r\n'
                b');\r\n'
            )
            policies = copy_block(
                '"ingest"."source_policies"',
                '"source_key", "id", "note"',
                f"youtube_discovery\t{YOUTUBE_POLICY}\tpolicy".encode(),
                f"tcgdex_catalog\t{TCGDEX_POLICY}\ttcgdex".encode(),
                f"other\t{OTHER_POLICY}\tother".encode(),
                crlf=True,
            )
            items = copy_block(
                '"ingest"."source_items"',
                '"note", "id", "source_policy_id"',
                f"youtube-source\\titem\t{YOUTUBE_ITEM}\t{YOUTUBE_POLICY}".encode(),
                f"other-source\\nitem\t{OTHER_ITEM}\t{OTHER_POLICY}".encode(),
                crlf=True,
            )
            legacy = copy_block(
                '"ingest"."source_discoveries"',
                '"note", "source_item_id"',
                f"legacy-youtube\t{YOUTUBE_ITEM}".encode(),
                crlf=True,
            )
            cache = copy_block(
                '"ingest"."youtube_discoveries"',
                '"title", "source_policy_id", "video_id"',
                f"cache\\tfirst\t{YOUTUBE_POLICY}\t{FIRST_VIDEO}".encode(),
                f"cache\\nsecond\t{YOUTUBE_POLICY}\t{SECOND_VIDEO}".encode(),
                crlf=True,
            )
        else:
            gate_ddl = GATE_DDL
            cache_ddl = (
                b"CREATE UNLOGGED TABLE ingest.youtube_discoveries (\n"
                b");\n"
            )
            policies = copy_block(
                "ingest.source_policies",
                "id, source_key, note",
                f"{YOUTUBE_POLICY}\tyoutube_discovery\tpolicy".encode(),
                f"{TCGDEX_POLICY}\ttcgdex_catalog\ttcgdex".encode(),
                f"{OTHER_POLICY}\tother\tother".encode(),
            )
            items = copy_block(
                "ingest.source_items",
                "note, source_policy_id, id",
                f"youtube-source\\titem\t{YOUTUBE_POLICY}\t{YOUTUBE_ITEM}".encode(),
                f"other-source\\nitem\t{OTHER_POLICY}\t{OTHER_ITEM}".encode(),
            )
            legacy = copy_block(
                "ingest.source_discoveries",
                "source_item_id, note",
                f"{YOUTUBE_ITEM}\tlegacy-youtube".encode(),
            )
            cache = copy_block(
                "ingest.youtube_discoveries",
                "video_id, source_policy_id, title",
                f"{FIRST_VIDEO}\t{YOUTUBE_POLICY}\tcache\\tfirst".encode(),
                f"{SECOND_VIDEO}\t{YOUTUBE_POLICY}\tcache\\nsecond".encode(),
            )
        unrelated = copy_block(
            "public.unrelated",
            "id, note",
            b"1\tescaped\\ttab\\nnewline",
            crlf=quoted,
        )
        sections = (
            (gate_ddl, cache_ddl, cache, legacy, unrelated, policies, items)
            if cache_first
            else (unrelated, gate_ddl, cache_ddl, policies, items, legacy, cache)
        )
        newline = b"\r\n" if quoted else b"\n"
        return newline.join((b"-- fixture start", b"".join(sections), b"-- fixture end", b""))

    def assert_only_cache_rows_removed(
        self, result: subprocess.CompletedProcess[bytes]
    ) -> None:
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stderr, b"")
        self.assertNotIn(FIRST_VIDEO.encode(), result.stdout)
        self.assertNotIn(SECOND_VIDEO.encode(), result.stdout)
        self.assertIn(YOUTUBE_ITEM.encode(), result.stdout)
        self.assertIn(OTHER_ITEM.encode(), result.stdout)
        self.assertIn(b"legacy-youtube", result.stdout)
        self.assertIn(YOUTUBE_POLICY.encode(), result.stdout)
        self.assertIn(b"1\tescaped\\ttab\\nnewline", result.stdout)
        self.assertIn(
            b"COPY ingest.youtube_discoveries (video_id, source_policy_id, title) FROM stdin;\n\\.\n",
            result.stdout,
        )
        self.assertIn(POST_YOUTUBE_GATE_SEED, result.stdout)
        self.assertLess(
            result.stdout.index(POST_YOUTUBE_GATE_SEED),
            result.stdout.index(GATE_ENABLE_RLS),
        )

    def test_removes_all_cache_rows_only_in_any_table_order(self) -> None:
        for cache_first in (False, True):
            with self.subTest(cache_first=cache_first):
                result = self.run_sanitizer(
                    self.complete_dump(cache_first=cache_first)
                )
                self.assert_only_cache_rows_removed(result)

    def test_supports_quoted_identifiers_crlf_and_copy_escapes(self) -> None:
        result = self.run_sanitizer(
            self.complete_dump(quoted=True, cache_first=True)
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertNotIn(FIRST_VIDEO.encode(), result.stdout)
        self.assertNotIn(SECOND_VIDEO.encode(), result.stdout)
        self.assertIn(YOUTUBE_ITEM.encode(), result.stdout)
        self.assertIn(b"legacy-youtube", result.stdout)
        self.assertIn(
            b'COPY "ingest"."youtube_discoveries" ("title", "source_policy_id", "video_id") FROM stdin;\r\n\\.\r\n',
            result.stdout,
        )

    def test_old_source_tables_are_byte_preserving_without_cache(self) -> None:
        dump = (
            b"-- schema without dedicated cache\n"
            + PRE_YOUTUBE_GATE_DDL
            + copy_block(
                "ingest.source_policies",
                "source_key, id",
                f"tcgdex_catalog\t{TCGDEX_POLICY}".encode(),
                f"other\t{OTHER_POLICY}".encode(),
            )
            + copy_block(
                "ingest.source_items",
                "id, source_policy_id, note",
                f"{YOUTUBE_ITEM}\t{OTHER_POLICY}\tyoutube-source-item".encode(),
            )
            + copy_block(
                "ingest.source_discoveries",
                "source_item_id, note",
                f"{YOUTUBE_ITEM}\tlegacy-youtube".encode(),
            )
        )
        result = self.run_sanitizer(
            dump, youtube_discoveries="absent", policy_id=None
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(
            result.stdout,
            dump.replace(
                GATE_ENABLE_RLS,
                POST_YOUTUBE_GATE_SEED.replace(b"youtube_discovery\n", b"")
                + GATE_ENABLE_RLS,
            ),
        )

    def test_policy_snapshot_missing_different_or_duplicate_fails_before_output(
        self,
    ) -> None:
        base = self.complete_dump()
        policy_row = f"{YOUTUBE_POLICY}\tyoutube_discovery\tpolicy\n".encode()
        tcgdex_row = f"{TCGDEX_POLICY}\ttcgdex_catalog\ttcgdex\n".encode()
        cases = {
            "missing": base.replace(policy_row, b""),
            "different": base.replace(
                policy_row,
                f"{WRONG_POLICY}\tyoutube_discovery\tpolicy\n".encode(),
            ),
            "duplicate": base.replace(policy_row, policy_row + policy_row),
            "missing-tcgdex": base.replace(tcgdex_row, b""),
            "duplicate-tcgdex": base.replace(tcgdex_row, tcgdex_row + tcgdex_row),
        }
        for name, dump in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(dump)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_cache_create_must_be_one_unlogged_header_in_same_dump(self) -> None:
        base = self.complete_dump()
        unlogged = b"CREATE UNLOGGED TABLE ingest.youtube_discoveries (\n"
        cases = {
            "logged-race": base.replace(
                unlogged,
                b"CREATE TABLE ingest.youtube_discoveries (\n",
            ),
            "temporary-race": base.replace(
                unlogged,
                b"CREATE TEMP TABLE ingest.youtube_discoveries (\n",
            ),
            "missing": base.replace(unlogged + b");\n", b""),
            "duplicate": base.replace(unlogged, unlogged + unlogged),
            "unsupported-multiline": base.replace(
                unlogged,
                b"CREATE UNLOGGED TABLE\n ingest.youtube_discoveries (\n",
            ),
        }
        for name, dump in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(dump)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_request_gate_schema_is_retained_but_all_live_state_is_rejected(self) -> None:
        base = self.complete_dump()
        cases = {
            "missing": base.replace(GATE_DDL, b""),
            "duplicate": base.replace(GATE_DDL, GATE_DDL + GATE_DDL),
            "unlogged": base.replace(
                b"CREATE TABLE ingest.source_request_gates",
                b"CREATE UNLOGGED TABLE ingest.source_request_gates",
            ),
            "temporary": base.replace(
                b"CREATE TABLE ingest.source_request_gates",
                b"CREATE TEMP TABLE ingest.source_request_gates",
            ),
            "nullable-source-key": base.replace(
                b"source_key text NOT NULL", b"source_key text"
            ),
            "missing-owner-column": base.replace(b"    owner_job_id uuid,\n", b""),
            "missing-owner-check": base.replace(
                b"    CONSTRAINT source_request_gates_owner_check CHECK ((((owner_job_id IS NULL) AND (owner_lease_generation IS NULL) AND (acquired_at IS NULL) AND (active_until IS NULL)) OR ((owner_job_id IS NOT NULL) AND (owner_lease_generation >= 1) AND (acquired_at IS NOT NULL) AND (active_until > acquired_at)))),\n",
                b"",
            ),
            "wrong-source-check": base.replace(
                b"[a-z0-9][a-z0-9_-]{0,62}", b"[a-z][a-z0-9_-]{0,62}"
            ),
            "missing-force-rls": base.replace(
                b"ALTER TABLE ONLY ingest.source_request_gates FORCE ROW LEVEL SECURITY;\n",
                b"",
            ),
            "missing-primary-key": base.replace(
                b"ALTER TABLE ONLY ingest.source_request_gates\n"
                b"    ADD CONSTRAINT source_request_gates_pkey PRIMARY KEY (source_key);\n",
                b"",
            ),
            "missing-enable-rls": base.replace(GATE_ENABLE_RLS, b""),
            "copy": base
            + copy_block(
                "ingest.source_request_gates",
                "source_key, owner_job_id",
                b"tcgdex_catalog\taaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            ),
            "quoted-copy": base
            + copy_block(
                '"ingest"."source_request_gates"',
                '"source_key"',
                b"tcgdex_catalog",
            ),
            "insert": base
            + b"INSERT INTO ingest.source_request_gates (source_key) "
            + b"VALUES ('tcgdex_catalog');\n",
            "select-policy": base
            + b"CREATE POLICY gate_read ON ingest.source_request_gates "
            + b"FOR SELECT TO service_role USING (true);\n",
            "multiline-all-policy": base
            + b'CREATE POLICY "gate_all"\n'
            + b'ON "ingest"."source_request_gates"\n'
            + b"FOR ALL TO service_role USING (true) WITH CHECK (true);\n",
            "quoted-name-newline-semicolon": base
            + b'CREATE POLICY "gate;\nread" ON ingest.source_request_gates\n'
            + b"FOR SELECT TO service_role USING (true);\n",
            "ordinary-backslash-string": base
            + b"CREATE POLICY gate_backslash ON ingest.source_request_gates "
            + b"USING (note = '\\');\n",
        }
        for name, dump in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(dump)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

        unrelated_policies = (
            b"CREATE POLICY unrelated_read ON public.unrelated "
            b"FOR SELECT TO service_role USING (true);\n"
            b'CREATE POLICY "on ingest.source_request_gates " ON public.unrelated '
            b"USING (true);\n"
            b"CREATE POLICY unrelated_string ON public.unrelated "
            b"USING (note = 'on ingest.source_request_gates ;');\n"
            b"CREATE POLICY unrelated_dollar ON public.unrelated "
            b"USING (note = $policy$on ingest.source_request_gates ;$policy$);\n"
            b"CREATE POLICY unrelated_backslash ON public.unrelated "
            b"USING (note = '\\');\n"
            b"CREATE POLICY unrelated_escape_string ON public.unrelated "
            b"USING (note = E'\\\\');\n"
            b"CREATE POLICY unrelated_comment ON public.unrelated "
            b"/* on ingest.source_request_gates ; /* nested ; */ */ USING (true);\n"
        )
        success = self.run_sanitizer(base + unrelated_policies)
        self.assertEqual(success.returncode, 0, success.stderr.decode())
        self.assertIn(unrelated_policies, success.stdout)

    def test_cache_policy_mismatch_and_malformed_id_fail_before_output(self) -> None:
        base = self.complete_dump()
        cases = {
            "different": base.replace(
                f"{FIRST_VIDEO}\t{YOUTUBE_POLICY}".encode(),
                f"{FIRST_VIDEO}\t{WRONG_POLICY}".encode(),
            ),
            "malformed": base.replace(
                f"{FIRST_VIDEO}\t{YOUTUBE_POLICY}".encode(),
                f"{FIRST_VIDEO}\tnot-a-uuid".encode(),
            ),
        }
        for name, dump in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(dump)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_presence_races_and_malformed_preflight_id_fail_before_output(self) -> None:
        missing_cache = self.complete_dump().replace(
            copy_block(
                "ingest.youtube_discoveries",
                "video_id, source_policy_id, title",
                f"{FIRST_VIDEO}\t{YOUTUBE_POLICY}\tcache\\tfirst".encode(),
                f"{SECOND_VIDEO}\t{YOUTUBE_POLICY}\tcache\\nsecond".encode(),
            ),
            b"",
        )
        cases = {
            "missing-cache": self.run_sanitizer(missing_cache),
            "unexpected-cache": self.run_sanitizer(
                self.complete_dump(),
                source_policies="absent",
                youtube_discoveries="absent",
                policy_id=None,
            ),
            "missing-policy-id": self.run_sanitizer(
                self.complete_dump(), policy_id=None
            ),
            "malformed-policy-id": self.run_sanitizer(
                self.complete_dump(), policy_id="not-a-uuid"
            ),
        }
        for name, result in cases.items():
            with self.subTest(name=name):
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_malformed_control_copy_shapes_fail_before_output(self) -> None:
        base = self.complete_dump()
        cache = copy_block(
            "ingest.youtube_discoveries",
            "video_id, source_policy_id, title",
            f"{FIRST_VIDEO}\t{YOUTUBE_POLICY}\tcache\\tfirst".encode(),
            f"{SECOND_VIDEO}\t{YOUTUBE_POLICY}\tcache\\nsecond".encode(),
        )
        cases = {
            "wrong-field-count": base.replace(
                f"{FIRST_VIDEO}\t{YOUTUBE_POLICY}\tcache\\tfirst\n".encode(),
                f"{FIRST_VIDEO}\t{YOUTUBE_POLICY}\n".encode(),
            ),
            "missing-policy-column": base.replace(
                b"COPY ingest.youtube_discoveries (video_id, source_policy_id, title) FROM stdin;",
                b"COPY ingest.youtube_discoveries (video_id, policy, title) FROM stdin;",
            ),
            "unterminated": base.replace(cache, cache.rsplit(b"\\.\n", 1)[0]),
            "duplicate-copy": base + cache,
        }
        for name, dump in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(dump)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_target_insert_is_rejected_but_legacy_data_is_not_targeted(self) -> None:
        legacy_inserts = self.complete_dump() + (
            b"INSERT INTO ingest.source_items (id) VALUES ('source-item-kept');\n"
            b"INSERT INTO ingest.source_discoveries (source_item_id) "
            b"VALUES ('legacy-discovery-kept');\n"
        )
        success = self.run_sanitizer(legacy_inserts)
        self.assertEqual(success.returncode, 0, success.stderr.decode())
        self.assertIn(b"source-item-kept", success.stdout)
        self.assertIn(b"legacy-discovery-kept", success.stdout)

        target_insert = self.complete_dump() + (
            b"  insert into ingest.youtube_discoveries (video_id) "
            b"VALUES ('payload-must-not-leak');\n"
        )
        failure = self.run_sanitizer(target_insert)
        self.assertNotEqual(failure.returncode, 0)
        self.assertEqual(failure.stdout, b"")
        self.assertNotIn(b"payload-must-not-leak", failure.stderr)

    def test_temporary_spool_is_removed_after_success_and_scan_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            spool_root = Path(temporary)
            environment = os.environ.copy()
            environment["TMPDIR"] = str(spool_root)

            success = self.run_sanitizer(
                self.complete_dump(), environment=environment
            )
            self.assertEqual(success.returncode, 0, success.stderr.decode())
            self.assertEqual(list(spool_root.iterdir()), [])

            malformed = self.complete_dump().replace(
                b"COPY ingest.youtube_discoveries (video_id, source_policy_id, title) FROM stdin;",
                b"COPY ingest.youtube_discoveries (video_id, wrong_policy, title) FROM stdin;",
            )
            failure = self.run_sanitizer(malformed, environment=environment)
            self.assertNotEqual(failure.returncode, 0)
            self.assertEqual(failure.stdout, b"")
            self.assertEqual(list(spool_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
