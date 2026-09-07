"""Bounded Asian product-market evidence; never infer the opening location."""

from __future__ import annotations

import json
import re

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY

from .public_studies import ReviewedPublicStudyAdapter

IDENTITY = PUBLIC_STUDIES_BY_KEY["garbage-rips-gem-vol2-cn-1-v1"]
POLICY_CONFIG: dict[str, object] = {
    "study_key": IDENTITY.study_key,
    "canonical_url": IDENTITY.source_url,
    "collector_version": IDENTITY.collector_version,
    "parser_version": IDENTITY.parser_version,
    "country_code": "CN",
    "country_name": "China",
    "geography_basis": "product_market",
    "geography_confidence": "tier_b",
    "set_external_id": "gem-pack-vol-2",
    "set_language": "zh-CN",
    "set_name": "Pokémon宝石包VOL.2",
    "product_scope": "all",
    "pack_count": 1,
    "observed_at": "2026-02-13T13:30:09Z",
    "denominator_complete": True,
    "set_official_url": "https://www.pokemon.cn/tcg/product/15518.html",
    "robots_url": "https://garbagerips.com/robots.txt",
    "robots_checked_at": "2026-09-07",
    "terms_url": "https://garbagerips.com/privacy.html",
    "terms_checked_at": "2026-09-07",
    "terms_status": "public_site_policy_reviewed",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}
TITLE = "Only Garbage Rips 😬 | Chinese Gem Pack Vol 2 (Eeveelutions)"
EVIDENCE_EXCERPT = "Chinese Gem Pack Vol 2 (Eeveelutions)\nOne pack. Eeveelutions."
EVIDENCE_SHA256 = "a53e1e4f4b881e8d7f8ba006764aae8b8e27323ffa1a41a138caf5c05ff1c804"


def _verify_document(document: str) -> None:
    videos = []
    for match in re.finditer(
        r"<script\b[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>",
        document,
        re.DOTALL,
    ):
        try:
            value = json.loads(match.group(1))
        except (ValueError, TypeError) as error:
            raise CollectorError("public study structured evidence is malformed") from error
        if isinstance(value, dict) and value.get("@type") == "VideoObject":
            videos.append(value)
    if len(videos) != 1:
        raise CollectorError("public study requires one exact video evidence record")
    video = videos[0]
    if (
        video.get("name") != TITLE
        or video.get("uploadDate") != POLICY_CONFIG["observed_at"]
        or video.get("url") != IDENTITY.source_url
        or video.get("embedUrl") != "https://www.youtube.com/embed/8jKHh-P7P7M"
    ):
        raise CollectorError("public study video identity or publication evidence drifted")


def garbage_rips_gem_vol2_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=IDENTITY,
        expected_policy_config=POLICY_CONFIG,
        title_tokens=(TITLE,),
        content_tags=("main",),
        evidence_patterns=tuple(
            re.compile(re.escape(part)) for part in EVIDENCE_EXCERPT.split("\n")
        ),
        expected_evidence_sha256=EVIDENCE_SHA256,
        document_validator=_verify_document,
    )
