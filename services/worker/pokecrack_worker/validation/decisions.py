from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from pokecrack_worker.config.registries import normalize_rarity
from pokecrack_worker.extraction.models import EvidenceTier, ExtractorOutput, ProductType

from .catalog import normalize_catalog_text
from .models import FieldCheckStatus, ValidationVerdict, ValidatorOutput
from .prechecks import is_valid_country_code

STATISTICS_FIELD_CHECKS = frozenset(
    {
        "set.name",
        "product.name",
        "product.type",
        "opening.pack_count",
        "opening.is_complete",
        "opening.opened_at",
        "location.country_code",
        "location.region",
        "purchase.retailer",
        "purchase.batch_code",
        "hits",
        "evidence_tier",
    }
)


class EvidenceStatus(StrEnum):
    ACCEPTED = "accepted"
    ACTIVITY_ONLY = "activity_only"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    status: EvidenceStatus
    selected: ValidatorOutput | None
    reason_codes: tuple[str, ...]
    eligible_for_rates: bool
    include_as_auxiliary: bool
    escalated: bool = False


def _text(value: str | None) -> str | None:
    return normalize_catalog_text(value) if value is not None else None


def _rarity(value: str | None) -> str | None:
    return normalize_rarity(value) if value is not None else None


def _extractor_facts(output: ExtractorOutput) -> tuple[object, ...]:
    hits = Counter(
        (
            normalize_catalog_text(hit.card_name),
            _text(hit.collector_number),
            _rarity(hit.rarity_label),
            hit.quantity,
        )
        for hit in output.hits
    )
    return (
        _text(output.set_name),
        _text(output.product_name),
        output.product_type,
        output.pack_count,
        output.is_complete,
        tuple(sorted(hits.items())),
        _text(output.country_code),
        _text(output.region),
        _text(output.retailer),
        _text(output.batch_code),
        output.opened_at,
        output.evidence_tier,
    )


def _validator_facts(output: ValidatorOutput) -> tuple[object, ...]:
    hits = Counter(
        (
            normalize_catalog_text(hit.card_name),
            _text(hit.collector_number),
            _rarity(hit.rarity_key),
            hit.quantity,
        )
        for hit in output.hits
    )
    return (
        _text(output.set_name),
        _text(output.product_name),
        output.product_type,
        output.pack_count,
        output.is_complete,
        tuple(sorted(hits.items())),
        _text(output.country_code),
        _text(output.region),
        _text(output.retailer),
        _text(output.batch_code),
        output.opened_at,
        output.evidence_tier,
    )


def _expected_verdict(tier: EvidenceTier) -> ValidationVerdict:
    if tier in (EvidenceTier.A, EvidenceTier.B):
        return ValidationVerdict.ACCEPT
    return ValidationVerdict.ACTIVITY_ONLY


def _rejected(*codes: str, escalated: bool = False) -> EvidenceDecision:
    return EvidenceDecision(
        status=EvidenceStatus.REJECTED,
        selected=None,
        reason_codes=tuple(codes),
        eligible_for_rates=False,
        include_as_auxiliary=False,
        escalated=escalated,
    )


def _field_check_rejections(
    output: ValidatorOutput, *, min_field_confidence: float
) -> tuple[str, ...]:
    reasons: list[str] = []
    if any(check.status is FieldCheckStatus.CONTRADICTED for check in output.field_checks):
        reasons.append("validator_field_contradicted")
    if any(
        check.status is not FieldCheckStatus.NOT_APPLICABLE
        and check.confidence < min_field_confidence
        for check in output.field_checks
    ):
        reasons.append("low_field_confidence")
    return tuple(reasons)


def _statistics_field_checks_complete(output: ValidatorOutput) -> bool:
    counts = Counter(check.field for check in output.field_checks)
    return all(counts[field] == 1 for field in STATISTICS_FIELD_CHECKS)


def _statistics_field_statuses_valid(output: ValidatorOutput) -> bool:
    checks = {check.field: check for check in output.field_checks}
    observed: dict[str, object | None] = {
        "set.name": output.set_name,
        "product.name": output.product_name,
        "product.type": output.product_type,
        "opening.pack_count": output.pack_count,
        "opening.is_complete": output.is_complete,
        "opening.opened_at": output.opened_at,
        "location.country_code": output.country_code,
        "location.region": output.region,
        "purchase.retailer": output.retailer,
        "purchase.batch_code": output.batch_code,
        "hits": output.hits,
        "evidence_tier": output.evidence_tier,
    }
    return all(
        value is None or checks[field].status is FieldCheckStatus.VERIFIED
        for field, value in observed.items()
    )


def _resolved(
    extraction: ExtractorOutput,
    selected: ValidatorOutput,
    *,
    reason_codes: tuple[str, ...] = (),
    escalated: bool = False,
) -> EvidenceDecision:
    if selected.decision is ValidationVerdict.REJECT:
        return _rejected("validator_rejected", escalated=escalated)
    if selected.decision is ValidationVerdict.ACTIVITY_ONLY:
        return EvidenceDecision(
            status=EvidenceStatus.ACTIVITY_ONLY,
            selected=selected,
            reason_codes=reason_codes + ("validator_activity_only",),
            eligible_for_rates=False,
            include_as_auxiliary=True,
            escalated=escalated,
        )

    if selected.country_code is not None and not is_valid_country_code(selected.country_code):
        return _rejected("invalid_country_code", escalated=escalated)

    selected_scope_rejections: list[str] = []
    if selected.product_type not in (
        ProductType.BOOSTER_BOX,
        ProductType.ETB,
        ProductType.BOOSTER_BUNDLE,
    ):
        selected_scope_rejections.append("outside_scope_product")
    if selected_scope_rejections:
        return _rejected(*selected_scope_rejections, escalated=escalated)

    if extraction.evidence_tier in (EvidenceTier.A, EvidenceTier.B):
        eligibility_reasons: list[str] = []
        if selected.country_code is None:
            eligibility_reasons.append("country_unresolved")
        if selected.is_complete is not True:
            eligibility_reasons.append("incomplete_opening")
        if selected.evidence_tier not in (EvidenceTier.A, EvidenceTier.B):
            eligibility_reasons.append("validator_evidence_tier_ineligible")
        if selected.eligible_for_statistics is not True:
            eligibility_reasons.append("validator_ineligible")
        if selected.duplicate_suspected:
            eligibility_reasons.append("duplicate_suspected")
        if selected.missing_required_fields:
            eligibility_reasons.append("missing_required_fields")
        if any(check.status is FieldCheckStatus.UNSUPPORTED for check in selected.field_checks):
            eligibility_reasons.append("validator_field_unsupported")
        if not _statistics_field_checks_complete(selected):
            eligibility_reasons.append("validator_field_checks_incomplete")
        elif not _statistics_field_statuses_valid(selected):
            eligibility_reasons.append("validator_field_status_invalid")
        if not any(check.status is FieldCheckStatus.VERIFIED for check in selected.field_checks):
            eligibility_reasons.append("validator_fields_unverified")
        if eligibility_reasons:
            return EvidenceDecision(
                status=EvidenceStatus.ACTIVITY_ONLY,
                selected=selected,
                reason_codes=reason_codes + tuple(dict.fromkeys(eligibility_reasons)),
                eligible_for_rates=False,
                include_as_auxiliary=True,
                escalated=escalated,
            )
        return EvidenceDecision(
            status=EvidenceStatus.ACCEPTED,
            selected=selected,
            reason_codes=reason_codes,
            eligible_for_rates=True,
            include_as_auxiliary=False,
            escalated=escalated,
        )
    tier_reason = (
        "tier_c_auxiliary" if extraction.evidence_tier is EvidenceTier.C else "tier_d_activity_only"
    )
    return EvidenceDecision(
        status=EvidenceStatus.ACTIVITY_ONLY,
        selected=selected,
        reason_codes=reason_codes or (tier_reason,),
        eligible_for_rates=False,
        include_as_auxiliary=extraction.evidence_tier is EvidenceTier.C,
        escalated=escalated,
    )


def resolve_evidence(
    extraction: ExtractorOutput,
    validation: ValidatorOutput,
    *,
    escalation: ValidatorOutput | None = None,
    min_confidence: float = 0.8,
    min_field_confidence: float = 0.85,
) -> EvidenceDecision:
    """Resolve independent AI claims conservatively.

    The first implemented path is direct extractor/validator agreement. Disputed
    claims are rejected until an escalation result establishes a majority.
    """

    hard_rejections: list[str] = []
    if any(
        country_code is not None and not is_valid_country_code(country_code)
        for country_code in (extraction.country_code, validation.country_code)
    ):
        hard_rejections.append("invalid_country_code")
    if extraction.product_type not in (
        ProductType.BOOSTER_BOX,
        ProductType.ETB,
        ProductType.BOOSTER_BUNDLE,
    ):
        hard_rejections.append("outside_scope_product")
    if extraction.confidence < min_confidence or validation.confidence < min_confidence:
        hard_rejections.append("low_confidence")
    if validation.conflict_codes:
        hard_rejections.append("reported_conflict")
    hard_rejections.extend(
        _field_check_rejections(validation, min_field_confidence=min_field_confidence)
    )
    if hard_rejections:
        return _rejected(*hard_rejections)
    if (
        extraction.evidence_tier is EvidenceTier.D
        and validation.evidence_tier is EvidenceTier.D
        and validation.decision in (ValidationVerdict.ACCEPT, ValidationVerdict.ACTIVITY_ONLY)
    ):
        return EvidenceDecision(
            status=EvidenceStatus.ACTIVITY_ONLY,
            selected=validation,
            reason_codes=("tier_d_activity_only",),
            eligible_for_rates=False,
            include_as_auxiliary=False,
        )
    facts_agree = _extractor_facts(extraction) == _validator_facts(validation)
    if extraction.evidence_tier in (EvidenceTier.C, EvidenceTier.D):
        decision_agrees = validation.decision in (
            ValidationVerdict.ACCEPT,
            ValidationVerdict.ACTIVITY_ONLY,
        )
    else:
        decision_agrees = validation.decision == _expected_verdict(extraction.evidence_tier)
    agrees = facts_agree and decision_agrees
    if not agrees:
        if escalation is None:
            return _rejected("unresolved_disagreement")
        escalation_rejections: list[str] = []
        if escalation.country_code is not None and not is_valid_country_code(
            escalation.country_code
        ):
            escalation_rejections.append("invalid_country_code")
        if escalation.confidence < min_confidence:
            escalation_rejections.append("low_confidence")
        if escalation.conflict_codes:
            escalation_rejections.append("reported_conflict")
        escalation_rejections.extend(
            _field_check_rejections(escalation, min_field_confidence=min_field_confidence)
        )
        if escalation_rejections:
            return _rejected(*escalation_rejections, escalated=True)
        escalation_agrees = _extractor_facts(extraction) == _validator_facts(
            escalation
        ) and escalation.decision == _expected_verdict(extraction.evidence_tier)
        if escalation_agrees:
            return _resolved(
                extraction,
                escalation,
                reason_codes=("escalation_agreed_with_extractor",),
                escalated=True,
            )
        escalation_confirms_validator = (
            _validator_facts(validation) == _validator_facts(escalation)
            and validation.decision == escalation.decision
        )
        if escalation_confirms_validator:
            return _resolved(
                extraction,
                escalation,
                reason_codes=("escalation_agreed_with_validator",),
                escalated=True,
            )
        return _rejected("unresolved_disagreement", escalated=True)
    return _resolved(extraction, validation)
