#!/usr/bin/env python3
"""Select and prune Pokecrack backups with daily/weekly retention."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import re
from collections.abc import Iterable


BACKUP_PATTERN = re.compile(r"^pokecrack-(\d{8}T\d{6}Z)\.sql\.gz$")


def parse_backup_timestamp(path: Path) -> datetime:
    """Parse a managed backup name; reject every other filename."""
    match = BACKUP_PATTERN.fullmatch(path.name)
    if match is None:
        raise ValueError(f"not a managed backup name: {path.name}")
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def _validate_count(name: str, value: int) -> None:
    if isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} retention must be a non-negative integer")


def select_backups_to_delete(
    paths: Iterable[Path],
    *,
    daily: int = 7,
    weekly: int = 4,
    protected_names: Iterable[str] = (),
) -> list[Path]:
    """Return managed backups outside the daily/weekly union.

    Daily retention keeps the newest backup on each of the newest N UTC dates.
    Weekly retention additionally keeps the newest backup in each of the newest
    N ISO weeks. Unknown filenames are deliberately ignored.
    """
    _validate_count("daily", daily)
    _validate_count("weekly", weekly)
    protected = set(protected_names)
    records: list[tuple[Path, datetime]] = []
    for path in paths:
        try:
            timestamp = parse_backup_timestamp(path)
        except ValueError:
            continue
        records.append((path, timestamp))
    records.sort(key=lambda item: (item[1], item[0].name), reverse=True)

    keep: set[Path] = {path for path, _ in records if path.name in protected}

    seen_dates: set[object] = set()
    for path, timestamp in records:
        day = timestamp.date()
        if day in seen_dates:
            continue
        if len(seen_dates) >= daily:
            break
        keep.add(path)
        seen_dates.add(day)

    seen_weeks: set[tuple[int, int]] = set()
    for path, timestamp in records:
        iso = timestamp.isocalendar()
        week = (iso.year, iso.week)
        if week in seen_weeks:
            continue
        if len(seen_weeks) >= weekly:
            break
        keep.add(path)
        seen_weeks.add(week)

    return [path for path, _ in records if path not in keep]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--daily", type=int, default=7)
    parser.add_argument("--weekly", type=int, default=4)
    parser.add_argument("--protect", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    directory = args.directory.resolve(strict=True)
    if not directory.is_dir() or directory.is_symlink():
        parser.error("--directory must be a real directory, not a symlink")

    candidates = [entry for entry in directory.iterdir() if entry.is_file() and not entry.is_symlink()]
    selected = select_backups_to_delete(
        candidates,
        daily=args.daily,
        weekly=args.weekly,
        protected_names=args.protect,
    )
    for path in selected:
        # Recheck immediately before deletion to constrain races and scope.
        if path.parent.resolve(strict=True) != directory or path.is_symlink() or not path.is_file():
            raise RuntimeError(f"refusing to remove changed path: {path}")
        if args.dry_run:
            print(f"would delete backup: {path.name}")
        else:
            path.unlink()
            print(f"deleted backup: {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
