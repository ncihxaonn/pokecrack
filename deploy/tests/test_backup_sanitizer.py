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
BLUESKY_POLICY = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
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
PUBLIC_STUDY_SOURCE_KEYS_V1 = (
    b"public_study_comicbook_us_55",
    b"public_study_wargamer_gb_17",
    b"public_study_cardchill_gb_90",
    b"public_study_bleedingcool_us_36",
    b"public_study_tcgtalk_sg_54",
)
POKESUP_PUBLIC_STUDY_SOURCE_KEY = b"public_study_pokesup_jp_30"
PUBLIC_STUDY_SOURCE_KEYS_V2 = PUBLIC_STUDY_SOURCE_KEYS_V1 + (
    POKESUP_PUBLIC_STUDY_SOURCE_KEY,
)
ASIA_PHASE_ONE_PUBLIC_STUDY_SOURCE_KEYS = (
    b"public_study_limitsend_kr_30",
    b"public_study_buyfunlife_tw_40",
    b"public_study_allonline_th_10",
)
PUBLIC_STUDY_SOURCE_KEYS_V3 = (
    PUBLIC_STUDY_SOURCE_KEYS_V2 + ASIA_PHASE_ONE_PUBLIC_STUDY_SOURCE_KEYS
)
PUBLIC_STUDY_SOURCE_KEYS = PUBLIC_STUDY_SOURCE_KEYS_V1
COMICBOOK_POLICY = "55555555-5555-4555-8555-555555555555"
WARGAMER_POLICY = "66666666-6666-4666-8666-666666666666"
CARDCHILL_POLICY = "77777777-7777-4777-8777-777777777770"
BLEEDINGCOOL_POLICY = "88888888-8888-4888-8888-888888888880"
TCGTALK_POLICY = "99999999-9999-4999-8999-999999999990"
POKESUP_POLICY = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
LIMITSEND_POLICY = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeee1"
BUYFUNLIFE_POLICY = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeee2"
ALLONLINE_POLICY = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeee3"
PUBLIC_STUDY_COLUMNS = (
    "study_key, source_policy_id, source_item_id, extraction_run_id, opening_id, "
    "country_code, country_name, geography_basis, geography_confidence, "
    "source_observed_at, pack_count, qualifying_hit_pack_count, set_external_id, "
    "product_scope, metric_key, metric_version, collector_version, parser_version, "
    "source_policy_version, evidence_sha256, first_verified_at, last_verified_at, is_demo"
)
PUBLIC_STUDY_DDL = b"""CREATE TABLE ingest.public_study_observations (
    study_key text NOT NULL,
    source_policy_id uuid NOT NULL,
    source_item_id uuid NOT NULL,
    extraction_run_id uuid NOT NULL,
    opening_id uuid NOT NULL,
    country_code text NOT NULL,
    country_name text NOT NULL,
    geography_basis text NOT NULL,
    geography_confidence text NOT NULL,
    source_observed_at timestamp with time zone NOT NULL,
    pack_count integer NOT NULL,
    qualifying_hit_pack_count integer NOT NULL,
    set_external_id text NOT NULL,
    product_scope text NOT NULL,
    metric_key text NOT NULL,
    metric_version text NOT NULL,
    collector_version text NOT NULL,
    parser_version text NOT NULL,
    source_policy_version text NOT NULL,
    evidence_sha256 text NOT NULL,
    first_verified_at timestamp with time zone NOT NULL,
    last_verified_at timestamp with time zone NOT NULL,
    is_demo boolean DEFAULT false NOT NULL,
    CONSTRAINT public_study_observations_country_name_check CHECK (((btrim(country_name) <> ''::text) AND (char_length(country_name) <= 160))),
    CONSTRAINT public_study_observations_counts_check CHECK ((((pack_count >= 1) AND (pack_count <= 100000)) AND ((qualifying_hit_pack_count >= 0) AND (qualifying_hit_pack_count <= pack_count)))),
    CONSTRAINT public_study_observations_geography_check CHECK (((geography_basis = ANY (ARRAY['publisher_country'::text, 'author_public_residence'::text])) AND (geography_confidence = 'tier_b'::text))),
    CONSTRAINT public_study_observations_hash_check CHECK ((evidence_sha256 ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT public_study_observations_key_check CHECK ((study_key ~ '^[a-z0-9][a-z0-9-]{0,119}$'::text)),
    CONSTRAINT public_study_observations_live_only_check CHECK ((NOT is_demo)),
    CONSTRAINT public_study_observations_metric_check CHECK (((metric_key = 'qualifying_hit_pack_rate'::text) AND (metric_version = 'global-sir-v1'::text))),
    CONSTRAINT public_study_observations_product_check CHECK ((product_scope = ANY (ARRAY['all'::text, 'booster_box'::text, 'etb'::text, 'booster_bundle'::text]))),
    CONSTRAINT public_study_observations_set_check CHECK (((btrim(set_external_id) <> ''::text) AND (char_length(set_external_id) <= 160))),
    CONSTRAINT public_study_observations_time_check CHECK ((last_verified_at >= first_verified_at)),
    CONSTRAINT public_study_observations_version_check CHECK (((btrim(collector_version) <> ''::text) AND (char_length(collector_version) <= 120) AND (btrim(parser_version) <> ''::text) AND (char_length(parser_version) <= 120) AND (btrim(source_policy_version) <> ''::text) AND (char_length(source_policy_version) <= 120)))
);
"""
POST_PUBLIC_STUDY_GATE_SEED = POST_YOUTUBE_GATE_SEED.replace(
    b"youtube_discovery\n",
    b"youtube_discovery\n" + b"\n".join(PUBLIC_STUDY_SOURCE_KEYS) + b"\n",
)
POST_PUBLIC_STUDY_GATE_SEED_V2 = POST_YOUTUBE_GATE_SEED.replace(
    b"youtube_discovery\n",
    b"youtube_discovery\n" + b"\n".join(PUBLIC_STUDY_SOURCE_KEYS_V2) + b"\n",
)
POST_PUBLIC_STUDY_GATE_SEED_V3 = POST_YOUTUBE_GATE_SEED.replace(
    b"youtube_discovery\n",
    b"youtube_discovery\n" + b"\n".join(PUBLIC_STUDY_SOURCE_KEYS_V3) + b"\n",
)
POST_BLUESKY_GATE_SEED = POST_YOUTUBE_GATE_SEED.replace(
    b"youtube_discovery\n",
    b"youtube_discovery\nbluesky_jetstream\n",
)
BLUESKY_CHECKPOINT_COLUMNS = (
    "source_policy_id, endpoint, protocol, collection, last_cursor, "
    "last_collected_at, events_seen_total, bytes_seen_total, "
    "candidates_seen_total, deletions_seen_total, is_demo, created_at, updated_at"
)
BLUESKY_CHECKPOINT_ROW = (
    f"{BLUESKY_POLICY}\t"
    "wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents\t"
    "xrpc.v1.json\tapp.bsky.feed.post\t123\t2026-08-30 00:00:00+00\t"
    "10\t2048\t2\t1\tf\t2026-08-29 00:00:00+00\t2026-08-30 00:00:00+00"
).encode()


def comicbook_ledger_row(**overrides: bytes) -> bytes:
    values = {
        "study_key": b"comicbook-perfect-order-us-55-v1",
        "source_policy_id": COMICBOOK_POLICY.encode(),
        "source_item_id": b"77777777-7777-4777-8777-777777777777",
        "extraction_run_id": b"88888888-8888-4888-8888-888888888888",
        "opening_id": b"99999999-9999-4999-8999-999999999999",
        "country_code": b"US",
        "country_name": b"United States",
        "geography_basis": b"publisher_country",
        "geography_confidence": b"tier_b",
        "source_observed_at": b"2026-03-19 21:00:00+00",
        "pack_count": b"55",
        "qualifying_hit_pack_count": b"1",
        "set_external_id": b"me03",
        "product_scope": b"all",
        "metric_key": b"qualifying_hit_pack_rate",
        "metric_version": b"global-sir-v1",
        "collector_version": b"public-study-comicbook-perfect-order-v1",
        "parser_version": b"comicbook-perfect-order-evidence-v1",
        "source_policy_version": b"public-study-comicbook-perfect-order-v1",
        "evidence_sha256": b"a" * 64,
        "first_verified_at": b"2026-08-29 01:02:03.123456+00",
        "last_verified_at": b"2026-08-29 01:02:03.123456+00",
        "is_demo": b"f",
    }
    values.update(overrides)
    return b"\t".join(values[column.strip()] for column in PUBLIC_STUDY_COLUMNS.split(","))


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
        public_studies: str = "absent",
        bluesky_jetstream: str = "absent",
        policy_id: str | None = YOUTUBE_POLICY,
        bluesky_policy_id: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        command = [
            "python3",
            str(SANITIZER),
            "--source-policies",
            source_policies,
            "--youtube-discoveries",
            youtube_discoveries,
            "--public-studies",
            public_studies,
            "--bluesky-jetstream",
            bluesky_jetstream,
        ]
        if policy_id is not None:
            command.extend(("--youtube-policy-id", policy_id))
        if bluesky_policy_id is not None:
            command.extend(("--bluesky-policy-id", bluesky_policy_id))
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

    def with_public_study_ledger(
        self,
        dump: bytes,
        *rows: bytes,
        ddl: bytes = PUBLIC_STUDY_DDL,
        columns: str = PUBLIC_STUDY_COLUMNS,
        source_keys: tuple[bytes, ...] = PUBLIC_STUDY_SOURCE_KEYS,
    ) -> bytes:
        youtube_row = f"{YOUTUBE_POLICY}\tyoutube_discovery\tpolicy\n".encode()
        policy_ids = {
            b"public_study_comicbook_us_55": COMICBOOK_POLICY,
            b"public_study_wargamer_gb_17": WARGAMER_POLICY,
            b"public_study_cardchill_gb_90": CARDCHILL_POLICY,
            b"public_study_bleedingcool_us_36": BLEEDINGCOOL_POLICY,
            b"public_study_tcgtalk_sg_54": TCGTALK_POLICY,
            POKESUP_PUBLIC_STUDY_SOURCE_KEY: POKESUP_POLICY,
            b"public_study_limitsend_kr_30": LIMITSEND_POLICY,
            b"public_study_buyfunlife_tw_40": BUYFUNLIFE_POLICY,
            b"public_study_allonline_th_10": ALLONLINE_POLICY,
        }
        policy_rows = b"".join(
            f"{policy_ids[source_key]}\t{source_key.decode()}\tpolicy\n".encode()
            for source_key in source_keys
        )
        ledger = ddl + copy_block(
            "ingest.public_study_observations",
            columns,
            *rows,
        )
        return dump.replace(youtube_row, youtube_row + policy_rows) + ledger

    def with_bluesky_checkpoint(self, dump: bytes) -> bytes:
        youtube_row = f"{YOUTUBE_POLICY}\tyoutube_discovery\tpolicy\n".encode()
        bluesky_row = f"{BLUESKY_POLICY}\tbluesky_jetstream\tpolicy\n".encode()
        checkpoint = copy_block(
            "ingest.bluesky_jetstream_checkpoints",
            BLUESKY_CHECKPOINT_COLUMNS,
            BLUESKY_CHECKPOINT_ROW,
        )
        return dump.replace(youtube_row, youtube_row + bluesky_row) + checkpoint

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

    def test_public_study_ledger_is_retained_and_its_idle_gates_are_reseeded(
        self,
    ) -> None:
        dump = self.with_public_study_ledger(
            self.complete_dump(),
            comicbook_ledger_row(),
        )

        result = self.run_sanitizer(dump, public_studies="present")

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"comicbook-perfect-order-us-55-v1", result.stdout)
        self.assertIn(POST_PUBLIC_STUDY_GATE_SEED, result.stdout)

    def test_public_study_accepts_exact_post_migration_profile_only(self) -> None:
        dump = self.with_public_study_ledger(
            self.complete_dump(),
            comicbook_ledger_row(),
            source_keys=PUBLIC_STUDY_SOURCE_KEYS_V2,
        )

        result = self.run_sanitizer(dump, public_studies="present")

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(POST_PUBLIC_STUDY_GATE_SEED_V2, result.stdout)
        self.assertEqual(
            result.stdout.count(POKESUP_PUBLIC_STUDY_SOURCE_KEY + b"\n"), 1
        )

        partial_profile = dump.replace(
            f"{TCGTALK_POLICY}\tpublic_study_tcgtalk_sg_54\tpolicy\n".encode(),
            b"",
            1,
        )
        result = self.run_sanitizer(partial_profile, public_studies="present")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_public_study_accepts_exact_asia_phase_one_profile_only(self) -> None:
        dump = self.with_public_study_ledger(
            self.complete_dump(),
            comicbook_ledger_row(),
            source_keys=PUBLIC_STUDY_SOURCE_KEYS_V3,
        )

        result = self.run_sanitizer(dump, public_studies="present")

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(POST_PUBLIC_STUDY_GATE_SEED_V3, result.stdout)
        for source_key in ASIA_PHASE_ONE_PUBLIC_STUDY_SOURCE_KEYS:
            self.assertEqual(result.stdout.count(source_key + b"\n"), 1)

        partial_profile = dump.replace(
            f"{BUYFUNLIFE_POLICY}\tpublic_study_buyfunlife_tw_40\tpolicy\n".encode(),
            b"",
            1,
        )
        result = self.run_sanitizer(partial_profile, public_studies="present")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_pokesup_study_key_is_not_promoted_to_the_statistical_ledger(self) -> None:
        dump = self.with_public_study_ledger(
            self.complete_dump(),
            comicbook_ledger_row(
                study_key=b"pokesup-abyss-eye-jp-30-v1",
                source_policy_id=POKESUP_POLICY.encode(),
            ),
            source_keys=PUBLIC_STUDY_SOURCE_KEYS_V2,
        )

        result = self.run_sanitizer(dump, public_studies="present")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_public_study_schema_copy_header_and_rows_are_fail_closed(self) -> None:
        base = self.with_public_study_ledger(
            self.complete_dump(),
            comicbook_ledger_row(),
        )
        cases = {
            "missing-create": base.replace(PUBLIC_STUDY_DDL, b""),
            "duplicate-create": base.replace(
                PUBLIC_STUDY_DDL,
                PUBLIC_STUDY_DDL + PUBLIC_STUDY_DDL,
            ),
            "unlogged-table": base.replace(
                b"CREATE TABLE ingest.public_study_observations",
                b"CREATE UNLOGGED TABLE ingest.public_study_observations",
            ),
            "changed-column-type": base.replace(
                b"    pack_count integer NOT NULL,",
                b"    pack_count bigint NOT NULL,",
            ),
            "removed-not-null": base.replace(
                b"    evidence_sha256 text NOT NULL,",
                b"    evidence_sha256 text,",
            ),
            "changed-check-expression": base.replace(
                b"(char_length(country_name) <= 160)",
                b"(char_length(country_name) <= 161)",
            ),
            "extra-schema-column": base.replace(
                b"    is_demo boolean DEFAULT false NOT NULL,",
                b"    raw_html text,\n    is_demo boolean DEFAULT false NOT NULL,",
            ),
            "extra-copy-column": base.replace(
                f"COPY ingest.public_study_observations ({PUBLIC_STUDY_COLUMNS})".encode(),
                f"COPY ingest.public_study_observations ({PUBLIC_STUDY_COLUMNS}, raw_html)".encode(),
            ).replace(
                comicbook_ledger_row() + b"\n",
                comicbook_ledger_row() + b"\t<html>sensitive</html>\n",
            ),
            "wrong-reviewed-count": base.replace(
                comicbook_ledger_row() + b"\n",
                comicbook_ledger_row(pack_count=b"56") + b"\n",
            ),
            "coverage-not-promoted-to-statistical-ledger": base.replace(
                b"comicbook-perfect-order-us-55-v1",
                b"cardchill-ascended-heroes-gb-90-v1",
            ),
            "wrong-source-policy": base.replace(
                comicbook_ledger_row() + b"\n",
                comicbook_ledger_row(source_policy_id=WARGAMER_POLICY.encode()) + b"\n",
            ),
            "invalid-evidence-hash": base.replace(
                comicbook_ledger_row() + b"\n",
                comicbook_ledger_row(evidence_sha256=b"<html>not-a-hash</html>") + b"\n",
            ),
            "non-utc-verification-time": base.replace(
                comicbook_ledger_row() + b"\n",
                comicbook_ledger_row(first_verified_at=b"2026-08-29 11:02:03+10")
                + b"\n",
            ),
            "duplicate-public-policy-uuid": base.replace(
                WARGAMER_POLICY.encode(),
                COMICBOOK_POLICY.encode(),
            ),
        }
        for name, dump in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(dump, public_studies="present")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"sensitive", result.stderr)

    def test_public_study_preflight_and_dump_must_match(self) -> None:
        result = self.run_sanitizer(
            self.complete_dump(),
            public_studies="present",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_bluesky_checkpoint_is_retained_but_private_activity_is_not(self) -> None:
        base = self.with_bluesky_checkpoint(self.complete_dump())
        result = self.run_sanitizer(
            base,
            bluesky_jetstream="present",
            bluesky_policy_id=BLUESKY_POLICY,
        )

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(BLUESKY_CHECKPOINT_ROW, result.stdout)
        self.assertIn(POST_BLUESKY_GATE_SEED, result.stdout)

        private_rows = (
            copy_block(
                "ingest.bluesky_jetstream_candidates",
                "at_uri, text_excerpt",
                b"at://did:plc:private/app.bsky.feed.post/one\tprivate marker",
            )
            + copy_block(
                "ingest.bluesky_jetstream_observations",
                "cursor, at_uri, text_excerpt",
                b"124\tat://did:plc:private/app.bsky.feed.post/one\tprivate marker",
            )
        )
        rejected = self.run_sanitizer(
            base + private_rows,
            bluesky_jetstream="present",
            bluesky_policy_id=BLUESKY_POLICY,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(rejected.stdout, b"")
        self.assertNotIn(b"private marker", rejected.stderr)

    def test_bluesky_preflight_policy_and_checkpoint_must_match(self) -> None:
        base = self.with_bluesky_checkpoint(self.complete_dump())
        cases = {
            "missing-checkpoint": base.replace(
                copy_block(
                    "ingest.bluesky_jetstream_checkpoints",
                    BLUESKY_CHECKPOINT_COLUMNS,
                    BLUESKY_CHECKPOINT_ROW,
                ),
                b"",
            ),
            "wrong-checkpoint-policy": base.replace(
                BLUESKY_POLICY.encode(), WRONG_POLICY.encode(), 1
            ),
            "drifted-endpoint": base.replace(
                b"jetstream.us-west.bsky.network", b"jetstream.example.invalid", 1
            ),
        }
        for name, dump in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(
                    dump,
                    bluesky_jetstream="present",
                    bluesky_policy_id=BLUESKY_POLICY,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

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

    def test_target_insert_inside_dollar_quoted_function_body_is_schema(self) -> None:
        function_definitions = (
            b"\nCREATE FUNCTION ingest.test_backup_function() RETURNS void\n"
            b"LANGUAGE plpgsql AS $function$\n"
            b"BEGIN\n"
            b"  INSERT INTO ingest.youtube_discoveries (video_id) "
            b"VALUES ('function-body-only');\n"
            b"  INSERT INTO ingest.nostr_relay_observations (event_id) "
            b"VALUES ('function-body-only');\n"
            b"END;\n"
            b"$function$;\n"
            b"CREATE FUNCTION ingest.test_inline_function() RETURNS text\n"
            b"LANGUAGE sql AS $$ SELECT 'inline'; $$;\n"
            b"SELECT $safe_tag$INSERT INTO ingest.source_request_gates "
            b"VALUES ('quoted text only')$safe_tag$;\n"
        )

        result = self.run_sanitizer(self.complete_dump() + function_definitions)

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(function_definitions, result.stdout)

    def test_top_level_target_insert_after_function_body_remains_rejected(
        self,
    ) -> None:
        dump = self.complete_dump() + (
            b"\nCREATE FUNCTION ingest.test_backup_function() RETURNS void\n"
            b"LANGUAGE plpgsql AS $function$\n"
            b"BEGIN\n"
            b"  INSERT INTO ingest.youtube_discoveries (video_id) "
            b"VALUES ('function-body-only');\n"
            b"END;\n"
            b"$function$;\n"
            b"INSERT INTO ingest.youtube_discoveries (video_id) "
            b"VALUES ($$top-level-payload-must-not-leak$$);\n"
        )

        result = self.run_sanitizer(dump)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(b"top-level-payload-must-not-leak", result.stderr)

    def test_dollar_tags_in_strings_comments_and_identifiers_do_not_hide_data(
        self,
    ) -> None:
        private_copy = copy_block(
            "ingest.bluesky_jetstream_observations",
            "at_uri, text_excerpt",
            b"at://did:plc:private/app.bsky.feed.post/one\tprivate-marker",
        )
        prefixes = {
            "single-quoted-comment": (
                b"COMMENT ON TABLE public.unrelated IS '$x$';\n"
            ),
            "line-comment": b"-- $x$ is text, not a delimiter\n",
            "quoted-identifier": b'COMMENT ON TABLE public."$x$" IS NULL;\n',
            "unquoted-identifier": b"COMMENT ON TABLE public.foo$x$ IS NULL;\n",
            "block-comment": b"/* $x$ is text, not a delimiter */\n",
        }

        for name, prefix in prefixes.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(
                    self.complete_dump()
                    + prefix
                    + private_copy
                    + b"COMMENT ON TABLE public.unrelated IS '$x$';\n"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"private-marker", result.stderr)

    def test_closing_dollar_tag_cannot_hide_same_line_target_data(self) -> None:
        suffixes = (
            b"$function$; INSERT INTO ingest.youtube_discoveries "
            b"VALUES ('private-insert');\n",
            b"$function$; COPY ingest.bluesky_jetstream_observations "
            b"(at_uri) FROM stdin;\n",
        )
        function_prefix = (
            self.complete_dump()
            + b"\nCREATE FUNCTION ingest.test_backup_function() RETURNS void\n"
            + b"LANGUAGE plpgsql AS $function$\n"
            + b"BEGIN\n"
            + b"  NULL;\n"
            + b"END;\n"
        )

        for suffix in suffixes:
            with self.subTest(suffix=suffix):
                result = self.run_sanitizer(function_prefix + suffix)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"private-insert", result.stderr)

    def test_multiline_quote_or_comment_suffix_cannot_hide_target_data(
        self,
    ) -> None:
        prefixes = (
            b"COMMENT ON TABLE public.unrelated IS 'first line\nsecond line'",
            b"/* first line\nsecond line */",
        )

        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                result = self.run_sanitizer(
                    self.complete_dump()
                    + prefix
                    + b"; COPY ingest.bluesky_jetstream_observations "
                    + b"(at_uri) FROM stdin;\n"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_comments_or_newlines_cannot_split_target_insert_tokens(self) -> None:
        statements = (
            b"INSERT /* split */ INTO ingest.youtube_discoveries\n"
            b"  (video_id) VALUES ('comment-split-marker');\n",
            b"INSERT\nINTO \"ingest\".\"youtube_discoveries\"\n"
            b"  (video_id) VALUES ('newline-split-marker');\n",
            b"INSERT /* first line\nsecond line */ INTO ONLY "
            b"ingest.youtube_discoveries (video_id) "
            b"VALUES ('multiline-comment-marker');\n",
            b"WITH harmless AS (SELECT 1) "
            b"INSERT INTO ingest.youtube_discoveries (video_id) "
            b"VALUES ('cte-marker');\n",
        )

        for statement in statements:
            with self.subTest(statement=statement):
                result = self.run_sanitizer(self.complete_dump() + statement)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"marker", result.stderr)

    def test_unicode_identifier_cannot_open_a_dollar_quote(self) -> None:
        unicode_identifier = "SELECT α$tag$;\n".encode()
        target_insert = (
            b"INSERT INTO ingest.youtube_discoveries (video_id) "
            b"VALUES ('unicode-boundary-marker');\n"
        )

        result = self.run_sanitizer(
            self.complete_dump()
            + unicode_identifier
            + target_insert
            + unicode_identifier
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(b"unicode-boundary-marker", result.stderr)

    def test_unicode_dollar_tag_hides_its_function_body_from_data_checks(
        self,
    ) -> None:
        function_definition = (
            "CREATE FUNCTION ingest.unicode_body() RETURNS void\n"
            "LANGUAGE plpgsql AS $é$\n"
            "BEGIN\n"
            "  PERFORM $tag$\n"
            "  INSERT INTO ingest.youtube_discoveries (video_id) "
            "VALUES ('function-body-text');\n"
            "  $tag$;\n"
            "END;\n"
            "$é$;\n"
        ).encode()

        result = self.run_sanitizer(
            self.complete_dump() + function_definition
        )

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(function_definition, result.stdout)

    def test_executable_do_body_is_rejected(self) -> None:
        bodies = (
            b"DO $do$\nBEGIN\n"
            b"  INSERT INTO ingest.youtube_discoveries (video_id) "
            b"VALUES ('direct-do-marker');\n"
            b"END\n$do$;\n",
            b"DO LANGUAGE plpgsql $do$\nBEGIN\n"
            b"  EXECUTE 'INSERT INTO ingest.youtube_discoveries "
            b"(video_id) VALUES (''dynamic-do-marker'')';\n"
            b"END\n$do$;\n",
        )

        for body in bodies:
            with self.subTest(body=body):
                result = self.run_sanitizer(self.complete_dump() + body)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"do-marker", result.stderr)

    def test_same_line_statement_cannot_hide_target_copy(self) -> None:
        dump = self.complete_dump() + (
            b"SELECT 1; COPY ingest.bluesky_jetstream_observations "
            b"(at_uri) FROM stdin;\n"
            b"at://did:plc:private/app.bsky.feed.post/one\n"
            b"\\.\n"
        )

        result = self.run_sanitizer(dump)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(b"did:plc:private", result.stderr)

    def test_unqualified_retention_targets_are_rejected(self) -> None:
        statements = (
            b"SET search_path = ingest;\n"
            b"INSERT INTO youtube_discoveries (video_id) "
            b"VALUES ('searchpath-insert-marker');\n",
            b"SET search_path = ingest;\n"
            b"COPY bluesky_jetstream_observations (at_uri) FROM stdin;\n"
            b"at://did:plc:private/app.bsky.feed.post/one\n"
            b"\\.\n",
        )

        for statement in statements:
            with self.subTest(statement=statement):
                result = self.run_sanitizer(self.complete_dump() + statement)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"marker", result.stderr)
                self.assertNotIn(b"did:plc:private", result.stderr)

    def test_quoted_retention_table_followed_by_alias_is_rejected(self) -> None:
        statements = (
            b'INSERT INTO ingest."youtube_discoveries"AS x (video_id) '
            b"VALUES ('quoted-alias-marker');\n",
            b'INSERT INTO "ingest"."youtube_discoveries"AS x (video_id) '
            b"VALUES ('quoted-schema-alias-marker');\n",
            b'INSERT INTO ONLY ingest."youtube_discoveries"AS x (video_id) '
            b"VALUES ('quoted-only-alias-marker');\n",
        )

        for statement in statements:
            with self.subTest(statement=statement):
                result = self.run_sanitizer(self.complete_dump() + statement)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"marker", result.stderr)

    def test_explicit_other_schema_same_name_is_not_a_retention_target(
        self,
    ) -> None:
        statements = (
            b"INSERT INTO public.youtube_discoveries (video_id) "
            b"VALUES ('other-schema-insert');\n",
            b"INSERT INTO youtube_discoveries_archive (video_id) "
            b"VALUES ('identifier-suffix-insert');\n",
            copy_block(
                "public.bluesky_jetstream_observations",
                "at_uri",
                b"other-schema-copy",
            ),
        )

        for statement in statements:
            with self.subTest(statement=statement):
                result = self.run_sanitizer(self.complete_dump() + statement)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertIn(statement, result.stdout)

    def test_unterminated_dollar_quoted_body_is_rejected(self) -> None:
        dump = self.complete_dump() + (
            b"\nCREATE FUNCTION ingest.test_backup_function() RETURNS void\n"
            b"LANGUAGE plpgsql AS $function$\n"
            b"BEGIN\n"
            b"  INSERT INTO ingest.youtube_discoveries (video_id) "
            b"VALUES ('function-body-only');\n"
        )

        result = self.run_sanitizer(dump)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

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
