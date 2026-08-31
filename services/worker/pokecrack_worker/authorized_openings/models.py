"""Strict, privacy-minimal DTOs for owner-authorized opening evidence."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from .iso_codes import CANONICAL_COUNTRY_NAMES, ISO_ALPHA2_CODES

_OBSERVED_AT_MIN = datetime(2000, 1, 1, tzinfo=UTC)
_UTC_SECONDS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SUBMISSION_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,159}$")
_TCGDEX_SET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-(?:[A-Z]{2}|[0-9]{3}))?$")
_LOWER_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ReviewState(StrEnum):
    QUEUED = "queued"
    IN_REVIEW = "in_review"
    ACCEPTED_STATISTICS = "accepted_statistics"
    ACCEPTED_ACTIVITY_ONLY = "accepted_activity_only"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    EXPIRED = "expired"


class RetractionReason(StrEnum):
    AUTHORIZATION_REVOKED = "authorization_revoked"
    EVIDENCE_CORRECTED = "evidence_corrected"
    PRIVACY_REQUEST = "privacy_request"
    POLICY_TAKEDOWN = "policy_takedown"


ALLOWED_REVIEW_REASONS: dict[ReviewState, frozenset[str]] = {
    ReviewState.IN_REVIEW: frozenset({"review_started"}),
    ReviewState.ACCEPTED_STATISTICS: frozenset({"evidence_verified"}),
    ReviewState.ACCEPTED_ACTIVITY_ONLY: frozenset({"activity_only"}),
    ReviewState.DUPLICATE: frozenset({"duplicate_provenance", "duplicate_source"}),
    ReviewState.REJECTED: frozenset(
        {
            "authorization_invalid",
            "evidence_incomplete",
            "geography_unverified",
            "denominator_incomplete",
            "reviewer_rejected",
        }
    ),
    ReviewState.EXPIRED: frozenset({"policy_expired"}),
}


def _canonical_text(value: str, *, field: str, maximum: int) -> str:
    if not 1 <= len(value) <= maximum:
        raise ValueError(f"{field} is outside the approved length")
    if value != value.strip() or unicodedata.normalize("NFKC", value) != value:
        raise ValueError(f"{field} must use canonical NFKC text without outer whitespace")
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError(f"{field} contains a forbidden control character")
    return value


def _sha256(value: str, *, field: str) -> str:
    if _LOWER_SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


class AuthorizedOpeningSubmission(BaseModel):
    """One exact JSONL row. Nullable fields remain required JSON keys."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    schema_version: Literal["1.0.0"] = Field(alias="schemaVersion")
    submission_key: StrictStr = Field(alias="submissionKey")
    discovery_platform: Literal["youtube", "bluesky", "nostr", "direct"] | None = Field(
        alias="discoveryPlatform"
    )
    discovery_candidate_sha256: StrictStr | None = Field(alias="discoveryCandidateSha256")
    source_identity_sha256: StrictStr = Field(alias="sourceIdentitySha256")
    authorization_reference_sha256: StrictStr = Field(alias="authorizationReferenceSha256")
    evidence_sha256: StrictStr = Field(alias="evidenceSha256")
    provenance_dedupe_sha256: StrictStr = Field(alias="provenanceDedupeSha256")
    country_code: StrictStr = Field(alias="countryCode")
    country_name: StrictStr = Field(alias="countryName")
    geography_basis: Literal[
        "opening_location",
        "publisher_country",
        "author_public_residence",
        "self_reported_country",
    ] = Field(alias="geographyBasis")
    geography_confidence: Literal["tier_a", "tier_b"] = Field(alias="geographyConfidence")
    language: StrictStr
    tcgdex_set_id: StrictStr = Field(alias="tcgdexSetId")
    product_scope: Literal["all", "booster_box", "etb", "booster_bundle"] = Field(
        alias="productScope"
    )
    observed_at: StrictStr = Field(alias="observedAt")
    pack_count: StrictInt = Field(alias="packCount", ge=1, le=100_000)
    qualifying_hit_pack_count: StrictInt = Field(alias="qualifyingHitPackCount", ge=0)
    denominator_complete: StrictBool = Field(alias="denominatorComplete")
    statistics_eligible: StrictBool = Field(alias="statisticsEligible")

    @field_validator("submission_key")
    @classmethod
    def validate_submission_key(cls, value: str) -> str:
        if _SUBMISSION_KEY_PATTERN.fullmatch(value) is None:
            raise ValueError("submissionKey is not a canonical stable key")
        return value

    @field_validator(
        "discovery_candidate_sha256",
        "source_identity_sha256",
        "authorization_reference_sha256",
        "evidence_sha256",
        "provenance_dedupe_sha256",
    )
    @classmethod
    def validate_sha256(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        field_name = getattr(info, "field_name", "fingerprint")
        return _sha256(value, field=field_name)

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        if value not in ISO_ALPHA2_CODES:
            raise ValueError("countryCode must be a reviewed ISO alpha-2 code")
        return value

    @field_validator("country_name")
    @classmethod
    def validate_country_name(cls, value: str) -> str:
        canonical = _canonical_text(value, field="countryName", maximum=160)
        allowed_punctuation = frozenset(" .,\u0027\u2019()&-")
        if any(
            not unicodedata.category(character).startswith(("L", "M"))
            and character not in allowed_punctuation
            for character in canonical
        ):
            raise ValueError("countryName contains a forbidden non-name character")
        return canonical

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if _LANGUAGE_PATTERN.fullmatch(value) is None:
            raise ValueError("language must use the approved canonical BCP47 subset")
        return value

    @field_validator("tcgdex_set_id")
    @classmethod
    def validate_tcgdex_set_id(cls, value: str) -> str:
        if _TCGDEX_SET_ID_PATTERN.fullmatch(value) is None:
            raise ValueError("tcgdexSetId is invalid")
        return value

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: str) -> str:
        if _UTC_SECONDS_PATTERN.fullmatch(value) is None:
            raise ValueError("observedAt must be canonical UTC seconds")
        try:
            parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        except ValueError as error:
            raise ValueError("observedAt is not a valid timestamp") from error
        if not _OBSERVED_AT_MIN <= parsed <= datetime.now(UTC) + timedelta(hours=24):
            raise ValueError("observedAt is outside the approved range")
        return value

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.country_name != CANONICAL_COUNTRY_NAMES[self.country_code]:
            raise ValueError("countryName must match the canonical ISO country name")
        if self.qualifying_hit_pack_count > self.pack_count:
            raise ValueError("qualifyingHitPackCount must not exceed packCount")
        if self.denominator_complete is not True:
            raise ValueError("denominatorComplete must be true")
        if self.discovery_candidate_sha256 is not None and self.discovery_platform not in {
            "youtube",
            "bluesky",
            "nostr",
        }:
            raise ValueError("discovery candidate requires a supported social platform")
        return self

    def as_payload(self) -> dict[str, object]:
        return self.model_dump(by_alias=True, mode="json")


def validate_actor(actor: str) -> str:
    return _canonical_text(actor, field="actor", maximum=160)


def reviewer_reference_hmac(actor: str, secret: str) -> str:
    """Domain-separated opaque reviewer reference; raw actor is never persisted."""

    canonical_actor = validate_actor(actor)
    secret_bytes = secret.encode("utf-8")
    if len(secret_bytes) < 32:
        raise ValueError("reviewer HMAC key must contain at least 32 UTF-8 bytes")
    message = b"pokecrack-authorized-opening-reviewer-v1\x00" + canonical_actor.encode("utf-8")
    return hmac.new(secret_bytes, message, hashlib.sha256).hexdigest()


def validate_review_transition(target: ReviewState, reason: str) -> None:
    if target is ReviewState.QUEUED:
        raise ValueError("queued is submit-only")
    _canonical_text(reason, field="reason", maximum=64)
    if reason not in ALLOWED_REVIEW_REASONS[target]:
        raise ValueError("reason is not allowed for the requested review decision")
