"""Bounded import of OpenCLI Browser Bridge JSON exports."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from pokecrack_worker.models import CollectorType, SourceItemCandidate

from .common import ImportFormatError, candidate_from_mapping


def import_opencli_candidates(
    path: str | Path,
    *,
    max_items: int = 1_000,
    max_bytes: int = 1_048_576,
) -> tuple[SourceItemCandidate, ...]:
    source = Path(path)
    raw = source.read_bytes()
    if len(raw) > max_bytes:
        raise ImportFormatError("OpenCLI export exceeds byte cap")
    try:
        document: Any = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ImportFormatError(f"OpenCLI export is not valid JSON: {error}") from error
    if not isinstance(document, Mapping):
        raise ImportFormatError("OpenCLI export must be an object")
    unknown = sorted(
        set(document) - {"version", "platform", "browser_profile", "collector_version", "items"}
    )
    if unknown:
        raise ImportFormatError("unknown OpenCLI field(s): " + ", ".join(unknown))
    if document.get("version") != 1:
        raise ImportFormatError("OpenCLI export version must be 1")
    platform = document.get("platform")
    items_value = document.get("items")
    if not isinstance(platform, str) or not platform:
        raise ImportFormatError("OpenCLI platform is required")
    if not isinstance(items_value, list):
        raise ImportFormatError("OpenCLI items must be an array")
    if len(items_value) > max_items:
        raise ImportFormatError(f"OpenCLI export exceeds max_items={max_items}")
    collector_version = document.get("collector_version", "opencli-import-v1")
    if not isinstance(collector_version, str) or not collector_version:
        raise ImportFormatError("OpenCLI collector_version must be a string")
    candidates: list[SourceItemCandidate] = []
    for index, item in enumerate(items_value):
        if not isinstance(item, Mapping):
            raise ImportFormatError(f"OpenCLI item {index} must be an object")
        value = dict(cast(Mapping[str, Any], item))
        value.setdefault("platform", platform)
        try:
            candidates.append(
                candidate_from_mapping(
                    value,
                    collector=CollectorType.OPENCLI_AUTHENTICATED,
                    collector_version=collector_version,
                )
            )
        except (ValueError, TypeError) as error:
            raise ImportFormatError(f"OpenCLI item {index}: {error}") from error
    return tuple(candidates)
