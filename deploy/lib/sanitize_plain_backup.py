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
RETENTION_CONTROL_TABLES = frozenset({SOURCE_POLICIES, YOUTUBE_DISCOVERIES})
YOUTUBE_SOURCE_KEY = b"youtube_discovery"
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*\Z")
COPY_SUFFIX = re.compile(r"FROM\s+stdin;\s*\Z", re.IGNORECASE)
TARGET_INSERT = re.compile(
    r'^\s*INSERT\s+INTO\s+(?:ingest|"ingest")\.'
    r'(?:source_policies|"source_policies"|'
    r'youtube_discoveries|"youtube_discoveries")(?:\s|\()',
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


class SanitizationError(ValueError):
    """The dump cannot be proved safe to retain."""


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
        self.youtube_create_count = 0

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

            header = parse_copy_header(line)
            if header is not None:
                block = self._start_block(header)
                continue

            if parse_youtube_create(line):
                self.youtube_create_count += 1
                if self.youtube_create_count != 1:
                    raise SanitizationError(
                        "duplicate youtube_discoveries CREATE TABLE header"
                    )
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
        self._validate_complete()

    def _emit(self, source: BinaryIO, destination: BinaryIO) -> None:
        block: CopyBlock | None = None
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
            destination.write(line)

        if block is not None:
            raise SanitizationError("unterminated COPY data block")

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
