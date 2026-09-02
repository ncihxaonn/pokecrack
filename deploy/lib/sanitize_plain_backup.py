#!/usr/bin/env python3
"""Sanitize retention-controlled state in a plain PostgreSQL dump.

The backup entrypoint invokes this program between ``pg_dump`` and ``gzip``.
It deliberately supports only the stable, line-oriented ``COPY ... FROM
stdin`` representation emitted by the repository's fixed pg_dump command.
Unexpected structure is an error: a partial pipeline output must never be
promoted to a managed backup.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID

SOURCE_POLICIES = ("ingest", "source_policies")
YOUTUBE_DISCOVERIES = ("ingest", "youtube_discoveries")
PUBLIC_STUDY_OBSERVATIONS = ("ingest", "public_study_observations")
SOURCE_REQUEST_GATES = ("ingest", "source_request_gates")
BLUESKY_CANDIDATES = ("ingest", "bluesky_jetstream_candidates")
BLUESKY_OBSERVATIONS = ("ingest", "bluesky_jetstream_observations")
BLUESKY_CHECKPOINTS = ("ingest", "bluesky_jetstream_checkpoints")
NOSTR_CANDIDATES = ("ingest", "nostr_relay_candidates")
NOSTR_OBSERVATIONS = ("ingest", "nostr_relay_observations")
NOSTR_CHECKPOINTS = ("ingest", "nostr_relay_checkpoints")
MASTODON_CANDIDATES = ("ingest", "mastodon_public_hashtag_candidates")
MASTODON_OBSERVATIONS = ("ingest", "mastodon_public_hashtag_observations")
MASTODON_CHECKPOINTS = ("ingest", "mastodon_public_hashtag_checkpoints")
MASTODON_COOLDOWNS = ("ingest", "mastodon_rate_cooldowns")
REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCES = (
    "analytics",
    "reviewed_global_aggregate_independent_sources",
)
REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS = (
    "analytics",
    "reviewed_global_aggregate_authorized_source_bindings",
)
REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS = (
    "analytics",
    "reviewed_global_aggregate_input_admissions",
)
REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES = frozenset(
    {
        REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCES,
        REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS,
        REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS,
    }
)
BLUESKY_EPHEMERAL_TABLES = frozenset({BLUESKY_CANDIDATES, BLUESKY_OBSERVATIONS})
NOSTR_EPHEMERAL_TABLES = frozenset({NOSTR_CANDIDATES, NOSTR_OBSERVATIONS})
MASTODON_EPHEMERAL_TABLES = frozenset({MASTODON_CANDIDATES, MASTODON_OBSERVATIONS})
EPHEMERAL_ACTIVITY_TABLES = (
    BLUESKY_EPHEMERAL_TABLES | NOSTR_EPHEMERAL_TABLES | MASTODON_EPHEMERAL_TABLES
)
RETENTION_CONTROL_TABLES = frozenset(
    {
        SOURCE_POLICIES,
        YOUTUBE_DISCOVERIES,
        PUBLIC_STUDY_OBSERVATIONS,
        BLUESKY_CHECKPOINTS,
        NOSTR_CHECKPOINTS,
        MASTODON_CHECKPOINTS,
        MASTODON_COOLDOWNS,
        *REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES,
    }
)
TCGDEX_SOURCE_KEY = b"tcgdex_catalog"
YOUTUBE_SOURCE_KEY = b"youtube_discovery"
BLUESKY_SOURCE_KEY = b"bluesky_jetstream"
MASTODON_SOURCE_KEY = b"mastodon_social"
NOSTR_SOURCE_KEYS = (
    b"nostr_relay_primal",
    b"nostr_relay_nos_lol",
    b"nostr_relay_nostr_net",
)
NOSTR_RELAY_KEYS = (b"primal", b"nos_lol", b"nostr_net")
NOSTR_ENDPOINTS = (
    b"wss://relay.primal.net/",
    b"wss://nos.lol/",
    b"wss://relay.nostr.net/",
)
NOSTR_NIP11_URLS = (
    b"https://relay.primal.net/",
    b"https://nos.lol/",
    b"https://relay.nostr.net/",
)
MASTODON_TAG_KEYS = (
    b"pokemontcg",
    b"pokemoncards",
    b"pokeca_ja",
    b"pokemon_card_ja",
    b"pokemon_card_ko",
    b"pokemon_card_zh_hans",
    b"pokemon_card_zh_hant",
)
NOSTR_APPROVED_TAGS_COPY = (
    b"{"
    b"pokemontcg,PokemonTCG,pokemoncards,PokemonCards,"
    b"\xe3\x83\x9d\xe3\x82\xb1\xe3\x82\xab,"
    b"\xe3\x83\x9d\xe3\x82\xb1\xe3\x83\xa2\xe3\x83\xb3\xe3\x82\xab\xe3\x83\xbc\xe3\x83\x89,"
    b"\xed\x8f\xac\xec\xbc\x93\xeb\xaa\xac\xec\xb9\xb4\xeb\x93\x9c,"
    b"\xe5\xae\x9d\xe5\x8f\xaf\xe6\xa2\xa6\xe5\x8d\xa1\xe7\x89\x8c,"
    b"\xe5\xaf\xb6\xe5\x8f\xaf\xe5\xa4\xa2\xe5\x8d\xa1\xe7\x89\x8c"
    b"}"
)
NOSTR_PROTOCOL = b"nip01"
PUBLIC_STUDY_SOURCE_KEYS = (
    b"public_study_comicbook_us_55",
    b"public_study_wargamer_gb_17",
    b"public_study_cardchill_gb_90",
    b"public_study_bleedingcool_us_36",
    b"public_study_tcgtalk_sg_54",
)
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*\Z")
COPY_SUFFIX = re.compile(r"FROM\s+stdin;\s*\Z", re.IGNORECASE)
DOLLAR_QUOTE_TAG = re.compile(
    rb"\$(?:[A-Za-z_\x80-\xff][A-Za-z0-9_\x80-\xff]*)?\$"
)
TARGET_TABLES = RETENTION_CONTROL_TABLES | EPHEMERAL_ACTIVITY_TABLES | {
    SOURCE_REQUEST_GATES
}
INGEST_TARGET_TABLE_NAMES = tuple(
    sorted(table[1] for table in TARGET_TABLES if table[0] == "ingest")
)
ANALYTICS_TARGET_TABLE_NAMES = tuple(
    sorted(table[1] for table in TARGET_TABLES if table[0] == "analytics")
)
TARGET_TABLE_NAMES = tuple(sorted(table[1] for table in TARGET_TABLES))


def _target_table_reference(table_names: tuple[str, ...]) -> str:
    unquoted = (
        r"(?:"
        + "|".join(re.escape(name) for name in table_names)
        + r")(?![A-Za-z0-9_$\x80-\xff])"
    )
    quoted = r'(?:"' + r'"|"'.join(re.escape(name) for name in table_names) + r'")'
    return rf"(?:{unquoted}|{quoted})"


def _schema_target_table_reference(schema: str, table_names: tuple[str, ...]) -> str:
    schema_reference = rf'(?:{re.escape(schema)}|"{re.escape(schema)}")'
    return (
        rf"(?:(?:{schema_reference}\s*\.\s*)?"
        rf"{_target_table_reference(table_names)})"
    )


TARGET_TABLE_REFERENCE = rf"(?:{_schema_target_table_reference('ingest', INGEST_TARGET_TABLE_NAMES)}|{_schema_target_table_reference('analytics', ANALYTICS_TARGET_TABLE_NAMES)})"
TARGET_INSERT = re.compile(
    r"^\s*INSERT\s+INTO\s+(?:ONLY\s+)?" + TARGET_TABLE_REFERENCE,
    re.IGNORECASE,
)
TARGET_DATA_STATEMENT = re.compile(
    rb'(?:^|[\s;)])(?:INSERT\s+INTO\s+(?:ONLY\s+)?|'
    rb'COPY\s+(?:BINARY\s+)?)'
    + TARGET_TABLE_REFERENCE.encode("ascii"),
    re.IGNORECASE,
)
ANY_COPY_STATEMENT_PREFIX = re.compile(rb"^\s*COPY\b", re.IGNORECASE)
DO_STATEMENT_PREFIX = re.compile(rb"^\s*DO(?:\s|$)", re.IGNORECASE)
MAX_SQL_STATEMENT_PREFIX_BYTES = 65_536
UNQUALIFIED_TARGET_TABLES = frozenset(TARGET_TABLE_NAMES)


@dataclass
class SqlLexState:
    mode: str = "normal"
    dollar_tag: bytes | None = None
    block_comment_depth: int = 0
    single_quote_backslash_escapes: bool = False
    statement_sql: bytearray = field(default_factory=bytearray)


def _is_identifier_byte(value: int) -> bool:
    return (
        ord("0") <= value <= ord("9")
        or ord("A") <= value <= ord("Z")
        or ord("a") <= value <= ord("z")
        or value in (ord("_"), ord("$"))
        or value >= 0x80
    )


def _append_statement_bytes(state: SqlLexState, value: bytes) -> None:
    if len(state.statement_sql) + len(value) > MAX_SQL_STATEMENT_PREFIX_BYTES:
        raise SanitizationError("SQL statement prefix exceeds the safety limit")
    state.statement_sql.extend(value)


def _append_statement_space(state: SqlLexState) -> None:
    if not state.statement_sql or state.statement_sql[-1] != ord(" "):
        _append_statement_bytes(state, b" ")


def _reject_target_statement_prefix(state: SqlLexState) -> None:
    statement = bytes(state.statement_sql)
    if DO_STATEMENT_PREFIX.match(statement):
        raise SanitizationError(
            "executable DO bodies are not supported in managed backups"
        )
    if TARGET_DATA_STATEMENT.search(statement):
        raise SanitizationError(
            "retention-control table data must use COPY FROM stdin"
        )
    if ANY_COPY_STATEMENT_PREFIX.match(statement):
        raise SanitizationError(
            "COPY headers must use the supported line-oriented pg_dump shape"
        )


def _finish_sql_statement(state: SqlLexState) -> None:
    _reject_target_statement_prefix(state)
    state.statement_sql.clear()


def _advance_sql_lex_state(line: bytes, state: SqlLexState) -> None:
    """Track SQL lexical context around PostgreSQL dollar-quoted bodies.

    The scanner recognizes dollar delimiters only in normal SQL, never inside
    ordinary strings, quoted identifiers, or comments. It retains only the
    normal-context statement prefix so comments and line breaks cannot split a
    protected ``INSERT INTO`` or ``COPY`` target across scanner boundaries.
    """

    index = 0
    while index < len(line):
        if state.mode == "dollar":
            assert state.dollar_tag is not None
            closing_at = line.find(state.dollar_tag, index)
            if closing_at < 0:
                return
            index = closing_at + len(state.dollar_tag)
            state.mode = "normal"
            state.dollar_tag = None
            continue

        if state.mode == "single_quote":
            if (
                state.single_quote_backslash_escapes
                and line[index] == ord("\\")
                and index + 1 < len(line)
            ):
                index += 2
            elif line[index] == ord("'"):
                if index + 1 < len(line) and line[index + 1] == ord("'"):
                    index += 2
                else:
                    state.mode = "normal"
                    state.single_quote_backslash_escapes = False
                    index += 1
            else:
                index += 1
            continue

        if state.mode == "double_quote":
            if line[index] == ord('"'):
                if index + 1 < len(line) and line[index + 1] == ord('"'):
                    _append_statement_bytes(state, b'""')
                    index += 2
                else:
                    _append_statement_bytes(state, b'"')
                    state.mode = "normal"
                    index += 1
            else:
                _append_statement_bytes(state, line[index : index + 1])
                index += 1
            continue

        if state.mode == "block_comment":
            if line[index : index + 2] == b"/*":
                state.block_comment_depth += 1
                index += 2
            elif line[index : index + 2] == b"*/":
                state.block_comment_depth -= 1
                index += 2
                if state.block_comment_depth == 0:
                    state.mode = "normal"
            else:
                index += 1
            continue

        if line[index : index + 2] == b"--":
            _append_statement_space(state)
            _reject_target_statement_prefix(state)
            return
        if line[index : index + 2] == b"/*":
            _append_statement_space(state)
            state.mode = "block_comment"
            state.block_comment_depth = 1
            index += 2
            continue
        if line[index] == ord("'"):
            _append_statement_space(state)
            state.mode = "single_quote"
            state.single_quote_backslash_escapes = (
                index > 0
                and line[index - 1] in (ord("E"), ord("e"))
                and (index < 2 or not _is_identifier_byte(line[index - 2]))
            )
            index += 1
            continue
        if line[index] == ord('"'):
            _append_statement_bytes(state, b'"')
            state.mode = "double_quote"
            index += 1
            continue

        opening = DOLLAR_QUOTE_TAG.match(line, index)
        if opening is not None and (
            index == 0 or not _is_identifier_byte(line[index - 1])
        ):
            _append_statement_space(state)
            _reject_target_statement_prefix(state)
            state.mode = "dollar"
            state.dollar_tag = opening.group(0)
            index = opening.end()
            continue

        if line[index] == ord(";"):
            _finish_sql_statement(state)
            index += 1
            continue
        if line[index] in b" \t\r\n\f\v":
            _append_statement_space(state)
            index += 1
            continue
        _append_statement_bytes(state, line[index : index + 1])
        index += 1

    _reject_target_statement_prefix(state)


YOUTUBE_CREATE_REFERENCE = re.compile(
    r"^\s*CREATE\s+(?:(?:UNLOGGED|TEMP|TEMPORARY)\s+)?TABLE\s+"
    r'(?:ingest(?![A-Za-z0-9_$])|"ingest")\s*\.\s*'
    r'(?:youtube_discoveries(?![A-Za-z0-9_$])|"youtube_discoveries")'
    r"(?:\s|\()",
    re.IGNORECASE,
)
YOUTUBE_CREATE = re.compile(
    r"^\s*CREATE\s+(?P<unlogged>UNLOGGED\s+)?TABLE\s+"
    r'(?:ingest(?![A-Za-z0-9_$])|"ingest")\s*\.\s*'
    r'(?:youtube_discoveries(?![A-Za-z0-9_$])|"youtube_discoveries")\s*\(',
    re.IGNORECASE,
)
REQUEST_GATES_CREATE_REFERENCE = re.compile(
    r"^\s*CREATE\s+(?:(?:UNLOGGED|TEMP|TEMPORARY)\s+)?TABLE\s+"
    r'(?:ingest(?![A-Za-z0-9_$])|"ingest")\s*\.\s*'
    r'(?:source_request_gates(?![A-Za-z0-9_$])|"source_request_gates")'
    r"(?:\s|\()",
    re.IGNORECASE,
)
REQUEST_GATES_CREATE = re.compile(
    r"^\s*CREATE\s+TABLE\s+"
    r'(?:ingest(?![A-Za-z0-9_$])|"ingest")\s*\.\s*'
    r'(?:source_request_gates(?![A-Za-z0-9_$])|"source_request_gates")\s*\(',
    re.IGNORECASE,
)
PUBLIC_STUDY_CREATE_REFERENCE = re.compile(
    r"^\s*CREATE\s+(?:(?:UNLOGGED|TEMP|TEMPORARY)\s+)?TABLE\s+"
    r'(?:ingest(?![A-Za-z0-9_$])|"ingest")\s*\.\s*'
    r'(?:public_study_observations(?![A-Za-z0-9_$])|"public_study_observations")'
    r"(?:\s|\()",
    re.IGNORECASE,
)
PUBLIC_STUDY_CREATE = re.compile(
    r"^\s*CREATE\s+TABLE\s+"
    r'(?:ingest(?![A-Za-z0-9_$])|"ingest")\s*\.\s*'
    r'(?:public_study_observations(?![A-Za-z0-9_$])|"public_study_observations")\s*\(',
    re.IGNORECASE,
)


def _aggregate_bridge_table_expression(table: tuple[str, str]) -> str:
    schema, name = table
    return (
        rf'(?:{re.escape(schema)}(?![A-Za-z0-9_$])|"{re.escape(schema)}")'
        rf"\s*\.\s*"
        rf'(?:{re.escape(name)}(?![A-Za-z0-9_$])|"{re.escape(name)}")'
    )


REVIEWED_GLOBAL_AGGREGATE_BRIDGE_CREATE_REFERENCE = {
    table: re.compile(
        r"^\s*CREATE\s+(?:(?:UNLOGGED|TEMP|TEMPORARY)\s+)?TABLE\s+"
        + _aggregate_bridge_table_expression(table)
        + r"(?:\s|\()",
        re.IGNORECASE,
    )
    for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES
}
REVIEWED_GLOBAL_AGGREGATE_BRIDGE_CREATE = {
    table: re.compile(
        r"^\s*CREATE\s+TABLE\s+"
        + _aggregate_bridge_table_expression(table)
        + r"\s*\(",
        re.IGNORECASE,
    )
    for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES
}
PUBLIC_STUDY_COPY_COLUMNS = (
    "study_key",
    "source_policy_id",
    "source_item_id",
    "extraction_run_id",
    "opening_id",
    "country_code",
    "country_name",
    "geography_basis",
    "geography_confidence",
    "source_observed_at",
    "pack_count",
    "qualifying_hit_pack_count",
    "set_external_id",
    "product_scope",
    "metric_key",
    "metric_version",
    "collector_version",
    "parser_version",
    "source_policy_version",
    "evidence_sha256",
    "first_verified_at",
    "last_verified_at",
    "is_demo",
)
BLUESKY_CHECKPOINT_COPY_COLUMNS = (
    "source_policy_id",
    "endpoint",
    "protocol",
    "collection",
    "last_cursor",
    "last_collected_at",
    "events_seen_total",
    "bytes_seen_total",
    "candidates_seen_total",
    "deletions_seen_total",
    "is_demo",
    "created_at",
    "updated_at",
)
# The Nostr migration deliberately retains only one checkpoint row per relay.
# Candidate/observation rows are excluded from logical backups.  Keep this
# inventory exact so a future schema cannot accidentally retain raw activity.
NOSTR_CHECKPOINT_COPY_COLUMNS = (
    "source_policy_id",
    "relay_key",
    "endpoint",
    "nip11_url",
    "protocol",
    "approved_tags",
    "last_checkpoint",
    "events_seen_total",
    "bytes_seen_total",
    "candidates_seen_total",
    "deletions_seen_total",
    "is_demo",
    "created_at",
    "updated_at",
)
MASTODON_CHECKPOINT_COPY_COLUMNS = (
    "source_policy_id",
    "instance_key",
    "tag_key",
    "last_status_id",
    "last_collected_at",
    "incomplete",
    "requests_seen_total",
    "statuses_seen_total",
    "bytes_seen_total",
    "candidates_seen_total",
    "is_demo",
    "created_at",
    "updated_at",
)
MASTODON_COOLDOWN_COPY_COLUMNS = (
    "source_policy_id",
    "instance_key",
    "cooldown_until",
    "is_demo",
    "created_at",
    "updated_at",
)
REVIEWED_GLOBAL_AGGREGATE_BRIDGE_COPY_COLUMNS = {
    REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCES: (
        "source_key",
        "canonical_domain",
        "domain_contract_version",
        "domain_contract_sha256",
        "created_at",
    ),
    REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS: (
        "binding_key",
        "source_identity_sha256",
        "authorization_reference_sha256",
        "independent_source_key",
        "authorization_contract_version",
        "authorization_contract_sha256",
        "valid_from",
        "valid_until",
        "created_at",
    ),
    REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS: (
        "admission_key",
        "input_kind",
        "public_study_key",
        "accepted_observation_id",
        "binding_key",
        "canonical_opening_fingerprint_sha256",
        "admission_contract_version",
        "admission_contract_sha256",
        "admitted_at",
    ),
}
REVIEWED_GLOBAL_AGGREGATE_BRIDGE_COLUMN_DECLARATIONS = {
    REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCES: (
        "source_key text not null",
        "canonical_domain text not null",
        "domain_contract_version text not null",
        "domain_contract_sha256 text not null",
        "created_at timestamp with time zone default statement_timestamp() not null",
    ),
    REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS: (
        "binding_key text not null",
        "source_identity_sha256 text not null",
        "authorization_reference_sha256 text not null",
        "independent_source_key text not null",
        "authorization_contract_version text not null",
        "authorization_contract_sha256 text not null",
        "valid_from timestamp with time zone not null",
        "valid_until timestamp with time zone",
        "created_at timestamp with time zone default statement_timestamp() not null",
    ),
    REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS: (
        "admission_key text not null",
        "input_kind text not null",
        "public_study_key text",
        "accepted_observation_id uuid",
        "binding_key text",
        "canonical_opening_fingerprint_sha256 text not null",
        "admission_contract_version text not null",
        "admission_contract_sha256 text not null",
        "admitted_at timestamp with time zone default statement_timestamp() not null",
    ),
}
REVIEWED_GLOBAL_AGGREGATE_BRIDGE_CHECK_TOKENS = {
    REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCES: {
        "reviewed_global_aggregate_independent_sources_key_check": (
            "check",
            "source_key",
            "[a-z0-9][a-z0-9._-]{0,119}",
            "btrim(source_key)",
            "normalize(source_key, nfkc)",
            "[[:cntrl:]]",
        ),
        "reviewed_global_aggregate_independent_sources_domain_check": (
            "check",
            "canonical_domain",
            "lower(canonical_domain)",
            "btrim(canonical_domain)",
            "normalize(canonical_domain, nfkc)",
            "char_length(canonical_domain)",
            "between 3 and 253",
            "^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
            "[[:cntrl:]]",
        ),
        "reviewed_global_aggregate_independent_sources_contract_check": (
            "check",
            "domain_contract_version",
            "domain_contract_sha256",
            "[a-z0-9][a-z0-9._-]{0,119}",
            "[0-9a-f]{64}",
        ),
    },
    REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS: {
        "reviewed_global_aggregate_authorized_source_bindings_key_check": (
            "check",
            "binding_key",
            "[a-z0-9][a-z0-9._-]{0,119}",
            "btrim(binding_key)",
            "normalize(binding_key, nfkc)",
            "[[:cntrl:]]",
        ),
        "reviewed_global_aggregate_authorized_source_bindings_hash_check": (
            "check",
            "source_identity_sha256",
            "authorization_reference_sha256",
            "authorization_contract_sha256",
            "[0-9a-f]{64}",
        ),
        "rga_asb_contract_check": (
            "check",
            "authorization_contract_version",
            "[a-z0-9][a-z0-9._-]{0,119}",
            "btrim(authorization_contract_version)",
            "normalize(authorization_contract_version, nfkc)",
            "[[:cntrl:]]",
        ),
        "rga_asb_window_check": (
            "check",
            "valid_until is null",
            "valid_until >= valid_from",
        ),
    },
    REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS: {
        "reviewed_global_aggregate_input_admissions_key_check": (
            "check",
            "admission_key",
            "[a-z0-9][a-z0-9._-]{0,159}",
            "btrim(admission_key)",
            "normalize(admission_key, nfkc)",
            "[[:cntrl:]]",
        ),
        "reviewed_global_aggregate_input_admissions_kind_check": (
            "check",
            "input_kind = 'public_study'",
            "public_study_key",
            "public_study_key is not null",
            "public_study_key ~ '^[a-z0-9][a-z0-9-]{0,119}$'",
            "accepted_observation_id is null",
            "binding_key is null",
            "input_kind = 'authorized_opening'",
            "accepted_observation_id is not null",
            "binding_key is not null",
        ),
        "reviewed_global_aggregate_input_admissions_hash_check": (
            "check",
            "canonical_opening_fingerprint_sha256",
            "admission_contract_sha256",
            "[0-9a-f]{64}",
        ),
        "reviewed_global_aggregate_input_admissions_contract_check": (
            "check",
            "admission_contract_version",
            "[a-z0-9][a-z0-9._-]{0,119}",
            "btrim(admission_contract_version)",
            "normalize(admission_contract_version, nfkc)",
            "[[:cntrl:]]",
        ),
    },
}
REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCE_SEEDS = frozenset(
    {
        (
            "public-study-comicbook-v1",
            "comicbook.com",
            "reviewed-public-study-domain-v1",
            "203fb8576dd77f4e5d8b0da5436007697aecaeaf521df66b541a1ecaf22bac7d",
        ),
        (
            "public-study-wargamer-v1",
            "www.wargamer.com",
            "reviewed-public-study-domain-v1",
            "841536c8203fa98aefff8e5a5babeec58d8e31ca627109c3fee9fceadd5a2cc1",
        ),
        (
            "public-study-cardchill-v1",
            "cardchill.com",
            "reviewed-public-study-domain-v1",
            "3868dca0a04c840032b85dc958ab96e3b3f8b5821c87a54c3946daadc97b026f",
        ),
        (
            "public-study-bleedingcool-v1",
            "bleedingcool.com",
            "reviewed-public-study-domain-v1",
            "65a31ab7ec173797b1748a3e82ce492da0b4be612bd1e70c02df4549b897efa0",
        ),
        (
            "public-study-tcgtalk-v1",
            "tcgtalk.com",
            "reviewed-public-study-domain-v1",
            "000ef62d275b3452ed34dc337bfc1fda14aa7212a3e8684f6f240dca2a11e858",
        ),
    }
)
REVIEWED_GLOBAL_AGGREGATE_BRIDGE_NAMED_STRUCTURAL_CONSTRAINTS = {
    REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCES: {},
    REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS: {
        "rga_asb_source_auth_key": (
            "unique (source_identity_sha256, authorization_reference_sha256)"
        ),
        "rga_asb_source_key_fkey": (
            "foreign key (independent_source_key) references "
            "analytics.reviewed_global_aggregate_independent_sources(source_key) "
            "on update restrict on delete restrict"
        ),
    },
    REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS: {
        "rga_ia_fingerprint_key": (
            "unique (canonical_opening_fingerprint_sha256)"
        ),
        "rga_ia_observation_fkey": (
            "foreign key (accepted_observation_id) references "
            "ingest.authorized_opening_observations(id) on update restrict "
            "on delete restrict"
        ),
        "rga_ia_binding_key_fkey": (
            "foreign key (binding_key) references "
            "analytics.reviewed_global_aggregate_authorized_source_bindings(binding_key) "
            "on update restrict on delete restrict"
        ),
    },
}
REVIEWED_GLOBAL_AGGREGATE_BRIDGE_ALTER_CONSTRAINTS = {
    REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCES: frozenset(
        {
            "primary key (source_key)",
            "unique (canonical_domain)",
        }
    ),
    REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS: frozenset(
        {
            "primary key (binding_key)",
            "unique (source_identity_sha256, authorization_reference_sha256)",
            "foreign key (independent_source_key) references "
            "analytics.reviewed_global_aggregate_independent_sources(source_key) "
            "on update restrict on delete restrict",
        }
    ),
    REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS: frozenset(
        {
            "primary key (admission_key)",
            "unique (canonical_opening_fingerprint_sha256)",
            "foreign key (accepted_observation_id) references "
            "ingest.authorized_opening_observations(id) on update restrict "
            "on delete restrict",
            "foreign key (binding_key) references "
            "analytics.reviewed_global_aggregate_authorized_source_bindings(binding_key) "
            "on update restrict on delete restrict",
        }
    ),
}
REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSION_INDEXES = frozenset(
    {
        "public_study_key",
        "accepted_observation_id",
    }
)
REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_BINDING_INDEX = "source-window"
SAFE_CONTRACT_KEY = re.compile(r"[a-z0-9][a-z0-9._-]{0,119}\Z")
SAFE_ADMISSION_KEY = re.compile(r"[a-z0-9][a-z0-9._-]{0,159}\Z")
SAFE_PUBLIC_STUDY_KEY = re.compile(r"[a-z0-9][a-z0-9-]{0,119}\Z")
CANONICAL_DOMAIN = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)
LOWERCASE_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PUBLIC_STUDY_COLUMN_DECLARATIONS = (
    "study_key text not null",
    "source_policy_id uuid not null",
    "source_item_id uuid not null",
    "extraction_run_id uuid not null",
    "opening_id uuid not null",
    "country_code text not null",
    "country_name text not null",
    "geography_basis text not null",
    "geography_confidence text not null",
    "source_observed_at timestamp with time zone not null",
    "pack_count integer not null",
    "qualifying_hit_pack_count integer not null",
    "set_external_id text not null",
    "product_scope text not null",
    "metric_key text not null",
    "metric_version text not null",
    "collector_version text not null",
    "parser_version text not null",
    "source_policy_version text not null",
    "evidence_sha256 text not null",
    "first_verified_at timestamp with time zone not null",
    "last_verified_at timestamp with time zone not null",
    "is_demo boolean default false not null",
)
PUBLIC_STUDY_CHECK_DECLARATIONS = frozenset(
    {
        "constraint public_study_observations_country_name_check check (((btrim(country_name) <> ''::text) and (char_length(country_name) <= 160)))",
        "constraint public_study_observations_counts_check check ((((pack_count >= 1) and (pack_count <= 100000)) and ((qualifying_hit_pack_count >= 0) and (qualifying_hit_pack_count <= pack_count))))",
        "constraint public_study_observations_geography_check check (((geography_basis = any (array['publisher_country'::text, 'author_public_residence'::text])) and (geography_confidence = 'tier_b'::text)))",
        "constraint public_study_observations_hash_check check ((evidence_sha256 ~ '^[0-9a-f]{64}$'::text))",
        "constraint public_study_observations_key_check check ((study_key ~ '^[a-z0-9][a-z0-9-]{0,119}$'::text))",
        "constraint public_study_observations_live_only_check check ((not is_demo))",
        "constraint public_study_observations_metric_check check (((metric_key = 'qualifying_hit_pack_rate'::text) and (metric_version = 'global-sir-v1'::text)))",
        "constraint public_study_observations_product_check check ((product_scope = any (array['all'::text, 'booster_box'::text, 'etb'::text, 'booster_bundle'::text])))",
        "constraint public_study_observations_set_check check (((btrim(set_external_id) <> ''::text) and (char_length(set_external_id) <= 160)))",
        "constraint public_study_observations_time_check check ((last_verified_at >= first_verified_at))",
        "constraint public_study_observations_version_check check (((btrim(collector_version) <> ''::text) and (char_length(collector_version) <= 120) and (btrim(parser_version) <> ''::text) and (char_length(parser_version) <= 120) and (btrim(source_policy_version) <> ''::text) and (char_length(source_policy_version) <= 120)))",
    }
)
PUBLIC_STUDY_POLICY_SOURCE_KEY = {
    b"comicbook-perfect-order-us-55-v1": b"public_study_comicbook_us_55",
    b"wargamer-chaos-rising-gb-17-v1": b"public_study_wargamer_gb_17",
}
PUBLIC_STUDY_EXACT_FIELDS = {
    b"comicbook-perfect-order-us-55-v1": {
        "country_code": b"US",
        "country_name": b"United States",
        "geography_basis": b"publisher_country",
        "geography_confidence": b"tier_b",
        "pack_count": b"55",
        "qualifying_hit_pack_count": b"1",
        "set_external_id": b"me03",
        "product_scope": b"all",
        "metric_key": b"qualifying_hit_pack_rate",
        "metric_version": b"global-sir-v1",
        "collector_version": b"public-study-comicbook-perfect-order-v1",
        "parser_version": b"comicbook-perfect-order-evidence-v1",
        "source_policy_version": b"public-study-comicbook-perfect-order-v1",
        "is_demo": b"f",
    },
    b"wargamer-chaos-rising-gb-17-v1": {
        "country_code": b"GB",
        "country_name": b"United Kingdom",
        "geography_basis": b"publisher_country",
        "geography_confidence": b"tier_b",
        "pack_count": b"17",
        "qualifying_hit_pack_count": b"0",
        "set_external_id": b"me04",
        "product_scope": b"all",
        "metric_key": b"qualifying_hit_pack_rate",
        "metric_version": b"global-sir-v1",
        "collector_version": b"public-study-wargamer-chaos-rising-v1",
        "parser_version": b"wargamer-chaos-rising-evidence-v1",
        "source_policy_version": b"public-study-wargamer-chaos-rising-v1",
        "is_demo": b"f",
    },
}
PUBLIC_STUDY_OBSERVED_AT = {
    b"comicbook-perfect-order-us-55-v1": datetime(2026, 3, 19, 21, tzinfo=UTC),
    b"wargamer-chaos-rising-gb-17-v1": datetime(2026, 5, 11, tzinfo=UTC),
}


def _normalize_sql(lines: list[bytes] | tuple[bytes, ...]) -> str:
    try:
        text = b"".join(lines).decode("utf-8")
    except UnicodeDecodeError as error:
        raise SanitizationError("request-gate schema is not UTF-8") from error
    # pg_dump quotes only identifiers that require it. Supporting simple quoted
    # fixture identifiers does not weaken the exact semantic contract below.
    text = re.sub(r'"([A-Za-z_][A-Za-z0-9_$]*)"', r"\1", text)
    return " ".join(text.casefold().split())


REQUEST_GATES_CREATE_COMMON = """CREATE TABLE ingest.source_request_gates (
    source_key text NOT NULL,
    owner_job_id uuid,
    owner_lease_generation bigint,
    acquired_at timestamp with time zone,
    active_until timestamp with time zone,
    CONSTRAINT source_request_gates_owner_check CHECK ((((owner_job_id IS NULL) AND (owner_lease_generation IS NULL) AND (acquired_at IS NULL) AND (active_until IS NULL)) OR ((owner_job_id IS NOT NULL) AND (owner_lease_generation >= 1) AND (acquired_at IS NOT NULL) AND (active_until > acquired_at)))),
    {source_constraint}
);
"""
REQUEST_GATES_CREATE_EXPECTED = {
    False: _normalize_sql(
        (
            REQUEST_GATES_CREATE_COMMON.format(
                source_constraint=(
                    "CONSTRAINT source_request_gates_source_check "
                    "CHECK ((source_key = 'tcgdex_catalog'::text))"
                )
            ).encode("utf-8"),
        )
    ),
    True: _normalize_sql(
        (
            REQUEST_GATES_CREATE_COMMON.format(
                source_constraint=(
                    "CONSTRAINT source_request_gates_source_check CHECK "
                    "((source_key ~ '^[a-z0-9][a-z0-9_-]{0,62}$'::text))"
                )
            ).encode("utf-8"),
        )
    ),
}
REQUEST_GATES_FORCE_RLS = _normalize_sql(
    (b"ALTER TABLE ONLY ingest.source_request_gates FORCE ROW LEVEL SECURITY;\n",)
)
REQUEST_GATES_PRIMARY_KEY = _normalize_sql(
    (
        b"ALTER TABLE ONLY ingest.source_request_gates\n",
        b"    ADD CONSTRAINT source_request_gates_pkey PRIMARY KEY (source_key);\n",
    )
)
REQUEST_GATES_ENABLE_RLS = _normalize_sql(
    (b"ALTER TABLE ingest.source_request_gates ENABLE ROW LEVEL SECURITY;\n",)
)
POLICY_STATEMENT_PREFIXES = (
    "create policy ",
    "alter policy ",
    "drop policy ",
    "comment on policy ",
)
POLICY_DOLLAR_QUOTE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")


class SanitizationError(ValueError):
    """The dump cannot be proved safe to retain."""


PolicyToken = tuple[str, str]


def _only_sql_trivia(text: str, start: int) -> bool:
    index = start
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        if text.startswith("--", index):
            newline = text.find("\n", index + 2)
            if newline < 0:
                return True
            index = newline + 1
            continue
        if text.startswith("/*", index):
            depth = 1
            index += 2
            while index < len(text) and depth:
                if text.startswith("/*", index):
                    depth += 1
                    index += 2
                elif text.startswith("*/", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            if depth:
                return False
            continue
        return False
    return True


def _policy_tokens_if_complete(
    lines: list[bytes],
) -> list[PolicyToken] | None:
    try:
        text = b"".join(lines).decode("utf-8")
    except UnicodeDecodeError as error:
        raise SanitizationError("policy statement is not UTF-8") from error

    tokens: list[PolicyToken] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if text.startswith("--", index):
            newline = text.find("\n", index + 2)
            if newline < 0:
                return None
            index = newline + 1
            continue
        if text.startswith("/*", index):
            depth = 1
            index += 2
            while index < len(text) and depth:
                if text.startswith("/*", index):
                    depth += 1
                    index += 2
                elif text.startswith("*/", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            if depth:
                return None
            continue
        if character == "'":
            escape_backslashes = (
                index > 0
                and text[index - 1] in "Ee"
                and (
                    index == 1
                    or not (text[index - 2].isalnum() or text[index - 2] in "_$")
                )
            )
            index += 1
            while index < len(text):
                if escape_backslashes and text[index] == "\\":
                    index += 2
                elif text[index] == "'":
                    if index + 1 < len(text) and text[index + 1] == "'":
                        index += 2
                    else:
                        index += 1
                        break
                else:
                    index += 1
            else:
                return None
            tokens.append(("literal", ""))
            continue
        if character == '"':
            decoded: list[str] = []
            index += 1
            while index < len(text):
                if text[index] == '"':
                    if index + 1 < len(text) and text[index + 1] == '"':
                        decoded.append('"')
                        index += 2
                    else:
                        index += 1
                        break
                else:
                    decoded.append(text[index])
                    index += 1
            else:
                return None
            tokens.append(("quoted_identifier", "".join(decoded)))
            continue
        if character == "$":
            delimiter_match = POLICY_DOLLAR_QUOTE.match(text, index)
            if delimiter_match is not None:
                delimiter = delimiter_match.group(0)
                content_start = delimiter_match.end()
                content_end = text.find(delimiter, content_start)
                if content_end < 0:
                    return None
                tokens.append(("literal", ""))
                index = content_end + len(delimiter)
                continue
        if character == ";":
            if not _only_sql_trivia(text, index + 1):
                raise SanitizationError("policy statement has unsupported trailing SQL")
            return tokens
        if character.isalpha() or character == "_":
            end = index + 1
            while end < len(text) and (text[end].isalnum() or text[end] in "_$"):
                end += 1
            tokens.append(("word", text[index:end].casefold()))
            index = end
            continue
        tokens.append(("punctuation", character))
        index += 1
    return None


def _identifier_value(token: PolicyToken) -> str | None:
    kind, value = token
    if kind in {"word", "quoted_identifier"}:
        return value
    return None


def _policy_target_table(tokens: list[PolicyToken]) -> tuple[str, str] | None:
    words = [token[1] if token[0] == "word" else None for token in tokens]
    if words[:2] in (["create", "policy"], ["alter", "policy"], ["drop", "policy"]):
        search_start = 2
    elif words[:3] == ["comment", "on", "policy"]:
        search_start = 3
    else:
        raise SanitizationError("unsupported policy statement prefix")

    for index in range(search_start, len(tokens)):
        if tokens[index] != ("word", "on"):
            continue
        target = index + 1
        if target < len(tokens) and tokens[target] == ("word", "only"):
            target += 1
        if target + 2 >= len(tokens):
            raise SanitizationError("policy statement has no qualified table target")
        schema = _identifier_value(tokens[target])
        table = _identifier_value(tokens[target + 2])
        if schema is None or tokens[target + 1] != ("punctuation", "."):
            return None
        if table is None:
            return None
        return (schema, table)
    raise SanitizationError("policy statement has no table target")


def _policy_targets_request_gates(tokens: list[PolicyToken]) -> bool:
    return _policy_target_table(tokens) == SOURCE_REQUEST_GATES


def _policy_targets_reviewed_global_aggregate_bridge(
    tokens: list[PolicyToken],
) -> bool:
    return _policy_target_table(tokens) in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES


@dataclass(frozen=True)
class CopyHeader:
    table: tuple[str, ...]
    columns: tuple[str, ...]


@dataclass(frozen=True)
class CopyBlock:
    header: CopyHeader
    column_indexes: dict[str, int]


def _split_outside_quotes(value: str, separator: str) -> list[str]:
    parts: list[str] = []
    start = 0
    in_quotes = False
    index = 0
    while index < len(value):
        character = value[index]
        if character == '"':
            if in_quotes and index + 1 < len(value) and value[index + 1] == '"':
                index += 2
                continue
            in_quotes = not in_quotes
        elif character == separator and not in_quotes:
            parts.append(value[start:index])
            start = index + 1
        index += 1
    if in_quotes:
        raise SanitizationError("unterminated quoted identifier in COPY header")
    parts.append(value[start:])
    return parts


def _parse_identifier(value: str) -> str:
    value = value.strip()
    if not value:
        raise SanitizationError("empty identifier in COPY header")
    if value.startswith('"'):
        if not value.endswith('"') or len(value) < 2:
            raise SanitizationError("malformed quoted identifier in COPY header")
        decoded = value[1:-1].replace('""', '"')
        if not decoded or "\x00" in decoded:
            raise SanitizationError("invalid quoted identifier in COPY header")
        return decoded
    if not IDENTIFIER.fullmatch(value):
        raise SanitizationError("unsupported identifier in COPY header")
    return value.lower()


def _find_unquoted(value: str, target: str, start: int = 0) -> int:
    in_quotes = False
    index = start
    while index < len(value):
        character = value[index]
        if character == '"':
            if in_quotes and index + 1 < len(value) and value[index + 1] == '"':
                index += 2
                continue
            in_quotes = not in_quotes
        elif character == target and not in_quotes:
            return index
        index += 1
    if in_quotes:
        raise SanitizationError("unterminated quoted identifier in COPY header")
    return -1


def parse_copy_header(line: bytes) -> CopyHeader | None:
    """Parse the single-line COPY form emitted by pg_dump.

    Non-COPY input returns ``None``. A line that starts a COPY statement but
    does not match the supported form raises instead of being passed through.
    """

    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError as exc:
        if line.lstrip()[:4].upper() == b"COPY":
            raise SanitizationError("COPY header is not valid UTF-8") from exc
        return None
    stripped = text.strip()
    if not re.match(r"COPY(?:\s|\Z)", stripped, re.IGNORECASE):
        return None

    remainder = stripped[4:].lstrip()
    open_parenthesis = _find_unquoted(remainder, "(")
    if open_parenthesis < 1:
        raise SanitizationError("unsupported COPY header")
    close_parenthesis = _find_unquoted(remainder, ")", open_parenthesis + 1)
    if close_parenthesis < 0:
        raise SanitizationError("unterminated COPY column list")

    table_text = remainder[:open_parenthesis].strip()
    columns_text = remainder[open_parenthesis + 1 : close_parenthesis]
    suffix = remainder[close_parenthesis + 1 :].strip()
    if not COPY_SUFFIX.fullmatch(suffix):
        raise SanitizationError("COPY must use FROM stdin")

    table = tuple(
        _parse_identifier(part) for part in _split_outside_quotes(table_text, ".")
    )
    columns = tuple(
        _parse_identifier(part) for part in _split_outside_quotes(columns_text, ",")
    )
    if len(table) not in (1, 2) or not columns:
        raise SanitizationError("unsupported COPY table or column list")
    if len(set(columns)) != len(columns):
        raise SanitizationError("duplicate column in COPY header")
    return CopyHeader(table=table, columns=columns)


def parse_youtube_create(line: bytes) -> bool | None:
    """Identify and validate the target CREATE TABLE header.

    The fixed plain ``pg_dump`` format emits this header on one line. A CREATE
    statement that references the target but is not that supported form is an
    error, since silently accepting it could retain a logged cache after a
    preflight-to-snapshot schema race.
    """

    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not re.match(r"^\s*CREATE(?:\s|\Z)", text, re.IGNORECASE):
        return None
    if not YOUTUBE_CREATE_REFERENCE.match(text):
        return None
    match = YOUTUBE_CREATE.match(text)
    if match is None:
        raise SanitizationError("unsupported youtube_discoveries CREATE TABLE header")
    if match.group("unlogged") is None:
        raise SanitizationError("youtube_discoveries CREATE TABLE is not UNLOGGED")
    return True


def parse_request_gates_create(line: bytes) -> bool | None:
    """Identify the one regular request-gate table definition."""

    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not re.match(r"^\s*CREATE(?:\s|\Z)", text, re.IGNORECASE):
        return None
    if not REQUEST_GATES_CREATE_REFERENCE.match(text):
        return None
    if REQUEST_GATES_CREATE.match(text) is None:
        raise SanitizationError("unsupported source_request_gates CREATE TABLE header")
    return True


def parse_public_study_create(line: bytes) -> bool | None:
    """Identify the one regular public-study ledger table definition."""

    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not re.match(r"^\s*CREATE(?:\s|\Z)", text, re.IGNORECASE):
        return None
    if not PUBLIC_STUDY_CREATE_REFERENCE.match(text):
        return None
    if PUBLIC_STUDY_CREATE.match(text) is None:
        raise SanitizationError(
            "unsupported public_study_observations CREATE TABLE header"
        )
    return True


def parse_reviewed_global_aggregate_bridge_create(
    line: bytes,
) -> tuple[str, str] | None:
    """Identify one regular private aggregate-bridge table definition."""

    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not re.match(r"^\s*CREATE(?:\s|\Z)", text, re.IGNORECASE):
        return None
    for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES:
        if not REVIEWED_GLOBAL_AGGREGATE_BRIDGE_CREATE_REFERENCE[table].match(text):
            continue
        if REVIEWED_GLOBAL_AGGREGATE_BRIDGE_CREATE[table].match(text) is None:
            raise SanitizationError(
                "aggregate bridge CREATE TABLE must be a regular logged table"
            )
        return table
    return None


def _reviewed_global_aggregate_bridge_alter_table(
    statement: str,
) -> tuple[str, str] | None:
    for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES:
        if re.match(
            r"^alter table(?: only)?\s+"
            + _aggregate_bridge_table_expression(table)
            + r"(?:\s|;|\Z)",
            statement,
            re.IGNORECASE,
        ):
            return table
    return None


def _reviewed_global_aggregate_bridge_index_table(
    statement: str,
) -> tuple[str, str] | None:
    if re.match(r"^create(?: unique)? index(?:\s|$)", statement, re.IGNORECASE) is None:
        return None
    for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES:
        if re.search(
            r"\bon\s+"
            + _aggregate_bridge_table_expression(table)
            + r"(?:\s|$)",
            statement,
            re.IGNORECASE,
        ):
            return table
    return None


def _split_create_declarations(
    lines: list[bytes], *, label: str = "public-study"
) -> tuple[str, ...]:
    try:
        text = b"".join(lines).decode("utf-8")
    except UnicodeDecodeError as error:
        raise SanitizationError(f"{label} schema is not UTF-8") from error
    open_parenthesis = text.find("(")
    close_parenthesis = text.rfind(");")
    if open_parenthesis < 0 or close_parenthesis <= open_parenthesis:
        raise SanitizationError(f"{label} CREATE TABLE is malformed")
    if text[close_parenthesis + 2 :].strip():
        raise SanitizationError(f"{label} CREATE TABLE has trailing SQL")
    body = text[open_parenthesis + 1 : close_parenthesis]
    declarations: list[str] = []
    start = 0
    depth = 0
    in_single_quote = False
    in_double_quote = False
    index = 0
    while index < len(body):
        character = body[index]
        if in_single_quote:
            if character == "'":
                if index + 1 < len(body) and body[index + 1] == "'":
                    index += 2
                    continue
                in_single_quote = False
        elif in_double_quote:
            if character == '"':
                if index + 1 < len(body) and body[index + 1] == '"':
                    index += 2
                    continue
                in_double_quote = False
        elif character == "'":
            in_single_quote = True
        elif character == '"':
            in_double_quote = True
        elif character == "(":
            depth += 1
        elif character == ")":
            if depth == 0:
                raise SanitizationError(
                    f"{label} schema has unbalanced parentheses"
                )
            depth -= 1
        elif character == "," and depth == 0:
            declarations.append(_normalize_sql((body[start:index].encode("utf-8"),)))
            start = index + 1
        index += 1
    if in_single_quote or in_double_quote or depth:
        raise SanitizationError(f"{label} schema is unterminated")
    declarations.append(_normalize_sql((body[start:].encode("utf-8"),)))
    if any(not declaration for declaration in declarations):
        raise SanitizationError(f"{label} schema has an empty declaration")
    return tuple(declarations)


def _validate_public_study_create(lines: list[bytes]) -> None:
    declarations = _split_create_declarations(lines)
    column_count = len(PUBLIC_STUDY_COLUMN_DECLARATIONS)
    columns = declarations[:column_count]
    if columns != PUBLIC_STUDY_COLUMN_DECLARATIONS:
        raise SanitizationError("unsupported public_study_observations column schema")
    constraint_declarations = declarations[column_count:]
    if (
        len(constraint_declarations) != len(PUBLIC_STUDY_CHECK_DECLARATIONS)
        or len(set(constraint_declarations)) != len(constraint_declarations)
        or frozenset(constraint_declarations) != PUBLIC_STUDY_CHECK_DECLARATIONS
    ):
        raise SanitizationError(
            "unsupported public_study_observations check-constraint schema"
        )


def _named_constraint(declaration: str, *, label: str) -> tuple[str, str]:
    match = re.fullmatch(r"constraint (?P<name>[a-z_][a-z0-9_$]*) (?P<semantic>.+)", declaration)
    if match is None:
        raise SanitizationError(f"{label} has an unnamed or malformed constraint")
    return match.group("name"), match.group("semantic")


def _validate_reviewed_global_aggregate_bridge_check(
    *, table: tuple[str, str], name: str, semantic: str
) -> None:
    expected_tokens = REVIEWED_GLOBAL_AGGREGATE_BRIDGE_CHECK_TOKENS[table].get(name)
    if expected_tokens is None:
        raise SanitizationError(
            f"unsupported {table[1]} inline constraint schema"
        )
    # pg_dump preserves CHECK expression semantics but may add parentheses and
    # explicit text casts.  Check every reviewed predicate token rather than
    # relying on layout, while the COPY validator independently enforces the
    # exact retained values.
    normalized = semantic.replace("::text", "")
    if any(token not in normalized for token in expected_tokens):
        raise SanitizationError(
            f"unsupported {table[1]} inline constraint schema"
        )


def _validate_reviewed_global_aggregate_bridge_create(
    table: tuple[str, str], lines: list[bytes]
) -> set[str]:
    label = table[1]
    declarations = _split_create_declarations(lines, label=label)
    expected_columns = REVIEWED_GLOBAL_AGGREGATE_BRIDGE_COLUMN_DECLARATIONS[table]
    columns = declarations[: len(expected_columns)]
    if columns != expected_columns:
        raise SanitizationError(f"unsupported {label} column schema")
    expected_checks = REVIEWED_GLOBAL_AGGREGATE_BRIDGE_CHECK_TOKENS[table]
    expected_named_structural = (
        REVIEWED_GLOBAL_AGGREGATE_BRIDGE_NAMED_STRUCTURAL_CONSTRAINTS[table]
    )
    seen_checks: set[str] = set()
    structural_constraints: set[str] = set()
    expected_structural = REVIEWED_GLOBAL_AGGREGATE_BRIDGE_ALTER_CONSTRAINTS[table]
    for declaration in declarations[len(expected_columns) :]:
        name, semantic = _named_constraint(declaration, label=label)
        if name in expected_checks:
            if name in seen_checks:
                raise SanitizationError(f"duplicate {label} check constraint")
            _validate_reviewed_global_aggregate_bridge_check(
                table=table, name=name, semantic=semantic
            )
            seen_checks.add(name)
            continue
        expected_semantic = expected_named_structural.get(name)
        if expected_semantic is not None:
            if semantic != expected_semantic:
                raise SanitizationError(f"unsupported {label} inline constraint schema")
            if semantic in structural_constraints:
                raise SanitizationError(f"duplicate {label} structural constraint")
            structural_constraints.add(semantic)
            continue
        if semantic in expected_structural:
            if semantic in expected_named_structural.values():
                raise SanitizationError(f"unsupported {label} inline constraint schema")
            if semantic in structural_constraints:
                raise SanitizationError(f"duplicate {label} structural constraint")
            structural_constraints.add(semantic)
            continue
        raise SanitizationError(f"unsupported {label} inline constraint schema")
    if seen_checks != set(expected_checks):
        raise SanitizationError(f"unsupported {label} inline constraint schema")
    return structural_constraints


def _without_line_ending(line: bytes) -> bytes:
    if line.endswith(b"\r\n"):
        return line[:-2]
    if line.endswith(b"\n"):
        return line[:-1]
    raise SanitizationError("COPY data row is missing a line ending")


def _canonical_uuid(value: bytes, *, field: str) -> str:
    if b"\\" in value or value == b"\\N":
        raise SanitizationError(f"{field} is not a plain UUID")
    try:
        text = value.decode("ascii")
        parsed = UUID(text)
    except (UnicodeDecodeError, ValueError) as exc:
        raise SanitizationError(f"{field} is not a valid UUID") from exc
    if str(parsed) != text:
        raise SanitizationError(f"{field} is not a canonical UUID")
    return str(parsed)


def _optional_canonical_uuid(value: bytes, *, field: str) -> str | None:
    if value == b"\\N":
        return None
    return _canonical_uuid(value, field=field)


def _plain_copy_text(value: bytes, *, field: str) -> str:
    if value == b"\\N" or b"\\" in value or b"\x00" in value:
        raise SanitizationError(f"{field} is not plain text")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SanitizationError(f"{field} is not UTF-8") from error


def _optional_plain_copy_text(value: bytes, *, field: str) -> str | None:
    if value == b"\\N":
        return None
    return _plain_copy_text(value, field=field)


def _contract_key_copy(value: bytes, *, field: str) -> str:
    text = _plain_copy_text(value, field=field)
    if SAFE_CONTRACT_KEY.fullmatch(text) is None:
        raise SanitizationError(f"{field} is not a bounded canonical contract key")
    return text


def _admission_key_copy(value: bytes, *, field: str) -> str:
    text = _plain_copy_text(value, field=field)
    if SAFE_ADMISSION_KEY.fullmatch(text) is None:
        raise SanitizationError(f"{field} is not a bounded canonical admission key")
    return text


def _canonical_domain_copy(value: bytes, *, field: str) -> str:
    text = _plain_copy_text(value, field=field)
    if CANONICAL_DOMAIN.fullmatch(text) is None:
        raise SanitizationError(f"{field} is not a canonical lowercase domain")
    return text


def _sha256_copy(value: bytes, *, field: str) -> str:
    text = _plain_copy_text(value, field=field)
    if LOWERCASE_SHA256.fullmatch(text) is None:
        raise SanitizationError(f"{field} is not a lowercase SHA-256")
    return text


def _utc_copy_timestamp(value: bytes, *, field: str) -> datetime:
    text = _plain_copy_text(value, field=field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise SanitizationError(f"{field} is not an ISO timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise SanitizationError(f"{field} is not an explicit UTC timestamp")
    return parsed


def _optional_utc_copy_timestamp(value: bytes, *, field: str) -> datetime | None:
    if value == b"\\N":
        return None
    return _utc_copy_timestamp(value, field=field)


def _copy_nonnegative_bigint(
    value: bytes, *, field: str, nullable: bool = False
) -> int | None:
    if nullable and value == b"\\N":
        return None
    text = _plain_copy_text(value, field=field)
    if re.fullmatch(r"0|[1-9][0-9]*", text) is None:
        raise SanitizationError(f"{field} is not a canonical non-negative integer")
    parsed = int(text)
    if parsed > 9223372036854775807:
        raise SanitizationError(f"{field} exceeds PostgreSQL bigint")
    return parsed


def _mastodon_status_id_copy(value: bytes, *, field: str) -> None:
    """Validate the only raw Mastodon value retained: a bounded cursor."""

    if value == b"\\N":
        return
    text = _plain_copy_text(value, field=field)
    if (
        not 1 <= len(text) <= 160
        or text != text.strip()
        or re.search(r"[\x00-\x1f\x7f]", text) is not None
    ):
        raise SanitizationError(f"{field} is not bounded opaque text")


def _column_indexes(header: CopyHeader) -> dict[str, int]:
    return {column: index for index, column in enumerate(header.columns)}


class PlainBackupSanitizer:
    def __init__(
        self,
        *,
        source_policies_present: bool,
        youtube_discoveries_present: bool,
        public_studies_present: bool,
        bluesky_jetstream_present: bool,
        youtube_policy_id: str | None,
        bluesky_policy_id: str | None,
        nostr_relay_present: bool = False,
        nostr_policy_ids: tuple[str, ...] | list[str] = (),
        mastodon_public_hashtag_present: bool = False,
        mastodon_policy_id: str | None = None,
        reviewed_global_aggregate_bridge_present: bool = False,
    ) -> None:
        if youtube_policy_id is not None:
            youtube_policy_id = _canonical_uuid(
                youtube_policy_id.encode("ascii"), field="YouTube policy id"
            )
        if bluesky_policy_id is not None:
            bluesky_policy_id = _canonical_uuid(
                bluesky_policy_id.encode("ascii"), field="Bluesky policy id"
            )
        if mastodon_policy_id is not None:
            mastodon_policy_id = _canonical_uuid(
                mastodon_policy_id.encode("ascii"), field="Mastodon policy id"
            )
        normalized_nostr_policy_ids: list[str] = []
        for index, policy_id in enumerate(nostr_policy_ids):
            if not isinstance(policy_id, str):
                raise SanitizationError(f"Nostr policy id {index + 1} must be text")
            normalized_nostr_policy_ids.append(
                _canonical_uuid(
                    policy_id.encode("ascii"),
                    field=f"Nostr policy id {index + 1}",
                )
            )
        if nostr_relay_present and len(normalized_nostr_policy_ids) != len(
            NOSTR_SOURCE_KEYS
        ):
            raise SanitizationError(
                "Nostr retention requires exactly three policy identifiers"
            )
        if not nostr_relay_present and normalized_nostr_policy_ids:
            raise SanitizationError(
                "Nostr policy identifiers require the exact private table set"
            )
        if len(set(normalized_nostr_policy_ids)) != len(normalized_nostr_policy_ids):
            raise SanitizationError("Nostr policy identifiers must be distinct")
        if youtube_discoveries_present and not (
            source_policies_present and youtube_policy_id is not None
        ):
            raise SanitizationError(
                "youtube_discoveries exists without one exact YouTube policy"
            )
        if youtube_policy_id is not None and not youtube_discoveries_present:
            raise SanitizationError("YouTube policy exists without youtube_discoveries")
        if public_studies_present and not (
            source_policies_present and youtube_discoveries_present
        ):
            raise SanitizationError(
                "public-study observations require the policy registry and YouTube-era gate schema"
            )
        if bluesky_jetstream_present and not (
            source_policies_present
            and youtube_discoveries_present
            and bluesky_policy_id is not None
        ):
            raise SanitizationError(
                "Bluesky state requires the policy registry and YouTube-era gate schema"
            )
        if bluesky_policy_id is not None and not bluesky_jetstream_present:
            raise SanitizationError(
                "Bluesky policy exists without the exact private table set"
            )
        if nostr_relay_present and not source_policies_present:
            raise SanitizationError("Nostr state requires the source policy registry")
        if mastodon_public_hashtag_present and not source_policies_present:
            raise SanitizationError(
                "Mastodon state requires the source policy registry"
            )
        if mastodon_public_hashtag_present and mastodon_policy_id is None:
            raise SanitizationError(
                "Mastodon state requires one exact Mastodon policy identifier"
            )
        if mastodon_policy_id is not None and not mastodon_public_hashtag_present:
            raise SanitizationError(
                "Mastodon policy exists without the exact Mastodon table set"
            )
        if reviewed_global_aggregate_bridge_present and not source_policies_present:
            raise SanitizationError(
                "reviewed global aggregate bridge requires the source policy registry"
            )

        self.expected = {
            SOURCE_POLICIES: source_policies_present,
            YOUTUBE_DISCOVERIES: youtube_discoveries_present,
            PUBLIC_STUDY_OBSERVATIONS: public_studies_present,
            BLUESKY_CHECKPOINTS: bluesky_jetstream_present,
            NOSTR_CHECKPOINTS: nostr_relay_present,
            MASTODON_CHECKPOINTS: mastodon_public_hashtag_present,
            MASTODON_COOLDOWNS: mastodon_public_hashtag_present,
            REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCES: (
                reviewed_global_aggregate_bridge_present
            ),
            REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS: (
                reviewed_global_aggregate_bridge_present
            ),
            REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS: (
                reviewed_global_aggregate_bridge_present
            ),
        }
        self.preflight_youtube_policy_id = youtube_policy_id
        self.preflight_bluesky_policy_id = bluesky_policy_id
        self.preflight_nostr_policy_ids = tuple(normalized_nostr_policy_ids)
        self.preflight_mastodon_policy_id = mastodon_policy_id
        self.bluesky_jetstream_present = bluesky_jetstream_present
        self.nostr_relay_present = nostr_relay_present
        self.mastodon_public_hashtag_present = mastodon_public_hashtag_present
        self.reviewed_global_aggregate_bridge_present = (
            reviewed_global_aggregate_bridge_present
        )
        self.request_gate_broad = (
            youtube_discoveries_present or mastodon_public_hashtag_present
        )
        self.seen = {table: 0 for table in RETENTION_CONTROL_TABLES}
        self.youtube_policy_rows: list[str] = []
        self.tcgdex_policy_rows = 0
        self.bluesky_policy_ids: list[str] = []
        self.nostr_policy_ids: dict[bytes, list[str]] = {
            source_key: [] for source_key in NOSTR_SOURCE_KEYS
        }
        self.bluesky_checkpoint_rows = 0
        self.nostr_checkpoint_rows = 0
        self.nostr_checkpoint_policy_ids: dict[bytes, str] = {}
        self.mastodon_policy_ids: list[str] = []
        self.mastodon_checkpoint_rows = 0
        self.mastodon_checkpoint_tag_keys: set[bytes] = set()
        self.mastodon_cooldown_rows = 0
        self.public_study_policy_ids = {
            source_key: [] for source_key in PUBLIC_STUDY_SOURCE_KEYS
        }
        self.public_study_rows: dict[bytes, tuple[bytes, str]] = {}
        self.public_study_object_ids = {
            column: set()
            for column in ("source_item_id", "extraction_run_id", "opening_id")
        }
        self.youtube_create_count = 0
        self.public_study_create_count = 0
        self.public_study_create_lines: list[bytes] | None = None
        self.reviewed_global_aggregate_bridge_create_counts = {
            table: 0 for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES
        }
        self.reviewed_global_aggregate_bridge_create_table: tuple[str, str] | None = (
            None
        )
        self.reviewed_global_aggregate_bridge_create_lines: list[bytes] | None = None
        self.reviewed_global_aggregate_bridge_alter_table: tuple[str, str] | None = (
            None
        )
        self.reviewed_global_aggregate_bridge_alter_lines: list[bytes] | None = None
        self.reviewed_global_aggregate_bridge_force_rls_counts = {
            table: 0 for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES
        }
        self.reviewed_global_aggregate_bridge_enable_rls_counts = {
            table: 0 for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES
        }
        self.reviewed_global_aggregate_bridge_constraints = {
            table: set() for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES
        }
        self.reviewed_global_aggregate_bridge_index_table: tuple[str, str] | None = (
            None
        )
        self.reviewed_global_aggregate_bridge_index_lines: list[bytes] | None = None
        self.reviewed_global_aggregate_bridge_indexes = {
            table: set() for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES
        }
        self.reviewed_global_aggregate_independent_sources: dict[
            str, tuple[str, str, str]
        ] = {}
        self.reviewed_global_aggregate_authorized_source_bindings: dict[
            str, str
        ] = {}
        self.reviewed_global_aggregate_binding_identity_pairs: set[tuple[str, str]] = (
            set()
        )
        self.reviewed_global_aggregate_input_admissions: dict[
            str, tuple[str, str | None]
        ] = {}
        self.reviewed_global_aggregate_input_fingerprints: set[str] = set()
        self.reviewed_global_aggregate_public_study_keys: set[str] = set()
        self.reviewed_global_aggregate_accepted_observation_ids: set[str] = set()
        self.request_gates_create_count = 0
        self.request_gates_create_lines: list[bytes] | None = None
        self.request_gates_alter_lines: list[bytes] | None = None
        self.policy_statement_lines: list[bytes] | None = None
        self.request_gates_force_rls_count = 0
        self.request_gates_primary_key_count = 0
        self.request_gates_enable_rls_count = 0

    def _finish_request_gates_create(self) -> None:
        lines = self.request_gates_create_lines
        if lines is None:
            raise SanitizationError("request-gate CREATE state is missing")
        expected = REQUEST_GATES_CREATE_EXPECTED[self.request_gate_broad]
        if _normalize_sql(lines) != expected:
            raise SanitizationError("unsupported source_request_gates schema")
        self.request_gates_create_lines = None

    def _finish_public_study_create(self) -> None:
        lines = self.public_study_create_lines
        if lines is None:
            raise SanitizationError("public-study CREATE state is missing")
        _validate_public_study_create(lines)
        self.public_study_create_lines = None

    def _finish_reviewed_global_aggregate_bridge_create(self) -> None:
        table = self.reviewed_global_aggregate_bridge_create_table
        lines = self.reviewed_global_aggregate_bridge_create_lines
        if table is None or lines is None:
            raise SanitizationError("aggregate bridge CREATE state is missing")
        inline_structural_constraints = (
            _validate_reviewed_global_aggregate_bridge_create(table, lines)
        )
        seen = self.reviewed_global_aggregate_bridge_constraints[table]
        if seen.intersection(inline_structural_constraints):
            raise SanitizationError("duplicate aggregate bridge constraint")
        seen.update(inline_structural_constraints)
        self.reviewed_global_aggregate_bridge_create_table = None
        self.reviewed_global_aggregate_bridge_create_lines = None

    def _finish_request_gates_alter(self) -> None:
        lines = self.request_gates_alter_lines
        if lines is None:
            raise SanitizationError("request-gate ALTER state is missing")
        statement = _normalize_sql(lines)
        if statement == REQUEST_GATES_FORCE_RLS:
            self.request_gates_force_rls_count += 1
        elif statement == REQUEST_GATES_PRIMARY_KEY:
            self.request_gates_primary_key_count += 1
        elif statement == REQUEST_GATES_ENABLE_RLS:
            self.request_gates_enable_rls_count += 1
        else:
            raise SanitizationError("unsupported source_request_gates ALTER TABLE")
        self.request_gates_alter_lines = None

    def _finish_reviewed_global_aggregate_bridge_alter(self) -> None:
        table = self.reviewed_global_aggregate_bridge_alter_table
        lines = self.reviewed_global_aggregate_bridge_alter_lines
        if table is None or lines is None:
            raise SanitizationError("aggregate bridge ALTER state is missing")
        statement = _normalize_sql(lines)
        table_expression = _aggregate_bridge_table_expression(table)
        prefix = r"alter table(?: only)?\s+" + table_expression + r"\s+"
        if re.fullmatch(prefix + r"force row level security;", statement):
            self.reviewed_global_aggregate_bridge_force_rls_counts[table] += 1
            if self.reviewed_global_aggregate_bridge_force_rls_counts[table] != 1:
                raise SanitizationError("duplicate aggregate bridge FORCE RLS")
        elif re.fullmatch(prefix + r"enable row level security;", statement):
            self.reviewed_global_aggregate_bridge_enable_rls_counts[table] += 1
            if self.reviewed_global_aggregate_bridge_enable_rls_counts[table] != 1:
                raise SanitizationError("duplicate aggregate bridge ENABLE RLS")
        else:
            constraint_match = re.fullmatch(
                prefix
                + r"add constraint (?P<name>[a-z_][a-z0-9_$]*) "
                + r"(?P<semantic>.+);",
                statement,
            )
            if constraint_match is None:
                raise SanitizationError("unsupported aggregate bridge ALTER TABLE")
            name = constraint_match.group("name")
            semantic = constraint_match.group("semantic")
            expected = REVIEWED_GLOBAL_AGGREGATE_BRIDGE_ALTER_CONSTRAINTS[table]
            expected_named = (
                REVIEWED_GLOBAL_AGGREGATE_BRIDGE_NAMED_STRUCTURAL_CONSTRAINTS[
                    table
                ]
            )
            seen = self.reviewed_global_aggregate_bridge_constraints[table]
            named_semantic = expected_named.get(name)
            if named_semantic is not None:
                if semantic != named_semantic:
                    raise SanitizationError("unsupported aggregate bridge constraint")
            elif semantic in expected_named.values():
                raise SanitizationError("unsupported aggregate bridge constraint")
            elif semantic not in expected:
                raise SanitizationError("unsupported aggregate bridge constraint")
            if semantic in seen:
                raise SanitizationError("unsupported aggregate bridge constraint")
            seen.add(semantic)
        self.reviewed_global_aggregate_bridge_alter_table = None
        self.reviewed_global_aggregate_bridge_alter_lines = None

    def _finish_reviewed_global_aggregate_bridge_index(self) -> None:
        table = self.reviewed_global_aggregate_bridge_index_table
        lines = self.reviewed_global_aggregate_bridge_index_lines
        if table is None or lines is None:
            raise SanitizationError("aggregate bridge index state is missing")
        statement = _normalize_sql(lines)
        if table == REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS:
            match = re.fullmatch(
                r"create unique index [a-z_][a-z0-9_$]* on "
                + _aggregate_bridge_table_expression(table)
                + r" using btree \((?P<column>public_study_key|accepted_observation_id)\) "
                r"where \((?P=column) is not null\);",
                statement,
            )
            if match is None:
                raise SanitizationError(
                    "unsupported aggregate bridge partial unique index"
                )
            index_key = match.group("column")
        elif table == REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS:
            if re.fullmatch(
                r"create index [a-z_][a-z0-9_$]* on "
                + _aggregate_bridge_table_expression(table)
                + r" using btree \(independent_source_key, valid_from, valid_until\);",
                statement,
            ) is None:
                raise SanitizationError("unsupported aggregate bridge binding index")
            index_key = REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_BINDING_INDEX
        else:
            raise SanitizationError("unexpected aggregate bridge index")
        seen_indexes = self.reviewed_global_aggregate_bridge_indexes[table]
        if index_key in seen_indexes:
            raise SanitizationError("duplicate aggregate bridge index")
        seen_indexes.add(index_key)
        self.reviewed_global_aggregate_bridge_index_table = None
        self.reviewed_global_aggregate_bridge_index_lines = None

    def _maybe_finish_policy_statement(self) -> None:
        lines = self.policy_statement_lines
        if lines is None:
            raise SanitizationError("policy statement state is missing")
        tokens = _policy_tokens_if_complete(lines)
        if tokens is None:
            return
        if _policy_targets_request_gates(tokens):
            raise SanitizationError(
                "source_request_gates must not have a row-level security policy"
            )
        if _policy_targets_reviewed_global_aggregate_bridge(tokens):
            raise SanitizationError(
                "aggregate bridge tables must not have a row-level security policy"
            )
        self.policy_statement_lines = None

    def _start_block(self, header: CopyHeader) -> CopyBlock:
        indexes = _column_indexes(header)
        if header.table in RETENTION_CONTROL_TABLES:
            self.seen[header.table] += 1
            if self.seen[header.table] != 1:
                raise SanitizationError(
                    f"duplicate retention-control COPY block: {'.'.join(header.table)}"
                )
        if header.table == SOURCE_POLICIES:
            if "id" not in indexes or "source_key" not in indexes:
                raise SanitizationError("source_policies COPY lacks id or source_key")
        elif header.table == YOUTUBE_DISCOVERIES and "source_policy_id" not in indexes:
            raise SanitizationError("youtube_discoveries COPY lacks source_policy_id")
        elif (
            header.table == PUBLIC_STUDY_OBSERVATIONS
            and header.columns != PUBLIC_STUDY_COPY_COLUMNS
        ):
            raise SanitizationError(
                "public_study_observations COPY columns do not match the exact retained schema"
            )
        elif (
            header.table == BLUESKY_CHECKPOINTS
            and header.columns != BLUESKY_CHECKPOINT_COPY_COLUMNS
        ):
            raise SanitizationError(
                "bluesky_jetstream_checkpoints COPY columns do not match the exact retained schema"
            )
        elif (
            header.table == NOSTR_CHECKPOINTS
            and header.columns != NOSTR_CHECKPOINT_COPY_COLUMNS
        ):
            raise SanitizationError(
                "nostr_relay_checkpoints COPY columns do not match the exact retained schema"
            )
        elif (
            header.table == MASTODON_CHECKPOINTS
            and header.columns != MASTODON_CHECKPOINT_COPY_COLUMNS
        ):
            raise SanitizationError(
                "mastodon_public_hashtag_checkpoints COPY columns do not match the exact retained schema"
            )
        elif (
            header.table == MASTODON_COOLDOWNS
            and header.columns != MASTODON_COOLDOWN_COPY_COLUMNS
        ):
            raise SanitizationError(
                "mastodon_rate_cooldowns COPY columns do not match the exact retained schema"
            )
        elif header.table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES:
            expected_columns = REVIEWED_GLOBAL_AGGREGATE_BRIDGE_COPY_COLUMNS[
                header.table
            ]
            if header.columns != expected_columns:
                raise SanitizationError(
                    f"{header.table[1]} COPY columns do not match the exact retained schema"
                )
        return CopyBlock(header=header, column_indexes=indexes)

    def _target_fields(self, block: CopyBlock, line: bytes) -> list[bytes]:
        fields = _without_line_ending(line).split(b"\t")
        if len(fields) != len(block.header.columns):
            raise SanitizationError("retention-control COPY row has wrong field count")
        return fields

    def _inspect_control_row(self, block: CopyBlock, line: bytes) -> None:
        if block.header.table not in RETENTION_CONTROL_TABLES:
            return
        fields = self._target_fields(block, line)
        if block.header.table == REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCES:
            self._inspect_reviewed_global_aggregate_independent_source_row(
                block, fields
            )
            return
        if block.header.table == REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS:
            self._inspect_reviewed_global_aggregate_authorized_binding_row(
                block, fields
            )
            return
        if block.header.table == REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS:
            self._inspect_reviewed_global_aggregate_input_admission_row(block, fields)
            return
        if block.header.table == SOURCE_POLICIES:
            source_key = fields[block.column_indexes["source_key"]]
            if b"\\" in source_key or source_key == b"\\N":
                raise SanitizationError("source policy key is not plain text")
            if source_key == YOUTUBE_SOURCE_KEY:
                self.youtube_policy_rows.append(
                    _canonical_uuid(
                        fields[block.column_indexes["id"]], field="dump policy id"
                    )
                )
            elif source_key == TCGDEX_SOURCE_KEY:
                self.tcgdex_policy_rows += 1
            elif source_key == BLUESKY_SOURCE_KEY:
                self.bluesky_policy_ids.append(
                    _canonical_uuid(
                        fields[block.column_indexes["id"]],
                        field="Bluesky source policy id",
                    )
                )
            elif source_key == MASTODON_SOURCE_KEY:
                self.mastodon_policy_ids.append(
                    _canonical_uuid(
                        fields[block.column_indexes["id"]],
                        field="Mastodon source policy id",
                    )
                )
            elif source_key in self.nostr_policy_ids:
                self.nostr_policy_ids[source_key].append(
                    _canonical_uuid(
                        fields[block.column_indexes["id"]],
                        field="Nostr source policy id",
                    )
                )
            elif source_key in self.public_study_policy_ids:
                self.public_study_policy_ids[source_key].append(
                    _canonical_uuid(
                        fields[block.column_indexes["id"]],
                        field="public-study policy id",
                    )
                )
            return
        if block.header.table == PUBLIC_STUDY_OBSERVATIONS:
            self._inspect_public_study_row(block, fields)
            return
        if block.header.table == BLUESKY_CHECKPOINTS:
            self._inspect_bluesky_checkpoint_row(block, fields)
            return
        if block.header.table == NOSTR_CHECKPOINTS:
            self._inspect_nostr_checkpoint_row(block, fields)
            return
        if block.header.table == MASTODON_CHECKPOINTS:
            self._inspect_mastodon_checkpoint_row(block, fields)
            return
        if block.header.table == MASTODON_COOLDOWNS:
            self._inspect_mastodon_cooldown_row(block, fields)
            return
        policy_id = _canonical_uuid(
            fields[block.column_indexes["source_policy_id"]],
            field="YouTube discovery policy id",
        )
        if policy_id != self.preflight_youtube_policy_id:
            raise SanitizationError(
                "youtube_discoveries row does not use the exact YouTube policy"
            )

    def _inspect_bluesky_checkpoint_row(
        self, block: CopyBlock, fields: list[bytes]
    ) -> None:
        self.bluesky_checkpoint_rows += 1
        if self.bluesky_checkpoint_rows != 1:
            raise SanitizationError("Bluesky checkpoint must contain exactly one row")
        indexes = block.column_indexes
        policy_id = _canonical_uuid(
            fields[indexes["source_policy_id"]], field="Bluesky checkpoint policy id"
        )
        if policy_id != self.preflight_bluesky_policy_id:
            raise SanitizationError(
                "Bluesky checkpoint does not use the exact preflight policy"
            )
        exact_text = {
            "endpoint": (
                "wss://jetstream.us-west.bsky.network/"
                "xrpc/network.bsky.jetstream.subscribeEvents"
            ),
            "protocol": "xrpc.v1.json",
            "collection": "app.bsky.feed.post",
            "is_demo": "f",
        }
        for column, expected in exact_text.items():
            if (
                _plain_copy_text(fields[indexes[column]], field=f"Bluesky {column}")
                != expected
            ):
                raise SanitizationError(f"Bluesky checkpoint {column} drifted")
        _copy_nonnegative_bigint(
            fields[indexes["last_cursor"]],
            field="Bluesky checkpoint last_cursor",
            nullable=True,
        )
        for column in (
            "events_seen_total",
            "bytes_seen_total",
            "candidates_seen_total",
            "deletions_seen_total",
        ):
            _copy_nonnegative_bigint(
                fields[indexes[column]], field=f"Bluesky checkpoint {column}"
            )
        last_collected = fields[indexes["last_collected_at"]]
        if last_collected != b"\\N":
            _utc_copy_timestamp(last_collected, field="Bluesky last_collected_at")
        created_at = _utc_copy_timestamp(
            fields[indexes["created_at"]], field="Bluesky checkpoint created_at"
        )
        updated_at = _utc_copy_timestamp(
            fields[indexes["updated_at"]], field="Bluesky checkpoint updated_at"
        )
        if updated_at < created_at:
            raise SanitizationError("Bluesky checkpoint timestamps are out of order")

    def _inspect_nostr_checkpoint_row(
        self, block: CopyBlock, fields: list[bytes]
    ) -> None:
        if not self.nostr_relay_present:
            raise SanitizationError(
                "dump contains Nostr checkpoints without the exact private table set"
            )
        self.nostr_checkpoint_rows += 1
        if self.nostr_checkpoint_rows > len(NOSTR_SOURCE_KEYS):
            raise SanitizationError("Nostr checkpoints must contain exactly three rows")
        indexes = block.column_indexes
        policy_id = _canonical_uuid(
            fields[indexes["source_policy_id"]], field="Nostr checkpoint policy id"
        )
        relay_key = _plain_copy_text(
            fields[indexes["relay_key"]], field="Nostr checkpoint relay key"
        ).encode("utf-8")
        try:
            relay_index = NOSTR_RELAY_KEYS.index(relay_key)
        except ValueError as error:
            raise SanitizationError(
                "Nostr checkpoint relay key is not approved"
            ) from error
        if relay_key in self.nostr_checkpoint_policy_ids:
            raise SanitizationError("Nostr checkpoint relay keys must be unique")
        expected_policy_id = self.preflight_nostr_policy_ids[relay_index]
        if policy_id != expected_policy_id:
            raise SanitizationError(
                "Nostr checkpoint does not use the exact preflight policy"
            )
        endpoint = _plain_copy_text(
            fields[indexes["endpoint"]], field="Nostr checkpoint endpoint"
        ).encode("utf-8")
        if endpoint != NOSTR_ENDPOINTS[relay_index]:
            raise SanitizationError("Nostr checkpoint endpoint drifted")
        nip11_url = _plain_copy_text(
            fields[indexes["nip11_url"]], field="Nostr checkpoint NIP-11 URL"
        ).encode("utf-8")
        if nip11_url != NOSTR_NIP11_URLS[relay_index]:
            raise SanitizationError("Nostr checkpoint NIP-11 URL drifted")
        protocol = _plain_copy_text(
            fields[indexes["protocol"]], field="Nostr checkpoint protocol"
        ).encode("utf-8")
        if protocol != NOSTR_PROTOCOL:
            raise SanitizationError("Nostr checkpoint protocol drifted")
        if fields[indexes["approved_tags"]] != NOSTR_APPROVED_TAGS_COPY:
            raise SanitizationError("Nostr checkpoint approved tags drifted")
        last_checkpoint = fields[indexes["last_checkpoint"]]
        if last_checkpoint != b"\\N":
            _utc_copy_timestamp(
                last_checkpoint, field="Nostr checkpoint last_checkpoint"
            )
        for column in (
            "events_seen_total",
            "bytes_seen_total",
            "candidates_seen_total",
            "deletions_seen_total",
        ):
            _copy_nonnegative_bigint(
                fields[indexes[column]], field=f"Nostr checkpoint {column}"
            )
        if fields[indexes["is_demo"]] != b"f":
            raise SanitizationError("Nostr checkpoint is_demo must be false")
        created_at = _utc_copy_timestamp(
            fields[indexes["created_at"]], field="Nostr checkpoint created_at"
        )
        updated_at = _utc_copy_timestamp(
            fields[indexes["updated_at"]], field="Nostr checkpoint updated_at"
        )
        if updated_at < created_at:
            raise SanitizationError("Nostr checkpoint timestamps are out of order")
        self.nostr_checkpoint_policy_ids[relay_key] = policy_id

    def _inspect_mastodon_checkpoint_row(
        self, block: CopyBlock, fields: list[bytes]
    ) -> None:
        if not self.mastodon_public_hashtag_present:
            raise SanitizationError(
                "dump contains Mastodon checkpoints without the exact table set"
            )
        self.mastodon_checkpoint_rows += 1
        if self.mastodon_checkpoint_rows > len(MASTODON_TAG_KEYS):
            raise SanitizationError(
                "Mastodon checkpoints must contain exactly seven rows"
            )
        indexes = block.column_indexes
        policy_id = _canonical_uuid(
            fields[indexes["source_policy_id"]], field="Mastodon checkpoint policy id"
        )
        if policy_id != self.preflight_mastodon_policy_id:
            raise SanitizationError(
                "Mastodon checkpoint does not use the exact preflight policy"
            )
        instance_key = _plain_copy_text(
            fields[indexes["instance_key"]], field="Mastodon checkpoint instance key"
        ).encode("utf-8")
        if instance_key != MASTODON_SOURCE_KEY:
            raise SanitizationError("Mastodon checkpoint instance key drifted")
        tag_key = _plain_copy_text(
            fields[indexes["tag_key"]], field="Mastodon checkpoint tag key"
        ).encode("ascii")
        if tag_key not in MASTODON_TAG_KEYS:
            raise SanitizationError("Mastodon checkpoint tag key is not approved")
        if tag_key in self.mastodon_checkpoint_tag_keys:
            raise SanitizationError("Mastodon checkpoint tag keys must be unique")
        self.mastodon_checkpoint_tag_keys.add(tag_key)
        _mastodon_status_id_copy(
            fields[indexes["last_status_id"]],
            field="Mastodon checkpoint last_status_id",
        )
        last_collected = fields[indexes["last_collected_at"]]
        if last_collected != b"\\N":
            _utc_copy_timestamp(
                last_collected, field="Mastodon checkpoint last_collected_at"
            )
        if fields[indexes["incomplete"]] not in {b"t", b"f"}:
            raise SanitizationError("Mastodon checkpoint incomplete must be boolean")
        for column in (
            "requests_seen_total",
            "statuses_seen_total",
            "bytes_seen_total",
            "candidates_seen_total",
        ):
            _copy_nonnegative_bigint(
                fields[indexes[column]], field=f"Mastodon checkpoint {column}"
            )
        if fields[indexes["is_demo"]] != b"f":
            raise SanitizationError("Mastodon checkpoint is_demo must be false")
        created_at = _utc_copy_timestamp(
            fields[indexes["created_at"]], field="Mastodon checkpoint created_at"
        )
        updated_at = _utc_copy_timestamp(
            fields[indexes["updated_at"]], field="Mastodon checkpoint updated_at"
        )
        if updated_at < created_at:
            raise SanitizationError("Mastodon checkpoint timestamps are out of order")

    def _inspect_mastodon_cooldown_row(
        self, block: CopyBlock, fields: list[bytes]
    ) -> None:
        if not self.mastodon_public_hashtag_present:
            raise SanitizationError(
                "dump contains Mastodon cooldowns without the exact table set"
            )
        self.mastodon_cooldown_rows += 1
        if self.mastodon_cooldown_rows != 1:
            raise SanitizationError("Mastodon cooldowns must contain exactly one row")
        indexes = block.column_indexes
        policy_id = _canonical_uuid(
            fields[indexes["source_policy_id"]], field="Mastodon cooldown policy id"
        )
        if policy_id != self.preflight_mastodon_policy_id:
            raise SanitizationError(
                "Mastodon cooldown does not use the exact preflight policy"
            )
        instance_key = _plain_copy_text(
            fields[indexes["instance_key"]], field="Mastodon cooldown instance key"
        ).encode("utf-8")
        if instance_key != MASTODON_SOURCE_KEY:
            raise SanitizationError("Mastodon cooldown instance key drifted")
        _utc_copy_timestamp(
            fields[indexes["cooldown_until"]], field="Mastodon cooldown cooldown_until"
        )
        if fields[indexes["is_demo"]] != b"f":
            raise SanitizationError("Mastodon cooldown is_demo must be false")
        created_at = _utc_copy_timestamp(
            fields[indexes["created_at"]], field="Mastodon cooldown created_at"
        )
        updated_at = _utc_copy_timestamp(
            fields[indexes["updated_at"]], field="Mastodon cooldown updated_at"
        )
        if updated_at < created_at:
            raise SanitizationError("Mastodon cooldown timestamps are out of order")

    def _inspect_reviewed_global_aggregate_independent_source_row(
        self, block: CopyBlock, fields: list[bytes]
    ) -> None:
        if not self.reviewed_global_aggregate_bridge_present:
            raise SanitizationError(
                "dump contains aggregate bridge rows absent from database preflight"
            )
        indexes = block.column_indexes
        source_key = _contract_key_copy(
            fields[indexes["source_key"]], field="aggregate source key"
        )
        canonical_domain = _canonical_domain_copy(
            fields[indexes["canonical_domain"]], field="aggregate source domain"
        )
        domain_contract_version = _contract_key_copy(
            fields[indexes["domain_contract_version"]],
            field="aggregate source domain contract version",
        )
        domain_contract_sha256 = _sha256_copy(
            fields[indexes["domain_contract_sha256"]],
            field="aggregate source domain contract hash",
        )
        _utc_copy_timestamp(
            fields[indexes["created_at"]], field="aggregate source created_at"
        )
        if source_key in self.reviewed_global_aggregate_independent_sources:
            raise SanitizationError("aggregate independent source key is duplicated")
        if any(
            canonical_domain == retained[0]
            for retained in self.reviewed_global_aggregate_independent_sources.values()
        ):
            raise SanitizationError("aggregate independent source domain is duplicated")
        self.reviewed_global_aggregate_independent_sources[source_key] = (
            canonical_domain,
            domain_contract_version,
            domain_contract_sha256,
        )

    def _inspect_reviewed_global_aggregate_authorized_binding_row(
        self, block: CopyBlock, fields: list[bytes]
    ) -> None:
        if not self.reviewed_global_aggregate_bridge_present:
            raise SanitizationError(
                "dump contains aggregate bridge rows absent from database preflight"
            )
        indexes = block.column_indexes
        binding_key = _contract_key_copy(
            fields[indexes["binding_key"]], field="aggregate binding key"
        )
        source_identity = _sha256_copy(
            fields[indexes["source_identity_sha256"]],
            field="aggregate binding source identity hash",
        )
        authorization_reference = _sha256_copy(
            fields[indexes["authorization_reference_sha256"]],
            field="aggregate binding authorization reference hash",
        )
        independent_source_key = _contract_key_copy(
            fields[indexes["independent_source_key"]],
            field="aggregate binding independent source key",
        )
        _contract_key_copy(
            fields[indexes["authorization_contract_version"]],
            field="aggregate binding authorization contract version",
        )
        _sha256_copy(
            fields[indexes["authorization_contract_sha256"]],
            field="aggregate binding authorization contract hash",
        )
        valid_from = _utc_copy_timestamp(
            fields[indexes["valid_from"]], field="aggregate binding valid_from"
        )
        valid_until = _optional_utc_copy_timestamp(
            fields[indexes["valid_until"]], field="aggregate binding valid_until"
        )
        _utc_copy_timestamp(
            fields[indexes["created_at"]], field="aggregate binding created_at"
        )
        if valid_until is not None and valid_until < valid_from:
            raise SanitizationError("aggregate binding validity window is inverted")
        if binding_key in self.reviewed_global_aggregate_authorized_source_bindings:
            raise SanitizationError("aggregate binding key is duplicated")
        identity_pair = (source_identity, authorization_reference)
        if identity_pair in self.reviewed_global_aggregate_binding_identity_pairs:
            raise SanitizationError("aggregate binding identity pair is duplicated")
        self.reviewed_global_aggregate_authorized_source_bindings[binding_key] = (
            independent_source_key
        )
        self.reviewed_global_aggregate_binding_identity_pairs.add(identity_pair)

    def _inspect_reviewed_global_aggregate_input_admission_row(
        self, block: CopyBlock, fields: list[bytes]
    ) -> None:
        if not self.reviewed_global_aggregate_bridge_present:
            raise SanitizationError(
                "dump contains aggregate bridge rows absent from database preflight"
            )
        indexes = block.column_indexes
        admission_key = _admission_key_copy(
            fields[indexes["admission_key"]], field="aggregate admission key"
        )
        input_kind = _plain_copy_text(
            fields[indexes["input_kind"]], field="aggregate admission input kind"
        )
        public_study_key = _optional_plain_copy_text(
            fields[indexes["public_study_key"]],
            field="aggregate admission public study key",
        )
        if public_study_key is not None:
            if SAFE_PUBLIC_STUDY_KEY.fullmatch(public_study_key) is None:
                raise SanitizationError(
                    "aggregate admission public study key is not a contract key"
                )
        accepted_observation_id = _optional_canonical_uuid(
            fields[indexes["accepted_observation_id"]],
            field="aggregate admission accepted observation id",
        )
        binding_key = _optional_plain_copy_text(
            fields[indexes["binding_key"]], field="aggregate admission binding key"
        )
        if binding_key is not None and SAFE_CONTRACT_KEY.fullmatch(binding_key) is None:
            raise SanitizationError("aggregate admission binding key is not a contract key")
        fingerprint = _sha256_copy(
            fields[indexes["canonical_opening_fingerprint_sha256"]],
            field="aggregate admission opening fingerprint hash",
        )
        _contract_key_copy(
            fields[indexes["admission_contract_version"]],
            field="aggregate admission contract version",
        )
        _sha256_copy(
            fields[indexes["admission_contract_sha256"]],
            field="aggregate admission contract hash",
        )
        _utc_copy_timestamp(
            fields[indexes["admitted_at"]], field="aggregate admission admitted_at"
        )
        if input_kind == "public_study":
            if (
                public_study_key is None
                or accepted_observation_id is not None
                or binding_key is not None
            ):
                raise SanitizationError(
                    "aggregate public-study admission has an invalid input shape"
                )
        elif input_kind == "authorized_opening":
            if (
                public_study_key is not None
                or accepted_observation_id is None
                or binding_key is None
            ):
                raise SanitizationError(
                    "aggregate authorized-opening admission has an invalid input shape"
                )
        else:
            raise SanitizationError("aggregate admission input kind is not approved")
        if admission_key in self.reviewed_global_aggregate_input_admissions:
            raise SanitizationError("aggregate admission key is duplicated")
        if fingerprint in self.reviewed_global_aggregate_input_fingerprints:
            raise SanitizationError("aggregate admission fingerprint is duplicated")
        self.reviewed_global_aggregate_input_fingerprints.add(fingerprint)
        if public_study_key is not None:
            if public_study_key in self.reviewed_global_aggregate_public_study_keys:
                raise SanitizationError("aggregate admission public study key is duplicated")
            self.reviewed_global_aggregate_public_study_keys.add(public_study_key)
        if accepted_observation_id is not None:
            if (
                accepted_observation_id
                in self.reviewed_global_aggregate_accepted_observation_ids
            ):
                raise SanitizationError(
                    "aggregate admission accepted observation id is duplicated"
                )
            self.reviewed_global_aggregate_accepted_observation_ids.add(
                accepted_observation_id
            )
        self.reviewed_global_aggregate_input_admissions[admission_key] = (
            input_kind,
            binding_key,
        )

    def _inspect_public_study_row(self, block: CopyBlock, fields: list[bytes]) -> None:
        indexes = block.column_indexes
        study_key_value = fields[indexes["study_key"]]
        _plain_copy_text(study_key_value, field="public-study key")
        exact_fields = PUBLIC_STUDY_EXACT_FIELDS.get(study_key_value)
        source_key = PUBLIC_STUDY_POLICY_SOURCE_KEY.get(study_key_value)
        expected_observed_at = PUBLIC_STUDY_OBSERVED_AT.get(study_key_value)
        if exact_fields is None or source_key is None or expected_observed_at is None:
            raise SanitizationError(
                "public-study ledger contains an unapproved study key"
            )
        if study_key_value in self.public_study_rows:
            raise SanitizationError(
                "public-study ledger contains a duplicate study key"
            )

        for column, expected_value in exact_fields.items():
            actual_value = fields[indexes[column]]
            _plain_copy_text(actual_value, field=f"public-study {column}")
            if actual_value != expected_value:
                raise SanitizationError(
                    f"public-study {column} does not match the reviewed contract"
                )

        policy_id = _canonical_uuid(
            fields[indexes["source_policy_id"]], field="public-study policy id"
        )
        for column, seen_ids in self.public_study_object_ids.items():
            object_id = _canonical_uuid(
                fields[indexes[column]], field=f"public-study {column}"
            )
            if object_id in seen_ids:
                raise SanitizationError(f"public-study {column} is duplicated")
            seen_ids.add(object_id)

        observed_at = _utc_copy_timestamp(
            fields[indexes["source_observed_at"]],
            field="public-study source_observed_at",
        )
        if observed_at != expected_observed_at:
            raise SanitizationError(
                "public-study source_observed_at does not match the reviewed contract"
            )
        first_verified_at = _utc_copy_timestamp(
            fields[indexes["first_verified_at"]],
            field="public-study first_verified_at",
        )
        last_verified_at = _utc_copy_timestamp(
            fields[indexes["last_verified_at"]],
            field="public-study last_verified_at",
        )
        if last_verified_at < first_verified_at:
            raise SanitizationError(
                "public-study verification timestamps are out of order"
            )
        evidence_sha256 = fields[indexes["evidence_sha256"]]
        _plain_copy_text(evidence_sha256, field="public-study evidence_sha256")
        if re.fullmatch(rb"[0-9a-f]{64}", evidence_sha256) is None:
            raise SanitizationError(
                "public-study evidence_sha256 is not a lowercase SHA-256"
            )
        self.public_study_rows[study_key_value] = (source_key, policy_id)

    def _validate_complete(self) -> None:
        for table, expected_present in self.expected.items():
            count = self.seen[table]
            if expected_present and count != 1:
                raise SanitizationError(
                    "expected retention-control COPY block is missing: "
                    f"{'.'.join(table)}"
                )
            if not expected_present and count != 0:
                raise SanitizationError(
                    f"unexpected retention-control COPY block: {'.'.join(table)}"
                )

        expected_create_count = int(self.expected[YOUTUBE_DISCOVERIES])
        if self.youtube_create_count != expected_create_count:
            if expected_create_count:
                raise SanitizationError(
                    "expected one UNLOGGED youtube_discoveries CREATE TABLE header"
                )
            raise SanitizationError(
                "unexpected youtube_discoveries CREATE TABLE header"
            )

        expected_public_create_count = int(self.expected[PUBLIC_STUDY_OBSERVATIONS])
        if self.public_study_create_count != expected_public_create_count:
            if expected_public_create_count:
                raise SanitizationError(
                    "expected one regular public_study_observations CREATE TABLE definition"
                )
            raise SanitizationError(
                "unexpected public_study_observations CREATE TABLE definition"
            )

        for table in REVIEWED_GLOBAL_AGGREGATE_BRIDGE_TABLES:
            expected_bridge_table = int(
                self.reviewed_global_aggregate_bridge_present
            )
            if (
                self.reviewed_global_aggregate_bridge_create_counts[table]
                != expected_bridge_table
            ):
                if expected_bridge_table:
                    raise SanitizationError(
                        f"expected one {table[1]} CREATE TABLE definition"
                    )
                raise SanitizationError(
                    f"unexpected {table[1]} CREATE TABLE definition"
                )
            if (
                self.reviewed_global_aggregate_bridge_force_rls_counts[table]
                != expected_bridge_table
            ):
                raise SanitizationError(
                    f"{table[1]} FORCE RLS does not match database preflight"
                )
            if (
                self.reviewed_global_aggregate_bridge_enable_rls_counts[table]
                != expected_bridge_table
            ):
                raise SanitizationError(
                    f"{table[1]} ENABLE RLS does not match database preflight"
                )
            expected_constraints = (
                REVIEWED_GLOBAL_AGGREGATE_BRIDGE_ALTER_CONSTRAINTS[table]
                if expected_bridge_table
                else set()
            )
            if (
                self.reviewed_global_aggregate_bridge_constraints[table]
                != expected_constraints
            ):
                raise SanitizationError(
                    f"{table[1]} constraint set does not match the reviewed contract"
                )
        expected_indexes = {
            REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCES: set(),
            REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_SOURCE_BINDINGS: (
                {REVIEWED_GLOBAL_AGGREGATE_AUTHORIZED_BINDING_INDEX}
                if self.reviewed_global_aggregate_bridge_present
                else set()
            ),
            REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSIONS: (
                set(REVIEWED_GLOBAL_AGGREGATE_INPUT_ADMISSION_INDEXES)
                if self.reviewed_global_aggregate_bridge_present
                else set()
            ),
        }
        if self.reviewed_global_aggregate_bridge_indexes != expected_indexes:
            raise SanitizationError(
                "aggregate bridge index set does not match the reviewed contract"
            )
        if self.reviewed_global_aggregate_bridge_present:
            retained_independent_sources = {
                (source_key, *contract)
                for source_key, contract in (
                    self.reviewed_global_aggregate_independent_sources.items()
                )
            }
            if (
                retained_independent_sources
                != REVIEWED_GLOBAL_AGGREGATE_INDEPENDENT_SOURCE_SEEDS
            ):
                raise SanitizationError(
                    "aggregate independent-source seed set does not match the reviewed contract"
                )
        for _binding_key, independent_source_key in (
            self.reviewed_global_aggregate_authorized_source_bindings.items()
        ):
            if (
                independent_source_key
                not in self.reviewed_global_aggregate_independent_sources
            ):
                raise SanitizationError(
                    "aggregate binding has no retained independent source"
                )
        for _admission_key, (input_kind, binding_key) in (
            self.reviewed_global_aggregate_input_admissions.items()
        ):
            if (
                input_kind == "authorized_opening"
                and binding_key
                not in self.reviewed_global_aggregate_authorized_source_bindings
            ):
                raise SanitizationError("aggregate admission has no retained binding")

        if self.request_gates_create_count != 1:
            raise SanitizationError(
                "expected one regular source_request_gates CREATE TABLE header"
            )
        if self.request_gates_force_rls_count != 1:
            raise SanitizationError("expected one source_request_gates FORCE RLS")
        if self.request_gates_primary_key_count != 1:
            raise SanitizationError("expected one source_request_gates primary key")
        if self.request_gates_enable_rls_count != 1:
            raise SanitizationError("expected one source_request_gates ENABLE RLS")
        if self.tcgdex_policy_rows != 1:
            raise SanitizationError(
                "dump must contain one exact TCGdex catalog source policy"
            )
        expected_bluesky_policy_ids = (
            [self.preflight_bluesky_policy_id] if self.bluesky_jetstream_present else []
        )
        if self.bluesky_policy_ids != expected_bluesky_policy_ids:
            raise SanitizationError(
                "dump Bluesky policy does not match the database preflight"
            )
        if self.bluesky_checkpoint_rows != int(self.bluesky_jetstream_present):
            raise SanitizationError(
                "dump Bluesky checkpoint does not match the database preflight"
            )
        if any(
            len(policy_ids) != int(self.nostr_relay_present)
            for policy_ids in self.nostr_policy_ids.values()
        ):
            raise SanitizationError(
                "dump Nostr policies do not match the database preflight"
            )
        if self.nostr_relay_present:
            for index, source_key in enumerate(NOSTR_SOURCE_KEYS):
                if (
                    self.nostr_policy_ids[source_key][0]
                    != self.preflight_nostr_policy_ids[index]
                ):
                    raise SanitizationError(
                        "dump Nostr policies do not match the database preflight"
                    )
        if self.nostr_checkpoint_rows != (
            len(NOSTR_SOURCE_KEYS) if self.nostr_relay_present else 0
        ):
            raise SanitizationError(
                "dump Nostr checkpoint does not match the database preflight"
            )
        if self.nostr_relay_present and set(self.nostr_checkpoint_policy_ids) != set(
            NOSTR_RELAY_KEYS
        ):
            raise SanitizationError(
                "dump Nostr checkpoint does not contain every approved relay"
            )
        expected_mastodon_policy_ids = (
            [self.preflight_mastodon_policy_id]
            if self.mastodon_public_hashtag_present
            else []
        )
        if self.mastodon_policy_ids != expected_mastodon_policy_ids:
            raise SanitizationError(
                "dump Mastodon policy does not match the database preflight"
            )
        if self.mastodon_checkpoint_rows != (
            len(MASTODON_TAG_KEYS) if self.mastodon_public_hashtag_present else 0
        ):
            raise SanitizationError(
                "dump Mastodon checkpoint does not match the database preflight"
            )
        if self.mastodon_public_hashtag_present and (
            self.mastodon_checkpoint_tag_keys != set(MASTODON_TAG_KEYS)
            or self.mastodon_cooldown_rows != 1
        ):
            raise SanitizationError(
                "dump Mastodon checkpoint/cooldown set is not exact"
            )
        if not self.mastodon_public_hashtag_present and self.mastodon_cooldown_rows:
            raise SanitizationError(
                "dump contains Mastodon cooldown without the exact table set"
            )
        expected_public_policy_rows = int(self.expected[PUBLIC_STUDY_OBSERVATIONS])
        if any(
            len(policy_ids) != expected_public_policy_rows
            for policy_ids in self.public_study_policy_ids.values()
        ):
            raise SanitizationError(
                "dump public-study policies do not match the database preflight"
            )
        retained_public_policy_ids = [
            policy_ids[0]
            for policy_ids in self.public_study_policy_ids.values()
            if policy_ids
        ]
        if len(set(retained_public_policy_ids)) != len(retained_public_policy_ids):
            raise SanitizationError(
                "public-study source policies must use distinct UUIDs"
            )
        for source_key, policy_id in self.public_study_rows.values():
            if self.public_study_policy_ids[source_key] != [policy_id]:
                raise SanitizationError(
                    "public-study ledger row does not use its exact source policy"
                )

        if self.preflight_youtube_policy_id is None:
            if self.youtube_policy_rows:
                raise SanitizationError(
                    "dump contains a YouTube policy absent from the database preflight"
                )
            return
        if self.youtube_policy_rows != [self.preflight_youtube_policy_id]:
            raise SanitizationError(
                "dump YouTube policy does not exactly match the database preflight"
            )

    def _scan(self, source: BinaryIO, spool: BinaryIO) -> None:
        block: CopyBlock | None = None
        sql_lex_state = SqlLexState()
        for line in source:
            spool.write(line)
            if block is not None:
                if line in (b"\\.\n", b"\\.\r\n"):
                    block = None
                    continue
                self._inspect_control_row(block, line)
                continue

            if sql_lex_state.mode != "normal":
                _advance_sql_lex_state(line, sql_lex_state)
                continue

            if self.request_gates_create_lines is not None:
                self.request_gates_create_lines.append(line)
                if line.rstrip() == b");":
                    self._finish_request_gates_create()
                continue

            if self.public_study_create_lines is not None:
                self.public_study_create_lines.append(line)
                if line.rstrip() == b");":
                    self._finish_public_study_create()
                continue

            if self.reviewed_global_aggregate_bridge_create_lines is not None:
                self.reviewed_global_aggregate_bridge_create_lines.append(line)
                if line.rstrip() == b");":
                    self._finish_reviewed_global_aggregate_bridge_create()
                continue

            if self.request_gates_alter_lines is not None:
                self.request_gates_alter_lines.append(line)
                if line.rstrip().endswith(b";"):
                    self._finish_request_gates_alter()
                continue

            if self.reviewed_global_aggregate_bridge_alter_lines is not None:
                self.reviewed_global_aggregate_bridge_alter_lines.append(line)
                if line.rstrip().endswith(b";"):
                    self._finish_reviewed_global_aggregate_bridge_alter()
                continue

            if self.reviewed_global_aggregate_bridge_index_lines is not None:
                self.reviewed_global_aggregate_bridge_index_lines.append(line)
                if line.rstrip().endswith(b";"):
                    self._finish_reviewed_global_aggregate_bridge_index()
                continue

            if self.policy_statement_lines is not None:
                self.policy_statement_lines.append(line)
                self._maybe_finish_policy_statement()
                continue

            header = parse_copy_header(line)
            if header is not None:
                if (
                    len(header.table) == 1
                    and header.table[0] in UNQUALIFIED_TARGET_TABLES
                ):
                    raise SanitizationError(
                        "retention-control COPY targets must be schema-qualified"
                    )
                if header.table == SOURCE_REQUEST_GATES:
                    raise SanitizationError(
                        "source_request_gates data must be excluded by pg_dump"
                    )
                if header.table in EPHEMERAL_ACTIVITY_TABLES:
                    raise SanitizationError(
                        "private activity data must be excluded by pg_dump"
                    )
                block = self._start_block(header)
                continue

            if parse_youtube_create(line):
                self.youtube_create_count += 1
                if self.youtube_create_count != 1:
                    raise SanitizationError(
                        "duplicate youtube_discoveries CREATE TABLE header"
                    )
                continue

            if parse_request_gates_create(line):
                self.request_gates_create_count += 1
                if self.request_gates_create_count != 1:
                    raise SanitizationError(
                        "duplicate source_request_gates CREATE TABLE header"
                    )
                self.request_gates_create_lines = [line]
                continue

            if parse_public_study_create(line):
                self.public_study_create_count += 1
                if self.public_study_create_count != 1:
                    raise SanitizationError(
                        "duplicate public_study_observations CREATE TABLE header"
                    )
                self.public_study_create_lines = [line]
                continue

            aggregate_bridge_create_table = (
                parse_reviewed_global_aggregate_bridge_create(line)
            )
            if aggregate_bridge_create_table is not None:
                self.reviewed_global_aggregate_bridge_create_counts[
                    aggregate_bridge_create_table
                ] += 1
                if (
                    self.reviewed_global_aggregate_bridge_create_counts[
                        aggregate_bridge_create_table
                    ]
                    != 1
                ):
                    raise SanitizationError(
                        "duplicate aggregate bridge CREATE TABLE header"
                    )
                self.reviewed_global_aggregate_bridge_create_table = (
                    aggregate_bridge_create_table
                )
                self.reviewed_global_aggregate_bridge_create_lines = [line]
                continue

            normalized_line = _normalize_sql((line,))
            if normalized_line.startswith(POLICY_STATEMENT_PREFIXES):
                self.policy_statement_lines = [line]
                self._maybe_finish_policy_statement()
                continue
            if normalized_line.startswith(
                (
                    "alter table only ingest.source_request_gates",
                    "alter table ingest.source_request_gates",
                )
            ):
                self.request_gates_alter_lines = [line]
                if line.rstrip().endswith(b";"):
                    self._finish_request_gates_alter()
                continue
            aggregate_bridge_alter_table = (
                _reviewed_global_aggregate_bridge_alter_table(normalized_line)
            )
            if aggregate_bridge_alter_table is not None:
                self.reviewed_global_aggregate_bridge_alter_table = (
                    aggregate_bridge_alter_table
                )
                self.reviewed_global_aggregate_bridge_alter_lines = [line]
                if line.rstrip().endswith(b";"):
                    self._finish_reviewed_global_aggregate_bridge_alter()
                continue
            aggregate_bridge_index_table = (
                _reviewed_global_aggregate_bridge_index_table(normalized_line)
            )
            if aggregate_bridge_index_table is not None:
                self.reviewed_global_aggregate_bridge_index_table = (
                    aggregate_bridge_index_table
                )
                self.reviewed_global_aggregate_bridge_index_lines = [line]
                if line.rstrip().endswith(b";"):
                    self._finish_reviewed_global_aggregate_bridge_index()
                continue

            try:
                text = line.decode("utf-8")
            except UnicodeDecodeError:
                text = ""
            if TARGET_INSERT.match(text):
                raise SanitizationError(
                    "retention-control table data must use COPY FROM stdin"
                )
            _advance_sql_lex_state(line, sql_lex_state)

        if block is not None:
            raise SanitizationError("unterminated COPY data block")
        if sql_lex_state.mode != "normal":
            raise SanitizationError("unterminated SQL quoted body or comment")
        if self.request_gates_create_lines is not None:
            raise SanitizationError("unterminated source_request_gates CREATE TABLE")
        if self.public_study_create_lines is not None:
            raise SanitizationError(
                "unterminated public_study_observations CREATE TABLE"
            )
        if self.reviewed_global_aggregate_bridge_create_lines is not None:
            raise SanitizationError("unterminated aggregate bridge CREATE TABLE")
        if self.request_gates_alter_lines is not None:
            raise SanitizationError("unterminated source_request_gates ALTER TABLE")
        if self.reviewed_global_aggregate_bridge_alter_lines is not None:
            raise SanitizationError("unterminated aggregate bridge ALTER TABLE")
        if self.reviewed_global_aggregate_bridge_index_lines is not None:
            raise SanitizationError("unterminated aggregate bridge CREATE INDEX")
        if self.policy_statement_lines is not None:
            raise SanitizationError("unterminated policy statement")
        self._validate_complete()

    def _emit(self, source: BinaryIO, destination: BinaryIO) -> None:
        block: CopyBlock | None = None
        gate_seed_written = False
        for line in source:
            if block is not None:
                if line in (b"\\.\n", b"\\.\r\n"):
                    destination.write(line)
                    block = None
                    continue
                if block.header.table != YOUTUBE_DISCOVERIES:
                    destination.write(line)
                continue

            header = parse_copy_header(line)
            if header is not None:
                block = CopyBlock(header=header, column_indexes=_column_indexes(header))
            if _normalize_sql((line,)) == REQUEST_GATES_ENABLE_RLS:
                destination.write(
                    b"\n-- Canonical idle request gates; live lease ownership is not retained.\n"
                    b"COPY ingest.source_request_gates (source_key) FROM stdin;\n"
                    b"tcgdex_catalog\n"
                )
                if self.expected[YOUTUBE_DISCOVERIES]:
                    destination.write(b"youtube_discovery\n")
                if self.bluesky_jetstream_present:
                    destination.write(b"bluesky_jetstream\n")
                if self.nostr_relay_present:
                    destination.writelines(
                        source_key + b"\n" for source_key in NOSTR_SOURCE_KEYS
                    )
                if self.mastodon_public_hashtag_present:
                    destination.write(MASTODON_SOURCE_KEY + b"\n")
                if self.expected[PUBLIC_STUDY_OBSERVATIONS]:
                    destination.writelines(
                        source_key + b"\n" for source_key in PUBLIC_STUDY_SOURCE_KEYS
                    )
                destination.write(b"\\.\n\n")
                gate_seed_written = True
            destination.write(line)

        if block is not None:
            raise SanitizationError("unterminated COPY data block")

        if not gate_seed_written:
            raise SanitizationError("request-gate seed insertion point is missing")

    def sanitize(self, source: BinaryIO, destination: BinaryIO) -> None:
        # Spool the entire pg_dump snapshot before emitting anything. This
        # keeps every structural mismatch fail-closed while avoiding buffering
        # a potentially large logical backup in RAM.
        with tempfile.TemporaryFile(mode="w+b") as spool:
            os.fchmod(spool.fileno(), 0o600)
            if stat.S_IMODE(os.fstat(spool.fileno()).st_mode) != 0o600:
                raise SanitizationError("temporary dump spool is not mode 0600")
            self._scan(source, spool)
            spool.flush()
            spool.seek(0)
            self._emit(spool, destination)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove disposable YouTube and private Bluesky/Nostr/Mastodon activity rows from a plain dump."
        )
    )
    presence = ("present", "absent")
    parser.add_argument("--source-policies", required=True, choices=presence)
    parser.add_argument("--youtube-discoveries", required=True, choices=presence)
    parser.add_argument("--public-studies", required=True, choices=presence)
    parser.add_argument("--bluesky-jetstream", required=True, choices=presence)
    # Kept optional for compatibility with pre-Nostr backup invocations.  The
    # current backup script always supplies this state explicitly.
    parser.add_argument("--nostr-relay", choices=presence, default="absent")
    parser.add_argument("--mastodon-public-hashtag", choices=presence, default="absent")
    parser.add_argument(
        "--reviewed-global-aggregate-bridge",
        choices=presence,
        default="absent",
    )
    parser.add_argument("--youtube-policy-id")
    parser.add_argument("--bluesky-policy-id")
    parser.add_argument("--mastodon-policy-id")
    parser.add_argument(
        "--nostr-policy-id",
        action="append",
        dest="nostr_policy_ids",
        default=[],
        metavar="UUID",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        sanitizer = PlainBackupSanitizer(
            source_policies_present=args.source_policies == "present",
            youtube_discoveries_present=args.youtube_discoveries == "present",
            public_studies_present=args.public_studies == "present",
            bluesky_jetstream_present=args.bluesky_jetstream == "present",
            youtube_policy_id=args.youtube_policy_id,
            bluesky_policy_id=args.bluesky_policy_id,
            nostr_relay_present=args.nostr_relay == "present",
            nostr_policy_ids=tuple(args.nostr_policy_ids),
            mastodon_public_hashtag_present=args.mastodon_public_hashtag == "present",
            mastodon_policy_id=args.mastodon_policy_id,
            reviewed_global_aggregate_bridge_present=(
                args.reviewed_global_aggregate_bridge == "present"
            ),
        )
        sanitizer.sanitize(sys.stdin.buffer, sys.stdout.buffer)
    except (SanitizationError, UnicodeEncodeError) as exc:
        print(f"backup sanitizer: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
