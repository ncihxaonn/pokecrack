from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SANITIZER = REPOSITORY_ROOT / "deploy" / "lib" / "sanitize_plain_backup.py"

SOURCE_TABLE = "analytics.reviewed_global_aggregate_independent_sources"
BINDING_TABLE = "analytics.reviewed_global_aggregate_authorized_source_bindings"
ADMISSION_TABLE = "analytics.reviewed_global_aggregate_input_admissions"
SOURCE_COLUMNS = (
    "source_key, canonical_domain, domain_contract_version, "
    "domain_contract_sha256, created_at"
)
BINDING_COLUMNS = (
    "binding_key, source_identity_sha256, authorization_reference_sha256, "
    "independent_source_key, authorization_contract_version, "
    "authorization_contract_sha256, valid_from, valid_until, created_at"
)
ADMISSION_COLUMNS = (
    "admission_key, input_kind, public_study_key, accepted_observation_id, "
    "binding_key, canonical_opening_fingerprint_sha256, "
    "admission_contract_version, admission_contract_sha256, admitted_at"
)
SOURCE_SEED_ROWS = (
    b"public-study-comicbook-v1\tcomicbook.com\t"
    b"reviewed-public-study-domain-v1\t"
    b"203fb8576dd77f4e5d8b0da5436007697aecaeaf521df66b541a1ecaf22bac7d\t"
    b"2026-09-03 00:00:00+00",
    b"public-study-wargamer-v1\twww.wargamer.com\t"
    b"reviewed-public-study-domain-v1\t"
    b"841536c8203fa98aefff8e5a5babeec58d8e31ca627109c3fee9fceadd5a2cc1\t"
    b"2026-09-03 00:00:00+00",
    b"public-study-cardchill-v1\tcardchill.com\t"
    b"reviewed-public-study-domain-v1\t"
    b"3868dca0a04c840032b85dc958ab96e3b3f8b5821c87a54c3946daadc97b026f\t"
    b"2026-09-03 00:00:00+00",
    b"public-study-bleedingcool-v1\tbleedingcool.com\t"
    b"reviewed-public-study-domain-v1\t"
    b"65a31ab7ec173797b1748a3e82ce492da0b4be612bd1e70c02df4549b897efa0\t"
    b"2026-09-03 00:00:00+00",
    b"public-study-tcgtalk-v1\ttcgtalk.com\t"
    b"reviewed-public-study-domain-v1\t"
    b"000ef62d275b3452ed34dc337bfc1fda14aa7212a3e8684f6f240dca2a11e858\t"
    b"2026-09-03 00:00:00+00",
)

GATE_DDL = b"""CREATE TABLE ingest.source_request_gates (
    source_key text NOT NULL,
    owner_job_id uuid,
    owner_lease_generation bigint,
    acquired_at timestamp with time zone,
    active_until timestamp with time zone,
    CONSTRAINT source_request_gates_owner_check CHECK ((((owner_job_id IS NULL) AND (owner_lease_generation IS NULL) AND (acquired_at IS NULL) AND (active_until IS NULL)) OR ((owner_job_id IS NOT NULL) AND (owner_lease_generation >= 1) AND (acquired_at IS NOT NULL) AND (active_until > acquired_at)))),
    CONSTRAINT source_request_gates_source_check CHECK ((source_key = 'tcgdex_catalog'::text))
);
ALTER TABLE ONLY ingest.source_request_gates FORCE ROW LEVEL SECURITY;
ALTER TABLE ONLY ingest.source_request_gates
    ADD CONSTRAINT source_request_gates_pkey PRIMARY KEY (source_key);
ALTER TABLE ingest.source_request_gates ENABLE ROW LEVEL SECURITY;
"""

SOURCE_DDL = b"""CREATE TABLE analytics.reviewed_global_aggregate_independent_sources (
    source_key text NOT NULL,
    canonical_domain text NOT NULL,
    domain_contract_version text NOT NULL,
    domain_contract_sha256 text NOT NULL,
    created_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,
    CONSTRAINT reviewed_global_aggregate_independent_sources_key_check CHECK ((source_key ~ '^[a-z0-9][a-z0-9._-]{0,119}$') AND (source_key = btrim(source_key)) AND (source_key = normalize(source_key, NFKC)) AND (source_key !~ '[[:cntrl:]]')),
    CONSTRAINT reviewed_global_aggregate_independent_sources_domain_check CHECK ((canonical_domain = lower(canonical_domain)) AND (canonical_domain = btrim(canonical_domain)) AND (canonical_domain = normalize(canonical_domain, NFKC)) AND (canonical_domain !~ '[[:cntrl:]]') AND (char_length(canonical_domain) BETWEEN 3 AND 253) AND (canonical_domain ~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$')),
    CONSTRAINT reviewed_global_aggregate_independent_sources_contract_check CHECK ((domain_contract_version ~ '^[a-z0-9][a-z0-9._-]{0,119}$') AND (domain_contract_version = btrim(domain_contract_version)) AND (domain_contract_version = normalize(domain_contract_version, NFKC)) AND (domain_contract_version !~ '[[:cntrl:]]') AND (domain_contract_sha256 ~ '^[0-9a-f]{64}$'))
);
"""
BINDING_DDL = b"""CREATE TABLE analytics.reviewed_global_aggregate_authorized_source_bindings (
    binding_key text NOT NULL,
    source_identity_sha256 text NOT NULL,
    authorization_reference_sha256 text NOT NULL,
    independent_source_key text NOT NULL,
    authorization_contract_version text NOT NULL,
    authorization_contract_sha256 text NOT NULL,
    valid_from timestamp with time zone NOT NULL,
    valid_until timestamp with time zone,
    created_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,
    CONSTRAINT reviewed_global_aggregate_authorized_source_bindings_key_check CHECK ((binding_key ~ '^[a-z0-9][a-z0-9._-]{0,119}$') AND (binding_key = btrim(binding_key)) AND (binding_key = normalize(binding_key, NFKC)) AND (binding_key !~ '[[:cntrl:]]')),
    CONSTRAINT reviewed_global_aggregate_authorized_source_bindings_hash_check CHECK ((source_identity_sha256 ~ '^[0-9a-f]{64}$') AND (authorization_reference_sha256 ~ '^[0-9a-f]{64}$') AND (authorization_contract_sha256 ~ '^[0-9a-f]{64}$')),
    CONSTRAINT rga_asb_contract_check CHECK ((authorization_contract_version ~ '^[a-z0-9][a-z0-9._-]{0,119}$') AND (authorization_contract_version = btrim(authorization_contract_version)) AND (authorization_contract_version = normalize(authorization_contract_version, NFKC)) AND (authorization_contract_version !~ '[[:cntrl:]]')),
    CONSTRAINT rga_asb_window_check CHECK ((valid_until IS NULL) OR (valid_until >= valid_from))
);
"""
ADMISSION_DDL = b"""CREATE TABLE analytics.reviewed_global_aggregate_input_admissions (
    admission_key text NOT NULL,
    input_kind text NOT NULL,
    public_study_key text,
    accepted_observation_id uuid,
    binding_key text,
    canonical_opening_fingerprint_sha256 text NOT NULL,
    admission_contract_version text NOT NULL,
    admission_contract_sha256 text NOT NULL,
    admitted_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,
    CONSTRAINT reviewed_global_aggregate_input_admissions_key_check CHECK ((admission_key ~ '^[a-z0-9][a-z0-9._-]{0,159}$') AND (admission_key = btrim(admission_key)) AND (admission_key = normalize(admission_key, NFKC)) AND (admission_key !~ '[[:cntrl:]]')),
    CONSTRAINT reviewed_global_aggregate_input_admissions_kind_check CHECK (((input_kind = 'public_study') AND (public_study_key IS NOT NULL) AND (public_study_key ~ '^[a-z0-9][a-z0-9-]{0,119}$') AND (accepted_observation_id IS NULL) AND (binding_key IS NULL)) OR ((input_kind = 'authorized_opening') AND (public_study_key IS NULL) AND (accepted_observation_id IS NOT NULL) AND (binding_key IS NOT NULL))),
    CONSTRAINT reviewed_global_aggregate_input_admissions_hash_check CHECK ((canonical_opening_fingerprint_sha256 ~ '^[0-9a-f]{64}$') AND (admission_contract_sha256 ~ '^[0-9a-f]{64}$')),
    CONSTRAINT reviewed_global_aggregate_input_admissions_contract_check CHECK ((admission_contract_version ~ '^[a-z0-9][a-z0-9._-]{0,119}$') AND (admission_contract_version = btrim(admission_contract_version)) AND (admission_contract_version = normalize(admission_contract_version, NFKC)) AND (admission_contract_version !~ '[[:cntrl:]]'))
);
"""


def copy_block(table: str, columns: str, *rows: bytes) -> bytes:
    return b"\n".join(
        (f"COPY {table} ({columns}) FROM stdin;".encode(), *rows, b"\\.", b"")
    )


def bridge_alters() -> bytes:
    return b"""ALTER TABLE ONLY analytics.reviewed_global_aggregate_independent_sources FORCE ROW LEVEL SECURITY;
ALTER TABLE ONLY analytics.reviewed_global_aggregate_authorized_source_bindings FORCE ROW LEVEL SECURITY;
ALTER TABLE ONLY analytics.reviewed_global_aggregate_input_admissions FORCE ROW LEVEL SECURITY;
ALTER TABLE ONLY analytics.reviewed_global_aggregate_independent_sources
    ADD CONSTRAINT reviewed_global_aggregate_independent_sources_pkey PRIMARY KEY (source_key);
ALTER TABLE ONLY analytics.reviewed_global_aggregate_independent_sources
    ADD CONSTRAINT reviewed_global_aggregate_independent_sources_canonical_domain_key UNIQUE (canonical_domain);
ALTER TABLE ONLY analytics.reviewed_global_aggregate_authorized_source_bindings
    ADD CONSTRAINT reviewed_global_aggregate_authorized_source_bindings_pkey PRIMARY KEY (binding_key);
ALTER TABLE ONLY analytics.reviewed_global_aggregate_authorized_source_bindings
    ADD CONSTRAINT rga_asb_source_auth_key UNIQUE (source_identity_sha256, authorization_reference_sha256);
ALTER TABLE ONLY analytics.reviewed_global_aggregate_authorized_source_bindings
    ADD CONSTRAINT rga_asb_source_key_fkey FOREIGN KEY (independent_source_key) REFERENCES analytics.reviewed_global_aggregate_independent_sources(source_key) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE ONLY analytics.reviewed_global_aggregate_input_admissions
    ADD CONSTRAINT reviewed_global_aggregate_input_admissions_pkey PRIMARY KEY (admission_key);
ALTER TABLE ONLY analytics.reviewed_global_aggregate_input_admissions
    ADD CONSTRAINT rga_ia_fingerprint_key UNIQUE (canonical_opening_fingerprint_sha256);
ALTER TABLE ONLY analytics.reviewed_global_aggregate_input_admissions
    ADD CONSTRAINT rga_ia_observation_fkey FOREIGN KEY (accepted_observation_id) REFERENCES ingest.authorized_opening_observations(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE ONLY analytics.reviewed_global_aggregate_input_admissions
    ADD CONSTRAINT rga_ia_binding_key_fkey FOREIGN KEY (binding_key) REFERENCES analytics.reviewed_global_aggregate_authorized_source_bindings(binding_key) ON UPDATE RESTRICT ON DELETE RESTRICT;
CREATE UNIQUE INDEX reviewed_global_aggregate_input_admissions_study_uq ON analytics.reviewed_global_aggregate_input_admissions USING btree (public_study_key) WHERE (public_study_key IS NOT NULL);
CREATE UNIQUE INDEX reviewed_global_aggregate_input_admissions_observation_uq ON analytics.reviewed_global_aggregate_input_admissions USING btree (accepted_observation_id) WHERE (accepted_observation_id IS NOT NULL);
CREATE INDEX reviewed_global_aggregate_authorized_source_bindings_source_idx ON analytics.reviewed_global_aggregate_authorized_source_bindings USING btree (independent_source_key, valid_from, valid_until);
ALTER TABLE analytics.reviewed_global_aggregate_independent_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics.reviewed_global_aggregate_authorized_source_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics.reviewed_global_aggregate_input_admissions ENABLE ROW LEVEL SECURITY;
"""


def bridge_dump(
    *, reverse_copy_order: bool = False, include_authorized_rows: bool = True
) -> bytes:
    binding_row = (
        b"reviewed-binding-one\t"
        + b"b" * 64
        + b"\t"
        + b"c" * 64
        + b"\tpublic-study-comicbook-v1\tauthorization-contract-v1\t"
        + b"d" * 64
        + b"\t2026-01-01 00:00:00+00\t\\N\t2026-09-03 00:00:00+00"
    )
    public_admission = (
        b"reviewed-admission-public\tpublic_study\tpublic-study-one\t\\N\t\\N\t"
        + b"e" * 64
        + b"\tadmission-contract-v1\t"
        + b"f" * 64
        + b"\t2026-09-03 00:00:00+00"
    )
    authorized_admission = (
        b"reviewed-admission-authorized\tauthorized_opening\t\\N\t"
        b"11111111-1111-4111-8111-111111111111\treviewed-binding-one\t"
        + b"1" * 64
        + b"\tadmission-contract-v1\t"
        + b"2" * 64
        + b"\t2026-09-03 00:00:00+00"
    )
    policies = copy_block(
        "ingest.source_policies",
        "id, source_key",
        b"33333333-3333-4333-8333-333333333333\ttcgdex_catalog",
    )
    binding_rows = (binding_row,) if include_authorized_rows else ()
    admission_rows = (
        (public_admission, authorized_admission) if include_authorized_rows else ()
    )
    blocks = [
        copy_block(SOURCE_TABLE, SOURCE_COLUMNS, *SOURCE_SEED_ROWS),
        copy_block(BINDING_TABLE, BINDING_COLUMNS, *binding_rows),
        copy_block(ADMISSION_TABLE, ADMISSION_COLUMNS, *admission_rows),
    ]
    if reverse_copy_order:
        blocks.reverse()
    return b"\n".join(
        (
            b"-- fixture start",
            GATE_DDL,
            SOURCE_DDL,
            BINDING_DDL,
            ADMISSION_DDL,
            policies,
            *blocks,
            bridge_alters(),
            b"-- fixture end",
            b"",
        )
    )


class ReviewedGlobalAggregateBackupTests(unittest.TestCase):
    def run_sanitizer(
        self, dump: bytes, *, bridge: str = "present"
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [
                "python3",
                str(SANITIZER),
                "--source-policies",
                "present",
                "--youtube-discoveries",
                "absent",
                "--public-studies",
                "absent",
                "--bluesky-jetstream",
                "absent",
                "--nostr-relay",
                "absent",
                "--mastodon-public-hashtag",
                "absent",
                "--reviewed-global-aggregate-bridge",
                bridge,
            ],
            input=dump,
            capture_output=True,
            check=False,
        )

    def assert_rejected(
        self, dump: bytes, *, bridge: str = "present", marker: bytes | None = None
    ) -> None:
        result = self.run_sanitizer(dump, bridge=bridge)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        if marker is not None:
            self.assertNotIn(marker, result.stderr)

    def test_retains_exact_private_bridge_bundle_in_any_copy_order(self) -> None:
        for reverse_copy_order in (False, True):
            with self.subTest(reverse_copy_order=reverse_copy_order):
                result = self.run_sanitizer(
                    bridge_dump(reverse_copy_order=reverse_copy_order)
                )
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertIn(f"COPY {SOURCE_TABLE}".encode(), result.stdout)
                self.assertIn(f"COPY {BINDING_TABLE}".encode(), result.stdout)
                self.assertIn(f"COPY {ADMISSION_TABLE}".encode(), result.stdout)
                self.assertIn(b"reviewed-admission-authorized", result.stdout)
                self.assertNotIn(
                    b"COPY ingest.source_request_gates (owner_job_id", result.stdout
                )

    def test_retains_empty_binding_and_admission_ledgers(self) -> None:
        result = self.run_sanitizer(bridge_dump(include_authorized_rows=False))
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(
            f"COPY {BINDING_TABLE} ({BINDING_COLUMNS}) FROM stdin;\n\\.\n".encode(),
            result.stdout,
        )
        self.assertIn(
            f"COPY {ADMISSION_TABLE} ({ADMISSION_COLUMNS}) FROM stdin;\n\\.\n".encode(),
            result.stdout,
        )

    def test_preflight_and_dump_bridge_presence_must_match(self) -> None:
        dump = bridge_dump()
        self.assert_rejected(dump, bridge="absent")
        source_header = f"COPY {SOURCE_TABLE}".encode()
        source_start = dump.index(source_header)
        source_end = dump.index(b"\\.\n", source_start) + len(b"\\.\n")
        self.assert_rejected(
            dump[:source_start] + dump[source_end:],
        )

    def test_schema_headers_rls_constraints_and_indexes_are_fail_closed(self) -> None:
        dump = bridge_dump()
        cases = {
            "unlogged": dump.replace(
                b"CREATE TABLE analytics.reviewed_global_aggregate_independent_sources",
                b"CREATE UNLOGGED TABLE analytics.reviewed_global_aggregate_independent_sources",
                1,
            ),
            "extra-column": dump.replace(
                b"    created_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,\n"
                b"    CONSTRAINT reviewed_global_aggregate_independent_sources_key_check",
                b"    created_at timestamp with time zone DEFAULT statement_timestamp() NOT NULL,\n"
                b"    private_marker text,\n"
                b"    CONSTRAINT reviewed_global_aggregate_independent_sources_key_check",
                1,
            ),
            "missing-force-rls": dump.replace(
                b"ALTER TABLE ONLY analytics.reviewed_global_aggregate_authorized_source_bindings FORCE ROW LEVEL SECURITY;\n",
                b"",
                1,
            ),
            "wrong-constraint": dump.replace(
                b"UNIQUE (canonical_domain);",
                b"UNIQUE (domain_contract_sha256);",
                1,
            ),
            "wrong-stable-constraint-name": dump.replace(
                b"rga_asb_source_auth_key",
                b"reviewed_global_aggregate_authorized_source_bindings_identity_authorization_key",
                1,
            ),
            "wrong-stable-check-name": dump.replace(
                b"rga_asb_contract_check",
                b"reviewed_global_aggregate_authorized_source_bindings_contract_check",
                1,
            ),
            "weakened-domain-length-check": dump.replace(
                b"char_length(canonical_domain) BETWEEN 3 AND 253",
                b"char_length(canonical_domain) >= 1",
                1,
            ),
            "weakened-domain-regex-check": dump.replace(
                b"canonical_domain ~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$'",
                b"canonical_domain ~ '.*'",
                1,
            ),
            "weakened-public-study-regex-check": dump.replace(
                b"public_study_key ~ '^[a-z0-9][a-z0-9-]{0,119}$'",
                b"public_study_key ~ '.*'",
                1,
            ),
            "missing-partial-index": dump.replace(
                b"CREATE UNIQUE INDEX reviewed_global_aggregate_input_admissions_study_uq ON analytics.reviewed_global_aggregate_input_admissions USING btree (public_study_key) WHERE (public_study_key IS NOT NULL);\n",
                b"",
                1,
            ),
            "bridge-policy": dump
            + b"CREATE POLICY bridge_read ON analytics.reviewed_global_aggregate_input_admissions FOR SELECT TO service_role USING (true);\n",
        }
        for name, candidate in cases.items():
            with self.subTest(name=name):
                self.assert_rejected(candidate, marker=b"private_marker")

    def test_rows_and_cross_table_closure_are_fail_closed(self) -> None:
        dump = bridge_dump()
        cases = {
            "noncanonical-domain": dump.replace(
                b"comicbook.com", b"ComicBook.COM", 1
            ),
            "drifted-source-seed": dump.replace(
                b"comicbook.com", b"comicbooks.com", 1
            ),
            "raw-contract-value": dump.replace(
                b"reviewed-public-study-domain-v1", b"private raw contract text", 1
            ),
            "bad-hash": dump.replace(
                b"203fb8576dd77f4e5d8b0da5436007697aecaeaf521df66b541a1ecaf22bac7d",
                b"private-marker" + b"x" * 50,
                1,
            ),
            "duplicate-source": dump.replace(
                b"\\.\n\nCOPY analytics.reviewed_global_aggregate_authorized_source_bindings",
                b"\npublic-study-comicbook-v1\texample.org\t"
                b"reviewed-public-study-domain-v1\t"
                + b"3" * 64
                + b"\t2026-09-03 00:00:00+00\n\\.\n\nCOPY analytics.reviewed_global_aggregate_authorized_source_bindings",
                1,
            ),
            "orphan-binding": dump.replace(
                b"public-study-comicbook-v1\tauthorization-contract-v1",
                b"missing-source\tauthorization-contract-v1",
                1,
            ),
            "inverted-window": dump.replace(
                b"2026-01-01 00:00:00+00\t\\N\t2026-09-03",
                b"2026-01-01 00:00:00+00\t2025-12-31 00:00:00+00\t2026-09-03",
                1,
            ),
            "bad-public-shape": dump.replace(
                b"public-study-one\t\\N\t\\N\t" + b"e" * 64,
                b"public-study-one\t11111111-1111-4111-8111-111111111111\t\\N\t"
                + b"e" * 64,
                1,
            ),
            "bad-public-study-key": dump.replace(
                b"public-study-one\t\\N\t\\N\t",
                b"public_study_one\t\\N\t\\N\t",
                1,
            ),
            "orphan-admission": dump.replace(
                b"reviewed-binding-one\t" + b"1" * 64,
                b"missing-binding\t" + b"1" * 64,
                1,
            ),
            "duplicate-fingerprint": dump.replace(
                b"reviewed-binding-one\t"
                + b"1" * 64
                + b"\tadmission-contract-v1",
                b"reviewed-binding-one\t"
                + b"e" * 64
                + b"\tadmission-contract-v1",
                1,
            ),
            "missing-source-seed": dump.replace(
                SOURCE_SEED_ROWS[-1] + b"\n", b"", 1
            ),
        }
        for name, candidate in cases.items():
            with self.subTest(name=name):
                self.assert_rejected(candidate, marker=b"private-marker")

    def test_admission_key_accepts_its_exact_160_character_boundary(self) -> None:
        max_length_key = b"a" + b"b" * 159
        result = self.run_sanitizer(
            bridge_dump().replace(b"reviewed-admission-public", max_length_key, 1)
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_analytics_target_data_cannot_bypass_copy_validation(self) -> None:
        dump = bridge_dump()
        cases = (
            b"INSERT INTO analytics.reviewed_global_aggregate_input_admissions "
            b"(admission_key) VALUES ('private-marker');\n",
            b"WITH harmless AS (SELECT 1) INSERT INTO analytics.reviewed_global_aggregate_authorized_source_bindings "
            b"(binding_key) VALUES ('private-marker');\n",
            b"SET search_path = analytics;\nINSERT INTO reviewed_global_aggregate_independent_sources "
            b"(source_key) VALUES ('private-marker');\n",
            b'INSERT /* split */ INTO "analytics"."reviewed_global_aggregate_input_admissions" '
            b"(admission_key) VALUES ('private-marker');\n",
        )
        for statement in cases:
            with self.subTest(statement=statement):
                self.assert_rejected(dump + statement, marker=b"private-marker")


if __name__ == "__main__":
    unittest.main()
