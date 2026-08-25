from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pokecrack_worker.config.registries import normalize_rarity
from pokecrack_worker.extraction.budget import BudgetPausedError
from pokecrack_worker.extraction.models import EvidenceTier, ExtractorOutput
from pokecrack_worker.extraction.providers import AIRunMetadata
from pokecrack_worker.extraction.service import AIExtractor

from .catalog import CatalogMatcher, MatchStatus
from .decisions import EvidenceDecision, EvidenceStatus, resolve_evidence
from .models import ValidatorOutput
from .prechecks import PrecheckResult, run_prechecks
from .service import AIValidator


class PipelineStatus(StrEnum):
    COMPLETED = "completed"
    BUDGET_PAUSED = "budget_paused"


@dataclass(frozen=True, slots=True)
class PipelineResult:
    extraction: ExtractorOutput | None
    validation: ValidatorOutput | None
    escalation: ValidatorOutput | None
    decision: EvidenceDecision
    prechecks: PrecheckResult | None
    catalog_set_id: str | None
    catalog_card_ids: tuple[str, ...]
    ai_runs: tuple[AIRunMetadata, ...]
    status: PipelineStatus = PipelineStatus.COMPLETED


def _rejection(code: str) -> EvidenceDecision:
    return EvidenceDecision(
        status=EvidenceStatus.REJECTED,
        selected=None,
        reason_codes=(code,),
        eligible_for_rates=False,
        include_as_auxiliary=False,
    )


@dataclass(slots=True)
class EvidencePipeline:
    extractor: AIExtractor
    validator: AIValidator
    catalog: CatalogMatcher
    escalation_validator: AIValidator | None = None
    min_confidence: float = 0.92
    min_field_confidence: float = 0.85

    def _catalog_context(
        self, extraction: ExtractorOutput
    ) -> tuple[dict[str, Any], str | None, tuple[str, ...], str | None]:
        if not extraction.set_name:
            return {}, None, (), None
        set_match = self.catalog.match_set(extraction.set_name)
        if set_match.status is not MatchStatus.MATCHED or set_match.value is None:
            code = (
                "catalog_set_ambiguous"
                if set_match.status is MatchStatus.AMBIGUOUS
                else "catalog_set_not_found"
            )
            return {}, None, (), code
        matched_set = set_match.value
        cards: list[dict[str, Any]] = []
        card_ids: list[str] = []
        for hit in extraction.hits:
            card_match = self.catalog.match_card(
                matched_set.set_id, hit.card_name, hit.collector_number
            )
            if card_match.status is not MatchStatus.MATCHED or card_match.value is None:
                code = (
                    "catalog_card_ambiguous"
                    if card_match.status is MatchStatus.AMBIGUOUS
                    else "catalog_card_not_found"
                )
                return {}, matched_set.set_id, tuple(card_ids), code
            card = card_match.value
            if (
                hit.rarity is not None
                and card.rarity_key is not None
                and normalize_rarity(hit.rarity) != normalize_rarity(card.rarity_key)
            ):
                return {}, matched_set.set_id, tuple(card_ids), "catalog_rarity_disagreement"
            card_ids.append(card.card_id)
            cards.append(
                {
                    "card_id": card.card_id,
                    "name": card.name,
                    "collector_number": card.collector_number,
                    "rarity_key": card.rarity_key,
                }
            )
        context = {
            "set": {"set_id": matched_set.set_id, "name": matched_set.name},
            "cards": cards,
        }
        return context, matched_set.set_id, tuple(card_ids), None

    def _validator_catalog_error(
        self, validation: ValidatorOutput, set_id: str | None
    ) -> str | None:
        if set_id is None:
            return None
        for hit in validation.hits:
            card_match = self.catalog.match_card(set_id, hit.card_name, hit.collector_number)
            if card_match.status is MatchStatus.NOT_FOUND:
                return "catalog_card_not_found"
            if card_match.status is MatchStatus.AMBIGUOUS:
                return "catalog_card_ambiguous"
            if card_match.status is not MatchStatus.MATCHED or card_match.value is None:
                continue
            catalog_rarity = card_match.value.rarity_key
            if catalog_rarity is not None and (
                hit.rarity_key is None
                or normalize_rarity(hit.rarity_key) != normalize_rarity(catalog_rarity)
            ):
                return "catalog_rarity_disagreement"
        return None

    def process(self, source_text: str) -> PipelineResult:
        try:
            extraction_completion = self.extractor.extract(source_text)
        except BudgetPausedError:
            return PipelineResult(
                extraction=None,
                validation=None,
                escalation=None,
                decision=_rejection("budget_paused"),
                prechecks=None,
                catalog_set_id=None,
                catalog_card_ids=(),
                ai_runs=(),
                status=PipelineStatus.BUDGET_PAUSED,
            )
        extraction = extraction_completion.output
        runs: list[AIRunMetadata] = [extraction_completion.run]
        prechecks = run_prechecks(extraction)
        if not prechecks.passed:
            return PipelineResult(
                extraction=extraction,
                validation=None,
                escalation=None,
                decision=_rejection("deterministic_precheck_failed"),
                prechecks=prechecks,
                catalog_set_id=None,
                catalog_card_ids=(),
                ai_runs=tuple(runs),
            )

        context, set_id, card_ids, catalog_error = self._catalog_context(extraction)
        if catalog_error and extraction.evidence_tier in (EvidenceTier.A, EvidenceTier.B):
            return PipelineResult(
                extraction=extraction,
                validation=None,
                escalation=None,
                decision=_rejection(catalog_error),
                prechecks=prechecks,
                catalog_set_id=set_id,
                catalog_card_ids=card_ids,
                ai_runs=tuple(runs),
            )

        try:
            validation_completion = self.validator.validate(
                source_text, extraction, catalog_context=context
            )
        except BudgetPausedError:
            return PipelineResult(
                extraction=extraction,
                validation=None,
                escalation=None,
                decision=_rejection("budget_paused"),
                prechecks=prechecks,
                catalog_set_id=set_id,
                catalog_card_ids=card_ids,
                ai_runs=tuple(runs),
                status=PipelineStatus.BUDGET_PAUSED,
            )
        validation = validation_completion.output
        runs.append(validation_completion.run)
        if set_id is not None and validation.set_id != set_id:
            decision = _rejection("validator_catalog_set_disagreement")
            return PipelineResult(
                extraction=extraction,
                validation=validation,
                escalation=None,
                decision=decision,
                prechecks=prechecks,
                catalog_set_id=set_id,
                catalog_card_ids=card_ids,
                ai_runs=tuple(runs),
            )
        validator_catalog_error = self._validator_catalog_error(validation, set_id)
        if validator_catalog_error is not None:
            return PipelineResult(
                extraction=extraction,
                validation=validation,
                escalation=None,
                decision=_rejection(validator_catalog_error),
                prechecks=prechecks,
                catalog_set_id=set_id,
                catalog_card_ids=card_ids,
                ai_runs=tuple(runs),
            )

        decision = resolve_evidence(
            extraction,
            validation,
            min_confidence=self.min_confidence,
            min_field_confidence=self.min_field_confidence,
        )
        escalation: ValidatorOutput | None = None
        if (
            decision.status is EvidenceStatus.REJECTED
            and "unresolved_disagreement" in decision.reason_codes
            and self.escalation_validator is not None
        ):
            try:
                escalation_completion = self.escalation_validator.validate(
                    source_text,
                    extraction,
                    catalog_context=context,
                    operation="escalate",
                )
            except BudgetPausedError:
                return PipelineResult(
                    extraction=extraction,
                    validation=validation,
                    escalation=None,
                    decision=_rejection("budget_paused"),
                    prechecks=prechecks,
                    catalog_set_id=set_id,
                    catalog_card_ids=card_ids,
                    ai_runs=tuple(runs),
                    status=PipelineStatus.BUDGET_PAUSED,
                )
            escalation = escalation_completion.output
            runs.append(escalation_completion.run)
            escalation_catalog_error = self._validator_catalog_error(escalation, set_id)
            if escalation_catalog_error is not None:
                return PipelineResult(
                    extraction=extraction,
                    validation=validation,
                    escalation=escalation,
                    decision=_rejection(escalation_catalog_error),
                    prechecks=prechecks,
                    catalog_set_id=set_id,
                    catalog_card_ids=card_ids,
                    ai_runs=tuple(runs),
                )
            decision = resolve_evidence(
                extraction,
                validation,
                escalation=escalation,
                min_confidence=self.min_confidence,
                min_field_confidence=self.min_field_confidence,
            )
        return PipelineResult(
            extraction=extraction,
            validation=validation,
            escalation=escalation,
            decision=decision,
            prechecks=prechecks,
            catalog_set_id=set_id,
            catalog_card_ids=card_ids,
            ai_runs=tuple(runs),
        )
