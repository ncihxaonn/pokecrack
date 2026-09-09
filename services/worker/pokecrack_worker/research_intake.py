"""Private reference intake, not source approval or pack-count evidence.

The GitHub publishing step constructs this manifest only after rebuilding the
validated research history. The worker and SQL independently validate its tiny
shape. No URL in this module is fetched, and no reported denominator is accepted.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit, urlunsplit

if TYPE_CHECKING:
    from pokecrack_worker.jobs.postgres import QueryExecutor

SCHEMA_VERSION = "research-intake-v1"
MAX_BYTES = 2 * 1024 * 1024
MAX_REFERENCES = 10_000
HASH = re.compile(r"[0-9a-f]{64}")
IMPORT_SQL = "SELECT ingest.import_research_intake_v1(%(manifest)s::jsonb) AS result"


def reference_url(value: object) -> str:
    """Same reference-only normalization as the research ledger; no redirects."""
    if not isinstance(value, str) or len(value) > 1000 or re.search(r'[\s<>\\`]', value):
        raise ValueError("invalid_reference_url")
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,63}", host)
        or host.endswith((".local", ".internal", ".localhost", ".invalid"))
    ):
        raise ValueError("invalid_reference_url")
    return urlunsplit(("https", host, parsed.path.rstrip("/") or "/", "", ""))


def validate_manifest(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_BYTES:
        raise ValueError("intake_manifest_too_large")
    value = json.loads(raw)
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "snapshot_sha256", "references"}
        or value["schema_version"] != SCHEMA_VERSION
        or not isinstance(value["snapshot_sha256"], str)
        or HASH.fullmatch(value["snapshot_sha256"]) is None
        or not isinstance(value["references"], list)
        or len(value["references"]) > MAX_REFERENCES
    ):
        raise ValueError("invalid_intake_manifest")
    urls = []
    for item in value["references"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"url", "report_group_sha256", "conflicting"}
            or not isinstance(item["report_group_sha256"], str)
            or HASH.fullmatch(item["report_group_sha256"]) is None
            or type(item["conflicting"]) is not bool
        ):
            raise ValueError("invalid_intake_reference")
        canonical = reference_url(item["url"])
        if canonical != item["url"]:
            raise ValueError("noncanonical_intake_reference")
        urls.append(canonical)
    if urls != sorted(set(urls)):
        raise ValueError("duplicate_or_unsorted_intake_references")
    return value


def import_manifest(executor: QueryExecutor, raw: bytes) -> dict[str, Any]:
    manifest = validate_manifest(raw)
    rows = executor.query(IMPORT_SQL, {"manifest": json.dumps(manifest, sort_keys=True)})
    if len(rows) != 1 or not isinstance(rows[0], Mapping) or set(rows[0]) != {"result"}:
        raise ValueError("invalid_intake_result")
    result = rows[0]["result"]
    count_keys = {
        "references_received", "references_inserted", "reference_count",
        "conflicting_count", "family_queued",
    }
    if (
        not isinstance(result, dict)
        or set(result) != {"status", "snapshot_sha256", *count_keys}
        or result["status"] not in {"accepted", "paused"}
        or result["snapshot_sha256"] != manifest["snapshot_sha256"]
        or any(type(result[key]) is not int or not 0 <= result[key] <= MAX_REFERENCES
               for key in count_keys)
        or result["references_received"] != len(manifest["references"])
        or result["references_inserted"] > result["references_received"]
        or result["family_queued"] > result["references_received"]
        or result["conflicting_count"] > result["reference_count"]
        or result["reference_count"] < result["references_inserted"]
    ):
        raise ValueError("invalid_intake_result")
    if result["status"] == "paused" and any(
        result[key] != 0 for key in ("references_inserted", "family_queued")
    ):
        raise ValueError("invalid_intake_result")
    return result
