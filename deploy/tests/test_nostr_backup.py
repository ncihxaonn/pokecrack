from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SANITIZER = REPOSITORY_ROOT / "deploy" / "lib" / "sanitize_plain_backup.py"

POLICIES = (
    ("11111111-1111-4111-8111-111111111111", "nostr_relay_primal"),
    ("22222222-2222-4222-8222-222222222222", "nostr_relay_nos_lol"),
    ("33333333-3333-4333-8333-333333333333", "nostr_relay_nostr_net"),
)
CHECKPOINTS = (
    (
        POLICIES[0][0],
        "primal",
        "wss://relay.primal.net/",
        "https://relay.primal.net/",
    ),
    (
        POLICIES[1][0],
        "nos_lol",
        "wss://nos.lol/",
        "https://nos.lol/",
    ),
    (
        POLICIES[2][0],
        "nostr_net",
        "wss://relay.nostr.net/",
        "https://relay.nostr.net/",
    ),
)
APPROVED_TAGS = (
    "{pokemontcg,PokemonTCG,pokemoncards,PokemonCards,"
    "ポケカ,ポケモンカード,포켓몬카드,宝可梦卡牌,寶可夢卡牌}"
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


def copy_block(table: str, columns: str, *rows: bytes) -> bytes:
    return b"\n".join(
        (f"COPY {table} ({columns}) FROM stdin;".encode(), *rows, b"\\.", b"")
    )


def nostr_dump(*, include_activity: bool = False, omit_checkpoint: str | None = None) -> bytes:
    policies = copy_block(
        "ingest.source_policies",
        "id, source_key",
        b"33333333-3333-4333-8333-333333333333\ttcgdex_catalog",
        *(f"{policy_id}\t{source_key}".encode() for policy_id, source_key in POLICIES),
    )
    rows = []
    for policy_id, relay_key, endpoint, nip11_url in CHECKPOINTS:
        if relay_key == omit_checkpoint:
            continue
        rows.append(
            "\t".join(
                (
                    policy_id,
                    relay_key,
                    endpoint,
                    nip11_url,
                    "nip01",
                    APPROVED_TAGS,
                    "\\N",
                    "10",
                    "1024",
                    "2",
                    "1",
                    "f",
                    "2026-08-29 00:00:00+00",
                    "2026-08-30 00:00:00+00",
                )
            ).encode()
        )
    checkpoints = copy_block(
        "ingest.nostr_relay_checkpoints",
        "source_policy_id, relay_key, endpoint, nip11_url, protocol, approved_tags, last_checkpoint, events_seen_total, bytes_seen_total, candidates_seen_total, deletions_seen_total, is_demo, created_at, updated_at",
        *rows,
    )
    activity = (
        copy_block(
            "ingest.nostr_relay_candidates",
            "event_id, pubkey, signature, content",
            b"a" * 64 + b"\t" + b"b" * 64 + b"\t" + b"c" * 128 + b"\tprivate",
        )
        if include_activity
        else b""
    )
    return b"\n".join((GATE_DDL, policies, activity, checkpoints, b""))


class NostrBackupRetentionTests(unittest.TestCase):
    def run_sanitizer(
        self,
        dump: bytes,
        *,
        nostr_relay: str = "present",
        policy_ids: tuple[str, ...] = tuple(policy_id for policy_id, _ in POLICIES),
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
            nostr_relay,
        ]
        for policy_id in policy_ids:
            command.extend(("--nostr-policy-id", policy_id))
        return subprocess.run(command, input=dump, capture_output=True, check=False)

    def test_retain_only_three_exact_checkpoints_and_reseed_idle_relays(self) -> None:
        result = self.run_sanitizer(nostr_dump())
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"COPY ingest.nostr_relay_checkpoints", result.stdout)
        self.assertIn(b"primal\nnostr_relay_nos_lol", result.stdout)
        self.assertIn(b"nostr_relay_nostr_net\n\\.\n", result.stdout)
        self.assertNotIn(b"event_id", result.stdout)
        self.assertNotIn(b"pubkey", result.stdout)
        self.assertNotIn(b"signature", result.stdout)

    def test_candidate_and_observation_rows_are_rejected_if_dump_excludes_fail(self) -> None:
        result = self.run_sanitizer(nostr_dump(include_activity=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"private activity data must be excluded", result.stderr)

    def test_checkpoint_set_must_be_exactly_three_and_bound_to_preflight_ids(self) -> None:
        missing = self.run_sanitizer(nostr_dump(omit_checkpoint="nos_lol"))
        self.assertNotEqual(missing.returncode, 0)
        mismatch = self.run_sanitizer(
            nostr_dump(),
            policy_ids=(POLICIES[1][0], POLICIES[0][0], POLICIES[2][0]),
        )
        self.assertNotEqual(mismatch.returncode, 0)

    def test_checkpoint_binding_and_counters_are_fail_closed(self) -> None:
        dump = nostr_dump()
        cases = {
            "wrong-endpoint": dump.replace(
                b"wss://relay.primal.net/", b"wss://relay.example.invalid/", 1
            ),
            "wrong-nip11-url": dump.replace(
                b"https://relay.primal.net/", b"https://relay.example.invalid/", 1
            ),
            "wrong-tags": dump.replace(b"PokemonTCG", b"PokemonSpam", 1),
            "negative-counter": dump.replace(b"\t10\t1024", b"\t-1\t1024", 1),
            "demo-row": dump.replace(b"\t1\tf\t2026-08-29", b"\t1\tt\t2026-08-29", 1),
        }
        for name, candidate in cases.items():
            with self.subTest(name=name):
                result = self.run_sanitizer(candidate)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_nostr_policy_without_private_tables_fails_closed(self) -> None:
        result = self.run_sanitizer(nostr_dump(), nostr_relay="absent", policy_ids=())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
