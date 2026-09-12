"""Project bounded public social metadata into the quantity-only volume lane.

The official YouTube collector and the public Bluesky collector intentionally
retain only small metadata/text windows.  This module extracts an explicit
pack-count claim from those bounded fields, stores no title or post text, and
marks the result as ``title_claim``.  Such rows are publishable for volume
coverage but are never used as hit-rate evidence and are never fetched again.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from pokecrack_worker.global_volume import (
    MAX_CANDIDATES,
    MAX_PACK_COUNT,
    SCHEMA_VERSION,
    import_manifest,
    validate_manifest,
)
from pokecrack_worker.jobs.postgres import QueryExecutor

# Read a larger disposable window from each source, then apply a fair
# round-robin selection below. The manifest remains capped by the shared
# global-volume contract, so this cannot turn into an unbounded query or write.
SOCIAL_SOURCE_QUERY_LIMIT = 1_000

YOUTUBE_DISCOVERIES_SQL = f"""
SELECT source_url, title
FROM ingest.youtube_discoveries
WHERE not is_demo
  AND expires_at > statement_timestamp()
ORDER BY last_seen_at DESC, video_id
LIMIT {SOCIAL_SOURCE_QUERY_LIMIT}
""".strip()

BLUESKY_CANDIDATES_SQL = f"""
SELECT public_url, text_excerpt
FROM ingest.bluesky_jetstream_candidates
WHERE not is_demo
  AND deleted_at IS NULL
  AND expires_at > statement_timestamp()
ORDER BY last_seen_at DESC, at_uri
LIMIT {SOCIAL_SOURCE_QUERY_LIMIT}
""".strip()

_YOUTUBE_WATCH_URL = re.compile(r"^https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})$")
_POKEMON_MARKER = re.compile(
    r"pokemon|pokémon|покемон|ポケモン|寶可夢|宝可梦|포켓몬|โปเกมอน|"
    r"पोकेमोन|पोकेमॉन|بوكيمون|tcg|trading\s+card|集換式卡牌|トレカ",
    re.IGNORECASE,
)
# Deliberately exclude boxes, bundles and ETBs: without an explicit pack
# quantity, converting a product count into packs would manufacture volume.
_PACK_UNIT = re.compile(
    r"(?:\bpacks?\b|\bboosters?\b|\bsobres?\b|\bpaquetes?\b|"
    r"\bpacotes?\b|\bbustine?\b|\bpak(?:ken)?\b|\bpakiet(?:y|ów)?\b|"
    r"\bpaket(?:e|y)?\b|\bпакет(?:а|ов)?\b|पैक(?:स)?|बूस्टर|"
    r"باك(?:ات)?|بستر|パック|팩|부스터|ซอง|gói|卡包|包)",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"(?<!\d)(?:\d{1,3}(?:[,. ]\d{3})+|\d{1,8})(?!\d)")


def extract_pack_count(value: object) -> int | None:
    """Return the number closest to an explicit pack unit in one claim."""

    if not isinstance(value, str) or not value or len(value) > 500:
        return None
    if not _POKEMON_MARKER.search(value):
        return None
    units = [*_PACK_UNIT.finditer(value)]
    if not units:
        return None
    matches: list[tuple[int, int, int]] = []
    for number in _NUMBER.finditer(value):
        start, end = number.span()
        # Reject decimal prices/ratios such as 1.5 packs.  Grouped thousands
        # (1,000 / 1.000 / 1 000) remain valid because the match includes all
        # three-digit groups.
        if (
            end < len(value)
            and value[end] in ".,"
            and end + 1 < len(value)
            and value[end + 1].isdigit()
        ) or (start > 1 and value[start - 1] in ".," and value[start - 2].isdigit()):
            continue
        distance = min(
            0
            if unit.start() <= end and start <= unit.end()
            else min(abs(start - unit.end()), abs(unit.start() - end))
            for unit in units
        )
        if distance > 48:
            continue
        raw = number.group(0).replace(",", "").replace(".", "").replace(" ", "")
        count = int(raw)
        if 1 <= count <= MAX_PACK_COUNT:
            matches.append((distance, start, count))
    if not matches:
        return None
    matches.sort()
    return matches[0][2]


def _youtube_embed_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = _YOUTUBE_WATCH_URL.fullmatch(value)
    if match is None:
        return None
    # The global-volume reference contract is query-free.  Embed is an
    # official, stable public URL for the same video and is used only for the
    # metadata-derived quantity row; the group hash retains the watch identity.
    return f"https://www.youtube.com/embed/{match[1]}"


def _candidate(*, url: str, claim: str, source_identity: str) -> dict[str, Any] | None:
    count = extract_pack_count(claim)
    if count is None:
        return None
    return {
        "url": url,
        "report_group_sha256": hashlib.sha256(
            f"social-volume-v1|{source_identity}".encode()
        ).hexdigest(),
        "pack_count": count,
        "pack_precision": "title_claim",
        "country_code": None,
        "geography_basis": "unknown",
        "set_external_id": None,
        "product_scope": "other",
        "source_language": None,
    }


def _rows(executor: QueryExecutor, sql: str, fields: set[str]) -> list[Mapping[str, Any]]:
    rows = executor.query(sql, {})
    result: list[Mapping[str, Any]] = []
    for row in rows:
        if set(row) != fields:
            raise ValueError("invalid_social_volume_row")
        result.append(row)
    return result


def build_manifest(executor: QueryExecutor) -> dict[str, Any]:
    """Build a bounded, deterministic manifest from disposable public metadata."""

    candidates: dict[str, dict[str, Any]] = {}
    source_urls: list[list[str]] = [[], []]
    for row in _rows(executor, YOUTUBE_DISCOVERIES_SQL, {"source_url", "title"}):
        url = _youtube_embed_url(row["source_url"])
        claim = row["title"]
        if url is None or not isinstance(claim, str):
            continue
        item = _candidate(url=url, claim=claim, source_identity=str(row["source_url"]))
        if item is not None:
            if url not in candidates:
                candidates[url] = item
                source_urls[0].append(url)

    for row in _rows(executor, BLUESKY_CANDIDATES_SQL, {"public_url", "text_excerpt"}):
        url = row["public_url"]
        claim = row["text_excerpt"]
        if not isinstance(url, str) or not isinstance(claim, str):
            continue
        item = _candidate(url=url, claim=claim, source_identity=url)
        if item is not None:
            if url not in candidates:
                candidates[url] = item
                source_urls[1].append(url)

    # Query results are newest-first, but the manifest contract requires URL
    # sorting. Select in source-fair recency order before applying that final
    # canonical sort; otherwise the alphabetically smallest host could starve
    # every later source once the shared cap is reached.
    selected_urls: list[str] = []
    while len(selected_urls) < MAX_CANDIDATES and any(source_urls):
        progressed = False
        for bucket in source_urls:
            if bucket and len(selected_urls) < MAX_CANDIDATES:
                selected_urls.append(bucket.pop(0))
                progressed = True
        if not progressed:
            break
    selected = sorted(
        (candidates[url] for url in selected_urls),
        key=lambda item: item["url"],
    )
    source_hash = hashlib.sha256(
        json.dumps(selected, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_sha256": source_hash,
        "candidates": selected,
    }
    return validate_manifest(json.dumps(manifest, sort_keys=True).encode("utf-8"))


def sync_social_volume(executor: QueryExecutor) -> dict[str, Any]:
    """Idempotently import current social metadata claims into global volume."""

    manifest = build_manifest(executor)
    result = import_manifest(
        executor,
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    return {"metadata_candidates": len(manifest["candidates"]), **result}
