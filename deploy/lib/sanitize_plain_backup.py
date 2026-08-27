#!/usr/bin/env python3
"""Remove retention-bounded YouTube rows from a plain PostgreSQL dump.

The backup entrypoint invokes this program between ``pg_dump`` and ``gzip``.
It deliberately supports only the stable, line-oriented ``COPY ... FROM
stdin`` representation emitted by the repository's fixed pg_dump command.
Unexpected structure is an error: a partial pipeline output must never be
promoted to a managed backup.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
import re
import stat
import sys
import tempfile
from typing import BinaryIO
from uuid import UUID


SOURCE_POLICIES = ("ingest", "source_policies")
SOURCE_ITEMS = ("ingest", "source_items")
SOURCE_DISCOVERIES = ("ingest", "source_discoveries")
TARGET_TABLES = frozenset({SOURCE_POLICIES, SOURCE_ITEMS, SOURCE_DISCOVERIES})
YOUTUBE_SOURCE_KEY = b"youtube_discovery"
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*\Z")
COPY_SUFFIX = re.compile(r"FROM\s+stdin;\s*\Z", re.IGNORECASE)
TARGET_INSERT = re.compile(
    r'^INSERT\s+INTO\s+(?:ingest|"ingest")\.'
    r'(?:source_policies|"source_policies"|source_items|"source_items"|'
    r'source_discoveries|"source_discoveries")(?:\s|\()'
)


class SanitizationError(ValueError):
    """The dump cannot be proved safe to retain."""


@dataclass(frozen=True)
class CopyHeader:
    table: tuple[str, ...]
    columns: tuple[str, ...]


@dataclass
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
        source_items_present: bool,
        source_discoveries_present: bool,
        youtube_policy_id: str | None,
    ) -> None:
        if youtube_policy_id is not None:
            youtube_policy_id = _canonical_uuid(
                youtube_policy_id.encode("ascii"), field="YouTube policy id"
            )
        if source_discoveries_present and youtube_policy_id is None:
            raise SanitizationError(
                "source_discoveries exists without an exact YouTube policy id"
            )
        if source_items_present and not source_policies_present:
            raise SanitizationError("source_items exists without source_policies")
        if youtube_policy_id is not None and not (
            source_policies_present and source_items_present
        ):
            raise SanitizationError(
                "YouTube policy exists without source_policies and source_items"
            )
        if source_discoveries_present and not source_items_present:
            raise SanitizationError("source_discoveries exists without source_items")

        self.expected = {
            SOURCE_POLICIES: source_policies_present,
            SOURCE_ITEMS: source_items_present,
            SOURCE_DISCOVERIES: source_discoveries_present,
        }
        self.preflight_youtube_policy_id = youtube_policy_id
        self.dump_youtube_policy_id: str | None = None
        self.seen = {table: 0 for table in TARGET_TABLES}
        self.youtube_policy_rows: list[str] = []
        self.discovery_source_item_ids: set[str] = set()

    def _start_block(self, header: CopyHeader) -> CopyBlock:
        indexes = _column_indexes(header)
        if header.table in TARGET_TABLES:
            self.seen[header.table] += 1
            if self.seen[header.table] != 1:
                raise SanitizationError("duplicate retention-sensitive COPY block")
        if header.table == SOURCE_POLICIES:
            if "id" not in indexes or "source_key" not in indexes:
                raise SanitizationError("source_policies COPY lacks id or source_key")
        elif header.table == SOURCE_ITEMS:
            if "id" not in indexes or "source_policy_id" not in indexes:
                raise SanitizationError(
                    "source_items COPY lacks id or source_policy_id"
                )
        elif header.table == SOURCE_DISCOVERIES and "source_item_id" not in indexes:
            raise SanitizationError("source_discoveries COPY lacks source_item_id")
        return CopyBlock(header=header, column_indexes=indexes)

    def _target_fields(self, block: CopyBlock, line: bytes) -> list[bytes]:
        content = _without_line_ending(line)
        fields = content.split(b"\t")
        if len(fields) != len(block.header.columns):
            raise SanitizationError(
                "retention-sensitive COPY row has wrong field count"
            )
        return fields

    def _inspect_row(self, block: CopyBlock, line: bytes) -> None:
        table = block.header.table
        if table not in TARGET_TABLES:
            return
        fields = self._target_fields(block, line)
        if table == SOURCE_DISCOVERIES:
            source_item_id = _canonical_uuid(
                fields[block.column_indexes["source_item_id"]],
                field="discovery source item id",
            )
            self.discovery_source_item_ids.add(source_item_id)
            return
        if table == SOURCE_POLICIES:
            source_key = fields[block.column_indexes["source_key"]]
            if b"\\" in source_key or source_key == b"\\N":
                raise SanitizationError("source policy key is not plain text")
            if source_key == YOUTUBE_SOURCE_KEY:
                policy_id = _canonical_uuid(
                    fields[block.column_indexes["id"]], field="dump policy id"
                )
                self.youtube_policy_rows.append(policy_id)
            return

        _canonical_uuid(fields[block.column_indexes["id"]], field="source item id")
        _canonical_uuid(
            fields[block.column_indexes["source_policy_id"]],
            field="source item policy id",
        )

    def _validate_complete(self) -> None:
        for table, expected_present in self.expected.items():
            count = self.seen[table]
            if expected_present and count != 1:
                raise SanitizationError(
                    f"expected retention-sensitive COPY block is missing: {'.'.join(table)}"
                )
            if not expected_present and count != 0:
                raise SanitizationError(
                    f"unexpected retention-sensitive COPY block: {'.'.join(table)}"
                )

        if self.preflight_youtube_policy_id is None:
            if self.youtube_policy_rows:
                raise SanitizationError(
                    "dump contains a YouTube policy absent from the database preflight"
                )
            self.dump_youtube_policy_id = None
        elif self.youtube_policy_rows != [self.preflight_youtube_policy_id]:
            raise SanitizationError(
                "dump YouTube policy does not exactly match the database preflight"
            )
        else:
            # Filtering is deliberately keyed by the mapping parsed from this
            # exact pg_dump snapshot. The psql value is only a cross-check.
            self.dump_youtube_policy_id = self.youtube_policy_rows[0]

    def _scan(self, source: BinaryIO, spool: BinaryIO) -> None:
        block: CopyBlock | None = None
        for line in source:
            spool.write(line)
            if block is not None:
                if line in (b"\\.\n", b"\\.\r\n"):
                    block = None
                    continue
                self._inspect_row(block, line)
                continue

            header = parse_copy_header(line)
            if header is not None:
                block = self._start_block(header)
                continue

            try:
                text = line.decode("utf-8")
            except UnicodeDecodeError:
                text = ""
            if TARGET_INSERT.match(text):
                raise SanitizationError(
                    "retention-sensitive table data must use COPY FROM stdin"
                )

        if block is not None:
            raise SanitizationError("unterminated COPY data block")
        self._validate_complete()

    def _emit(self, source: BinaryIO, destination: BinaryIO) -> None:
        block: CopyBlock | None = None
        unmatched_discovery_ids = set(self.discovery_source_item_ids)

        for line in source:
            if block is not None:
                if line in (b"\\.\n", b"\\.\r\n"):
                    destination.write(line)
                    block = None
                    continue

                table = block.header.table
                if table == SOURCE_DISCOVERIES:
                    continue
                if table == SOURCE_ITEMS:
                    fields = self._target_fields(block, line)
                    source_item_id = _canonical_uuid(
                        fields[block.column_indexes["id"]],
                        field="source item id",
                    )
                    policy_id = _canonical_uuid(
                        fields[block.column_indexes["source_policy_id"]],
                        field="source item policy id",
                    )
                    is_discovery_parent = (
                        source_item_id in self.discovery_source_item_ids
                    )
                    if is_discovery_parent:
                        unmatched_discovery_ids.discard(source_item_id)
                    if is_discovery_parent or policy_id == self.dump_youtube_policy_id:
                        continue
                destination.write(line)
                continue

            header = parse_copy_header(line)
            if header is not None:
                # The first pass already proved uniqueness and required columns.
                block = CopyBlock(header=header, column_indexes=_column_indexes(header))
            destination.write(line)

        if block is not None:
            raise SanitizationError("unterminated COPY data block")
        if unmatched_discovery_ids:
            raise SanitizationError(
                "discovery row refers to a source item absent from the dump"
            )

    def sanitize(self, source: BinaryIO, destination: BinaryIO) -> None:
        # pg_dump is internally snapshot-consistent, but table order is not a
        # retention contract. Spooling to an unlinked 0600 file lets the first
        # pass derive every discovery parent and policy mapping from one dump,
        # then lets the second pass filter without buffering the dump in RAM.
        with tempfile.TemporaryFile(mode="w+b") as spool:
            os.fchmod(spool.fileno(), 0o600)
            if stat.S_IMODE(os.fstat(spool.fileno()).st_mode) != 0o600:
                raise SanitizationError("temporary dump spool is not mode 0600")
            self._scan(source, spool)
            spool.flush()
            spool.seek(0)
            self._emit(spool, destination)


def _presence(value: str) -> bool:
    return value == "present"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sanitize retention-bounded rows from a plain PostgreSQL dump."
    )
    choices = ("present", "absent")
    parser.add_argument("--source-policies", required=True, choices=choices)
    parser.add_argument("--source-items", required=True, choices=choices)
    parser.add_argument("--source-discoveries", required=True, choices=choices)
    parser.add_argument("--youtube-policy-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        sanitizer = PlainBackupSanitizer(
            source_policies_present=_presence(args.source_policies),
            source_items_present=_presence(args.source_items),
            source_discoveries_present=_presence(args.source_discoveries),
            youtube_policy_id=args.youtube_policy_id,
        )
        sanitizer.sanitize(sys.stdin.buffer, sys.stdout.buffer)
    except (SanitizationError, UnicodeEncodeError) as exc:
        print(f"backup sanitizer: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
