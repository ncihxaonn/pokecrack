#!/usr/bin/env python3
"""Build a deduplicated global research ledger, never a production admission.

URLs identify reports, not independent samples. Connected report/cohort aliases
collapse into one record. Contradictory counts quarantine the entire component.
Reported fractions remain source reports, not pooled estimates or audited pulls.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

MAX_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 2000
FIELDS = {"study_id", "cohort_ids", "urls", "set", "language", "product",
          "country", "geography_basis", "packs", "pack_precision", "metrics",
          "method", "limitations"}


def token(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", value):
        raise ValueError("invalid_identity")
    return value


def reference_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 1000 or re.search(r'[\s<>\\`]', value):
        raise ValueError("invalid_reference_url")
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment
            or not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,63}", host)
            or host.endswith((".local", ".internal", ".localhost", ".invalid"))):
        raise ValueError("invalid_reference_url")
    # Reference-only: this module never fetches these URLs. Do not conflate
    # www/non-www or rewrite paths; that requires explicit reviewed aliases.
    return urlunsplit(("https", host, parsed.path.rstrip("/") or "/", "", ""))


def positive_count(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 100000000:
        raise ValueError("invalid_pack_count")
    return value


def validate_record(record: object) -> dict:
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise ValueError("invalid_study_fields")
    record = dict(record)
    token(record["study_id"])
    for field in ("cohort_ids", "urls", "limitations"):
        values = record[field]
        if not isinstance(values, list) or len(values) > 100:
            raise ValueError("invalid_list")
        normalizer = reference_url if field == "urls" else token
        record[field] = sorted({normalizer(value) for value in values})
    if not record["urls"] or not record["cohort_ids"]:
        raise ValueError("missing_provenance")
    for field in ("set", "method"):
        token(record[field])
    for field in ("language", "product"):
        if record[field] is not None:
            token(record[field])
    country = record["country"]
    if country is not None and (not isinstance(country, str)
                                or not re.fullmatch(r"[A-Z]{2}", country)):
        raise ValueError("invalid_country")
    basis = record["geography_basis"]
    if basis not in {"opening_location", "publisher_country", "product_market", "unknown"}:
        raise ValueError("invalid_geography_basis")
    if (country is None) != (basis == "unknown"):
        raise ValueError("country_requires_evidence_basis")
    precision = record["pack_precision"]
    if precision not in {"exact_reported", "lower_bound", "title_claim", "unknown"}:
        raise ValueError("invalid_pack_precision")
    packs = record["packs"]
    if packs is not None:
        positive_count(packs)
    if (packs is None) != (precision == "unknown"):
        raise ValueError("pack_precision_mismatch")
    metrics = record["metrics"]
    if not isinstance(metrics, list) or len(metrics) > 100:
        raise ValueError("invalid_metrics")
    seen = set()
    for metric in metrics:
        if not isinstance(metric, dict) or set(metric) != {"category", "hits", "unit"}:
            raise ValueError("invalid_metric")
        category = token(metric["category"])
        if category in seen:
            raise ValueError("duplicate_metric")
        seen.add(category)
        # Distinguish card yield from probability of a pack containing a hit.
        if metric["unit"] not in {"cards", "packs_with_hit"}:
            raise ValueError("invalid_metric_unit")
        hits = metric["hits"]
        if type(hits) is not int or not 0 <= hits <= 100000000:
            raise ValueError("invalid_hit_count")
        if precision != "exact_reported":
            raise ValueError("exact_metric_requires_exact_denominator")
        if metric["unit"] == "packs_with_hit" and hits > packs:
            raise ValueError("hits_exceed_packs")
    record["metrics"] = sorted(metrics, key=lambda item: item["category"])
    return record


def build_ledger(raw: bytes) -> dict:
    if len(raw) > MAX_BYTES:
        raise ValueError("input_too_large")
    data = json.loads(raw)
    if (not isinstance(data, dict) or set(data) != {"version", "studies"}
            or type(data["version"]) is not int or data["version"] != 1
            or not isinstance(data["studies"], list) or len(data["studies"]) > MAX_RECORDS):
        raise ValueError("invalid_catalog")
    records = [validate_record(row) for row in data["studies"]]
    # Deterministic connected components: shared original cohorts OR shared
    # reference URLs imply possible overlap, even through multiple aliases.
    parents = list(range(len(records)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    owners = {}
    for index, record in enumerate(records):
        keys = [("study", record["study_id"])]
        keys += [("cohort", value) for value in record["cohort_ids"]]
        keys += [("url", value) for value in record["urls"]]
        for key in keys:
            if key in owners:
                parents[root(index)] = root(owners[key])
            else:
                owners[key] = index
    components = {}
    for index, record in enumerate(records):
        components.setdefault(root(index), []).append(record)
    studies = []
    for component in components.values():
        conflicts = []
        selected = {}
        for field in ("set", "language", "product", "country", "geography_basis",
                      "packs", "pack_precision", "method"):
            values = {json.dumps(row[field], sort_keys=True) for row in component}
            if len(values) > 1:
                conflicts.append(field)
                selected[field] = None
            else:
                selected[field] = component[0][field]
        metrics = {}
        for row in component:
            for metric in row["metrics"]:
                key = metric["category"]
                if key in metrics and metrics[key] != metric:
                    conflicts.append("metric:" + key)
                metrics[key] = metric
        # Quarantine all counts when related reports disagree. No "latest wins"
        # or automatic summation of partially overlapping aggregate cohorts.
        if conflicts:
            selected["packs"] = None
            selected["pack_precision"] = "unknown"
            metrics = {}
        studies.append({
            "study_ids": sorted({row["study_id"] for row in component}),
            "cohort_ids": sorted({x for row in component for x in row["cohort_ids"]}),
            "urls": sorted({x for row in component for x in row["urls"]}),
            **selected,
            "metrics": [metrics[key] for key in sorted(metrics)],
            "limitations": sorted({x for row in component for x in row["limitations"]}),
            "conflicts": sorted(set(conflicts)),
            "status": "conflicting_reports" if conflicts else "reported_not_independently_audited",
            "statistics_eligible": False,
        })
    return {"version": 1, "scope": "global", "layer": "research_references",
            "input_reports": len(records), "distinct_report_groups": len(studies),
            "verified_unique_packs": None, "production_admitted": False,
            "studies": sorted(studies, key=lambda row: row["study_ids"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args()
    with args.catalog.open("rb") as source:
        result = build_ledger(source.read(MAX_BYTES + 1))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
