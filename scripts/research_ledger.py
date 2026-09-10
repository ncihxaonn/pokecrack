"""Read and persist the single durable ledger for automated research history."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

LEDGER_VERSION = 1
LEDGER_PATH = Path(__file__).resolve().parents[1] / "data/research/research-ledger.json"
LEDGER_KEYS = frozenset({"version", "country_reports", "global_batches", "asia_reports"})
MAX_LEDGER_BYTES = 2 * 1024 * 1024


def _path(path: Path | None = None) -> Path:
    return Path(path) if path is not None else LEDGER_PATH


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def empty_ledger() -> dict:
    return {"version": LEDGER_VERSION, "country_reports": [],
            "global_batches": [], "asia_reports": []}


def _validate_shape(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != LEDGER_KEYS:
        raise ValueError("invalid_research_ledger")
    if value["version"] != LEDGER_VERSION:
        raise ValueError("invalid_research_ledger")
    if any(not isinstance(value[key], list)
           for key in ("country_reports", "global_batches", "asia_reports")):
        raise ValueError("invalid_research_ledger")
    return value


def load(path: Path | None = None) -> dict:
    ledger_path = _path(path)
    try:
        value = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("invalid_research_ledger") from None
    return _validate_shape(value)


def save(ledger: dict, path: Path | None = None) -> None:
    value = _validate_shape(ledger)
    ledger_path = _path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=ledger_path.parent,
                prefix=f".{ledger_path.name}.", delete=False) as temporary:
            temporary_path = temporary.name
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, ledger_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def append_unique(ledger: dict, collection: str, value: dict) -> bool:
    entries = ledger[collection]
    value_fingerprint = _fingerprint(value)
    if any(_fingerprint(entry) == value_fingerprint for entry in entries):
        return False
    entries.append(value)
    return True


def validate_checkpoint(raw: bytes) -> dict:
    """Validate reference-only checkpoint data without executing branch code."""
    if len(raw) > MAX_LEDGER_BYTES:
        raise ValueError("research_checkpoint_too_large")
    value = _validate_shape(json.loads(raw))
    if type(value["version"]) is not int:
        raise ValueError("invalid_research_ledger")
    # Lazy imports avoid the research modules' shared-ledger import cycle.
    from asia_research import validate as validate_asia
    from country_research import validate_report
    from global_research import validate_batch
    for report in value["country_reports"]:
        validate_report(_canonical(report).encode())
    for batch in value["global_batches"]:
        validate_batch(_canonical(batch).encode())
    countries = set()
    for report in value["asia_reports"]:
        if not isinstance(report, dict):
            raise ValueError("invalid_research_ledger")
        validate_asia(_canonical(report).encode(), report.get("country"))
        if report["country"] in countries:
            raise ValueError("research_checkpoint_conflict")
        countries.add(report["country"])
    return value


def merge_checkpoints(current: dict, pending: dict) -> dict:
    """Append independent research; refuse competing progress or replacements."""
    merged = validate_checkpoint(_canonical(current).encode())
    incoming = validate_checkpoint(_canonical(pending).encode())
    progress = {}
    for report in merged["country_reports"]:
        for country in report["targets"]:
            progress[(report["sweep"], country)] = _fingerprint(report)
    for report in incoming["country_reports"]:
        digest = _fingerprint(report)
        for country in report["targets"]:
            key = (report["sweep"], country)
            if key in progress and progress[key] != digest:
                raise ValueError("research_checkpoint_conflict")
            progress[key] = digest
        append_unique(merged, "country_reports", report)
    for batch in incoming["global_batches"]:
        append_unique(merged, "global_batches", batch)
    asia = {report["country"]: report for report in merged["asia_reports"]}
    for report in incoming["asia_reports"]:
        if report["country"] in asia and _canonical(asia[report["country"]]) != _canonical(report):
            raise ValueError("research_checkpoint_conflict")
        upsert_asia_report(merged, report)
    return validate_checkpoint(_canonical(merged).encode())


def upsert_asia_report(ledger: dict, report: dict) -> bool:
    for index, existing in enumerate(ledger["asia_reports"]):
        if existing.get("country") == report.get("country"):
            if _canonical(existing) == _canonical(report):
                return False
            ledger["asia_reports"][index] = report
            return True
    ledger["asia_reports"].append(report)
    return True
