from __future__ import annotations

import json

import pytest

from pokecrack_worker.collectors.base import FetchResponse
from pokecrack_worker.global_volume import (
    SCHEMA_VERSION,
    PublicRobotsGate,
    validate_manifest,
    verify_candidate,
)


def candidate(url: str = "https://example.com/report") -> dict[str, object]:
    return {
        "url": url,
        "report_group_sha256": "a" * 64,
        "pack_count": 30,
        "pack_precision": "exact_reported",
        "country_code": None,
        "geography_basis": "unknown",
        "set_external_id": "sample-set",
        "product_scope": "other",
        "source_language": "en",
    }


def manifest(*items: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_sha256": "b" * 64,
        "candidates": list(items),
    }


class Client:
    def __init__(self, responses: dict[str, FetchResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        del timeout_seconds
        self.calls.append(url)
        return self.responses[url]


def test_manifest_is_strict_and_sorted() -> None:
    first = candidate()
    second = candidate("https://example.com/second")
    value = manifest(first, second)
    assert validate_manifest(json.dumps(value).encode()) == value
    with pytest.raises(ValueError, match="duplicate_or_unsorted"):
        validate_manifest(json.dumps(manifest(second, first)).encode())


def test_public_page_count_is_verified_without_retaining_page_text() -> None:
    url = "https://example.com/report"
    client = Client(
        {
            "https://example.com/robots.txt": FetchResponse(
                404, "https://example.com/robots.txt", {}, b""
            ),
            url: FetchResponse(
                200,
                url,
                {"content-type": "text/html; charset=utf-8"},
                b"<html><title>Pokemon report</title><body>30 booster packs opened</body></html>",
            ),
        }
    )
    robots = PublicRobotsGate(client=client, followup_delay_seconds=0)
    result = verify_candidate(candidate(), client=client, robots=robots)
    assert result["status"] == "verified"
    assert result["evidence_sha256"] and len(result["evidence_sha256"]) == 64
    assert "30 booster" not in json.dumps(result)


def test_robots_denial_and_missing_count_never_pass() -> None:
    url = "https://example.com/report"
    denied_client = Client(
        {
            "https://example.com/robots.txt": FetchResponse(
                200,
                "https://example.com/robots.txt",
                {"content-type": "text/plain"},
                b"User-agent: *\nDisallow: /\n",
            ),
            url: FetchResponse(200, url, {"content-type": "text/html"}, b"Pokemon report 30 packs"),
        }
    )
    denied = verify_candidate(
        candidate(),
        client=denied_client,
        robots=PublicRobotsGate(client=denied_client, followup_delay_seconds=0),
    )
    assert denied == {"status": "rejected", "error_code": "robots_denied", "evidence_sha256": None}

    missing_client = Client(
        {
            "https://example.com/robots.txt": FetchResponse(
                404, "https://example.com/robots.txt", {}, b""
            ),
            url: FetchResponse(200, url, {"content-type": "text/html"}, b"Pokemon report 31 cards"),
        }
    )
    missing = verify_candidate(
        candidate(),
        client=missing_client,
        robots=PublicRobotsGate(client=missing_client, followup_delay_seconds=0),
    )
    assert missing["status"] == "rejected"
    assert missing["error_code"] == "pack_count_not_found"
