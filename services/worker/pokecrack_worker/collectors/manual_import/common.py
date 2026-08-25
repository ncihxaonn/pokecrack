"""Shared bounded parsing for user-supplied fixture/manual imports."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pokecrack_worker.models import CollectorType, SourceItemCandidate, hash_author


class ImportFormatError(ValueError):
    pass


def _optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def candidate_from_mapping(
    value: Mapping[str, Any],
    *,
    collector: CollectorType,
    collector_version: str,
) -> SourceItemCandidate:
    source_url = _optional(value.get("source_url"))
    text = _optional(value.get("text"))
    if source_url is None or text is None:
        raise ImportFormatError("source_url and text are required")
    raw_metadata = value.get("metadata", {})
    if isinstance(raw_metadata, str):
        try:
            raw_metadata = json.loads(raw_metadata) if raw_metadata.strip() else {}
        except json.JSONDecodeError as error:
            raise ImportFormatError(f"metadata is not valid JSON: {error}") from error
    if not isinstance(raw_metadata, Mapping):
        raise ImportFormatError("metadata must be an object")
    raw_media = value.get("media_urls", ())
    if isinstance(raw_media, str):
        media_urls = tuple(item.strip() for item in raw_media.split("|") if item.strip())
    elif isinstance(raw_media, list | tuple):
        media_urls = tuple(str(item) for item in raw_media)
    else:
        raise ImportFormatError("media_urls must be a list or pipe-delimited string")
    raw_author = _optional(value.get("author"))
    supplied_hash = _optional(value.get("author_hash"))
    author_hash = hash_author(raw_author) if raw_author else supplied_hash
    return SourceItemCandidate(
        platform=_optional(value.get("platform")) or "manual",
        external_id=_optional(value.get("external_id")),
        source_url=source_url,
        title=_optional(value.get("title")),
        text=text,
        published_at=_optional(value.get("published_at")),
        author_hash=author_hash,
        media_urls=media_urls,
        metadata=dict(raw_metadata),
        collector=collector,
        collector_version=collector_version,
        source_policy_version=_optional(value.get("source_policy_version")) or "1",
    )
