"""Manual CSV importer."""

from __future__ import annotations

import csv
from pathlib import Path

from pokecrack_worker.models import CollectorType, SourceItemCandidate

from .common import ImportFormatError, candidate_from_mapping

_ALLOWED_COLUMNS = {
    "platform",
    "external_id",
    "source_url",
    "title",
    "text",
    "published_at",
    "author",
    "author_hash",
    "media_urls",
    "metadata",
    "source_policy_version",
}


def import_csv_candidates(
    path: str | Path, *, max_rows: int = 10_000
) -> tuple[SourceItemCandidate, ...]:
    if max_rows < 1:
        raise ValueError("max_rows must be positive")
    source = Path(path)
    with source.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ImportFormatError("CSV requires a header")
        unknown = sorted(set(reader.fieldnames) - _ALLOWED_COLUMNS)
        if unknown:
            raise ImportFormatError("unknown CSV column(s): " + ", ".join(unknown))
        items: list[SourceItemCandidate] = []
        for row_number, row in enumerate(reader, start=2):
            if len(items) >= max_rows:
                raise ImportFormatError(f"CSV exceeds max_rows={max_rows}")
            try:
                items.append(
                    candidate_from_mapping(
                        row,
                        collector=CollectorType.MANUAL_IMPORT,
                        collector_version="manual-csv-v1",
                    )
                )
            except (ValueError, TypeError) as error:
                raise ImportFormatError(f"CSV row {row_number}: {error}") from error
    return tuple(items)
