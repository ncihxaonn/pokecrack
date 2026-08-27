#!/usr/bin/env python3
"""Remove the disposable YouTube discovery cache from a plain PostgreSQL dump.

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
from dataclasses import dataclass
from typing import BinaryIO
from uuid import UUID

SOURCE_POLICIES = ("ingest", "source_policies")
YOUTUBE_DISCOVERIES = ("ingest", "youtube_discoveries")
SOURCE_REQUEST_GATES = ("ingest", "source_request_gates")
RETENTION_CONTROL_TABLES = frozenset({SOURCE_POLICIES, YOUTUBE_DISCOVERIES})
TCGDEX_SOURCE_KEY = b"tcgdex_catalog"
YOUTUBE_SOURCE_KEY = b"youtube_discovery"
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*\Z")
COPY_SUFFIX = re.compile(r"FROM\s+stdin;\s*\Z", re.IGNORECASE)
TARGET_INSERT = re.compile(
    r'^\s*INSERT\s+INTO\s+(?:ingest|"ingest")\.'
    r'(?:source_policies|"source_policies"|'
    r'youtube_discoveries|"youtube_discoveries"|'
    r'source_request_gates|"source_request_gates")(?:\s|\()',
    re.IGNORECASE,
)
YOUTUBE_CREATE_REFERENCE = re.compile(
    r'^\s*CREATE\s+(?:(?:UNLOGGED|TEMP|TEMPORARY)\s+)?TABLE\s+'
    r'(?:ingest(?![A-Za-z0-9_$])|"ingest")\s*\.\s*'
    r'(?:youtube_discoveries(?![A-Za-z0-9_$])|"youtube_discoveries")'
    r'(?:\s|\()',
    re.IGNORECASE,
)
YOUTUBE_CREATE = re.compile(
    r'^\s*CREATE\s+(?P<unlogged>UNLOGGED\s+)?TABLE\s+'
    r'(?:ingest(?![A-Za-z0-9_$])|"ingest")\s*\.\s*'
    r'(?:youtube_discoveries(?![A-Za-z0-9_$])|"youtube_discoveries")\s*\(',
    re.IGNORECASE,
)
REQUEST_GATES_CREATE_REFERENCE = re.compile(
    r'^\s*CREATE\s+(?:(?:UNLOGGED|TEMP|TEMPORARY)\s+)?TABLE\s+'
    r'(?:ingest(?![A-Za-z0-9_$])|"ingest")\s*\.\s*'
    r'(?:source_request_gates(?![A-Za-z0-9_$])|"source_request_gates")'
    r'(?:\s|\()',
    re.IGNORECASE,
)
REQUEST_GATES_CREATE = re.compile(
    r'^\s*CREATE\s+TABLE\s+'
    r'(?:ingest(?![A-Za-z0-9_$])|"ingest")\s*\.\s*'
    r'(?:source_request_gates(?![A-Za-z0-9_$])|"source_request_gates")\s*\(',
    re.IGNORECASE,
)


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
                    or not (
                        text[index - 2].isalnum()
                        or text[index - 2] in "_$"
                    )
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
                raise SanitizationError(
                    "policy statement has unsupported trailing SQL"
                )
            return tokens
        if character.isalpha() or character == "_":
            end = index + 1
            while end < len(text) and (
                text[end].isalnum() or text[end] in "_$"
            ):
                end += 1
            tokens.append(("word", text[index:end].casefold()))
            index = end
            continue
        tokens.append(("punctuation", character))
        index += 1
    return None


def _identifier_is(token: PolicyToken, expected: str) -> bool:
    kind, value = token
    return (kind == "word" and value == expected) or (
        kind == "quoted_identifier" and value == expected
    )


def _policy_targets_request_gates(tokens: list[PolicyToken]) -> bool:
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
        return (
            _identifier_is(tokens[target], "ingest")
            and tokens[target + 1] == ("punctuation", ".")
            and _identifier_is(tokens[target + 2], "source_request_gates")
        )
    raise SanitizationError("policy statement has no table target")


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

    table = tuple(_parse_identifier(part) for part in _split_outside_quotes(table_text, "."))
    columns = tuple(_parse_identifier(part) for part in _split_outside_quotes(columns_text, ","))
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
        raise SanitizationError(
            "unsupported youtube_discoveries CREATE TABLE header"
        )
    if match.group("unlogged") is None:
        raise SanitizationError(
            "youtube_discoveries CREATE TABLE is not UNLOGGED"
        )
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
        raise SanitizationError(
            "unsupported source_request_gates CREATE TABLE header"
        )
    return True


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


def _column_indexes(header: CopyHeader) -> dict[str, int]:
    return {column: index for index, column in enumerate(header.columns)}


class PlainBackupSanitizer:
    def __init__(
        self,
        *,
        source_policies_present: bool,
        youtube_discoveries_present: bool,
        youtube_policy_id: str | None,
    ) -> None:
        if youtube_policy_id is not None:
            youtube_policy_id = _canonical_uuid(
                youtube_policy_id.encode("ascii"), field="YouTube policy id"
            )
        if youtube_discoveries_present and not (
            source_policies_present and youtube_policy_id is not None
        ):
            raise SanitizationError(
                "youtube_discoveries exists without one exact YouTube policy"
            )
        if youtube_policy_id is not None and not youtube_discoveries_present:
            raise SanitizationError(
                "YouTube policy exists without youtube_discoveries"
            )

        self.expected = {
            SOURCE_POLICIES: source_policies_present,
            YOUTUBE_DISCOVERIES: youtube_discoveries_present,
        }
        self.preflight_youtube_policy_id = youtube_policy_id
        self.seen = {table: 0 for table in RETENTION_CONTROL_TABLES}
        self.youtube_policy_rows: list[str] = []
        self.tcgdex_policy_rows = 0
        self.youtube_create_count = 0
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
        expected = REQUEST_GATES_CREATE_EXPECTED[
            self.expected[YOUTUBE_DISCOVERIES]
        ]
        if _normalize_sql(lines) != expected:
            raise SanitizationError("unsupported source_request_gates schema")
        self.request_gates_create_lines = None

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
        self.policy_statement_lines = None

    def _start_block(self, header: CopyHeader) -> CopyBlock:
        indexes = _column_indexes(header)
        if header.table in RETENTION_CONTROL_TABLES:
            self.seen[header.table] += 1
            if self.seen[header.table] != 1:
                raise SanitizationError(
                    "duplicate retention-control COPY block: "
                    f"{'.'.join(header.table)}"
                )
        if header.table == SOURCE_POLICIES:
            if "id" not in indexes or "source_key" not in indexes:
                raise SanitizationError("source_policies COPY lacks id or source_key")
        elif (
            header.table == YOUTUBE_DISCOVERIES
            and "source_policy_id" not in indexes
        ):
            raise SanitizationError(
                "youtube_discoveries COPY lacks source_policy_id"
            )
        return CopyBlock(header=header, column_indexes=indexes)

    def _target_fields(self, block: CopyBlock, line: bytes) -> list[bytes]:
        fields = _without_line_ending(line).split(b"\t")
        if len(fields) != len(block.header.columns):
            raise SanitizationError(
                "retention-control COPY row has wrong field count"
            )
        return fields

    def _inspect_control_row(self, block: CopyBlock, line: bytes) -> None:
        if block.header.table not in RETENTION_CONTROL_TABLES:
            return
        fields = self._target_fields(block, line)
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
            return
        policy_id = _canonical_uuid(
            fields[block.column_indexes["source_policy_id"]],
            field="YouTube discovery policy id",
        )
        if policy_id != self.preflight_youtube_policy_id:
            raise SanitizationError(
                "youtube_discoveries row does not use the exact YouTube policy"
            )

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
                    "unexpected retention-control COPY block: "
                    f"{'.'.join(table)}"
                )

        expected_create_count = int(self.expected[YOUTUBE_DISCOVERIES])
        if self.youtube_create_count != expected_create_count:
            if expected_create_count:
                raise SanitizationError(
                    "expected one UNLOGGED youtube_discoveries CREATE TABLE "
                    "header"
                )
            raise SanitizationError(
                "unexpected youtube_discoveries CREATE TABLE header"
            )

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
        for line in source:
            spool.write(line)
            if block is not None:
                if line in (b"\\.\n", b"\\.\r\n"):
                    block = None
                    continue
                self._inspect_control_row(block, line)
                continue

            if self.request_gates_create_lines is not None:
                self.request_gates_create_lines.append(line)
                if line.rstrip() == b");":
                    self._finish_request_gates_create()
                continue

            if self.request_gates_alter_lines is not None:
                self.request_gates_alter_lines.append(line)
                if line.rstrip().endswith(b";"):
                    self._finish_request_gates_alter()
                continue

            if self.policy_statement_lines is not None:
                self.policy_statement_lines.append(line)
                self._maybe_finish_policy_statement()
                continue

            header = parse_copy_header(line)
            if header is not None:
                if header.table == SOURCE_REQUEST_GATES:
                    raise SanitizationError(
                        "source_request_gates data must be excluded by pg_dump"
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

            normalized_line = _normalize_sql((line,))
            if normalized_line.startswith(POLICY_STATEMENT_PREFIXES):
                self.policy_statement_lines = [line]
                self._maybe_finish_policy_statement()
                continue
            if normalized_line.startswith(
                "alter table only ingest.source_request_gates"
            ) or normalized_line.startswith(
                "alter table ingest.source_request_gates"
            ):
                self.request_gates_alter_lines = [line]
                if line.rstrip().endswith(b";"):
                    self._finish_request_gates_alter()
                continue

            try:
                text = line.decode("utf-8")
            except UnicodeDecodeError:
                text = ""
            if TARGET_INSERT.match(text):
                raise SanitizationError(
                    "retention-control table data must use COPY FROM stdin"
                )

        if block is not None:
            raise SanitizationError("unterminated COPY data block")
        if self.request_gates_create_lines is not None:
            raise SanitizationError("unterminated source_request_gates CREATE TABLE")
        if self.request_gates_alter_lines is not None:
            raise SanitizationError("unterminated source_request_gates ALTER TABLE")
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
                block = CopyBlock(
                    header=header, column_indexes=_column_indexes(header)
                )
            if _normalize_sql((line,)) == REQUEST_GATES_ENABLE_RLS:
                destination.write(
                    b"\n-- Canonical idle request gates; live lease ownership is not retained.\n"
                    b"COPY ingest.source_request_gates (source_key) FROM stdin;\n"
                    b"tcgdex_catalog\n"
                )
                if self.expected[YOUTUBE_DISCOVERIES]:
                    destination.write(b"youtube_discovery\n")
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
        description="Remove disposable YouTube discovery rows from a plain dump."
    )
    presence = ("present", "absent")
    parser.add_argument("--source-policies", required=True, choices=presence)
    parser.add_argument("--youtube-discoveries", required=True, choices=presence)
    parser.add_argument("--youtube-policy-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        sanitizer = PlainBackupSanitizer(
            source_policies_present=args.source_policies == "present",
            youtube_discoveries_present=args.youtube_discoveries == "present",
            youtube_policy_id=args.youtube_policy_id,
        )
        sanitizer.sanitize(sys.stdin.buffer, sys.stdout.buffer)
    except (SanitizationError, UnicodeEncodeError) as exc:
        print(f"backup sanitizer: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
