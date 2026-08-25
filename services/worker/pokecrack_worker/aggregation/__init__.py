"""Eligibility-gated idempotent aggregate builders."""

from .eligibility import STATISTICAL_EVIDENCE_TIERS, is_statistics_eligible
from .models import (
    AggregateRecord,
    AggregateScope,
    AggregationRun,
    OpeningObservation,
    PublicAggregateSummary,
)
from .repository import InMemoryAggregateRepository
from .service import AggregationService, build_public_summary

__all__ = [
    "AggregateRecord",
    "AggregateScope",
    "AggregationRun",
    "AggregationService",
    "InMemoryAggregateRepository",
    "OpeningObservation",
    "PublicAggregateSummary",
    "STATISTICAL_EVIDENCE_TIERS",
    "build_public_summary",
    "is_statistics_eligible",
]
