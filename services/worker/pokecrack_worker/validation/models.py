from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pokecrack_worker.extraction.models import EvidenceTier, ProductType
from pokecrack_worker.extraction.providers import validate_json_schema


class ValidationVerdict(StrEnum):
    ACCEPT = "accept"
    ACTIVITY_ONLY = "activity_only"
    REJECT = "reject"


class FieldCheckStatus(StrEnum):
    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class FieldCheck:
    field: str
    status: FieldCheckStatus
    confidence: float
    evidence_reference: str | None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> FieldCheck:
        expected = {"field", "status", "confidence", "evidence_reference"}
        if set(value) != expected:
            raise ValueError("field_check must contain all exact fields")
        return cls(
            field=str(value["field"]),
            status=FieldCheckStatus(value["status"]),
            confidence=float(value["confidence"]),
            evidence_reference=value["evidence_reference"],
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "status": self.status.value,
            "confidence": self.confidence,
            "evidence_reference": self.evidence_reference,
        }


@dataclass(frozen=True, slots=True)
class ValidatedHit:
    card_id: str | None
    card_name: str
    collector_number: str | None
    rarity_key: str | None
    quantity: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ValidatedHit:
        return cls(
            card_id=value.get("card_id"),
            card_name=str(value["card_name"]),
            collector_number=value.get("collector_number"),
            rarity_key=value.get("rarity_key"),
            quantity=int(value["quantity"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "card_name": self.card_name,
            "collector_number": self.collector_number,
            "rarity_key": self.rarity_key,
            "quantity": self.quantity,
        }


@dataclass(frozen=True, slots=True)
class ValidatorOutput:
    """Validator verdict plus independently observed facts used for resolution."""

    decision: ValidationVerdict
    set_id: str | None
    set_name: str | None
    product_name: str | None
    pack_count: int | None
    hits: tuple[ValidatedHit, ...]
    country_code: str | None
    region: str | None
    retailer: str | None
    batch_code: str | None
    opened_at: str | None
    evidence_tier: EvidenceTier
    confidence: float
    conflict_codes: tuple[str, ...]
    product_type: ProductType = ProductType.UNKNOWN
    eligible_for_statistics: bool | None = None
    field_checks: tuple[FieldCheck, ...] = ()
    contradictions: tuple[str, ...] = ()
    missing_required_fields: tuple[str, ...] = ()
    duplicate_suspected: bool = False
    rejection_reasons: tuple[str, ...] = ()
    is_complete: bool | None = None

    @property
    def verdict(self) -> ValidationVerdict:
        return self.decision

    @property
    def overall_confidence(self) -> float:
        return self.confidence

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ValidatorOutput:
        if "verdict" not in value:
            raise ValueError("validator output must use the strict validator schema")
        validate_json_schema(value, cls.json_schema())
        if "verdict" in value:
            expected = {
                "verdict",
                "observed",
                "overall_confidence",
                "eligible_for_statistics",
                "evidence_tier",
                "field_checks",
                "contradictions",
                "missing_required_fields",
                "duplicate_suspected",
                "rejection_reasons",
            }
            if set(value) != expected:
                raise ValueError("validator output must contain observed and all exact fields")
            observed = value["observed"]
            if not isinstance(observed, Mapping):
                raise ValueError("observed must be an object")
            observed_expected = {
                "set_name",
                "product_name",
                "product_type",
                "pack_count",
                "is_complete",
                "hits",
                "country_code",
                "region",
                "retailer",
                "batch_code",
                "opened_at",
            }
            if set(observed) != observed_expected:
                raise ValueError("observed must contain all exact independently observed fields")
            raw_hits = observed["hits"]
            if not isinstance(raw_hits, list):
                raise ValueError("observed.hits must be an array")
            hits: list[ValidatedHit] = []
            for raw_hit in raw_hits:
                if not isinstance(raw_hit, Mapping) or set(raw_hit) != {
                    "card_name",
                    "collector_number",
                    "rarity_key",
                    "quantity",
                }:
                    raise ValueError("observed hit must contain all exact fields")
                hits.append(ValidatedHit.from_mapping(raw_hit))
            contradictions = tuple(value["contradictions"])
            reasons = tuple(value["rejection_reasons"])
            return cls(
                decision=ValidationVerdict(value["verdict"]),
                set_id=None,
                set_name=observed["set_name"],
                product_name=observed["product_name"],
                product_type=ProductType(observed["product_type"]),
                pack_count=observed["pack_count"],
                hits=tuple(hits),
                country_code=observed["country_code"],
                region=observed["region"],
                retailer=observed["retailer"],
                batch_code=observed["batch_code"],
                opened_at=observed["opened_at"],
                evidence_tier=EvidenceTier(value["evidence_tier"]),
                confidence=float(value["overall_confidence"]),
                conflict_codes=contradictions,
                eligible_for_statistics=bool(value["eligible_for_statistics"]),
                field_checks=tuple(FieldCheck.from_mapping(item) for item in value["field_checks"]),
                contradictions=contradictions,
                missing_required_fields=tuple(value["missing_required_fields"]),
                duplicate_suspected=bool(value["duplicate_suspected"]),
                rejection_reasons=reasons,
                is_complete=observed["is_complete"],
            )
        raise ValueError("validator output must use the strict validator schema")

    def to_mapping(self) -> dict[str, Any]:
        eligible = self.eligible_for_statistics
        if eligible is None:
            eligible = (
                self.decision is ValidationVerdict.ACCEPT
                and self.evidence_tier in (EvidenceTier.A, EvidenceTier.B)
                and not self.conflict_codes
                and not self.duplicate_suspected
            )
        checks = self.field_checks or (
            FieldCheck("overall", FieldCheckStatus.VERIFIED, self.confidence, None),
        )
        contradictions = self.contradictions or self.conflict_codes
        reasons = self.rejection_reasons
        if self.decision is ValidationVerdict.REJECT and not reasons:
            reasons = ("validator_rejected",)
        return {
            "verdict": self.decision.value,
            "observed": {
                "set_name": self.set_name,
                "product_name": self.product_name,
                "product_type": self.product_type.value,
                "pack_count": self.pack_count,
                "is_complete": self.is_complete,
                "hits": [
                    {
                        "card_name": hit.card_name,
                        "collector_number": hit.collector_number,
                        "rarity_key": hit.rarity_key,
                        "quantity": hit.quantity,
                    }
                    for hit in self.hits
                ],
                "country_code": self.country_code,
                "region": self.region,
                "retailer": self.retailer,
                "batch_code": self.batch_code,
                "opened_at": self.opened_at,
            },
            "overall_confidence": self.confidence,
            "eligible_for_statistics": eligible,
            "evidence_tier": self.evidence_tier.value,
            "field_checks": [item.to_mapping() for item in checks],
            "contradictions": list(contradictions),
            "missing_required_fields": list(self.missing_required_fields),
            "duplicate_suspected": self.duplicate_suspected,
            "rejection_reasons": list(reasons),
        }

    @staticmethod
    def json_schema() -> dict[str, Any]:
        confidence = {"type": "number", "minimum": 0, "maximum": 1}
        code_array = {
            "type": "array",
            "maxItems": 100,
            "items": {"type": "string", "minLength": 1, "maxLength": 128},
        }
        properties: dict[str, Any] = {
            "verdict": {"type": "string", "enum": [item.value for item in ValidationVerdict]},
            "observed": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "set_name",
                    "product_name",
                    "product_type",
                    "pack_count",
                    "is_complete",
                    "hits",
                    "country_code",
                    "region",
                    "retailer",
                    "batch_code",
                    "opened_at",
                ],
                "properties": {
                    "set_name": {"type": ["string", "null"], "maxLength": 200},
                    "product_name": {"type": ["string", "null"], "maxLength": 200},
                    "product_type": {
                        "type": "string",
                        "enum": [item.value for item in ProductType],
                    },
                    "pack_count": {"type": ["integer", "null"], "minimum": 0},
                    "is_complete": {"type": ["boolean", "null"]},
                    "hits": {
                        "type": "array",
                        "maxItems": 1000,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "card_name",
                                "collector_number",
                                "rarity_key",
                                "quantity",
                            ],
                            "properties": {
                                "card_name": {"type": "string", "minLength": 1, "maxLength": 200},
                                "collector_number": {"type": ["string", "null"], "maxLength": 64},
                                "rarity_key": {"type": ["string", "null"], "maxLength": 128},
                                "quantity": {"type": "integer", "minimum": 1, "maximum": 100000},
                            },
                        },
                    },
                    "country_code": {"type": ["string", "null"], "pattern": "^[A-Z]{2}$"},
                    "region": {"type": ["string", "null"], "maxLength": 160},
                    "retailer": {"type": ["string", "null"], "maxLength": 200},
                    "batch_code": {"type": ["string", "null"], "maxLength": 128},
                    "opened_at": {"type": ["string", "null"], "maxLength": 64},
                },
            },
            "overall_confidence": confidence,
            "eligible_for_statistics": {"type": "boolean"},
            "evidence_tier": {"type": "string", "enum": [item.value for item in EvidenceTier]},
            "field_checks": {
                "type": "array",
                "minItems": 1,
                "maxItems": 100,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["field", "status", "confidence", "evidence_reference"],
                    "properties": {
                        "field": {"type": "string", "minLength": 1, "maxLength": 128},
                        "status": {
                            "type": "string",
                            "enum": [item.value for item in FieldCheckStatus],
                        },
                        "confidence": confidence,
                        "evidence_reference": {
                            "type": ["string", "null"],
                            "minLength": 1,
                            "maxLength": 2000,
                        },
                    },
                },
            },
            "contradictions": code_array,
            "missing_required_fields": code_array,
            "duplicate_suspected": {"type": "boolean"},
            "rejection_reasons": code_array,
        }
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": list(properties),
            "properties": properties,
        }
