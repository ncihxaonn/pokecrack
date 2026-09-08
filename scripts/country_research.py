#!/usr/bin/env python3
"""Resume country-first research from bot-owned evidence, never from a clock slot."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from asia_research import MAX_BYTES, research_document
from country_targets import COUNTRIES, COUNTRY_REGION, REGION_ORDER, REGIONS
from global_research import (
    REPO, accumulate, failure_code, fingerprint, load_history, prompt as global_prompt,
    schema as study_schema, validate_batch,
)

MARKER = "<!-- pokecrack-country-research-v1 -->"
TITLE = "[Country research batch] "
CAMPAIGN = "country-first-20260908-v1"
MAX_TARGETS = 3
MAX_SWEEPS = 100


def validate_selection(value: object) -> dict:
    if (not isinstance(value, dict) or set(value) != {"campaign", "sweep", "targets"}
            or value["campaign"] != CAMPAIGN or type(value["sweep"]) is not int
            or not 1 <= value["sweep"] <= MAX_SWEEPS):
        raise ValueError("invalid_country_selection")
    targets = value["targets"]
    if (not isinstance(targets, list) or not 1 <= len(targets) <= MAX_TARGETS
            or not all(isinstance(code, str) and code in COUNTRIES for code in targets)
            or len(set(targets)) != len(targets)
            or len({COUNTRY_REGION[code] for code in targets}) != 1):
        raise ValueError("invalid_country_selection")
    return {"campaign": CAMPAIGN, "sweep": value["sweep"], "targets": list(targets)}


def validate_report(raw: bytes, selection: dict | None = None) -> dict:
    if len(raw) > MAX_BYTES:
        raise ValueError("batch_too_large")
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"campaign", "sweep", "targets", "results"}:
        raise ValueError("invalid_country_report")
    selected = validate_selection({key: value[key] for key in ("campaign", "sweep", "targets")})
    if selection is not None and selected != validate_selection(selection):
        raise ValueError("country_selection_mismatch")
    results = value["results"]
    if not isinstance(results, list) or len(results) != len(selected["targets"]):
        raise ValueError("country_results_incomplete")
    by_country = {}
    for result in results:
        if (not isinstance(result, dict) or set(result) != {"target", "studies"}
                or not isinstance(result["target"], str)
                or result["target"] not in selected["targets"] or result["target"] in by_country
                or not isinstance(result["studies"], list) or len(result["studies"]) > 2):
            raise ValueError("invalid_country_result")
        batch = validate_batch(json.dumps({"version": 1, "studies": result["studies"]}).encode())
        # Search target is not evidence of the returned study's geography.
        by_country[result["target"]] = {"target": result["target"], "studies": batch["studies"]}
    report = {**selected, "results": [by_country[code] for code in selected["targets"]]}
    if len(json.dumps(report, sort_keys=True, ensure_ascii=True).encode()) > MAX_BYTES:
        raise ValueError("normalized_batch_too_large")
    return report


def country_history() -> list[dict]:
    response = subprocess.run([
        "gh", "issue", "list", "--repo", REPO, "--state", "all", "--limit", "1000",
        "--json", "title,body,author",
    ], check=True, capture_output=True, text=True)
    issues = json.loads(response.stdout)
    if not isinstance(issues, list) or len(issues) >= 1000:
        raise ValueError("history_capacity_requires_archive")
    reports = []
    for issue in issues:
        author = issue.get("author") or {}
        if not (author.get("is_bot") is True and author.get("login") in {
                "app/github-actions", "github-actions[bot]"}
                and issue["title"].startswith(TITLE) and issue["body"].startswith(MARKER)):
            continue
        parts = issue["body"].split("```json\n")
        if len(parts) != 2 or not parts[1].endswith("\n```\n"):
            raise ValueError("invalid_history_body")
        report = validate_report(parts[1][:-5].encode())
        if issue["title"] != TITLE + fingerprint(report):
            raise ValueError("history_fingerprint_mismatch")
        reports.append(report)
    return reports


def select_targets(history: list[dict]) -> dict:
    completed = {(report["sweep"], code) for report in history for code in report["targets"]}
    for sweep in range(1, MAX_SWEEPS + 1):
        for region in REGION_ORDER:
            remaining = [code for code, _ in REGIONS[region] if (sweep, code) not in completed]
            if remaining:
                return {"campaign": CAMPAIGN, "sweep": sweep, "targets": remaining[:MAX_TARGETS]}
    raise ValueError("history_capacity_requires_archive")


def schema(selection: dict) -> dict:
    selected = validate_selection(selection)
    study = study_schema()["properties"]["studies"]["items"]
    properties = {
        "campaign": {"type": "string", "enum": [CAMPAIGN]},
        "sweep": {"type": "integer", "enum": [selected["sweep"]]},
        "targets": {"type": "array", "items": {"type": "string", "enum": selected["targets"]}},
        "results": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"target": {"type": "string", "enum": selected["targets"]},
                           "studies": {"type": "array", "items": study}},
            "required": ["target", "studies"]}},
    }
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def prompt(selection: dict) -> str:
    selected = validate_selection(selection)
    targets = ", ".join(f"{code}: {COUNTRIES[code]}" for code in selected["targets"])
    return global_prompt(COUNTRY_REGION[selected["targets"][0]]) + f"""
This run belongs to a COUNTRY-LEVEL campaign, not city research.
Selection to echo exactly: {json.dumps(selected, ensure_ascii=True)}
Research EACH of these targets: {targets}. Use at most 12 queries TOTAL, shared
fairly across targets; include local-language queries, not only English SEO guides.
Return exactly one results item for each target, at most TWO studies per target.
An empty studies array means no eligible PRIMARY candidate found in this bounded
pass, not no Pokemon activity and not zero observed packs. Never pad empty results.
The target field is ONLY search provenance; a study's country/geography_basis must
still follow its own evidence. Unknown geography stays null. Do not relabel a
Japanese product or a global English study as a local opening to satisfy a target.
Exclude counterfeit/resealed products, marketing lifetime totals and localized
retailer copies. Do not collect cities, addresses, contact or personal details.
Research is NOT independent source approval and cannot mark a country live.
"""


def issue_body(report: dict) -> str:
    return (MARKER + "\nCountry-level research only; no admitted observations.\n"
            "Checked targets: " + ", ".join(report["targets"]) + "\n"
            "An empty result means no suitable candidate in this pass, never zero activity.\n"
            "```json\n" + json.dumps(report, sort_keys=True, ensure_ascii=True) + "\n```\n")


def snapshot(report: dict, history: list[dict], seed: dict, global_history: list[dict]) -> dict:
    reports = {fingerprint(item): item for item in [*history, report]}
    rows = [row for item in reports.values() for result in item["results"] for row in result["studies"]]
    _, ledger = accumulate({"version": 1, "studies": rows}, seed, global_history)
    current_sweep = report["sweep"]
    checked = {code for item in reports.values() if item["sweep"] == current_sweep
               for code in item["targets"]}
    return {"campaign": CAMPAIGN, "granularity": "country_or_area", "sweep": current_sweep,
            "phase_order": list(REGION_ORDER), "target_count": len(COUNTRIES),
            "checked_this_sweep": [code for code in COUNTRIES if code in checked],
            "next": select_targets(list(reports.values())), "ledger": ledger,
            "production_admitted": False}


def publish(report: dict, seed_path: Path) -> dict:
    history = country_history()
    # Compute the complete bounded ledger BEFORE making any GitHub write.
    output = snapshot(report, history, json.loads(seed_path.read_bytes()), load_history())
    identical = any(fingerprint(item) == fingerprint(report) for item in history)
    overlapping = any(item["sweep"] == report["sweep"] and
                      set(item["targets"]) & set(report["targets"]) for item in history)
    if overlapping and not identical:
        raise ValueError("country_progress_conflict")
    if not identical:
        if validate_selection({key: report[key] for key in ("campaign", "sweep", "targets")}) != select_targets(history):
            raise ValueError("country_selection_mismatch")
        subprocess.run(["gh", "issue", "create", "--repo", REPO,
                        "--title", TITLE + fingerprint(report), "--body-file", "-"],
                       input=issue_body(report), text=True, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output


def read_bounded(path: Path) -> bytes:
    with path.open("rb") as source:
        return source.read(MAX_BYTES + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--select", action="store_true")
    mode.add_argument("--research", type=Path)
    mode.add_argument("--publish", type=Path)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--seed", type=Path, default=Path("data/research/global-studies.json"))
    args = parser.parse_args()
    stage = "selection"
    try:
        if args.select:
            output = select_targets(country_history())
        elif args.research:
            selection = validate_selection(json.loads(read_bounded(args.research)))
            stage = "research"
            raw = research_document(prompt(selection), schema(selection))
            stage = "validation"
            output = validate_report(raw, selection)
        else:
            if args.selection is None:
                raise ValueError("invalid_country_selection")
            selection = validate_selection(json.loads(read_bounded(args.selection)))
            stage = "validation"
            report = validate_report(read_bounded(args.publish), selection)
            stage = "publication"
            output = publish(report, args.seed)
        print(json.dumps(output, sort_keys=True))
    except (ValueError, OSError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        # Country-specific errors are a fixed vocabulary, never raw content.
        code = str(error) if type(error) is ValueError and str(error) in {
            "invalid_country_selection", "invalid_country_report", "invalid_country_result",
            "country_results_incomplete", "country_selection_mismatch", "country_progress_conflict",
        } else failure_code(error)
        raise SystemExit(f"country_research_failed: stage={stage} code={code}; no production data admitted") from None


if __name__ == "__main__":
    main()
