"""Manual newline-delimited JSON importer."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from pokecrack_worker.models import CollectorType, SourceItemCandidate

from .common import ImportFormatError, candidate_from_mapping


def import_jsonl_candidates(
    path: str | Path,
    *,
    max_rows: int = 10_000,
    max_line_chars: int = 100_000,
) -> tuple[SourceItemCandidate, ...]:
    if max_rows < 1 or max_line_chars < 1:
        raise ValueError("JSONL limits must be positive")
    items: list[SourceItemCandidate] = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            if not raw_line.strip():
                continue
            if len(raw_line) > max_line_chars:
                raise ImportFormatError(f"JSONL line {line_number} exceeds character cap")
            if len(items) >= max_rows:
                raise ImportFormatError(f"JSONL exceeds max_rows={max_rows}")
            try:
                value: Any = json.loads(raw_line)
                if not isinstance(value, Mapping):
                    raise ImportFormatError("each JSONL line must be an object")
                items.append(
                    candidate_from_mapping(
                        cast(Mapping[str, Any], value),
                        collector=CollectorType.MANUAL_IMPORT,
                        collector_version="manual-jsonl-v1",
                    )
                )
            except (json.JSONDecodeError, ValueError, TypeError) as error:
                raise ImportFormatError(f"JSONL line {line_number}: {error}") from error
    return tuple(items)
