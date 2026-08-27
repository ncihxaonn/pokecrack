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
YOUTUBE_ITEM = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REBOUND_ITEM = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
OTHER_ITEM = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


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
        source_items: str = "present",
        source_discoveries: str = "present",
        policy_id: str | None = YOUTUBE_POLICY,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        command = [
            "python3",
            str(SANITIZER),
            "--source-policies",
            source_policies,
            "--source-items",
            source_items,
            "--source-discoveries",
            source_discoveries,
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
        discoveries_first: bool = False,
    ) -> bytes:
        if quoted:
            policies = copy_block(
                '"ingest"."source_policies"',
                '"source_key", "id", "note"',
                f"youtube_discovery\t{YOUTUBE_POLICY}\tpolicy".encode(),
                f"other\t{OTHER_POLICY}\tother".encode(),
                crlf=True,
            )
            items = copy_block(
                '"ingest"."source_items"',
                '"note", "id", "source_policy_id"',
                f"youtube\\ttab\\nline\t{YOUTUBE_ITEM}\t{YOUTUBE_POLICY}".encode(),
                f"rebound\\tfield\t{REBOUND_ITEM}\t{OTHER_POLICY}".encode(),
                f"keep\\nfield\t{OTHER_ITEM}\t{OTHER_POLICY}".encode(),
                crlf=True,
            )
            discoveries = copy_block(
                '"ingest"."source_discoveries"',
                '"note", "source_item_id"',
                f"query\\tA\t{YOUTUBE_ITEM}".encode(),
                f"query\\nB\t{REBOUND_ITEM}".encode(),
                crlf=True,
            )
        else:
            policies = copy_block(
                "ingest.source_policies",
                "id, source_key, note",
                f"{YOUTUBE_POLICY}\tyoutube_discovery\tpolicy".encode(),
                f"{OTHER_POLICY}\tother\tother".encode(),
            )
            items = copy_block(
                "ingest.source_items",
                "note, source_policy_id, id",
                f"youtube\\ttab\\nline\t{YOUTUBE_POLICY}\t{YOUTUBE_ITEM}".encode(),
                f"rebound\\tfield\t{OTHER_POLICY}\t{REBOUND_ITEM}".encode(),
                f"keep\\nfield\t{OTHER_POLICY}\t{OTHER_ITEM}".encode(),
            )
            discoveries = copy_block(
                "ingest.source_discoveries",
                "source_item_id, note",
                f"{YOUTUBE_ITEM}\tquery\\tA".encode(),
                f"{REBOUND_ITEM}\tquery\\nB".encode(),
            )
        unrelated = copy_block(
            "public.unrelated",
            "id, note",
            b"1\tescaped\\ttab\\nnewline",
        )
        sections = (
            (discoveries, unrelated, policies, items)
            if discoveries_first
            else (
                unrelated,
                policies,
                items,
                discoveries,
            )
        )
        return b"-- fixture start\n" + b"".join(sections) + b"-- fixture end\n"

    def assert_sanitized(self, result: subprocess.CompletedProcess[bytes]) -> None:
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stderr, b"")
        self.assertNotIn(YOUTUBE_ITEM.encode(), result.stdout)
        self.assertNotIn(REBOUND_ITEM.encode(), result.stdout)
        self.assertIn(OTHER_ITEM.encode(), result.stdout)
        self.assertIn(YOUTUBE_POLICY.encode(), result.stdout)
        self.assertIn(b"1\tescaped\\ttab\\nnewline", result.stdout)
        discovery = result.stdout.split(b"COPY ingest.source_discoveries", 1)[-1]
        if b"COPY ingest.source_discoveries" in result.stdout:
            self.assertTrue(discovery.startswith(b" (source_item_id, note) FROM stdin;\n\\.\n"))

    def test_filters_policy_rows_and_rebound_discovery_parents_in_any_table_order(
        self,
    ) -> None:
        for discoveries_first in (False, True):
            with self.subTest(discoveries_first=discoveries_first):
                result = self.run_sanitizer(self.complete_dump(discoveries_first=discoveries_first))
                self.assert_sanitized(result)

    def test_supports_quoted_schema_table_columns_crlf_and_copy_escapes(self) -> None:
        result = self.run_sanitizer(self.complete_dump(quoted=True, discoveries_first=True))
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertNotIn(YOUTUBE_ITEM.encode(), result.stdout)
        self.assertNotIn(REBOUND_ITEM.encode(), result.stdout)
        self.assertIn(OTHER_ITEM.encode(), result.stdout)
        self.assertIn(
            b'COPY "ingest"."source_discoveries" ("note", "source_item_id") FROM stdin;\r\n\\.\r\n',
            result.stdout,
        )

    def test_no_youtube_policy_and_no_discovery_table_is_byte_preserving(self) -> None:
        dump = (
            b"-- old schema\n"
            + copy_block(
                "ingest.source_policies",
                "source_key, id",
                f"other\t{OTHER_POLICY}".encode(),
            )
            + copy_block(
                "ingest.source_items",
                "id, source_policy_id, note",
                f"{OTHER_ITEM}\t{OTHER_POLICY}\tescaped\\tvalue".encode(),
            )
        )
        result = self.run_sanitizer(dump, source_discoveries="absent", policy_id=None)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, dump)

    def test_policy_without_discovery_table_still_filters_matching_source_items(
        self,
    ) -> None:
        dump = copy_block(
            "ingest.source_policies",
            "id, source_key",
            f"{YOUTUBE_POLICY}\tyoutube_discovery".encode(),
            f"{OTHER_POLICY}\tother".encode(),
        ) + copy_block(
            "ingest.source_items",
            "source_policy_id, id",
            f"{YOUTUBE_POLICY}\t{YOUTUBE_ITEM}".encode(),
            f"{OTHER_POLICY}\t{OTHER_ITEM}".encode(),
        )
        result = self.run_sanitizer(dump, source_discoveries="absent")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertNotIn(YOUTUBE_ITEM.encode(), result.stdout)
        self.assertIn(OTHER_ITEM.encode(), result.stdout)

    def test_preflight_policy_mismatch_and_ambiguity_fail_before_output(self) -> None:
        base = self.complete_dump()
        cases = {
            "missing": base.replace(f"{YOUTUBE_POLICY}\tyoutube_discovery\tpolicy\n".encode(), b""),
            "different": base.replace(
                YOUTUBE_POLICY.encode(),
                b"33333333-3333-4333-8333-333333333333",
                1,
            ),
            "duplicate": base.replace(
                f"{YOUTUBE_POLICY}\tyoutube_discovery\tpolicy\n".encode(),
                (
                    f"{YOUTUBE_POLICY}\tyoutube_discovery\tpolicy\n"
                    f"{YOUTUBE_POLICY}\tyoutube_discovery\tagain\n"
                ).encode(),
            ),
        }
        for name, dump in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(dump)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_policy_appearing_after_absent_preflight_fails_closed(self) -> None:
        result = self.run_sanitizer(
            self.complete_dump(), policy_id=None, source_discoveries="present"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_malformed_sensitive_copy_rows_columns_and_terminators_fail_closed(
        self,
    ) -> None:
        base = self.complete_dump()
        cases = {
            "wrong-field-count": base.replace(
                f"{OTHER_POLICY}\tother\tother\n".encode(),
                f"{OTHER_POLICY}\tother\n".encode(),
            ),
            "missing-policy-column": base.replace(
                b"COPY ingest.source_items (note, source_policy_id, id) FROM stdin;",
                b"COPY ingest.source_items (note, policy, id) FROM stdin;",
            ),
            "unterminated": base.rsplit(b"\\.\n", 1)[0],
            "duplicate-copy": base
            + copy_block("ingest.source_discoveries", "source_item_id", REBOUND_ITEM.encode()),
        }
        for name, dump in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(dump)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_orphan_discovery_parent_and_target_insert_do_not_succeed(self) -> None:
        orphan = self.complete_dump().replace(
            REBOUND_ITEM.encode(),
            b"dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            1,
        )
        result = self.run_sanitizer(orphan)
        self.assertNotEqual(result.returncode, 0)

        target_insert = self.complete_dump() + (
            b"INSERT INTO ingest.source_items (id) VALUES ('payload-must-not-leak');\n"
        )
        result = self.run_sanitizer(target_insert)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(b"payload-must-not-leak", result.stderr)

    def test_unexpected_discovery_table_and_noncanonical_ids_fail_closed(self) -> None:
        result = self.run_sanitizer(self.complete_dump(), source_discoveries="absent")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

        inconsistent = self.run_sanitizer(
            b"-- inconsistent preflight\n",
            source_policies="absent",
            source_items="present",
            source_discoveries="absent",
            policy_id=None,
        )
        self.assertNotEqual(inconsistent.returncode, 0)
        self.assertEqual(inconsistent.stdout, b"")

        malformed = self.complete_dump().replace(OTHER_ITEM.encode(), b"not-a-uuid", 1)
        result = self.run_sanitizer(malformed)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_temporary_spool_is_removed_after_success_and_scan_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            spool_root = Path(temporary)
            environment = os.environ.copy()
            environment["TMPDIR"] = str(spool_root)

            success = self.run_sanitizer(self.complete_dump(), environment=environment)
            self.assertEqual(success.returncode, 0, success.stderr.decode())
            self.assertEqual(list(spool_root.iterdir()), [])

            malformed = self.complete_dump().replace(
                b"COPY ingest.source_items (note, source_policy_id, id) FROM stdin;",
                b"COPY ingest.source_items (note, wrong_column, id) FROM stdin;",
            )
            failure = self.run_sanitizer(malformed, environment=environment)
            self.assertNotEqual(failure.returncode, 0)
            self.assertEqual(list(spool_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
