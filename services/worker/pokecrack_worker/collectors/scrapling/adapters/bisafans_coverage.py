"""One reviewed Bisafans denominator-only display report."""

from __future__ import annotations

import re

from pokecrack_worker.collectors.base import HTTPClient
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.deduplication.fingerprints import content_sha256

from .public_studies import ReviewedPublicStudyAdapter

IDENTITY = PUBLIC_STUDIES_BY_KEY["bisafans-flying-fists-de-36-v1"]

# Bound to the visible German statistics page by the 2026-09-11 MAM-only
# HTTP probe. The second number is a card yield, not a hit-pack numerator.
FIRST_EVIDENCE = (
    "Da wir zu jeder Pokémon Sammelkartenerweiterung ein Boosterdisplay mit 36 Packungen öffnen"
)
SECOND_EVIDENCE = (
    "In XY Fliegende Fäuste waren in unserem Display 47 Karten der "
    "Seltenheitsstufe Rare oder seltener."
)
EVIDENCE_EXCERPT = f"{FIRST_EVIDENCE}\n{SECOND_EVIDENCE}"
EVIDENCE_SHA256 = content_sha256(EVIDENCE_EXCERPT)

POLICY_CONFIG: dict[str, object] = {
    "study_key": IDENTITY.study_key,
    "canonical_url": IDENTITY.source_url,
    "collector_version": IDENTITY.collector_version,
    "parser_version": IDENTITY.parser_version,
    "country_code": "DE",
    "country_name": "Germany",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "publisher_country_url": "https://www.bisafans.de/impressum.php",
    "publisher_country_review_method": "source_business_identity_matched_to_public_site_impressum",
    "publisher_country_checked_at": "2026-09-11",
    "opening_country": None,
    "opened_at": None,
    "set_external_id": "xy3",
    "set_language": "de",
    "set_language_basis": "source_page_is_german",
    "set_name": "Fliegende Fäuste",
    "set_official_url": "https://www.pokemon.com/de/pokemon-sammelkartenspiel/pokemon-karten/series/xy3/49/",
    "product_scope": "booster_box",
    "pack_count": 36,
    "observed_at": "2026-09-11T00:00:00Z",
    "observed_at_basis": "initial_mam_verification_date_not_opening_time",
    "denominator_complete": True,
    "cohort_id": "bisafans-fliegende-faeuste-display-36",
    "robots_url": "https://www.bisafans.de/robots.txt",
    "robots_checked_at": "2026-09-11",
    "terms_checked_at": "2026-09-11",
    "terms_status": "no_separate_content_reuse_license_found",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}


def bisafans_flying_fists_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=IDENTITY,
        expected_policy_config=POLICY_CONFIG,
        title_tokens=("Statistiken",),
        content_tags=("body",),
        evidence_patterns=(
            re.compile(re.escape(FIRST_EVIDENCE)),
            re.compile(re.escape(SECOND_EVIDENCE)),
        ),
        expected_evidence_sha256=EVIDENCE_SHA256,
    )


__all__ = [
    "EVIDENCE_EXCERPT",
    "EVIDENCE_SHA256",
    "FIRST_EVIDENCE",
    "IDENTITY",
    "POLICY_CONFIG",
    "SECOND_EVIDENCE",
    "bisafans_flying_fists_adapter",
]
