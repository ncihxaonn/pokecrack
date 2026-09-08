"""Bounded Star Birth cohort adapter; native card counts are not hit-pack rates."""

from __future__ import annotations

import re

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY

from .nanjakorya_study import parse_star_birth_report
from .public_studies import ReviewedPublicStudyAdapter

IDENTITY = PUBLIC_STUDIES_BY_KEY["nanjakorya-star-birth-jp-100-v1"]
POLICY_CONFIG: dict[str, object] = {
    "study_key": "nanjakorya-star-birth-jp-100-v1",
    "canonical_url": "https://nanjakorya.com/1123",
    "collector_version": "public-study-nanjakorya-star-birth-v1",
    "parser_version": "nanjakorya-star-birth-evidence-v1",
    "country_code": "JP",
    "country_name": "Japan",
    "geography_basis": "product_market",
    "geography_confidence": "tier_b",
    "set_external_id": "s9",
    "set_language": "ja",
    "set_name": "Star Birth",
    "product_scope": "all",
    "pack_count": 100,
    "observed_at": "2022-02-21T20:40:46Z",
    "denominator_complete": True,
    "set_official_url": "https://www.pokemon-card.com/ex/s9/index.html",
    "robots_url": "https://nanjakorya.com/robots.txt",
    "robots_checked_at": "2026-09-08",
    "terms_checked_at": "2026-09-08",
    "terms_status": "no_independent_terms_page",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
    "rarity_card_counts": {"RR": 16, "RRR": 6, "SR": 4, "HR": 1},
    "loose_pack_count": 80,
    "premium_box_pack_count": 20,
    "opening_country": None,
    "opened_at": None,
    "report_evidence_sha256": "b5dc75b772fb6b63a198c72f43193e76e2fd48f332ec546dd1800062640552ad",
}
TITLE = "バラ100パック開けてみた結果【ポケカ-スターバース編】"
EVIDENCE_EXCERPT = TITLE
EVIDENCE_SHA256 = "e9c87d754c51746c9af0cf3c85d164bfee5bf90c84e69e8c65ca46cfda2601e9"


def _verify_document(document: str) -> None:
    report = parse_star_birth_report(document)
    if report.evidence_sha256 != POLICY_CONFIG["report_evidence_sha256"]:
        raise CollectorError("public study complete report digest drifted")


def nanjakorya_star_birth_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=IDENTITY,
        expected_policy_config=POLICY_CONFIG,
        title_tokens=(TITLE,),
        evidence_patterns=(re.compile(re.escape(EVIDENCE_EXCERPT)),),
        expected_evidence_sha256=EVIDENCE_SHA256,
        document_validator=_verify_document,
        max_response_bytes=524288,
    )
