from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SANITIZER = REPOSITORY_ROOT / "deploy" / "lib" / "sanitize_plain_backup.py"
POLICY = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TAG_KEYS = (
    "pokemontcg",
    "pokemoncards",
    "pokeca_ja",
    "pokemon_card_ja",
    "pokemon_card_ko",
    "pokemon_card_zh_hans",
    "pokemon_card_zh_hant",
)
GATE_DDL = b"""CREATE TABLE ingest.source_request_gates (
    source_key text NOT NULL,
    owner_job_id uuid,
    owner_lease_generation bigint,
    acquired_at timestamp with time zone,
    active_until timestamp with time zone,
    CONSTRAINT source_request_gates_owner_check CHECK ((((owner_job_id IS NULL) AND (owner_lease_generation IS NULL) AND (acquired_at IS NULL) AND (active_until IS NULL)) OR ((owner_job_id IS NOT NULL) AND (owner_lease_generation >= 1) AND (acquired_at IS NOT NULL) AND (active_until > acquired_at)))),
    CONSTRAINT source_request_gates_source_check CHECK ((source_key ~ '^[a-z0-9][a-z0-9_-]{0,62}$'::text))
);
ALTER TABLE ONLY ingest.source_request_gates FORCE ROW LEVEL SECURITY;
ALTER TABLE ONLY ingest.source_request_gates
    ADD CONSTRAINT source_request_gates_pkey PRIMARY KEY (source_key);
ALTER TABLE ingest.source_request_gates ENABLE ROW LEVEL SECURITY;
"""


def copy_block(table: str, columns: str, *rows: bytes) -> bytes:
    return b"\n".join(
        (f"COPY {table} ({columns}) FROM stdin;".encode(), *rows, b"\\.", b"")
    )


def mastodon_dump(
    *, include_activity: bool = False, omit_tag: str | None = None
) -> bytes:
    policies = copy_block(
        "ingest.source_policies",
        "id, source_key",
        b"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb\ttcgdex_catalog",
        f"{POLICY}\tmastodon_social".encode(),
    )
    checkpoint_rows = []
    for tag_key in TAG_KEYS:
        if tag_key == omit_tag:
            continue
        checkpoint_rows.append(
            (
                f"{POLICY}\tmastodon_social\t{tag_key}\topaque-001\t"
                "2026-08-30 00:00:00+00\tf\t1\t2\t2048\t1\tf\t"
                "2026-08-29 00:00:00+00\t2026-08-30 00:00:00+00"
            ).encode()
        )
    checkpoints = copy_block(
        "ingest.mastodon_public_hashtag_checkpoints",
        "source_policy_id, instance_key, tag_key, last_status_id, last_collected_at, incomplete, requests_seen_total, statuses_seen_total, bytes_seen_total, candidates_seen_total, is_demo, created_at, updated_at",
        *checkpoint_rows,
    )
    cooldown = copy_block(
        "ingest.mastodon_rate_cooldowns",
        "source_policy_id, instance_key, cooldown_until, is_demo, created_at, updated_at",
        f"{POLICY}\tmastodon_social\t2000-01-01 00:00:00+00\tf\t2026-08-29 00:00:00+00\t2026-08-30 00:00:00+00".encode(),
    )
    activity = (
        copy_block(
            "ingest.mastodon_public_hashtag_candidates",
            "source_policy_id, status_key_sha256",
            f"{POLICY}\t{'a' * 64}".encode(),
        )
        if include_activity
        else b""
    )
    return b"\n".join((GATE_DDL, policies, activity, checkpoints, cooldown, b""))


class MastodonBackupRetentionTests(unittest.TestCase):
    def run_sanitizer(
        self,
        dump: bytes,
        *,
        mastodon_public_hashtag: str = "present",
        policy_id: str | None = POLICY,
    ) -> subprocess.CompletedProcess[bytes]:
        command = [
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
            mastodon_public_hashtag,
        ]
        if policy_id is not None:
            command.extend(("--mastodon-policy-id", policy_id))
        return subprocess.run(command, input=dump, capture_output=True, check=False)

    def test_retains_only_exact_checkpoints_and_shared_cooldown(self) -> None:
        result = self.run_sanitizer(mastodon_dump())
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"COPY ingest.mastodon_public_hashtag_checkpoints", result.stdout)
        self.assertIn(b"COPY ingest.mastodon_rate_cooldowns", result.stdout)
        self.assertIn(b"mastodon_social\n\\.", result.stdout)

        # The sanitizer inserts the source gate only after proving the dump;
        # it retains no live owner fields and seeds one shared idle row.
        self.assertIn(b"mastodon_social\n\\.\n", result.stdout)
        self.assertNotIn(
            b"COPY ingest.source_request_gates (owner_job_id", result.stdout
        )

    def test_candidate_activity_data_is_rejected_if_pg_dump_did_not_exclude_it(
        self,
    ) -> None:
        result = self.run_sanitizer(mastodon_dump(include_activity=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"private activity data must be excluded", result.stderr)

    def test_checkpoint_set_policy_binding_and_opaque_cursor_are_fail_closed(
        self,
    ) -> None:
        for name, dump in {
            "missing-tag": mastodon_dump(omit_tag="pokemon_card_ko"),
            "wrong-instance": mastodon_dump().replace(
                b"mastodon_social\tpokemontcg", b"other_social\tpokemontcg", 1
            ),
            "oversize-cursor": mastodon_dump().replace(b"opaque-001", b"x" * 161, 1),
            "wrong-policy": mastodon_dump().replace(
                POLICY.encode(),
                b"c" * 8 + b"-" + b"c" * 4 + b"-4ccc-8ccc-" + b"c" * 12,
                1,
            ),
        }.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(dump)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_policy_and_table_presence_must_match(self) -> None:
        result = self.run_sanitizer(
            mastodon_dump(), mastodon_public_hashtag="absent", policy_id=None
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
