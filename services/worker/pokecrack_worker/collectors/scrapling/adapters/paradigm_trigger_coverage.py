"""Exact primary Paradigm Trigger cohort, independent of the Star Birth report."""

from __future__ import annotations

import hashlib
import re

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY

from .paradigm_trigger_study import TITLE, parse_paradigm_trigger_report
from .public_studies import ReviewedPublicStudyAdapter

IDENTITY = PUBLIC_STUDIES_BY_KEY["nanjakorya-paradigm-jp-100-v1"]
POLICY_CONFIG: dict[str, object] = {
    "study_key": "nanjakorya-paradigm-jp-100-v1",
    "canonical_url": "https://nanjakorya.com/1823",
    "collector_version": "public-study-nanjakorya-paradigm-v1",
    "parser_version": "nanjakorya-paradigm-evidence-v1",
    "country_code": "JP",
    "country_name": "Japan",
    "geography_basis": "product_market",
    "geography_confidence": "tier_b",
    "set_external_id": "s12",
    "set_language": "ja",
    "set_name": "Paradigm Trigger",
    "product_scope": "all",
    "pack_count": 100,
    "observed_at": "2022-10-21T11:10:35Z",
    "denominator_complete": True,
    "set_official_url": "https://www.pokemon-card.com/ex/s12/index.html",
    "robots_url": "https://nanjakorya.com/robots.txt",
    "robots_checked_at": "2026-09-08",
    "terms_checked_at": "2026-09-08",
    "terms_status": "no_independent_terms_page",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
    "rarity_card_counts": {"RR": 14, "RRR": 7, "SR": 1, "HR": 2},
    "purchase_group_pack_counts": [30, 10, 30, 30],
    "source_label_inconsistencies": True,
    "opening_country": None,
    "opened_at": None,
    "report_evidence_sha256": "e34a7b2043134f3c8ed6d62b024b64bf3d9c8503a0f3c66564ecbbc36b8b6b6c",
}
EVIDENCE_EXCERPT = TITLE
EVIDENCE_SHA256 = hashlib.sha256(EVIDENCE_EXCERPT.encode()).hexdigest()


def _verify_document(document: str) -> None:
    report = parse_paradigm_trigger_report(document)
    if report.evidence_sha256 != POLICY_CONFIG["report_evidence_sha256"]:
        raise CollectorError("public study complete report digest drifted")


def nanjakorya_paradigm_trigger_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
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
