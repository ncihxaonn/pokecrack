from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from pokecrack_worker import cli
from pokecrack_worker.authorized_openings import (
    AuthorizedOpeningBundleError,
    AuthorizedOpeningSubmission,
    PostgresAuthorizedOpeningRepository,
    RetractionReason,
    RetractionResult,
    ReviewQueueItem,
    ReviewResult,
    ReviewState,
    SubmissionResult,
    load_authorized_opening_bundle,
    reviewer_reference_hmac,
)
from pokecrack_worker.authorized_openings.iso_codes import ISO_ALPHA2_CODES
from pokecrack_worker.authorized_openings.repository import _LIST_SQL
from pokecrack_worker.cli import app

runner = CliRunner()
NOW = datetime(2026, 8, 31, 4, 0, tzinfo=UTC)
SUBMISSION_ID = UUID("11111111-1111-4111-8111-111111111111")
OBSERVATION_ID = UUID("22222222-2222-4222-8222-222222222222")


def _payload(
    *,
    key: str = "opening.jp.001",
    country_code: str = "JP",
    country_name: str = "Japan",
    language: str = "ja",
    platform: str | None = "bluesky",
    candidate: str | None = "a" * 64,
    statistics_eligible: bool = True,
) -> dict[str, object]:
    return {
        "schemaVersion": "1.0.0",
        "submissionKey": key,
        "discoveryPlatform": platform,
        "discoveryCandidateSha256": candidate,
        "sourceIdentitySha256": "b" * 64,
        "authorizationReferenceSha256": "c" * 64,
        "evidenceSha256": "d" * 64,
        "provenanceDedupeSha256": "e" * 64,
        "countryCode": country_code,
        "countryName": country_name,
        "geographyBasis": "opening_location",
        "geographyConfidence": "tier_a",
        "language": language,
        "tcgdexSetId": "sv8a",
        "productScope": "booster_box",
        "observedAt": "2026-08-30T03:02:01Z",
        "packCount": 36,
        "qualifyingHitPackCount": 1,
        "denominatorComplete": True,
        "statisticsEligible": statistics_eligible,
    }


def _write_bundle(path: Path, *payloads: dict[str, object]) -> None:
    path.write_text(
        "".join(json.dumps(payload, ensure_ascii=False) + "\n" for payload in payloads),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("country_code", "country_name", "language"),
    (
        ("JP", "Japan", "ja"),
        ("KR", "South Korea", "ko"),
        ("BR", "Brazil", "pt-BR"),
        ("CN", "China", "zh-Hans-CN"),
        ("SG", "Singapore", "en"),
        ("PH", "Philippines", "fil"),
    ),
)
def test_submission_accepts_global_iso_and_canonical_bcp47_values(
    country_code: str, country_name: str, language: str
) -> None:
    submission = AuthorizedOpeningSubmission.model_validate(
        _payload(country_code=country_code, country_name=country_name, language=language)
    )

    assert submission.country_code == country_code
    assert submission.language == language
    assert set(submission.as_payload()) == set(_payload())


def test_worker_iso_allowlist_matches_the_reviewed_249_code_catalog() -> None:
    assert len(ISO_ALPHA2_CODES) == 249
    assert {"AU", "BR", "CN", "GB", "JP", "KR", "SG", "US"} < ISO_ALPHA2_CODES
    assert {"UK", "ZZ"}.isdisjoint(ISO_ALPHA2_CODES)


def test_country_name_must_match_its_iso_code_not_an_identity_or_free_text() -> None:
    with pytest.raises(ValidationError):
        AuthorizedOpeningSubmission.model_validate(
            _payload(country_code="JP", country_name="Alice")
        )
    with pytest.raises(ValidationError):
        AuthorizedOpeningSubmission.model_validate(
            _payload(country_code="US", country_name="Japan")
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("schemaVersion", "1"),
        ("countryCode", "ZZ"),
        ("countryCode", "UK"),
        ("countryName", "https://identity.example/secret-handle"),
        ("countryName", "Ｊａｐａｎ"),
        ("countryName", "Japan\n"),
        ("language", "pt-br"),
        ("language", "EN"),
        ("tcgdexSetId", "bad/set"),
        ("observedAt", "2026-08-30T03:02:01+00:00"),
        ("packCount", True),
        ("packCount", "36"),
        ("denominatorComplete", False),
        ("sourceIdentitySha256", "A" * 64),
    ),
)
def test_submission_rejects_malformed_or_noncanonical_values(field: str, value: object) -> None:
    payload = _payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        AuthorizedOpeningSubmission.model_validate(payload)


@pytest.mark.parametrize("raw_field", ("sourceUrl", "text", "handle", "author", "rawPayload"))
def test_submission_forbids_raw_or_extra_fields(raw_field: str) -> None:
    payload = _payload()
    payload[raw_field] = "https://identity.example/secret-handle"

    with pytest.raises(ValidationError):
        AuthorizedOpeningSubmission.model_validate(payload)


def test_submission_requires_candidate_platform_coupling_and_ordered_counts() -> None:
    with pytest.raises(ValidationError):
        AuthorizedOpeningSubmission.model_validate(_payload(platform="direct", candidate="a" * 64))
    payload = _payload()
    payload["qualifyingHitPackCount"] = 37
    with pytest.raises(ValidationError):
        AuthorizedOpeningSubmission.model_validate(payload)


def test_bundle_load_is_bounded_exact_and_rejects_conflicts_without_values(tmp_path: Path) -> None:
    valid = tmp_path / "valid.jsonl"
    _write_bundle(valid, _payload())
    assert len(load_authorized_opening_bundle(valid)) == 1

    duplicate = tmp_path / "duplicate.jsonl"
    first = _payload()
    second = _payload(key="opening.jp.002")
    _write_bundle(duplicate, first, second)
    with pytest.raises(AuthorizedOpeningBundleError) as duplicate_error:
        load_authorized_opening_bundle(duplicate)
    assert duplicate_error.value.code == "duplicate_provenance"
    assert "e" * 64 not in str(duplicate_error.value)

    duplicate_key = tmp_path / "duplicate-key.jsonl"
    duplicate_key.write_text(
        '{"schemaVersion":"1.0.0","schemaVersion":"secret"}\n', encoding="utf-8"
    )
    with pytest.raises(AuthorizedOpeningBundleError) as key_error:
        load_authorized_opening_bundle(duplicate_key)
    assert key_error.value.code == "duplicate_json_key"
    assert "secret" not in str(key_error.value)


def test_bundle_rejects_empty_non_utf8_and_row_caps(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(AuthorizedOpeningBundleError, match="empty_bundle"):
        load_authorized_opening_bundle(empty)

    non_utf8 = tmp_path / "non-utf8.jsonl"
    non_utf8.write_bytes(b"\xff\n")
    with pytest.raises(AuthorizedOpeningBundleError, match="invalid_utf8"):
        load_authorized_opening_bundle(non_utf8)

    too_many = tmp_path / "too-many.jsonl"
    _write_bundle(too_many, _payload(), _payload(key="opening.jp.002"))
    with pytest.raises(AuthorizedOpeningBundleError, match="too_many_rows"):
        load_authorized_opening_bundle(too_many, max_rows=1)


def test_reviewer_reference_is_domain_separated_hmac_and_validates_actor() -> None:
    key = "owner-held-review-key-32-bytes-minimum"
    actor = "reviewer-01"
    reference = reviewer_reference_hmac(actor, key)

    assert len(reference) == 64
    assert reference != hashlib.sha256(actor.encode()).hexdigest()
    assert reference == reviewer_reference_hmac(actor, key)
    with pytest.raises(ValueError):
        reviewer_reference_hmac("reviewer\n01", key)
    with pytest.raises(ValueError):
        reviewer_reference_hmac(actor, "short")


class _Context:
    def __init__(self, enter_value: object) -> None:
        self.enter_value = enter_value
        self.entered = 0

    def __enter__(self) -> object:
        self.entered += 1
        return self.enter_value

    def __exit__(self, *_args: object) -> None:
        return None


class _Cursor:
    def __init__(self, row_batches: list[list[dict[str, object]]]) -> None:
        self.row_batches = row_batches
        self.executions: list[tuple[str, dict[str, object]]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, params: dict[str, object]) -> None:
        self.executions.append((sql, params))

    def fetchall(self) -> list[dict[str, object]]:
        return self.row_batches.pop(0)


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self.cursor_value = cursor
        self.transaction_context = _Context(self)

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def transaction(self) -> _Context:
        return self.transaction_context

    def cursor(self, **_kwargs: object) -> _Cursor:
        return self.cursor_value


def test_postgres_submit_uses_one_explicit_transaction_and_parameterized_json() -> None:
    cursor = _Cursor([[{"submission_id": SUBMISSION_ID, "revision": 1, "state": "queued"}]])
    connection = _Connection(cursor)
    repository = PostgresAuthorizedOpeningRepository(lambda: connection)
    submission = AuthorizedOpeningSubmission.model_validate(_payload())

    results = repository.submit_many((submission,))

    assert results == (SubmissionResult(SUBMISSION_ID, 1, ReviewState.QUEUED),)
    assert connection.transaction_context.entered == 1
    sql, params = cursor.executions[0]
    assert "submit_authorized_opening_v1(%(payload)s::jsonb)" in sql
    assert "a" * 64 not in sql
    assert json.loads(str(params["payload"])) == _payload()


def test_postgres_list_query_never_selects_private_or_free_text_identity_fields() -> None:
    lowered = _LIST_SQL.casefold()
    for forbidden in (
        "submission_key",
        "discovery_candidate_sha256",
        "source_identity_sha256",
        "authorization_reference_sha256",
        "evidence_sha256",
        "provenance_dedupe_sha256",
        "country_name",
    ):
        assert forbidden not in lowered


def test_postgres_list_derives_canonical_country_name_from_reviewed_code() -> None:
    row = {
        "submission_id": SUBMISSION_ID,
        "revision": 1,
        "state": "queued",
        "discovery_platform": "bluesky",
        "country_code": "JP",
        "geography_basis": "opening_location",
        "geography_confidence": "tier_a",
        "language": "ja",
        "tcgdex_set_id": "sv8a",
        "product_scope": "booster_box",
        "observed_at": NOW,
        "pack_count": 36,
        "qualifying_hit_pack_count": 1,
        "denominator_complete": True,
        "statistics_eligible_requested": True,
        "created_at": NOW,
        "updated_at": NOW,
        "expires_at": NOW + timedelta(days=30),
    }
    cursor = _Cursor([[row]])
    repository = PostgresAuthorizedOpeningRepository(lambda: _Connection(cursor))

    items = repository.list_reviews("queued", 50)

    assert len(items) == 1
    assert items[0].country_name == "Japan"


def test_postgres_review_and_retract_use_exact_parameterized_rpcs_and_transactions() -> None:
    review_cursor = _Cursor(
        [
            [
                {
                    "submission_id": SUBMISSION_ID,
                    "revision": 2,
                    "state": "accepted_statistics",
                    "accepted_observation_id": OBSERVATION_ID,
                }
            ]
        ]
    )
    review_connection = _Connection(review_cursor)
    review_repository = PostgresAuthorizedOpeningRepository(lambda: review_connection)
    reviewer_reference = "f" * 64

    reviewed = review_repository.review(
        SUBMISSION_ID,
        1,
        ReviewState.ACCEPTED_STATISTICS,
        reviewer_reference,
        "evidence_verified",
    )

    assert reviewed.accepted_observation_id == OBSERVATION_ID
    assert review_connection.transaction_context.entered == 1
    review_sql, review_params = review_cursor.executions[0]
    assert "review_authorized_opening_v1" in review_sql
    assert reviewer_reference not in review_sql
    assert review_params == {
        "submission_id": SUBMISSION_ID,
        "expected_revision": 1,
        "target_state": "accepted_statistics",
        "reviewer_reference_sha256": reviewer_reference,
        "reason_code": "evidence_verified",
    }

    retract_cursor = _Cursor(
        [
            [
                {
                    "accepted_observation_id": OBSERVATION_ID,
                    "reason_code": "privacy_request",
                    "retracted_at": NOW,
                }
            ]
        ]
    )
    retract_connection = _Connection(retract_cursor)
    retract_repository = PostgresAuthorizedOpeningRepository(lambda: retract_connection)

    retracted = retract_repository.retract(
        OBSERVATION_ID,
        reviewer_reference,
        RetractionReason.PRIVACY_REQUEST,
    )

    assert retracted.accepted_observation_id == OBSERVATION_ID
    assert retract_connection.transaction_context.entered == 1
    retract_sql, retract_params = retract_cursor.executions[0]
    assert "retract_authorized_opening_v1" in retract_sql
    assert reviewer_reference not in retract_sql
    assert retract_params == {
        "accepted_observation_id": OBSERVATION_ID,
        "reviewer_reference_sha256": reviewer_reference,
        "reason_code": "privacy_request",
    }


def _queue_item() -> ReviewQueueItem:
    return ReviewQueueItem(
        submission_id=SUBMISSION_ID,
        revision=1,
        state=ReviewState.QUEUED,
        discovery_platform="bluesky",
        country_code="JP",
        country_name="Japan",
        geography_basis="opening_location",
        geography_confidence="tier_a",
        language="ja",
        tcgdex_set_id="sv8a",
        product_scope="booster_box",
        observed_at=NOW,
        pack_count=36,
        qualifying_hit_pack_count=1,
        denominator_complete=True,
        statistics_eligible_requested=True,
        created_at=NOW,
        updated_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )


class _Repository:
    def __init__(self) -> None:
        self.submissions: Any = None
        self.list_args: Any = None
        self.review_args: Any = None
        self.retract_args: Any = None
        self.failure: Exception | None = None

    def submit_many(self, submissions: object) -> tuple[SubmissionResult, ...]:
        if self.failure is not None:
            raise self.failure
        self.submissions = submissions
        return (SubmissionResult(SUBMISSION_ID, 1, ReviewState.QUEUED),)

    def list_reviews(self, state: str, limit: int) -> tuple[ReviewQueueItem, ...]:
        if self.failure is not None:
            raise self.failure
        self.list_args = (state, limit)
        return (_queue_item(),)

    def review(
        self,
        submission_id: UUID,
        expected_revision: int,
        target_state: ReviewState,
        reviewer_reference_sha256: str,
        reason_code: str,
    ) -> ReviewResult:
        if self.failure is not None:
            raise self.failure
        self.review_args = (
            submission_id,
            expected_revision,
            target_state,
            reviewer_reference_sha256,
            reason_code,
        )
        return ReviewResult(SUBMISSION_ID, 2, target_state, OBSERVATION_ID)

    def retract(
        self,
        accepted_observation_id: UUID,
        reviewer_reference_sha256: str,
        reason_code: RetractionReason,
    ) -> RetractionResult:
        if self.failure is not None:
            raise self.failure
        self.retract_args = (
            accepted_observation_id,
            reviewer_reference_sha256,
            reason_code,
        )
        return RetractionResult(
            accepted_observation_id,
            reason_code,
            NOW,
        )


def _submit_env() -> dict[str, str]:
    return {
        "DATA_MODE": "live",
        "SUPABASE_DB_URL": "postgresql://submit-secret@submit.invalid/db",
    }


def _review_env() -> dict[str, str]:
    return {
        "DATA_MODE": "live",
        "AUTHORIZED_OPENING_REVIEW_DB_URL": "postgresql://review-secret@review.invalid/db",
        "AUTHORIZED_OPENING_REVIEW_HMAC_KEY": "owner-held-review-key-32-bytes-minimum",
    }


def test_submit_dry_run_is_offline_counts_only_and_redacts_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "private-name.jsonl"
    _write_bundle(bundle, _payload())

    result = runner.invoke(app, ["authorized-opening", "submit", str(bundle), "--dry-run"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload == {
        "counts": {
            "activityOnlyRequested": 0,
            "statisticsEligibleRequested": 1,
            "validated": 1,
        },
        "dryRun": True,
        "event": "authorized_opening_submit",
        "mutated": False,
    }
    assert "private-name" not in result.output
    assert "a" * 64 not in result.output
    assert "Japan" not in result.output


@pytest.mark.parametrize(
    "args",
    (
        ["authorized-opening", "--help"],
        ["authorized-opening", "submit", "--help"],
        ["authorized-opening", "list", "--help"],
        ["authorized-opening", "review", "--help"],
        ["authorized-opening", "retract", "--help"],
    ),
)
def test_authorized_opening_commands_have_help(args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output


def test_invalid_submit_never_echoes_raw_extra_field_or_value(tmp_path: Path) -> None:
    bundle = tmp_path / "invalid.jsonl"
    payload = _payload()
    payload["sourceUrl"] = "https://identity.example/secret-handle"
    _write_bundle(bundle, payload)

    result = runner.invoke(app, ["authorized-opening", "submit", str(bundle), "--dry-run"])

    assert result.exit_code == 2
    assert json.loads(result.output)["code"] == "invalid_row"
    for forbidden in ("sourceUrl", "identity.example", "secret-handle", "a" * 64):
        assert forbidden not in result.output


def test_live_submit_uses_submit_dsn_and_outputs_only_ids_states_and_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle.jsonl"
    _write_bundle(bundle, _payload())
    repository = _Repository()
    dsns: list[str] = []

    def repository_factory(dsn: str) -> _Repository:
        dsns.append(dsn)
        return repository

    monkeypatch.setattr(cli, "_operator_repository", repository_factory)
    result = runner.invoke(app, ["authorized-opening", "submit", str(bundle)], env=_submit_env())

    assert result.exit_code == 0, result.output
    assert dsns == ["postgresql://submit-secret@submit.invalid/db"]
    assert json.loads(result.stdout)["results"] == [
        {"revision": 1, "state": "queued", "submissionId": str(SUBMISSION_ID)}
    ]
    for forbidden in ("submit-secret", "review-secret", "Japan", "a" * 64):
        assert forbidden not in result.output


def test_live_list_requires_reviewer_dsn_and_redacts_all_fingerprints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _Repository()
    dsns: list[str] = []

    def repository_factory(dsn: str) -> _Repository:
        dsns.append(dsn)
        return repository

    monkeypatch.setattr(cli, "_operator_repository", repository_factory)
    result = runner.invoke(
        app,
        ["authorized-opening", "list", "--state", "all", "--limit", "10"],
        env=_review_env(),
    )

    assert result.exit_code == 0, result.output
    assert dsns == ["postgresql://review-secret@review.invalid/db"]
    assert repository.list_args == ("all", 10)
    payload = json.loads(result.stdout)
    assert payload["count"] == 1
    assert payload["items"][0]["countryCode"] == "JP"
    for forbidden in (
        "submissionKey",
        "Sha256",
        "submit-secret",
        "review-secret",
        "a" * 64,
        "b" * 64,
    ):
        assert forbidden not in result.output


def test_live_review_hmacs_actor_and_never_outputs_actor_key_digest_or_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _Repository()
    monkeypatch.setattr(cli, "_operator_repository", lambda *_args, **_kwargs: repository)
    result = runner.invoke(
        app,
        [
            "authorized-opening",
            "review",
            str(SUBMISSION_ID),
            "--expected-revision",
            "1",
            "--decision",
            "accepted_statistics",
            "--actor",
            "reviewer-01",
            "--reason",
            "evidence_verified",
        ],
        env=_review_env(),
    )

    assert result.exit_code == 0, result.output
    assert repository.review_args is not None
    reference = repository.review_args[3]
    assert isinstance(reference, str) and len(reference) == 64
    payload = json.loads(result.stdout)
    assert payload["state"] == "accepted_statistics"
    for forbidden in (
        "reviewer-01",
        "owner-held-review-key",
        reference,
        "evidence_verified",
        "review-secret",
    ):
        assert forbidden not in result.output


def test_review_dry_run_validates_transition_without_database_or_sensitive_output() -> None:
    result = runner.invoke(
        app,
        [
            "authorized-opening",
            "review",
            str(SUBMISSION_ID),
            "--expected-revision",
            "1",
            "--decision",
            "rejected",
            "--actor",
            "reviewer-01",
            "--reason",
            "reviewer_rejected",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["counts"] == {"validated": 1}
    for forbidden in (str(SUBMISSION_ID), "reviewer-01", "reviewer_rejected"):
        assert forbidden not in result.output


def test_live_retract_uses_reviewer_hmac_and_outputs_only_observation_and_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _Repository()
    monkeypatch.setattr(cli, "_operator_repository", lambda _dsn: repository)
    result = runner.invoke(
        app,
        [
            "authorized-opening",
            "retract",
            str(OBSERVATION_ID),
            "--actor",
            "reviewer-01",
            "--reason",
            "privacy_request",
        ],
        env=_review_env(),
    )

    assert result.exit_code == 0, result.output
    assert repository.retract_args is not None
    reference = repository.retract_args[1]
    assert isinstance(reference, str) and len(reference) == 64
    assert json.loads(result.stdout) == {
        "observationId": str(OBSERVATION_ID),
        "status": "retracted",
    }
    for forbidden in ("reviewer-01", "privacy_request", reference, "review-secret"):
        assert forbidden not in result.output


def test_retract_dry_run_is_counts_only_and_rejects_unknown_reason() -> None:
    valid = runner.invoke(
        app,
        [
            "authorized-opening",
            "retract",
            str(OBSERVATION_ID),
            "--actor",
            "reviewer-01",
            "--reason",
            "authorization_revoked",
            "--dry-run",
        ],
    )
    assert valid.exit_code == 0, valid.output
    assert json.loads(valid.stdout)["counts"] == {"validated": 1}
    for forbidden in (str(OBSERVATION_ID), "reviewer-01", "authorization_revoked"):
        assert forbidden not in valid.output

    invalid = runner.invoke(
        app,
        [
            "authorized-opening",
            "retract",
            str(OBSERVATION_ID),
            "--actor",
            "reviewer-01",
            "--reason",
            "delete_everything",
            "--dry-run",
        ],
    )
    assert invalid.exit_code == 2
    assert json.loads(invalid.output) == {"error": "invalid_retraction_request"}


def test_review_rejects_mismatched_reason_and_missing_reviewer_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mismatched = runner.invoke(
        app,
        [
            "authorized-opening",
            "review",
            str(SUBMISSION_ID),
            "--expected-revision",
            "1",
            "--decision",
            "duplicate",
            "--actor",
            "reviewer-01",
            "--reason",
            "evidence_verified",
            "--dry-run",
        ],
    )
    assert mismatched.exit_code == 2
    assert json.loads(mismatched.output) == {"error": "invalid_review_request"}

    monkeypatch.setattr(cli, "_operator_repository", lambda *_args, **_kwargs: _Repository())
    env = _review_env()
    env.pop("AUTHORIZED_OPENING_REVIEW_HMAC_KEY")
    missing = runner.invoke(
        app,
        [
            "authorized-opening",
            "review",
            str(SUBMISSION_ID),
            "--expected-revision",
            "1",
            "--decision",
            "in_review",
            "--actor",
            "reviewer-01",
            "--reason",
            "review_started",
        ],
        env=env,
    )
    assert missing.exit_code == 78
    assert json.loads(missing.output)["error"] == "reviewer_hmac_unavailable"


def test_database_errors_are_sanitized_for_submit_list_and_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle.jsonl"
    _write_bundle(bundle, _payload())
    repository = _Repository()
    repository.failure = RuntimeError(
        "postgresql://user:database-secret@db.invalid/ plus " + "a" * 64
    )
    monkeypatch.setattr(cli, "_operator_repository", lambda *_args, **_kwargs: repository)

    commands = (
        ["authorized-opening", "submit", str(bundle)],
        ["authorized-opening", "list"],
        [
            "authorized-opening",
            "review",
            str(SUBMISSION_ID),
            "--expected-revision",
            "1",
            "--decision",
            "in_review",
            "--actor",
            "reviewer-01",
            "--reason",
            "review_started",
        ],
        [
            "authorized-opening",
            "retract",
            str(OBSERVATION_ID),
            "--actor",
            "reviewer-01",
            "--reason",
            "privacy_request",
        ],
    )
    for index, command in enumerate(commands):
        result = runner.invoke(
            app,
            command,
            env=_submit_env() if index == 0 else _review_env(),
        )
        assert result.exit_code == 1
        assert json.loads(result.output)["error"] == "database_unavailable"
        for forbidden in ("database-secret", "db.invalid", "a" * 64, "Traceback"):
            assert forbidden not in result.output


def test_submit_and_reviewer_credentials_are_not_cross_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle.jsonl"
    _write_bundle(bundle, _payload())
    monkeypatch.setattr(cli, "_operator_repository", lambda _dsn: _Repository())

    submit = runner.invoke(
        app,
        ["authorized-opening", "submit", str(bundle)],
        env=_submit_env(),
    )
    review_list = runner.invoke(app, ["authorized-opening", "list"], env=_review_env())
    assert submit.exit_code == 0, submit.output
    assert review_list.exit_code == 0, review_list.output

    submit_with_reviewer_only = runner.invoke(
        app,
        ["authorized-opening", "submit", str(bundle)],
        env={**_review_env(), "SUPABASE_DB_URL": ""},
    )
    list_with_submit_only = runner.invoke(
        app,
        ["authorized-opening", "list"],
        env={**_submit_env(), "AUTHORIZED_OPENING_REVIEW_DB_URL": ""},
    )
    assert json.loads(submit_with_reviewer_only.output)["error"] == "submit_database_unavailable"
    assert json.loads(list_with_submit_only.output)["error"] == "review_database_unavailable"
