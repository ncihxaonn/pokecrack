"""Fail-closed local operators for the authorized-opening RPC boundary.

The operator path deliberately has no collector, browser, URL fetcher, or raw
evidence store.  It accepts one owner-produced JSON envelope from a mode-0600
regular file, validates the exact v1 shape locally, and then sends the
validated JSON to one of the reviewed PostgreSQL functions.  All database
errors are collapsed to safe operator-facing codes; opaque references and
evidence digests never appear in output.
"""

from __future__ import annotations

import json
import os
import re
import stat
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, NoReturn
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pokecrack_worker.db import PsycopgQueryExecutor

MAX_ENVELOPE_BYTES = 16_384
ENVELOPE_FILE_MODE = 0o600
SCHEMA_VERSION = "1.0.0"

SUBMITTER_ROLE = "pokecrack_authorized_opening_submitter"
SUBMITTER_LOGIN = "pokecrack_authorized_opening_submitter_login"
REVIEWER_ROLE = "pokecrack_authorized_opening_reviewer"
REVIEWER_LOGIN = "pokecrack_authorized_opening_reviewer_login"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,159}$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")
_LANGUAGE = re.compile(r"^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$")
_SET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
_UTC_SECONDS = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_SUPPORTED_SSL_MODES = frozenset({"require", "verify-ca", "verify-full"})
_SUPPORTED_DSN_OPTIONS = frozenset(
    {
        "application_name",
        "channel_binding",
        "connect_timeout",
        "gssencmode",
        "options",
        "require_auth",
        "sslcert",
        "sslcrl",
        "sslcrldir",
        "sslkey",
        "sslmode",
        "sslnegotiation",
        "sslrootcert",
        "target_session_attrs",
    }
)
_SAFE_STATES = frozenset(
    {
        "queued",
        "in_review",
        "accepted_statistics",
        "accepted_activity_only",
        "duplicate",
        "rejected",
        "expired",
        "retracted",
    }
)
_SAFE_RETRACTION_REASONS = frozenset(
    {
        "authorization_revoked",
        "evidence_corrected",
        "privacy_request",
        "policy_takedown",
    }
)

SubmissionState = Literal[
    "in_review",
    "accepted_statistics",
    "accepted_activity_only",
    "duplicate",
    "rejected",
    "expired",
]
ReviewListState = Literal[
    "all",
    "queued",
    "in_review",
    "accepted_statistics",
    "accepted_activity_only",
    "duplicate",
    "rejected",
    "expired",
]
ReviewReason = Literal[
    "review_started",
    "evidence_verified",
    "activity_only",
    "duplicate_provenance",
    "duplicate_source",
    "authorization_invalid",
    "evidence_incomplete",
    "geography_unverified",
    "denominator_incomplete",
    "reviewer_rejected",
    "policy_expired",
]
RetractionReason = Literal[
    "authorization_revoked",
    "evidence_corrected",
    "privacy_request",
    "policy_takedown",
]


class AuthorizedOpeningOperatorError(RuntimeError):
    """An expected, safe error that may be rendered to a local operator."""

    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


def _operator_error(code: str, message: str) -> NoReturn:
    raise AuthorizedOpeningOperatorError(code, message)


def _has_control_characters(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def _canonical_text(value: str, *, max_length: int, field_name: str) -> str:
    if not value or len(value) > max_length:
        _operator_error("invalid_envelope", f"{field_name} is not canonical")
    normalized = unicodedata.normalize("NFKC", value)
    if value != normalized or value != value.strip() or _has_control_characters(value):
        _operator_error("invalid_envelope", f"{field_name} is not canonical")
    return value


class AuthorizedOpeningEnvelope(BaseModel):
    """The exact camel-case payload accepted by ``submit_authorized_opening_v1``."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=False,
        str_strip_whitespace=False,
    )

    schema_version: Literal["1.0.0"] = Field(alias="schemaVersion")
    submission_key: str = Field(alias="submissionKey", min_length=1, max_length=160)
    discovery_platform: Literal["youtube", "bluesky", "nostr", "direct"] = Field(
        alias="discoveryPlatform"
    )
    discovery_candidate_sha256: str | None = Field(alias="discoveryCandidateSha256")
    source_identity_sha256: str = Field(alias="sourceIdentitySha256", min_length=64, max_length=64)
    authorization_reference_sha256: str = Field(
        alias="authorizationReferenceSha256", min_length=64, max_length=64
    )
    evidence_sha256: str = Field(alias="evidenceSha256", min_length=64, max_length=64)
    provenance_dedupe_sha256: str = Field(
        alias="provenanceDedupeSha256", min_length=64, max_length=64
    )
    country_code: str = Field(alias="countryCode", min_length=2, max_length=2)
    country_name: str = Field(alias="countryName", min_length=1, max_length=160)
    geography_basis: Literal[
        "opening_location",
        "publisher_country",
        "author_public_residence",
        "self_reported_country",
    ] = Field(alias="geographyBasis")
    geography_confidence: Literal["tier_a", "tier_b"] = Field(alias="geographyConfidence")
    language: str = Field(alias="language", min_length=2, max_length=35)
    tcgdex_set_id: str = Field(alias="tcgdexSetId", min_length=1, max_length=160)
    product_scope: Literal["all", "booster_box", "etb", "booster_bundle"] = Field(
        alias="productScope"
    )
    observed_at: str = Field(alias="observedAt")
    pack_count: int = Field(alias="packCount", ge=1, le=100_000)
    qualifying_hit_pack_count: int = Field(alias="qualifyingHitPackCount", ge=0, le=100_000)
    denominator_complete: Literal[True] = Field(alias="denominatorComplete")
    statistics_eligible: bool = Field(alias="statisticsEligible")

    @model_validator(mode="after")
    def validate_canonical_contract(self) -> AuthorizedOpeningEnvelope:
        if _KEY.fullmatch(self.submission_key) is None:
            _operator_error("invalid_envelope", "submissionKey is not canonical")
        for name, value in (
            ("sourceIdentitySha256", self.source_identity_sha256),
            ("authorizationReferenceSha256", self.authorization_reference_sha256),
            ("evidenceSha256", self.evidence_sha256),
            ("provenanceDedupeSha256", self.provenance_dedupe_sha256),
        ):
            if _SHA256.fullmatch(value) is None:
                _operator_error("invalid_envelope", f"{name} is not a lowercase SHA-256 reference")
        if _COUNTRY.fullmatch(self.country_code) is None:
            _operator_error("invalid_envelope", "countryCode is not canonical")
        _canonical_text(self.country_name, max_length=160, field_name="countryName")
        if _LANGUAGE.fullmatch(self.language) is None:
            _operator_error("invalid_envelope", "language is not canonical")
        if _SET_ID.fullmatch(self.tcgdex_set_id) is None:
            _operator_error("invalid_envelope", "tcgdexSetId is not canonical")
        if _UTC_SECONDS.fullmatch(self.observed_at) is None:
            _operator_error("invalid_envelope", "observedAt must use UTC seconds")
        try:
            observed_at = datetime.strptime(self.observed_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=UTC
            )
        except ValueError:
            _operator_error("invalid_envelope", "observedAt is not a valid timestamp")
        if observed_at < datetime(2000, 1, 1, tzinfo=UTC):
            _operator_error("invalid_envelope", "observedAt is outside the approved range")
        if observed_at > datetime.now(UTC) + timedelta(hours=24):
            _operator_error("invalid_envelope", "observedAt is outside the approved range")
        if self.qualifying_hit_pack_count > self.pack_count:
            _operator_error("invalid_envelope", "opening counts are not coherent")

        # This boundary is for an explicitly supplied creator/owner envelope.
        # A social candidate is never promoted by this command, even though the
        # database contract retains a bounded field for other future paths.
        if self.discovery_platform != "direct" or self.discovery_candidate_sha256 is not None:
            _operator_error(
                "social_derived_rejected",
                "social discovery cannot be submitted through the authorized-opening operator",
            )
        return self


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _operator_error("invalid_envelope", "the envelope contains duplicate fields")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    del value
    _operator_error("invalid_envelope", "the envelope contains a non-finite JSON number")


def _load_envelope_json(raw: bytes) -> AuthorizedOpeningEnvelope:
    if len(raw) > MAX_ENVELOPE_BYTES:
        _operator_error("invalid_envelope", "the envelope exceeds the fixed size limit")
    try:
        decoded = raw.decode("utf-8")
        payload = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except AuthorizedOpeningOperatorError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        _operator_error("invalid_envelope", "the envelope is not valid UTF-8 JSON")
    if not isinstance(payload, dict):
        _operator_error("invalid_envelope", "the envelope must be a JSON object")
    try:
        envelope = AuthorizedOpeningEnvelope.model_validate(payload)
        serialized = json.dumps(
            envelope.model_dump(by_alias=True, mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except AuthorizedOpeningOperatorError:
        raise
    except (ValidationError, TypeError, ValueError):
        _operator_error("invalid_envelope", "the envelope does not match the exact v1 contract")
    if len(serialized) > MAX_ENVELOPE_BYTES:
        _operator_error("invalid_envelope", "the envelope exceeds the fixed size limit")
    return envelope


def read_authorized_opening_envelope(path: Path) -> AuthorizedOpeningEnvelope:
    """Read one owner envelope without following symlinks or retaining it."""

    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
    except OSError:
        _operator_error(
            "private_input_required",
            "envelope must be an existing mode-0600 regular file",
        )
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            file_stat = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(file_stat.st_mode)
                or stat.S_IMODE(file_stat.st_mode) != ENVELOPE_FILE_MODE
                or file_stat.st_uid != os.geteuid()
            ):
                _operator_error(
                    "private_input_required",
                    "envelope must be an existing mode-0600 regular file",
                )
            raw = stream.read(MAX_ENVELOPE_BYTES + 1)
    except AuthorizedOpeningOperatorError:
        raise
    except (OSError, ValueError):
        _operator_error("private_input_required", "the envelope could not be read safely")
    return _load_envelope_json(raw)


class AuthorizedOpeningOperatorSettings(BaseSettings):
    """Isolated operator config; it never falls back to worker/service DSNs."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    authorized_opening_submitter_db_url: SecretStr | None = None
    authorized_opening_reviewer_db_url: SecretStr | None = None


def _fixed_role_dsn(
    dsn: str,
    *,
    environment_name: str,
    expected_login: str,
    expected_role: str,
) -> str:
    """Validate a dedicated TLS DSN and pin its session role option."""

    try:
        parts = urlsplit(dsn)
        username = unquote(parts.username or "")
        if (
            parts.scheme not in {"postgres", "postgresql"}
            or not parts.netloc
            or not parts.hostname
            or parts.fragment
            or username != expected_login
            or not parts.password
        ):
            raise ValueError
        query = parse_qsl(
            parts.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=32,
        )
    except (TypeError, ValueError):
        _operator_error(
            "invalid_configuration",
            f"{environment_name} must be a dedicated TLS PostgreSQL URL",
        )
    query_keys = [key for key, _value in query]
    if len(query_keys) != len(set(query_keys)) or not set(query_keys) <= _SUPPORTED_DSN_OPTIONS:
        _operator_error(
            "invalid_configuration",
            f"{environment_name} has unsupported or duplicate connection options",
        )
    query_values = dict(query)
    if query_values.get("sslmode") not in _SUPPORTED_SSL_MODES:
        _operator_error(
            "invalid_configuration",
            f"{environment_name} requires sslmode=require or stronger",
        )
    expected_options = f"-c role={expected_role}"
    if query_values.get("options") != expected_options:
        _operator_error(
            "invalid_configuration",
            f"{environment_name} must pin the reviewed least-privilege role",
        )
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, quote_via=quote),
            "",
        )
    )


def _operator_dsn(config: AuthorizedOpeningOperatorSettings, *, reviewer: bool) -> str:
    if reviewer:
        configured = config.authorized_opening_reviewer_db_url
        environment_name = "AUTHORIZED_OPENING_REVIEWER_DB_URL"
        expected_login = REVIEWER_LOGIN
        expected_role = REVIEWER_ROLE
    else:
        configured = config.authorized_opening_submitter_db_url
        environment_name = "AUTHORIZED_OPENING_SUBMITTER_DB_URL"
        expected_login = SUBMITTER_LOGIN
        expected_role = SUBMITTER_ROLE
    if configured is None or not configured.get_secret_value().strip():
        _operator_error(
            "invalid_configuration",
            f"{environment_name} is required in a separate mode-0600 operator environment",
        )
    return _fixed_role_dsn(
        configured.get_secret_value(),
        environment_name=environment_name,
        expected_login=expected_login,
        expected_role=expected_role,
    )


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    submission_id: UUID
    revision: int
    state: str


@dataclass(frozen=True, slots=True)
class ReviewResult:
    submission_id: UUID
    revision: int
    state: str


@dataclass(frozen=True, slots=True)
class RetractionResult:
    accepted_observation_id: UUID
    reason_code: str


@dataclass(frozen=True, slots=True)
class ReviewQueueItem:
    submission_id: UUID
    revision: int
    state: str


SUBMIT_AUTHORIZED_OPENING_SQL = """
select submission_id, revision, state
from ingest.submit_authorized_opening_v1(%(payload)s::jsonb)
"""
LIST_AUTHORIZED_OPENING_REVIEWS_SQL = """
select submission_id, revision, state
from ingest.list_authorized_opening_reviews_v1(%(requested_state)s, %(requested_limit)s)
"""
REVIEW_AUTHORIZED_OPENING_SQL = """
select submission_id, revision, state, accepted_observation_id
from ingest.review_authorized_opening_v1(
  %(requested_submission_id)s::uuid,
  %(expected_revision)s::bigint,
  %(target_state)s,
  %(reviewer_reference_sha256)s,
  %(reason_code)s
)
"""
RETRACT_AUTHORIZED_OPENING_SQL = """
select accepted_observation_id, reason_code
from ingest.retract_authorized_opening_v1(
  %(requested_observation_id)s::uuid,
  %(reviewer_reference_sha256)s,
  %(requested_reason_code)s
)
"""


def _uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        _operator_error("database_protocol_error", "the database returned an unsafe result")
    try:
        return UUID(value)
    except ValueError:
        _operator_error("database_protocol_error", "the database returned an unsafe result")


def _positive_revision(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _operator_error("database_protocol_error", "the database returned an unsafe result")
    return value


def _safe_state(value: object) -> str:
    if not isinstance(value, str) or value not in _SAFE_STATES or _has_control_characters(value):
        _operator_error("database_protocol_error", "the database returned an unsafe result")
    return value


def _safe_retraction_reason(value: object) -> str:
    if not isinstance(value, str) or value not in _SAFE_RETRACTION_REASONS:
        _operator_error("database_protocol_error", "the database returned an unsafe result")
    return value


class AuthorizedOpeningRpcClient:
    """Typed calls to the four reviewed functions; no table SQL is exposed."""

    def __init__(self, executor: PsycopgQueryExecutor) -> None:
        self._executor = executor

    def _query(
        self,
        sql: str,
        params: Mapping[str, object],
    ) -> tuple[Mapping[str, Any], ...]:
        try:
            return self._executor.query(sql, params)
        except AuthorizedOpeningOperatorError:
            raise
        except Exception as error:
            del error
            _operator_error("database_unavailable", "the authorized-opening database call failed")

    @staticmethod
    def _submission_result(row: Mapping[str, Any]) -> SubmissionResult:
        return SubmissionResult(
            submission_id=_uuid(row.get("submission_id")),
            revision=_positive_revision(row.get("revision")),
            state=_safe_state(row.get("state")),
        )

    def submit(self, envelope: AuthorizedOpeningEnvelope) -> SubmissionResult:
        payload = json.dumps(
            envelope.model_dump(by_alias=True, mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        rows = self._query(SUBMIT_AUTHORIZED_OPENING_SQL, {"payload": payload})
        if len(rows) != 1:
            _operator_error("database_protocol_error", "the database returned an unsafe result")
        return self._submission_result(rows[0])

    def list_reviews(
        self, requested_state: ReviewListState, requested_limit: int
    ) -> tuple[ReviewQueueItem, ...]:
        rows = self._query(
            LIST_AUTHORIZED_OPENING_REVIEWS_SQL,
            {"requested_state": requested_state, "requested_limit": requested_limit},
        )
        items: list[ReviewQueueItem] = []
        for row in rows:
            items.append(
                ReviewQueueItem(
                    submission_id=_uuid(row.get("submission_id")),
                    revision=_positive_revision(row.get("revision")),
                    state=_safe_state(row.get("state")),
                )
            )
        return tuple(items)

    def review(
        self,
        submission_id: UUID,
        expected_revision: int,
        target_state: SubmissionState,
        reviewer_reference_sha256: str,
        reason_code: ReviewReason,
    ) -> ReviewResult:
        rows = self._query(
            REVIEW_AUTHORIZED_OPENING_SQL,
            {
                "requested_submission_id": str(submission_id),
                "expected_revision": expected_revision,
                "target_state": target_state,
                "reviewer_reference_sha256": reviewer_reference_sha256,
                "reason_code": reason_code,
            },
        )
        if len(rows) != 1:
            _operator_error("database_protocol_error", "the database returned an unsafe result")
        result = self._submission_result(rows[0])
        return ReviewResult(result.submission_id, result.revision, result.state)

    def retract(
        self,
        observation_id: UUID,
        reviewer_reference_sha256: str,
        reason_code: RetractionReason,
    ) -> RetractionResult:
        rows = self._query(
            RETRACT_AUTHORIZED_OPENING_SQL,
            {
                "requested_observation_id": str(observation_id),
                "reviewer_reference_sha256": reviewer_reference_sha256,
                "requested_reason_code": reason_code,
            },
        )
        if len(rows) != 1:
            _operator_error("database_protocol_error", "the database returned an unsafe result")
        row = rows[0]
        return RetractionResult(
            accepted_observation_id=_uuid(row.get("accepted_observation_id")),
            reason_code=_safe_retraction_reason(row.get("reason_code")),
        )


def build_operator_client(*, reviewer: bool) -> AuthorizedOpeningRpcClient:
    """Build a client from only the dedicated operator environment variable."""

    try:
        config = AuthorizedOpeningOperatorSettings(_env_file=None)
    except ValidationError:
        _operator_error(
            "invalid_configuration", "authorized-opening operator configuration is invalid"
        )
    dsn = _operator_dsn(config, reviewer=reviewer)
    try:
        return AuthorizedOpeningRpcClient(PsycopgQueryExecutor.from_dsn(dsn))
    except Exception as error:
        del error
        _operator_error(
            "invalid_configuration", "authorized-opening database configuration is invalid"
        )


def parse_uuid(value: str) -> UUID:
    try:
        parsed = UUID(value)
    except (AttributeError, ValueError, TypeError):
        _operator_error("invalid_request", "the requested identifier is not a UUID")
    if str(parsed) != value:
        _operator_error("invalid_request", "the requested identifier must be a canonical UUID")
    return parsed


def validate_reviewer_reference(value: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _operator_error(
            "invalid_request", "reviewer reference must be a lowercase SHA-256 reference"
        )
    return value


def validate_review_list_request(*, state: str, limit: int) -> ReviewListState:
    allowed_states = {
        "all",
        "queued",
        "in_review",
        "accepted_statistics",
        "accepted_activity_only",
        "duplicate",
        "rejected",
        "expired",
    }
    if state not in allowed_states:
        _operator_error("invalid_request", "review state filter is not allowed")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        _operator_error("invalid_request", "review limit must be between 1 and 100")
    return state  # type: ignore[return-value]


def validate_review_request(
    *,
    target_state: str,
    reason_code: str,
    expected_revision: int,
) -> tuple[SubmissionState, ReviewReason]:
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 1
    ):
        _operator_error("invalid_request", "expected revision must be positive")
    state_reason: dict[str, set[str]] = {
        "in_review": {"review_started"},
        "accepted_statistics": {"evidence_verified"},
        "accepted_activity_only": {"activity_only"},
        "duplicate": {"duplicate_provenance", "duplicate_source"},
        "rejected": {
            "authorization_invalid",
            "evidence_incomplete",
            "geography_unverified",
            "denominator_incomplete",
            "reviewer_rejected",
        },
        "expired": {"policy_expired"},
    }
    if target_state not in state_reason or reason_code not in state_reason[target_state]:
        _operator_error("invalid_request", "review state and reason are not an allowed pair")
    return target_state, reason_code  # type: ignore[return-value]


def validate_retraction_request(reason_code: str) -> RetractionReason:
    if not isinstance(reason_code, str) or reason_code not in {
        "authorization_revoked",
        "evidence_corrected",
        "privacy_request",
        "policy_takedown",
    }:
        _operator_error("invalid_request", "retraction reason is not allowed")
    return reason_code  # type: ignore[return-value]


def safe_submission_payload(result: SubmissionResult | ReviewResult) -> dict[str, object]:
    revision = _positive_revision(result.revision)
    state = _safe_state(result.state)
    return {
        "submission_id": str(result.submission_id),
        "revision": revision,
        "state": state,
    }


def safe_review_queue_payload(items: Sequence[ReviewQueueItem]) -> dict[str, object]:
    return {
        "reviews": [
            {
                "submission_id": str(item.submission_id),
                "revision": item.revision,
                "state": item.state,
            }
            for item in items
        ]
    }


def safe_retraction_payload(result: RetractionResult) -> dict[str, object]:
    reason_code = _safe_retraction_reason(result.reason_code)
    return {
        "accepted_observation_id": str(result.accepted_observation_id),
        "reason_code": reason_code,
        "state": "retracted",
    }


__all__ = [
    "AuthorizedOpeningEnvelope",
    "AuthorizedOpeningOperatorError",
    "AuthorizedOpeningOperatorSettings",
    "AuthorizedOpeningRpcClient",
    "ENVELOPE_FILE_MODE",
    "LIST_AUTHORIZED_OPENING_REVIEWS_SQL",
    "MAX_ENVELOPE_BYTES",
    "RETRACT_AUTHORIZED_OPENING_SQL",
    "REVIEW_AUTHORIZED_OPENING_SQL",
    "SUBMIT_AUTHORIZED_OPENING_SQL",
    "build_operator_client",
    "parse_uuid",
    "read_authorized_opening_envelope",
    "safe_retraction_payload",
    "safe_review_queue_payload",
    "safe_submission_payload",
    "validate_retraction_request",
    "validate_review_list_request",
    "validate_review_request",
    "validate_reviewer_reference",
]
