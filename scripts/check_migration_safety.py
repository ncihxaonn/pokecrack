"""Audit only unapplied Supabase migrations for destructive SQL.

DELETE statements require an exact, reasoned fingerprint in the repository
allowlist. DROP/TRUNCATE statements are never allowlisted by this gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIGRATION_NAME = re.compile(r"^(?P<version>\d{14})_[a-z0-9_]+\.sql$")
VERSION = re.compile(r"^\d{14}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DESTRUCTIVE_SQL = re.compile(
    r"(?P<delete>\bdelete\s+from\b)"
    r"|(?P<truncate>\btruncate(?:\s+table)?\b)"
    r"|(?P<drop>\bdrop\s+(?:database|schema|table|column)\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DestructiveStatement:
    kind: str
    line: int
    normalized: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class MigrationAudit:
    pending: tuple[str, ...]
    reviewed_deletes: int
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def _without_comments(source: str) -> str:
    """Remove SQL comments while preserving offsets and executable bodies."""

    output = list(source)
    index = 0
    block_depth = 0
    quote: str | None = None
    while index < len(source):
        if quote is not None:
            if source[index] == quote:
                if index + 1 < len(source) and source[index + 1] == quote:
                    index += 2
                    continue
                quote = None
            elif quote == "'" and source[index] == "\\" and index + 1 < len(source):
                index += 2
                continue
            index += 1
            continue
        if block_depth:
            if source.startswith("/*", index):
                output[index : index + 2] = "  "
                block_depth += 1
                index += 2
            elif source.startswith("*/", index):
                output[index : index + 2] = "  "
                block_depth -= 1
                index += 2
            else:
                if source[index] != "\n":
                    output[index] = " "
                index += 1
            continue
        if source[index] in {"'", '"'}:
            quote = source[index]
            index += 1
            continue
        if source.startswith("--", index):
            end = source.find("\n", index)
            if end == -1:
                end = len(source)
            for offset in range(index, end):
                output[offset] = " "
            index = end
            continue
        if source.startswith("/*", index):
            output[index : index + 2] = "  "
            block_depth = 1
            index += 2
            continue
        index += 1
    if block_depth:
        raise ValueError("unterminated SQL block comment")
    if quote is not None:
        raise ValueError("unterminated SQL quoted value")
    return "".join(output)


def _statement_end(source: str, start: int) -> int:
    index = start
    quote: str | None = None
    dollar_quote: str | None = None
    while index < len(source):
        if dollar_quote is not None:
            if source.startswith(dollar_quote, index):
                index += len(dollar_quote)
                dollar_quote = None
            else:
                index += 1
            continue
        if quote is not None:
            if source[index] == quote:
                if index + 1 < len(source) and source[index + 1] == quote:
                    index += 2
                    continue
                quote = None
            elif quote == "'" and source[index] == "\\" and index + 1 < len(source):
                index += 2
                continue
            index += 1
            continue
        if source[index] in {"'", '"'}:
            quote = source[index]
            index += 1
            continue
        if source[index] == "$":
            delimiter = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", source[index:])
            if delimiter is not None:
                dollar_quote = delimiter.group(0)
                index += len(dollar_quote)
                continue
        if source[index] == ";":
            return index + 1
        index += 1
    return len(source)


def _normalize_statement(source: str) -> str:
    return " ".join(source.casefold().split())


def scan_destructive_statements(source: str) -> tuple[DestructiveStatement, ...]:
    uncommented = _without_comments(source)
    statements: list[DestructiveStatement] = []
    for match in DESTRUCTIVE_SQL.finditer(uncommented):
        kind = next(
            name for name, value in match.groupdict().items() if value is not None
        )
        normalized = _normalize_statement(
            uncommented[match.start() : _statement_end(uncommented, match.start())]
        )
        statements.append(
            DestructiveStatement(
                kind=kind,
                line=source.count("\n", 0, match.start()) + 1,
                normalized=normalized,
                fingerprint=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            )
        )
    return tuple(statements)


def _migration_files(directory: Path) -> dict[str, Path]:
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("migrations directory must be a real directory")
    migrations: dict[str, Path] = {}
    for path in sorted(directory.glob("*.sql")):
        if path.is_symlink():
            raise ValueError(f"migration file must not be a symbolic link: {path.name}")
        match = MIGRATION_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError(f"invalid migration filename: {path.name}")
        version = match.group("version")
        if version in migrations:
            raise ValueError(f"duplicate migration version: {version}")
        migrations[version] = path
    return migrations


def _applied_versions(path: Path) -> set[str]:
    versions: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = raw.strip()
        if not value:
            continue
        if VERSION.fullmatch(value) is None:
            raise ValueError(f"invalid applied migration version at line {line_number}")
        versions.add(value)
    return versions


def _reviewed_deletes(path: Path) -> tuple[Counter[tuple[str, str]], list[str]]:
    try:
        document: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(
            "migration safety allowlist is not valid UTF-8 JSON"
        ) from error
    if not isinstance(document, dict) or set(document) != {
        "version",
        "reviewed_deletes",
    }:
        raise ValueError("allowlist must contain only version and reviewed_deletes")
    if document["version"] != 1 or not isinstance(document["reviewed_deletes"], list):
        raise ValueError(
            "allowlist version must be 1 and reviewed_deletes must be an array"
        )
    reviewed: Counter[tuple[str, str]] = Counter()
    errors: list[str] = []
    for index, raw in enumerate(document["reviewed_deletes"]):
        if not isinstance(raw, dict) or set(raw) != {
            "migration",
            "statement_sha256",
            "reason",
        }:
            errors.append(f"allowlist entry {index} has an invalid shape")
            continue
        migration = raw["migration"]
        fingerprint = raw["statement_sha256"]
        reason = raw["reason"]
        if (
            not isinstance(migration, str)
            or MIGRATION_NAME.fullmatch(migration) is None
        ):
            errors.append(f"allowlist entry {index} has an invalid migration name")
            continue
        if not isinstance(fingerprint, str) or SHA256.fullmatch(fingerprint) is None:
            errors.append(
                f"allowlist entry {index} has an invalid statement fingerprint"
            )
            continue
        if not isinstance(reason, str) or len(reason.strip()) < 12:
            errors.append(f"allowlist entry {index} requires a meaningful audit reason")
            continue
        reviewed[(migration, fingerprint)] += 1
    return reviewed, errors


def audit_migrations(
    migrations_dir: Path,
    applied_versions_file: Path,
    allowlist_file: Path,
) -> MigrationAudit:
    errors: list[str] = []
    try:
        migrations = _migration_files(migrations_dir)
        applied = _applied_versions(applied_versions_file)
        reviewed, allowlist_errors = _reviewed_deletes(allowlist_file)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        return MigrationAudit((), 0, (str(error),))
    errors.extend(allowlist_errors)

    remote_only = sorted(applied - set(migrations))
    if remote_only:
        errors.append(
            "applied migration versions are missing locally: " + ", ".join(remote_only)
        )

    statements_by_migration: dict[str, tuple[DestructiveStatement, ...]] = {}
    for path in migrations.values():
        try:
            statements_by_migration[path.name] = scan_destructive_statements(
                path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError, ValueError) as error:
            errors.append(f"{path.name}: {error}")

    actual_delete_counts = Counter(
        (migration, statement.fingerprint)
        for migration, statements in statements_by_migration.items()
        for statement in statements
        if statement.kind == "delete"
    )
    for key, expected_count in reviewed.items():
        actual_count = actual_delete_counts[key]
        if actual_count < expected_count:
            errors.append(
                f"allowlist entry no longer matches {key[0]} ({key[1]}): "
                f"expected {expected_count}, found {actual_count}"
            )

    pending_versions = sorted(set(migrations) - applied)
    reviewed_used: Counter[tuple[str, str]] = Counter()
    for version in pending_versions:
        path = migrations[version]
        for statement in statements_by_migration.get(path.name, ()):
            location = f"{path.name}:{statement.line}"
            if statement.kind != "delete":
                errors.append(f"{location}: {statement.kind.upper()} is forbidden")
                continue
            key = (path.name, statement.fingerprint)
            if reviewed_used[key] >= reviewed[key]:
                errors.append(
                    f"{location}: DELETE requires an audited allowlist fingerprint "
                    f"({statement.fingerprint})"
                )
                continue
            reviewed_used[key] += 1

    return MigrationAudit(
        pending=tuple(migrations[version].name for version in pending_versions),
        reviewed_deletes=sum(reviewed_used.values()),
        errors=tuple(errors),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--migrations-dir", type=Path, default=Path("supabase/migrations")
    )
    parser.add_argument("--applied-versions-file", type=Path, required=True)
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=Path("config/migration-safety-allowlist.json"),
    )
    args = parser.parse_args()
    audit = audit_migrations(
        args.migrations_dir.resolve(),
        args.applied_versions_file.resolve(),
        args.allowlist.resolve(),
    )
    print(
        json.dumps(
            {
                "ok": audit.ok,
                "pending_migrations": list(audit.pending),
                "reviewed_delete_statements": audit.reviewed_deletes,
                "errors": list(audit.errors),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if audit.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
