"""Explicit-transaction PostgreSQL operator repository with redacted DTOs."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from .iso_codes import CANONICAL_COUNTRY_NAMES
from .models import AuthorizedOpeningSubmission, RetractionReason, ReviewState

_SUBMIT_SQL = """
SELECT submission_id, revision, state
FROM ingest.submit_authorized_opening_v1(%(payload)s::jsonb)
"""

_LIST_SQL = """
SELECT
  submission_id,
  revision,
  state,
  discovery_platform,
  country_code,
  geography_basis,
  geography_confidence,
  language,
  tcgdex_set_id,
  product_scope,
  observed_at,
  pack_count,
  qualifying_hit_pack_count,
  denominator_complete,
  statistics_eligible_requested,
  created_at,
  updated_at,
  expires_at
FROM ingest.list_authorized_opening_reviews_v1(%(state)s, %(limit)s)
"""

_REVIEW_SQL = """
SELECT submission_id, revision, state, accepted_observation_id
FROM ingest.review_authorized_opening_v1(
  %(submission_id)s,
  %(expected_revision)s,
  %(target_state)s,
  %(reviewer_reference_sha256)s,
  %(reason_code)s
)
"""

_RETRACT_SQL = """
SELECT accepted_observation_id, reason_code, retracted_at
FROM ingest.retract_authorized_opening_v1(
  %(accepted_observation_id)s,
  %(reviewer_reference_sha256)s,
  %(reason_code)s
)
"""


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    submission_id: UUID
    revision: int
    state: ReviewState


@dataclass(frozen=True, slots=True)
class ReviewResult:
    submission_id: UUID
    revision: int
    state: ReviewState
    accepted_observation_id: UUID | None


@dataclass(frozen=True, slots=True)
class RetractionResult:
    accepted_observation_id: UUID
    reason_code: RetractionReason
    retracted_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewQueueItem:
    submission_id: UUID
    revision: int
    state: ReviewState
    discovery_platform: str | None
    country_code: str
    country_name: str
    geography_basis: str
    geography_confidence: str
    language: str
    tcgdex_set_id: str
    product_scope: str
    observed_at: datetime
    pack_count: int
    qualifying_hit_pack_count: int
    denominator_complete: bool
    statistics_eligible_requested: bool
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class AuthorizedOpeningRepository(Protocol):
    def submit_many(
        self, submissions: Sequence[AuthorizedOpeningSubmission]
    ) -> tuple[SubmissionResult, ...]: ...

    def list_reviews(self, state: str, limit: int) -> tuple[ReviewQueueItem, ...]: ...

    def review(
        self,
        submission_id: UUID,
        expected_revision: int,
        target_state: ReviewState,
        reviewer_reference_sha256: str,
        reason_code: str,
    ) -> ReviewResult: ...

    def retract(
        self,
        accepted_observation_id: UUID,
        reviewer_reference_sha256: str,
        reason_code: RetractionReason,
    ) -> RetractionResult: ...


def _uuid(value: object, *, field: str, nullable: bool = False) -> UUID | None:
    if value is None and nullable:
        return None
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        parsed = UUID(value)
        if value == str(parsed):
            return parsed
    raise RuntimeError(f"database returned invalid {field}")


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"database returned invalid {field}")
    return value


def _state(value: object) -> ReviewState:
    if not isinstance(value, str):
        raise RuntimeError("database returned invalid state")
    return ReviewState(value)


def _datetime(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError(f"database returned invalid {field}")
    return value


def _text(value: object, *, field: str, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise RuntimeError(f"database returned invalid {field}")
    return value


def _boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimeError(f"database returned invalid {field}")
    return value


def _submission_result(row: Mapping[str, Any]) -> SubmissionResult:
    submission_id = _uuid(row.get("submission_id"), field="submission_id")
    assert submission_id is not None
    return SubmissionResult(
        submission_id=submission_id,
        revision=_integer(row.get("revision"), field="revision"),
        state=_state(row.get("state")),
    )


def _review_result(row: Mapping[str, Any]) -> ReviewResult:
    submission_id = _uuid(row.get("submission_id"), field="submission_id")
    assert submission_id is not None
    return ReviewResult(
        submission_id=submission_id,
        revision=_integer(row.get("revision"), field="revision"),
        state=_state(row.get("state")),
        accepted_observation_id=_uuid(
            row.get("accepted_observation_id"),
            field="accepted_observation_id",
            nullable=True,
        ),
    )


def _retraction_result(row: Mapping[str, Any]) -> RetractionResult:
    observation_id = _uuid(row.get("accepted_observation_id"), field="accepted_observation_id")
    assert observation_id is not None
    raw_reason = row.get("reason_code")
    if not isinstance(raw_reason, str):
        raise RuntimeError("database returned invalid reason_code")
    return RetractionResult(
        accepted_observation_id=observation_id,
        reason_code=RetractionReason(raw_reason),
        retracted_at=_datetime(row.get("retracted_at"), field="retracted_at"),
    )


def _review_queue_item(row: Mapping[str, Any]) -> ReviewQueueItem:
    submission_id = _uuid(row.get("submission_id"), field="submission_id")
    assert submission_id is not None
    country_code = _text(row.get("country_code"), field="country_code")
    assert country_code is not None
    try:
        country_name = CANONICAL_COUNTRY_NAMES[country_code]
    except KeyError as error:
        raise RuntimeError("database returned invalid country_code") from error
    return ReviewQueueItem(
        submission_id=submission_id,
        revision=_integer(row.get("revision"), field="revision"),
        state=_state(row.get("state")),
        discovery_platform=_text(
            row.get("discovery_platform"), field="discovery_platform", nullable=True
        ),
        country_code=country_code,
        country_name=country_name,
        geography_basis=str(_text(row.get("geography_basis"), field="geography_basis")),
        geography_confidence=str(
            _text(row.get("geography_confidence"), field="geography_confidence")
        ),
        language=str(_text(row.get("language"), field="language")),
        tcgdex_set_id=str(_text(row.get("tcgdex_set_id"), field="tcgdex_set_id")),
        product_scope=str(_text(row.get("product_scope"), field="product_scope")),
        observed_at=_datetime(row.get("observed_at"), field="observed_at"),
        pack_count=_integer(row.get("pack_count"), field="pack_count"),
        qualifying_hit_pack_count=_integer(
            row.get("qualifying_hit_pack_count"), field="qualifying_hit_pack_count"
        ),
        denominator_complete=_boolean(
            row.get("denominator_complete"), field="denominator_complete"
        ),
        statistics_eligible_requested=_boolean(
            row.get("statistics_eligible_requested"), field="statistics_eligible_requested"
        ),
        created_at=_datetime(row.get("created_at"), field="created_at"),
        updated_at=_datetime(row.get("updated_at"), field="updated_at"),
        expires_at=_datetime(row.get("expires_at"), field="expires_at"),
    )


class PostgresAuthorizedOpeningRepository:
    """Short-lived connections; each command is one explicit transaction."""

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    @classmethod
    def from_dsn(cls, dsn: str) -> PostgresAuthorizedOpeningRepository:
        def connect() -> Any:
            import psycopg

            return psycopg.connect(dsn)

        return cls(connect)

    def submit_many(
        self, submissions: Sequence[AuthorizedOpeningSubmission]
    ) -> tuple[SubmissionResult, ...]:
        if not submissions:
            raise ValueError("at least one submission is required")
        from psycopg.rows import dict_row

        results: list[SubmissionResult] = []
        with self._connection_factory() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    for submission in submissions:
                        cursor.execute(
                            _SUBMIT_SQL,
                            {
                                "payload": json.dumps(
                                    submission.as_payload(),
                                    sort_keys=True,
                                    separators=(",", ":"),
                                )
                            },
                        )
                        rows = tuple(cursor.fetchall())
                        if len(rows) != 1:
                            raise RuntimeError(
                                "authorized opening submit returned invalid row count"
                            )
                        results.append(_submission_result(rows[0]))
        return tuple(results)

    def list_reviews(self, state: str, limit: int) -> tuple[ReviewQueueItem, ...]:
        from psycopg.rows import dict_row

        with self._connection_factory() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(_LIST_SQL, {"state": state, "limit": limit})
                    rows = tuple(cursor.fetchall())
        return tuple(_review_queue_item(row) for row in rows)

    def review(
        self,
        submission_id: UUID,
        expected_revision: int,
        target_state: ReviewState,
        reviewer_reference_sha256: str,
        reason_code: str,
    ) -> ReviewResult:
        from psycopg.rows import dict_row

        with self._connection_factory() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        _REVIEW_SQL,
                        {
                            "submission_id": submission_id,
                            "expected_revision": expected_revision,
                            "target_state": target_state.value,
                            "reviewer_reference_sha256": reviewer_reference_sha256,
                            "reason_code": reason_code,
                        },
                    )
                    rows = tuple(cursor.fetchall())
                    if len(rows) != 1:
                        raise RuntimeError("authorized opening review returned invalid row count")
        return _review_result(rows[0])

    def retract(
        self,
        accepted_observation_id: UUID,
        reviewer_reference_sha256: str,
        reason_code: RetractionReason,
    ) -> RetractionResult:
        from psycopg.rows import dict_row

        with self._connection_factory() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        _RETRACT_SQL,
                        {
                            "accepted_observation_id": accepted_observation_id,
                            "reviewer_reference_sha256": reviewer_reference_sha256,
                            "reason_code": reason_code.value,
                        },
                    )
                    rows = tuple(cursor.fetchall())
                    if len(rows) != 1:
                        raise RuntimeError("authorized opening retract returned invalid row count")
        return _retraction_result(rows[0])
