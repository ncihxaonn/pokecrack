#!/usr/bin/env python3
"""Turn the validated research ledger into a quantity-only intake manifest.

The manifest contains public URLs and source-reported pack counts only.  It is
not a hit-rate dataset and it does not identify people.  The database and the
deployed worker validate the same bounded shape before anything is projected
to the public dashboard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "services/worker"))

from global_studies import build_ledger, token
from pokecrack_worker.global_volume import (
    MAX_BYTES,
    MAX_CANDIDATES,
    SCHEMA_VERSION,
    validate_manifest,
)
from pokecrack_worker.research_intake import reference_url


def _product_scope(value: object) -> str:
    if not isinstance(value, str):
        return "other"
    lowered = value.casefold()
    if "elite" in lowered and "trainer" in lowered:
        return "etb"
    if "bundle" in lowered:
        return "booster_bundle"
    if "booster_box" in lowered or "booster-box" in lowered or "booster box" in lowered:
        return "booster_box"
    return "other"


def _language(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value if re.fullmatch(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8}){0,2}$", value) else None


def _report_group_sha256(urls: list[str], cohorts: list[str]) -> str:
    identity = json.dumps(
        {"urls": sorted(urls), "cohort_ids": sorted(cohorts)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _ledger_groups(source: dict[str, Any], seed: dict[str, Any] | None) -> list[dict[str, Any]]:
    if isinstance(source.get("ledger"), dict):
        groups = source["ledger"].get("studies")
        if not isinstance(groups, list):
            raise TypeError("invalid_intake_ledger")
        return [group for group in groups if isinstance(group, dict)]

    if source.get("version") != 1:
        raise ValueError("invalid_intake_ledger")
    rows: list[dict[str, Any]] = []
    if seed is not None and isinstance(seed.get("studies"), list):
        rows.extend(row for row in seed["studies"] if isinstance(row, dict))
    for batch in source.get("global_batches", []):
        if isinstance(batch, dict) and isinstance(batch.get("studies"), list):
            rows.extend(row for row in batch["studies"] if isinstance(row, dict))
    for report in source.get("country_reports", []):
        if not isinstance(report, dict):
            continue
        for result in report.get("results", []):
            if isinstance(result, dict) and isinstance(result.get("studies"), list):
                rows.extend(row for row in result["studies"] if isinstance(row, dict))
    if not rows:
        return []
    return build_ledger(json.dumps({"version": 1, "studies": rows}).encode())["studies"]


def _candidate_from_group(group: dict[str, Any]) -> dict[str, Any] | None:
    if group.get("conflicts") or group.get("status") not in {
        "reported_not_independently_audited",
    }:
        return None
    urls = group.get("urls")
    cohorts = group.get("cohort_ids")
    packs = group.get("packs")
    precision = group.get("pack_precision")
    if not isinstance(urls, list) or not urls or not isinstance(cohorts, list) or not cohorts:
        return None
    if type(packs) is not int or packs <= 0:
        return None
    if precision not in {"exact_reported", "lower_bound", "title_claim"}:
        return None
    try:
        normalized_urls = sorted({reference_url(url) for url in urls})
        normalized_cohorts = sorted({token(cohort) for cohort in cohorts})
    except (TypeError, ValueError):
        return None
    if not normalized_urls or not normalized_cohorts:
        return None
    country = group.get("country")
    basis = group.get("geography_basis")
    if country is not None and (
        not isinstance(country, str) or len(country) != 2 or country.upper() != country
    ):
        return None
    if basis not in {"opening_location", "publisher_country", "product_market", "unknown"}:
        return None
    if (country is None) != (basis == "unknown"):
        return None
    set_id = group.get("set")
    if set_id is not None:
        try:
            token(set_id)
        except (TypeError, ValueError):
            set_id = None
    return {
        "url": normalized_urls[0],
        "report_group_sha256": _report_group_sha256(normalized_urls, normalized_cohorts),
        "pack_count": packs,
        "pack_precision": precision,
        "country_code": country,
        "geography_basis": basis,
        "set_external_id": set_id,
        "product_scope": _product_scope(group.get("product")),
        "source_language": _language(group.get("language")),
    }


def _asia_candidates(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for report in ledger.get("asia_reports", []):
        if not isinstance(report, dict):
            continue
        country = report.get("country")
        if not isinstance(country, str) or len(country) != 2 or country.upper() != country:
            continue
        for item in report.get("candidates", []):
            if not isinstance(item, dict) or type(item.get("pack_count")) is not int:
                continue
            try:
                url = reference_url(item.get("source_url"))
            except (TypeError, ValueError):
                continue
            basis = item.get("geography_basis")
            if basis not in {"opening_location", "publisher_country", "product_market", "unknown"}:
                continue
            attributed_country = country if basis != "unknown" else None
            identity = _report_group_sha256([url], [f"asia-{country}-{url}"])
            candidates.append(
                {
                    "url": url,
                    "report_group_sha256": identity,
                    "pack_count": item["pack_count"],
                    "pack_precision": "exact_reported",
                    "country_code": attributed_country,
                    "geography_basis": basis,
                    "set_external_id": None,
                    "product_scope": "other",
                    "source_language": None,
                }
            )
    return candidates


def build_manifest(raw: bytes, *, seed_raw: bytes | None = None) -> dict[str, Any]:
    if len(raw) > 4 * MAX_BYTES:
        raise ValueError("intake_snapshot_too_large")
    source = json.loads(raw)
    if not isinstance(source, dict):
        raise TypeError("invalid_intake_snapshot")
    seed = json.loads(seed_raw) if seed_raw is not None else None
    if seed is not None and not isinstance(seed, dict):
        raise ValueError("invalid_intake_seed")
    groups = _ledger_groups(source, seed)
    candidates: dict[str, dict[str, Any] | None] = {}
    for group in groups:
        candidate = _candidate_from_group(group)
        if candidate is None:
            continue
        url = candidate["url"]
        if url in candidates and candidates[url] != candidate:
            candidates[url] = None
        elif url not in candidates:
            candidates[url] = candidate
    if "version" in source:
        for candidate in _asia_candidates(source):
            url = candidate["url"]
            if url in candidates and candidates[url] != candidate:
                candidates[url] = None
            elif url not in candidates:
                candidates[url] = candidate
    selected = [candidate for candidate in candidates.values() if candidate is not None]
    selected.sort(key=lambda item: item["url"])
    if len(selected) > MAX_CANDIDATES:
        selected = selected[:MAX_CANDIDATES]
    combined_hash = hashlib.sha256(raw + (b"\0" + seed_raw if seed_raw else b"")).hexdigest()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_sha256": combined_hash,
        "candidates": selected,
    }
    return validate_manifest(json.dumps(manifest, sort_keys=True).encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--seed", type=Path, default=Path("data/research/global-studies.json"))
    args = parser.parse_args()
    try:
        raw = args.ledger.read_bytes()
        seed_raw = args.seed.read_bytes() if args.seed.exists() else None
        result = build_manifest(raw, seed_raw=seed_raw)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise SystemExit("global-volume-intake: invalid_snapshot") from None
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
