"""Primary pull-rate eligibility gate."""

from __future__ import annotations

from .models import OpeningObservation

STATISTICAL_EVIDENCE_TIERS = frozenset({"A", "B"})
SUPPORTED_MVP_PRODUCT_TYPES = frozenset({"booster_box", "etb", "booster_bundle"})


def is_statistics_eligible(opening: OpeningObservation) -> bool:
    return (
        opening.source_status == "accepted"
        and opening.validation_status == "accepted"
        and opening.complete_opening
        and opening.eligible_for_statistics
        and opening.evidence_tier in STATISTICAL_EVIDENCE_TIERS
        and opening.duplicate_of is None
        and not opening.duplicate_suspected
        and opening.pack_count is not None
        and opening.pack_count > 0
        and opening.set_id is not None
        and opening.catalog_mapped
        and opening.language.strip().casefold() == "en"
        and opening.country_code.strip().upper() == "AU"
        and opening.product_type in SUPPORTED_MVP_PRODUCT_TYPES
    )
