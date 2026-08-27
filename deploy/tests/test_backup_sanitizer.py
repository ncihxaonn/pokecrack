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
WRONG_POLICY = "33333333-3333-4333-8333-333333333333"
YOUTUBE_ITEM = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_ITEM = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
FIRST_VIDEO = "AbCdEfGhI_1"
SECOND_VIDEO = "ZyXwVuTsR-2"


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
            policies = copy_block(
                "ingest.source_policies",
                "id, source_key, note",
                f"{YOUTUBE_POLICY}\tyoutube_discovery\tpolicy".encode(),
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
            (cache, legacy, unrelated, policies, items)
            if cache_first
            else (unrelated, policies, items, legacy, cache)
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
            + copy_block(
                "ingest.source_policies",
                "source_key, id",
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
        self.assertEqual(result.stdout, dump)

    def test_policy_snapshot_missing_different_or_duplicate_fails_before_output(
        self,
    ) -> None:
        base = self.complete_dump()
        policy_row = f"{YOUTUBE_POLICY}\tyoutube_discovery\tpolicy\n".encode()
        cases = {
            "missing": base.replace(policy_row, b""),
            "different": base.replace(
                policy_row,
                f"{WRONG_POLICY}\tyoutube_discovery\tpolicy\n".encode(),
            ),
            "duplicate": base.replace(policy_row, policy_row + policy_row),
        }
        for name, dump in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(dump)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

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
