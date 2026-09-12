"""Quantity-first public report intake with a small, fail-closed page check.

This lane is deliberately separate from the reviewed hit-rate pipeline.  It
publishes counts that a public report claims, deduplicated by report group, and
never creates a numerator, probability, or personal profile.  A later check
may confirm that the public page still contains the claimed count; an access
denial, login wall, redirect, or challenge is never bypassed.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Mapping
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from pokecrack_worker.research_intake import reference_url

if TYPE_CHECKING:
    from pokecrack_worker.collectors.base import FetchResponse, HTTPClient
    from pokecrack_worker.jobs.postgres import QueryExecutor


SCHEMA_VERSION = "global-volume-intake-v1"
MAX_BYTES = 2 * 1024 * 1024
MAX_CANDIDATES = 1_000
MAX_RESPONSE_BYTES = 1_000_000
MAX_PACK_COUNT = 100_000_000
HASH = re.compile(r"^[0-9a-f]{64}$")
TOKEN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")
LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8}){0,2}$")
COUNTRY = re.compile(r"^[A-Z]{2}$")
PRECISIONS = frozenset({"exact_reported", "lower_bound", "title_claim"})
GEOGRAPHY_BASES = frozenset({"opening_location", "publisher_country", "product_market", "unknown"})
PRODUCT_SCOPES = frozenset({"all", "booster_box", "booster_bundle", "etb", "other"})
IMPORT_SQL = "SELECT ingest.import_global_volume_intake_v1(%(manifest)s::jsonb) AS result"
CLAIM_SQL = """
SELECT *
FROM ingest.claim_global_volume_candidates_v1(
  p_worker_id => %(worker_id)s,
  p_limit => %(limit)s::integer
)
""".strip()
FINALIZE_SQL = """
SELECT ingest.finalize_global_volume_candidate_v1(
  p_worker_id => %(worker_id)s,
  p_url => %(url)s,
  p_result => %(result)s::jsonb
) AS result
""".strip()

_PACK_WORD = re.compile(
    r"(?:\b(?:pack|packs|booster|boosters|box|boxes|carton|cartons|bundle|bundles|etb|etbs)\b|"
    r"パック|ボックス|箱|paquete|paquetes|sobre|sobres|pacote|pacotes|bustina|bustine|"
    r"pak|pakken|karton|карточ|пакет|пачк|包|盒)",
    re.IGNORECASE,
)
_POKEMON_MARKER = re.compile(
    r"pokemon|pokémon|ポケモン|寶可夢|宝可梦|tcg|trading\s+card|集換式卡牌|トレカ",
    re.IGNORECASE,
)
_YOUTUBE_EMBED_URL = re.compile(r"^https://www\.youtube\.com/embed/[A-Za-z0-9_-]{11}$")


def _canonical_global_volume_url(value: object) -> str:
    """Accept normal reference URLs plus the query-free YouTube embed form."""

    if isinstance(value, str) and _YOUTUBE_EMBED_URL.fullmatch(value):
        return value
    return reference_url(value)


def _header(headers: object, name: str) -> str:
    if not hasattr(headers, "items"):
        return ""
    expected = name.casefold()
    return next(
        (str(value) for key, value in headers.items() if str(key).casefold() == expected),
        "",
    )


def _count_pattern(count: int) -> re.Pattern[str]:
    raw = str(count)
    variants = [re.escape(raw)]
    if len(raw) >= 4:
        grouped = f"{count:,}"
        variants.extend(
            re.escape(value)
            for value in (grouped, grouped.replace(",", "."), grouped.replace(",", " "))
        )
    return re.compile(rf"(?<!\d)(?:{'|'.join(dict.fromkeys(variants))})(?!\d)")


class _VisibleTextParser(HTMLParser):
    """Keep only bounded visible text; never retain the source document."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in {"script", "style", "noscript", "template", "svg"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "template", "svg"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth and data.strip():
            self.text_parts.append(data)

    @property
    def text(self) -> str:
        return " ".join("".join(self.text_parts).split())


def validate_candidate(value: object) -> dict[str, Any]:
    fields = {
        "url",
        "report_group_sha256",
        "pack_count",
        "pack_precision",
        "country_code",
        "geography_basis",
        "set_external_id",
        "product_scope",
        "source_language",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("invalid_global_volume_candidate")
    candidate = dict(value)
    if _canonical_global_volume_url(candidate["url"]) != candidate["url"]:
        raise ValueError("noncanonical_global_volume_url")
    if not isinstance(candidate["report_group_sha256"], str) or not HASH.fullmatch(
        candidate["report_group_sha256"]
    ):
        raise ValueError("invalid_report_group_sha256")
    if (
        type(candidate["pack_count"]) is not int
        or not 1 <= candidate["pack_count"] <= MAX_PACK_COUNT
    ):
        raise ValueError("invalid_global_volume_pack_count")
    if candidate["pack_precision"] not in PRECISIONS:
        raise ValueError("invalid_global_volume_precision")
    country_code = candidate["country_code"]
    if country_code is not None and (
        not isinstance(country_code, str) or COUNTRY.fullmatch(country_code) is None
    ):
        raise ValueError("invalid_global_volume_country")
    basis = candidate["geography_basis"]
    if basis not in GEOGRAPHY_BASES:
        raise ValueError("invalid_global_volume_geography")
    if (country_code is None) != (basis == "unknown"):
        raise ValueError("global_volume_country_requires_basis")
    set_id = candidate["set_external_id"]
    if set_id is not None and (not isinstance(set_id, str) or TOKEN.fullmatch(set_id) is None):
        raise ValueError("invalid_global_volume_set")
    if candidate["product_scope"] not in PRODUCT_SCOPES:
        raise ValueError("invalid_global_volume_product")
    language = candidate["source_language"]
    if language is not None and (
        not isinstance(language, str) or LANGUAGE.fullmatch(language) is None
    ):
        raise ValueError("invalid_global_volume_language")
    return candidate


def validate_manifest(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_BYTES:
        raise ValueError("global_volume_manifest_too_large")
    value = json.loads(raw)
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "snapshot_sha256", "candidates"}
        or value["schema_version"] != SCHEMA_VERSION
        or not isinstance(value["snapshot_sha256"], str)
        or HASH.fullmatch(value["snapshot_sha256"]) is None
        or not isinstance(value["candidates"], list)
        or len(value["candidates"]) > MAX_CANDIDATES
    ):
        raise ValueError("invalid_global_volume_manifest")
    candidates = [validate_candidate(item) for item in value["candidates"]]
    urls = [item["url"] for item in candidates]
    if urls != sorted(set(urls)):
        raise ValueError("duplicate_or_unsorted_global_volume_candidates")
    value["candidates"] = candidates
    return value


def import_manifest(executor: QueryExecutor, raw: bytes) -> dict[str, Any]:
    manifest = validate_manifest(raw)
    rows = executor.query(IMPORT_SQL, {"manifest": json.dumps(manifest, sort_keys=True)})
    if len(rows) != 1 or set(rows[0]) != {"result"}:
        raise ValueError("invalid_global_volume_import_result")
    result = rows[0]["result"]
    keys = {
        "status",
        "snapshot_sha256",
        "candidates_received",
        "candidates_inserted",
        "conflicting_count",
    }
    if (
        not isinstance(result, dict)
        or set(result) != keys
        or result["status"] not in {"accepted", "paused"}
        or result["snapshot_sha256"] != manifest["snapshot_sha256"]
        or any(
            type(result[key]) is not int or not 0 <= result[key] <= MAX_CANDIDATES
            for key in keys - {"status", "snapshot_sha256"}
        )
        or result["candidates_received"] != len(manifest["candidates"])
        or result["candidates_inserted"] > result["candidates_received"]
        or result["conflicting_count"] > result["candidates_received"]
    ):
        raise ValueError("invalid_global_volume_import_result")
    return result


def _validate_worker_id(worker_id: str) -> str:
    if not isinstance(worker_id, str) or not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,159}", worker_id
    ):
        raise ValueError("invalid_global_volume_worker")
    return worker_id


def claim_candidates(
    executor: QueryExecutor, worker_id: str, limit: int = 8
) -> list[dict[str, Any]]:
    _validate_worker_id(worker_id)
    if type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError("invalid_global_volume_limit")
    rows = executor.query(CLAIM_SQL, {"worker_id": worker_id, "limit": limit})
    expected = {
        "url",
        "report_group_sha256",
        "pack_count",
        "pack_precision",
        "country_code",
        "geography_basis",
        "set_external_id",
        "product_scope",
        "source_language",
        "state",
        "attempts",
    }
    result: list[dict[str, Any]] = []
    for row in rows:
        if set(row) != expected or row["state"] != "checking":
            raise ValueError("invalid_global_volume_claim_result")
        candidate = {key: row[key] for key in expected - {"state", "attempts"}}
        validate_candidate(candidate)
        if type(row["attempts"]) is not int or not 1 <= row["attempts"] <= 3:
            raise ValueError("invalid_global_volume_claim_result")
        result.append(candidate)
    return result


def validate_result(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"status", "error_code", "evidence_sha256"}:
        raise ValueError("invalid_global_volume_result")
    status = value["status"]
    error_code = value["error_code"]
    evidence = value["evidence_sha256"]
    if status not in {"verified", "rejected", "retry"}:
        raise ValueError("invalid_global_volume_result")
    if status == "verified":
        if (
            error_code is not None
            or not isinstance(evidence, str)
            or HASH.fullmatch(evidence) is None
        ):
            raise ValueError("invalid_global_volume_result")
    else:
        if not isinstance(error_code, str) or error_code not in {
            "robots_denied",
            "robots_unavailable",
            "source_challenged",
            "source_http_status",
            "source_redirected",
            "source_not_html",
            "source_too_large",
            "source_invalid_utf8",
            "page_scope_not_found",
            "pack_count_not_found",
            "source_temporarily_unavailable",
        }:
            raise ValueError("invalid_global_volume_result")
        if evidence is not None:
            raise ValueError("invalid_global_volume_result")
    return dict(value)


def finalize_candidate(
    executor: QueryExecutor, worker_id: str, url: str, result: Mapping[str, object]
) -> dict[str, Any]:
    _validate_worker_id(worker_id)
    canonical = _canonical_global_volume_url(url)
    if canonical != url:
        raise ValueError("noncanonical_global_volume_url")
    validated = validate_result(dict(result))
    rows = executor.query(
        FINALIZE_SQL,
        {
            "worker_id": worker_id,
            "url": url,
            "result": json.dumps(validated, sort_keys=True),
        },
    )
    if len(rows) != 1 or set(rows[0]) != {"result"} or not isinstance(rows[0]["result"], dict):
        raise ValueError("invalid_global_volume_finalize_result")
    return dict(rows[0]["result"])


RobotsDecision = Literal["allowed", "denied", "unavailable"]


class PublicRobotsGate:
    """Respect robots while treating a missing robots file as no directive."""

    def __init__(
        self,
        *,
        client: HTTPClient,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 64 * 1024,
        followup_delay_seconds: float = 2.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 0 <= followup_delay_seconds <= 120:
            raise ValueError("followup_delay_seconds must be between 0 and 120")
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.followup_delay_seconds = followup_delay_seconds
        self.sleeper = sleeper

    def decision(self, url: str, *, user_agent: str) -> RobotsDecision:
        try:
            canonical = reference_url(url)
            parsed = urlsplit(canonical)
            robots_url = f"https://{parsed.hostname}/robots.txt"
            response = self.client.get(robots_url, timeout_seconds=self.timeout_seconds)
            if response.status_code == 404:
                if self.followup_delay_seconds:
                    self.sleeper(self.followup_delay_seconds)
                return "allowed"
            if response.status_code != 200:
                return "unavailable"
            if reference_url(response.url) != robots_url:
                return "unavailable"
            if len(response.body) > self.max_response_bytes:
                return "unavailable"
            content_type = _header(response.headers, "content-type").casefold()
            if content_type and "text/plain" not in content_type:
                return "unavailable"
            document = response.body.decode("utf-8", errors="strict")
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(document.splitlines())
            if not parser.can_fetch(user_agent, canonical):
                return "denied"
            if self.followup_delay_seconds:
                self.sleeper(self.followup_delay_seconds)
            return "allowed"
        except (OSError, UnicodeDecodeError, TimeoutError, ValueError):
            return "unavailable"


def _retry_or_reject(status_code: int) -> tuple[str, str]:
    if status_code in {408, 425, 429} or status_code >= 500:
        return "retry", "source_temporarily_unavailable"
    return "rejected", "source_http_status"


def verify_candidate(
    candidate: Mapping[str, Any],
    *,
    client: HTTPClient,
    robots: PublicRobotsGate,
    user_agent: str = "PokecrackPublicVolume/1",
) -> dict[str, Any]:
    validated = validate_candidate(dict(candidate))
    url = validated["url"]
    if validated["pack_precision"] == "title_claim":
        # Social metadata claims are already bounded by the official/public
        # collector. They are quantity-only rows, so do not fetch a video or
        # post page, follow a redirect, or turn a metadata claim into page
        # evidence. The database migration normally keeps these rows out of
        # the page-check queue; this branch is defensive for old leases.
        evidence = hashlib.sha256(
            f"{url}|{validated['pack_count']}|title-claim-metadata-v1".encode()
        ).hexdigest()
        return {"status": "verified", "error_code": None, "evidence_sha256": evidence}
    robots_decision = robots.decision(url, user_agent=user_agent)
    if robots_decision == "denied":
        return {"status": "rejected", "error_code": "robots_denied", "evidence_sha256": None}
    if robots_decision == "unavailable":
        return {"status": "retry", "error_code": "robots_unavailable", "evidence_sha256": None}
    try:
        response: FetchResponse = client.get(url, timeout_seconds=robots.timeout_seconds)
    except (OSError, TimeoutError, RuntimeError):
        return {
            "status": "retry",
            "error_code": "source_temporarily_unavailable",
            "evidence_sha256": None,
        }
    try:
        if reference_url(response.url) != url:
            return {
                "status": "rejected",
                "error_code": "source_redirected",
                "evidence_sha256": None,
            }
    except ValueError:
        return {"status": "rejected", "error_code": "source_redirected", "evidence_sha256": None}
    if response.status_code != 200:
        status, error_code = _retry_or_reject(response.status_code)
        return {"status": status, "error_code": error_code, "evidence_sha256": None}
    if len(response.body) > MAX_RESPONSE_BYTES:
        return {"status": "rejected", "error_code": "source_too_large", "evidence_sha256": None}
    content_type = _header(response.headers, "content-type").casefold()
    if content_type and "text/html" not in content_type:
        return {"status": "rejected", "error_code": "source_not_html", "evidence_sha256": None}
    try:
        document = response.body.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return {"status": "rejected", "error_code": "source_invalid_utf8", "evidence_sha256": None}
    parser = _VisibleTextParser()
    try:
        parser.feed(document)
        parser.close()
    except (ValueError, TypeError):
        return {"status": "rejected", "error_code": "page_scope_not_found", "evidence_sha256": None}
    text = parser.text
    if not _POKEMON_MARKER.search(text):
        return {"status": "rejected", "error_code": "page_scope_not_found", "evidence_sha256": None}
    count_match = _count_pattern(validated["pack_count"]).search(text)
    if count_match is None:
        return {"status": "rejected", "error_code": "pack_count_not_found", "evidence_sha256": None}
    start = max(0, count_match.start() - 120)
    end = min(len(text), count_match.end() + 120)
    context = text[start:end]
    if not _PACK_WORD.search(context):
        return {"status": "rejected", "error_code": "pack_count_not_found", "evidence_sha256": None}
    evidence = hashlib.sha256(
        f"{url}|{validated['pack_count']}|{validated['pack_precision']}|{context}".encode()
    ).hexdigest()
    return {"status": "verified", "error_code": None, "evidence_sha256": evidence}


def process_candidates(
    executor: QueryExecutor,
    *,
    worker_id: str,
    limit: int = 8,
    client: HTTPClient | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    candidates = claim_candidates(executor, worker_id, limit)
    http_client: HTTPClient
    if client is None:
        from pokecrack_worker.collectors.scrapling.http import ScraplingHTTPClient

        http_client = ScraplingHTTPClient.live(timeout_seconds=30.0)
    else:
        http_client = client
    robots = PublicRobotsGate(client=http_client, followup_delay_seconds=2.0, sleeper=sleeper)
    counts = {"claimed": len(candidates), "verified": 0, "rejected": 0, "retry": 0}
    for candidate in candidates:
        result = verify_candidate(candidate, client=http_client, robots=robots)
        finalize_candidate(executor, worker_id, candidate["url"], result)
        counts[result["status"]] += 1
    return counts
