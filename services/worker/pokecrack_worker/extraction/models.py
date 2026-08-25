from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class EvidenceTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ProductType(StrEnum):
    BOOSTER_BOX = "booster_box"
    ETB = "etb"
    BOOSTER_BUNDLE = "booster_bundle"
    OTHER = "other"
    UNKNOWN = "unknown"


class ContentType(StrEnum):
    VIDEO = "video"
    ARTICLE = "article"
    SOCIAL_POST = "social_post"
    PRODUCT_LISTING = "product_listing"
    MANUAL_IMPORT = "manual_import"
    UNKNOWN = "unknown"


class ExtractionDecision(StrEnum):
    CANDIDATE = "candidate"
    ACTIVITY_ONLY = "activity_only"
    REJECT = "reject"


class EvidenceField(StrEnum):
    SET_NAME = "set_name"
    PRODUCT_NAME = "product_name"
    PRODUCT_TYPE = "product_type"
    PACK_COUNT = "pack_count"
    HITS = "hits"
    COUNTRY_CODE = "country_code"
    REGION = "region"
    RETAILER = "retailer"
    BATCH_CODE = "batch_code"
    OPENED_AT = "opened_at"
    EVIDENCE_TIER = "evidence_tier"


@dataclass(frozen=True, slots=True)
class ExtractedHit:
    card_name: str
    collector_number: str | None
    rarity_label: str | None
    quantity: int
    confidence: float = 1.0
    evidence_reference: str | None = None

    @property
    def rarity(self) -> str | None:
        return self.rarity_label

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExtractedHit:
        allowed = {
            "card_name",
            "collector_number",
            "rarity",
            "rarity_label",
            "quantity",
            "confidence",
            "evidence_reference",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError("unknown field(s): " + ", ".join(sorted(unknown)))
        rarity = value.get("rarity", value.get("rarity_label"))
        return cls(
            card_name=str(value["card_name"]),
            collector_number=value.get("collector_number"),
            rarity_label=rarity,
            quantity=int(value["quantity"]),
            confidence=float(value.get("confidence", 1.0)),
            evidence_reference=value.get("evidence_reference"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "card_name": self.card_name,
            "collector_number": self.collector_number,
            "rarity": self.rarity_label,
            "quantity": self.quantity,
            "confidence": self.confidence,
            "evidence_reference": self.evidence_reference,
        }


@dataclass(frozen=True, slots=True)
class EvidenceQuote:
    field: str
    quote: str
    source_locator: str | None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "quote": self.quote,
            "source_locator": self.source_locator,
        }


@dataclass(frozen=True, slots=True)
class ExtractorOutput:
    """Normalized extractor facts backed by the exact nested provider contract."""

    set_name: str | None
    product_name: str | None
    pack_count: int | None
    hits: tuple[ExtractedHit, ...]
    country_code: str | None
    region: str | None
    retailer: str | None
    batch_code: str | None
    opened_at: str | None
    evidence_tier: EvidenceTier
    confidence: float
    evidence: tuple[EvidenceQuote, ...]
    product_type: ProductType = ProductType.UNKNOWN
    content_type: ContentType = ContentType.UNKNOWN
    decision: ExtractionDecision = ExtractionDecision.CANDIDATE
    is_complete: bool | None = None
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def overall_confidence(self) -> float:
        return self.confidence

    @property
    def evidence_tier_candidate(self) -> EvidenceTier:
        return self.evidence_tier

    def _reference(self, *fields: str) -> str | None:
        for quote in self.evidence:
            if quote.field in fields:
                return quote.source_locator or quote.quote
        return None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExtractorOutput:
        if "set" not in value:
            # Transitional fixture compatibility; real providers must pass nested schema validation.
            allowed = {
                "set_name",
                "product_name",
                "product_type",
                "pack_count",
                "hits",
                "country_code",
                "region",
                "retailer",
                "batch_code",
                "opened_at",
                "evidence_tier",
                "confidence",
                "evidence",
            }
            unknown = set(value) - allowed
            if unknown:
                raise ValueError("unknown field(s): " + ", ".join(sorted(unknown)))
            return cls(
                set_name=value.get("set_name"),
                product_name=value.get("product_name"),
                product_type=ProductType(value.get("product_type", "unknown")),
                pack_count=value.get("pack_count"),
                hits=tuple(ExtractedHit.from_mapping(item) for item in value.get("hits", [])),
                country_code=value.get("country_code"),
                region=value.get("region"),
                retailer=value.get("retailer"),
                batch_code=value.get("batch_code"),
                opened_at=value.get("opened_at"),
                evidence_tier=EvidenceTier(value.get("evidence_tier", "D")),
                confidence=float(value.get("confidence", 0.0)),
                evidence=tuple(
                    EvidenceQuote(item["field"], item["quote"], item.get("source_locator"))
                    for item in value.get("evidence", [])
                ),
            )
        expected = {
            "content_type",
            "decision",
            "set",
            "product",
            "opening",
            "location",
            "purchase",
            "hits",
            "evidence_tier_candidate",
            "overall_confidence",
            "missing_fields",
            "warnings",
        }
        unknown = set(value) - expected
        missing = expected - set(value)
        if unknown or missing:
            raise ValueError(
                "extractor fields mismatch; unknown="
                + ",".join(sorted(unknown))
                + " missing="
                + ",".join(sorted(missing))
            )
        set_value = value["set"]
        product = value["product"]
        opening = value["opening"]
        location = value["location"]
        purchase = value["purchase"]
        if not all(
            isinstance(item, Mapping) for item in (set_value, product, opening, location, purchase)
        ):
            raise ValueError("nested extractor fields must be objects")
        evidence: list[EvidenceQuote] = []
        for field, container in (
            ("set_name", set_value),
            ("product_name", product),
            ("pack_count", opening),
            ("country_code", location),
            ("retailer", purchase),
        ):
            reference = container.get("evidence_reference")
            if isinstance(reference, str) and reference:
                evidence.append(EvidenceQuote(field, reference, reference))
        return cls(
            content_type=ContentType(value["content_type"]),
            decision=ExtractionDecision(value["decision"]),
            set_name=set_value.get("name"),
            product_name=product.get("name"),
            product_type=ProductType(product.get("type", "unknown")),
            pack_count=opening.get("pack_count"),
            is_complete=opening.get("is_complete"),
            opened_at=opening.get("opened_at"),
            country_code=location.get("country_code"),
            region=location.get("region"),
            retailer=purchase.get("retailer"),
            batch_code=purchase.get("batch_code"),
            hits=tuple(ExtractedHit.from_mapping(item) for item in value["hits"]),
            evidence_tier=EvidenceTier(value["evidence_tier_candidate"]),
            confidence=float(value["overall_confidence"]),
            evidence=tuple(evidence),
            missing_fields=tuple(value["missing_fields"]),
            warnings=tuple(value["warnings"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        confidence = self.confidence
        return {
            "content_type": self.content_type.value,
            "decision": self.decision.value,
            "set": {
                "name": self.set_name,
                "confidence": confidence,
                "evidence_reference": self._reference("set_name"),
            },
            "product": {
                "name": self.product_name,
                "type": self.product_type.value,
                "confidence": confidence,
                "evidence_reference": self._reference("product_name", "product_type"),
            },
            "opening": {
                "pack_count": self.pack_count,
                "is_complete": self.is_complete,
                "opened_at": self.opened_at,
                "confidence": confidence,
                "evidence_reference": self._reference("pack_count", "opened_at"),
            },
            "location": {
                "country_code": self.country_code,
                "region": self.region,
                "confidence": confidence,
                "evidence_reference": self._reference("country_code", "region"),
            },
            "purchase": {
                "retailer": self.retailer,
                "batch_code": self.batch_code,
                "confidence": confidence,
                "evidence_reference": self._reference("retailer", "batch_code"),
            },
            "hits": [item.to_mapping() for item in self.hits],
            "evidence_tier_candidate": self.evidence_tier.value,
            "overall_confidence": confidence,
            "missing_fields": list(self.missing_fields),
            "warnings": list(self.warnings),
        }

    @staticmethod
    def json_schema() -> dict[str, Any]:
        nullable = {"type": ["string", "null"], "minLength": 1, "maxLength": 300}
        reference = {"type": ["string", "null"], "minLength": 1, "maxLength": 2000}
        confidence = {"type": "number", "minimum": 0, "maximum": 1}

        def observed(properties: dict[str, Any]) -> dict[str, Any]:
            fields = {**properties, "confidence": confidence, "evidence_reference": reference}
            return {
                "type": "object",
                "additionalProperties": False,
                "required": list(fields),
                "properties": fields,
            }

        properties: dict[str, Any] = {
            "content_type": {"type": "string", "enum": [item.value for item in ContentType]},
            "decision": {"type": "string", "enum": [item.value for item in ExtractionDecision]},
            "set": observed({"name": nullable}),
            "product": observed(
                {
                    "name": nullable,
                    "type": {"type": "string", "enum": [item.value for item in ProductType]},
                }
            ),
            "opening": observed(
                {
                    "pack_count": {"type": ["integer", "null"], "minimum": 0, "maximum": 10000},
                    "is_complete": {"type": ["boolean", "null"]},
                    "opened_at": {"type": ["string", "null"], "format": "date-time"},
                }
            ),
            "location": observed(
                {
                    "country_code": {"type": ["string", "null"], "pattern": "^[A-Z]{2}$"},
                    "region": nullable,
                }
            ),
            "purchase": observed({"retailer": nullable, "batch_code": nullable}),
            "hits": {
                "type": "array",
                "maxItems": 10000,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "card_name",
                        "collector_number",
                        "rarity",
                        "quantity",
                        "confidence",
                        "evidence_reference",
                    ],
                    "properties": {
                        "card_name": {"type": "string", "minLength": 1, "maxLength": 300},
                        "collector_number": {
                            "type": ["string", "null"],
                            "minLength": 1,
                            "maxLength": 64,
                        },
                        "rarity": {"type": ["string", "null"], "minLength": 1, "maxLength": 128},
                        "quantity": {"type": "integer", "minimum": 1, "maximum": 1000},
                        "confidence": confidence,
                        "evidence_reference": reference,
                    },
                },
            },
            "evidence_tier_candidate": {
                "type": "string",
                "enum": [item.value for item in EvidenceTier],
            },
            "overall_confidence": confidence,
            "missing_fields": {
                "type": "array",
                "maxItems": 100,
                "items": {"type": "string", "minLength": 1, "maxLength": 128},
            },
            "warnings": {
                "type": "array",
                "maxItems": 100,
                "items": {"type": "string", "minLength": 1, "maxLength": 256},
            },
        }
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": list(properties),
            "properties": properties,
        }
