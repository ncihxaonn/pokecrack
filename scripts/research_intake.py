#!/usr/bin/env python3
"""Build a private reference manifest from the validated country ledger artifact.

Run only in the separate GitHub publishing stage, never in the source-research
process. The output cannot approve sources or carry pack/hit/location claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/worker"))
from pokecrack_worker.research_intake import (
    MAX_BYTES, MAX_REFERENCES, SCHEMA_VERSION, reference_url, validate_manifest,
)
from global_studies import token


def build_manifest(raw: bytes) -> dict:
    if len(raw) > 4 * MAX_BYTES:
        raise ValueError("intake_snapshot_too_large")
    snapshot = json.loads(raw)
    if not isinstance(snapshot, dict) or snapshot.get("production_admitted") is not False:
        raise ValueError("invalid_intake_snapshot")
    ledger = snapshot.get("ledger")
    if (
        not isinstance(ledger, dict)
        or ledger.get("layer") != "research_references"
        or ledger.get("scope") != "global"
        or ledger.get("production_admitted") is not False
        or ledger.get("verified_unique_packs", "missing") is not None
        or not isinstance(ledger.get("studies"), list)
        or len(ledger["studies"]) > 2000
    ):
        raise ValueError("invalid_intake_ledger")
    references = {}
    for group in ledger["studies"]:
        if (
            not isinstance(group, dict)
            or group.get("statistics_eligible") is not False
            or group.get("status") not in {"conflicting_reports", "reported_not_independently_audited"}
            or not isinstance(group.get("conflicts"), list)
            or not isinstance(group.get("urls"), list)
            or not group["urls"]
            or not isinstance(group.get("cohort_ids"), list)
            or not group["cohort_ids"]
        ):
            raise ValueError("invalid_intake_group")
        urls = sorted({reference_url(url) for url in group["urls"]})
        cohorts = sorted({token(cohort) for cohort in group["cohort_ids"]})
        conflicting = bool(group["conflicts"])
        if conflicting != (group["status"] == "conflicting_reports"):
            raise ValueError("invalid_intake_conflict")
        # This hash addresses a research report group, not independent physical
        # packs. Newly discovered aliases may change it; durable history is GitHub.
        identity = json.dumps({"urls": urls, "cohort_ids": cohorts}, sort_keys=True)
        digest = hashlib.sha256(identity.encode()).hexdigest()
        for url in urls:
            if url in references:
                raise ValueError("overlapping_intake_groups")
            references[url] = {"url": url, "report_group_sha256": digest, "conflicting": conflicting}
            if len(references) > MAX_REFERENCES:
                raise ValueError("intake_reference_capacity")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "references": [references[url] for url in sorted(references)],
    }
    return validate_manifest(json.dumps(manifest, sort_keys=True).encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    try:
        with args.snapshot.open("rb") as source:
            result = build_manifest(source.read(4 * MAX_BYTES + 1))
    except (OSError, ValueError, TypeError, KeyError):
        # No exception text, page data, URLs or filesystem paths in public logs.
        raise SystemExit("research-intake: invalid_snapshot") from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
