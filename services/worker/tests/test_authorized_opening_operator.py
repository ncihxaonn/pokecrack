from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

import pytest
from typer.testing import CliRunner

from pokecrack_worker.authorized_opening_operator import (
    AuthorizedOpeningEnvelope,
    AuthorizedOpeningOperatorError,
    AuthorizedOpeningRpcClient,
    RetractionResult,
    ReviewQueueItem,
    ReviewResult,
    SubmissionResult,
    _fixed_role_dsn,
    _load_envelope_json,
    read_authorized_opening_envelope,
    safe_retraction_payload,
    safe_review_queue_payload,
    safe_submission_payload,
    validate_review_list_request,
    validate_review_request,
    validate_reviewer_reference,
)
from pokecrack_worker.cli import app

runner = CliRunner()
HASHES = {
    "sourceIdentitySha256": "a" * 64,
    "authorizationReferenceSha256": "b" * 64,
    "evidenceSha256": "c" * 64,
    "provenanceDedupeSha256": "d" * 64,
}


def envelope_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schemaVersion": "1.0.0",
        "submissionKey": "operator-test-1",
        "discoveryPlatform": "direct",
        "discoveryCandidateSha256": None,
        **HASHES,
        "countryCode": "AU",
        "countryName": "Australia",
        "geographyBasis": "opening_location",
        "geographyConfidence": "tier_a",
        "language": "en",
        "tcgdexSetId": "sv01",
        "productScope": "all",
        "observedAt": "2026-08-30T00:00:00Z",
        "packCount": 36,
        "qualifyingHitPackCount": 2,
        "denominatorComplete": True,
        "statisticsEligible": True,
    }
    payload.update(overrides)
    return payload


def write_private_envelope(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "opening-envelope.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


def test_exact_owner_envelope_validates_and_is_read_only(tmp_path: Path) -> None:
    path = write_private_envelope(tmp_path, envelope_payload())

    envelope = read_authorized_opening_envelope(path)

    assert isinstance(envelope, AuthorizedOpeningEnvelope)
    assert envelope.discovery_platform == "direct"
    assert path.stat().st_size > 0
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "overrides, expected_code",
    [
        ({"unexpected": "url or social id"}, "invalid_envelope"),
        ({"sourceUrl": "https://example.invalid/raw"}, "invalid_envelope"),
        ({"submissionKey": "https://example.invalid/opening"}, "invalid_envelope"),
        ({"submissionKey": "mailto:owner@example.invalid"}, "invalid_envelope"),
        ({"submissionKey": "a:opaque-uri"}, "invalid_envelope"),
        ({"submissionKey": "h%74tps%3A%2F%2Fexample.invalid/opening"}, "invalid_envelope"),
        ({"submissionKey": "https%253A%252F%252Fexample.invalid/opening"}, "invalid_envelope"),
        ({"countryName": "https://example.invalid/country"}, "invalid_envelope"),
        ({"countryName": "urn:pokecrack:country"}, "invalid_envelope"),
        ({"language": "https://example.invalid/lang"}, "invalid_envelope"),
        ({"tcgdexSetId": "urn:pokecrack:set"}, "invalid_envelope"),
        ({"observedAt": "https://example.invalid/time"}, "invalid_envelope"),
        ({"discoveryPlatform": "bluesky"}, "social_derived_rejected"),
        (
            {"discoveryPlatform": "youtube", "discoveryCandidateSha256": "e" * 64},
            "social_derived_rejected",
        ),
        ({"discoveryCandidateSha256": "e" * 64}, "social_derived_rejected"),
        ({"denominatorComplete": False}, "invalid_envelope"),
        ({"packCount": 0}, "invalid_envelope"),
        ({"qualifyingHitPackCount": 37}, "invalid_envelope"),
        ({"countryCode": "us"}, "invalid_envelope"),
        ({"evidenceSha256": "not-a-hash"}, "invalid_envelope"),
    ],
)
def test_malformed_unauthorized_and_social_payloads_fail_closed(
    overrides: dict[str, object], expected_code: str
) -> None:
    with pytest.raises(AuthorizedOpeningOperatorError) as error:
        _load_envelope_json(json.dumps(envelope_payload(**overrides)).encode("utf-8"))

    assert error.value.code == expected_code
    assert "url or social id" not in error.value.safe_message
    assert "https://" not in error.value.safe_message
    assert "not-a-hash" not in error.value.safe_message


def test_duplicate_json_keys_fail_closed() -> None:
    raw = json.dumps(envelope_payload()).replace(
        '"submissionKey": "operator-test-1"',
        '"submissionKey": "operator-test-1", "submissionKey": "operator-test-2"',
    )

    with pytest.raises(AuthorizedOpeningOperatorError) as error:
        _load_envelope_json(raw.encode("utf-8"))

    assert error.value.code == "invalid_envelope"


def test_non_0600_file_and_symlink_are_rejected(tmp_path: Path) -> None:
    source = write_private_envelope(tmp_path, envelope_payload())
    source.chmod(0o640)
    with pytest.raises(AuthorizedOpeningOperatorError) as mode_error:
        read_authorized_opening_envelope(source)
    assert mode_error.value.code == "private_input_required"

    source.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(source)
    with pytest.raises(AuthorizedOpeningOperatorError) as link_error:
        read_authorized_opening_envelope(link)
    assert link_error.value.code == "private_input_required"


def test_non_regular_fifo_is_rejected_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "opening-envelope.fifo"
    os.mkfifo(fifo, 0o600)

    with pytest.raises(AuthorizedOpeningOperatorError) as error:
        read_authorized_opening_envelope(fifo)

    assert error.value.code == "private_input_required"


def test_envelope_size_is_bounded() -> None:
    oversized = envelope_payload(countryName="A" * 160)
    raw = json.dumps(oversized).encode("utf-8") + b" " * 16_384

    with pytest.raises(AuthorizedOpeningOperatorError) as error:
        _load_envelope_json(raw)

    assert error.value.code == "invalid_envelope"


@pytest.mark.parametrize(
    "dsn, expected",
    [
        (
            "postgresql://pokecrack_authorized_opening_submitter_login:secret@db.example/pokecrack?sslmode=require&options=-c%20role%3Dpokecrack_authorized_opening_submitter",
            "postgresql://pokecrack_authorized_opening_submitter_login:secret@db.example/pokecrack?sslmode=require&options=-c%20role%3Dpokecrack_authorized_opening_submitter",
        ),
    ],
)
def test_submitter_dsn_is_fixed_to_the_dedicated_role(dsn: str, expected: str) -> None:
    assert (
        _fixed_role_dsn(
            dsn,
            environment_name="AUTHORIZED_OPENING_SUBMITTER_DB_URL",
            expected_login="pokecrack_authorized_opening_submitter_login",
            expected_role="pokecrack_authorized_opening_submitter",
        )
        == expected
    )


def test_reviewer_dsn_accepts_only_a_canonical_existing_login_name() -> None:
    dsn = (
        "postgresql://owner_review_login:secret@db.example/pokecrack?"
        "sslmode=verify-full&options=-c%20role%3Dpokecrack_authorized_opening_reviewer"
    )
    assert (
        _fixed_role_dsn(
            dsn,
            environment_name="AUTHORIZED_OPENING_REVIEWER_DB_URL",
            expected_login=None,
            expected_role="pokecrack_authorized_opening_reviewer",
        )
        == dsn
    )


@pytest.mark.parametrize(
    "username",
    [
        "",
        "postgres",
        "service_role",
        "pokecrack_authorized_opening_reviewer",
        "reviewer-login",
        "reviewer%20login",
    ],
)
def test_reviewer_dsn_rejects_unreviewed_login_names(username: str) -> None:
    dsn = (
        f"postgresql://{username}:secret@db.example/pokecrack?"
        "sslmode=require&options=-c%20role%3Dpokecrack_authorized_opening_reviewer"
    )
    with pytest.raises(AuthorizedOpeningOperatorError) as error:
        _fixed_role_dsn(
            dsn,
            environment_name="AUTHORIZED_OPENING_REVIEWER_DB_URL",
            expected_login=None,
            expected_role="pokecrack_authorized_opening_reviewer",
        )
    assert error.value.code == "invalid_configuration"
    assert "secret" not in error.value.safe_message


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://wrong_login:secret@db.example/pokecrack?sslmode=require&options=-c%20role%3Dpokecrack_authorized_opening_submitter",
        "postgresql://pokecrack_authorized_opening_submitter_login:secret@db.example/pokecrack?sslmode=disable&options=-c%20role%3Dpokecrack_authorized_opening_submitter",
        "postgresql://pokecrack_authorized_opening_submitter_login:secret@db.example/pokecrack?sslmode=require&options=-c%20role%3Dservice_role",
        "postgresql://pokecrack_authorized_opening_submitter_login:secret@db.example/pokecrack?sslmode=require&options=-c%20role%3Dpokecrack_authorized_opening_submitter&options=bad",
    ],
)
def test_invalid_submitter_dsn_fails_without_exposing_credential(dsn: str) -> None:
    with pytest.raises(AuthorizedOpeningOperatorError) as error:
        _fixed_role_dsn(
            dsn,
            environment_name="AUTHORIZED_OPENING_SUBMITTER_DB_URL",
            expected_login="pokecrack_authorized_opening_submitter_login",
            expected_role="pokecrack_authorized_opening_submitter",
        )

    assert error.value.code == "invalid_configuration"
    assert "secret" not in error.value.safe_message
    assert "service_role" not in error.value.safe_message


class FakeExecutor:
    def __init__(self, rows: tuple[dict[str, object], ...]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object]]] = []

    def query(self, sql: str, params: dict[str, object]) -> tuple[dict[str, object], ...]:
        self.calls.append((sql, params))
        return self.rows


def test_rpc_client_calls_only_typed_functions_and_never_table_dml() -> None:
    fake = FakeExecutor(
        (
            {
                "submission_id": "00000000-0000-0000-0000-000000000001",
                "revision": 1,
                "state": "queued",
            },
        )
    )
    client = AuthorizedOpeningRpcClient(fake)  # type: ignore[arg-type]

    result = client.submit(AuthorizedOpeningEnvelope.model_validate(envelope_payload()))

    assert result == SubmissionResult(UUID("00000000-0000-0000-0000-000000000001"), 1, "queued")
    sql, params = fake.calls[0]
    lowered = sql.lower()
    assert "ingest.submit_authorized_opening_direct_v1" in lowered
    assert all(token not in lowered for token in ("insert into", "update ", "delete from"))
    assert all(value not in sql for value in HASHES.values())
    assert all(value not in json.dumps(params) for value in ("https://", "raw"))


def test_reviewer_rpc_calls_are_typed_and_return_only_safe_fields() -> None:
    submission_id = "00000000-0000-0000-0000-000000000001"
    fake = FakeExecutor(
        (
            {
                "submission_id": submission_id,
                "revision": 2,
                "state": "accepted_statistics",
                "accepted_observation_id": "00000000-0000-0000-0000-000000000002",
            },
        )
    )
    client = AuthorizedOpeningRpcClient(fake)  # type: ignore[arg-type]
    reference = "e" * 64

    review = client.review(
        UUID(submission_id),
        1,
        "accepted_statistics",
        reference,
        "evidence_verified",
    )

    assert review.submission_id == UUID(submission_id)
    assert review.revision == 2
    assert review.state == "accepted_statistics"
    assert review.accepted_observation_id == UUID("00000000-0000-0000-0000-000000000002")
    sql, params = fake.calls[0]
    assert "ingest.review_authorized_opening_v1" in sql.lower()
    assert reference in json.dumps(params)
    assert "accepted_observation_id" in sql

    fake.rows = (
        {"submission_id": submission_id, "revision": 1, "state": "queued"},
        {"submission_id": "00000000-0000-0000-0000-000000000002", "revision": 1, "state": "queued"},
    )
    queue = client.list_reviews("queued", 50)
    assert len(queue) == 2
    assert all(item.state == "queued" for item in queue)


def test_reviewer_connection_attestation_accepts_only_the_reviewed_capability() -> None:
    fake = FakeExecutor(
        (
            {
                "session_identity": True,
                "capability_active": True,
                "capability_contract": True,
                "capability_membership": True,
                "capability_membership_contract": True,
                "login_contract": True,
                "capability_acl_clean": True,
                "login_acl_clean": True,
                "object_ownership_clean": True,
            },
        )
    )
    client = AuthorizedOpeningRpcClient(fake)  # type: ignore[arg-type]

    client.attest_reviewer_connection()
    assert "pg_has_role" in fake.calls[0][0]
    assert "pg_auth_members" in fake.calls[0][0]
    assert "pg_roles" in fake.calls[0][0]


def test_submitter_connection_attestation_accepts_only_the_reviewed_capability() -> None:
    fake = FakeExecutor(
        (
            {
                "session_identity": True,
                "capability_active": True,
                "capability_contract": True,
                "capability_membership": True,
                "capability_membership_contract": True,
                "login_contract": True,
                "capability_acl_clean": True,
                "login_acl_clean": True,
                "object_ownership_clean": True,
            },
        )
    )
    client = AuthorizedOpeningRpcClient(fake)  # type: ignore[arg-type]

    client.attest_submitter_connection()
    sql = fake.calls[0][0].lower()
    assert "session_user" in sql
    assert "current_user" in sql
    assert "pokecrack_authorized_opening_submitter" in sql
    assert "submit_authorized_opening_direct_v1" in sql


@pytest.mark.parametrize(
    "rows",
    [
        (),
        (
            {
                "session_identity": False,
                "capability_active": True,
                "capability_contract": True,
                "capability_membership": True,
                "capability_membership_contract": True,
                "login_contract": True,
                "capability_acl_clean": True,
                "login_acl_clean": True,
                "object_ownership_clean": True,
            },
        ),
        (
            {
                "session_identity": True,
                "capability_active": False,
                "capability_contract": True,
                "capability_membership": True,
                "capability_membership_contract": True,
                "login_contract": True,
                "capability_acl_clean": True,
                "login_acl_clean": True,
                "object_ownership_clean": True,
            },
        ),
        (
            {
                "session_identity": True,
                "capability_active": True,
                "capability_contract": False,
                "capability_membership": True,
                "capability_membership_contract": True,
                "login_contract": True,
                "capability_acl_clean": True,
                "login_acl_clean": True,
                "object_ownership_clean": True,
            },
        ),
        (
            {
                "session_identity": True,
                "capability_active": True,
                "capability_contract": True,
                "capability_membership": True,
                "capability_membership_contract": True,
                "login_contract": True,
                "capability_acl_clean": False,
                "login_acl_clean": True,
                "object_ownership_clean": True,
            },
        ),
        (
            {
                "session_identity": True,
                "capability_active": True,
                "capability_contract": True,
                "capability_membership": True,
                "capability_membership_contract": True,
                "login_contract": True,
                "capability_acl_clean": True,
                "login_acl_clean": False,
                "object_ownership_clean": True,
            },
        ),
    ],
)
def test_reviewer_connection_attestation_fails_closed(rows: tuple[dict[str, object], ...]) -> None:
    client = AuthorizedOpeningRpcClient(FakeExecutor(rows))  # type: ignore[arg-type]
    with pytest.raises(AuthorizedOpeningOperatorError) as error:
        client.attest_reviewer_connection()
    assert error.value.code == "invalid_configuration"


def test_connection_attestation_fails_closed_on_missing_or_extra_fields() -> None:
    incomplete = AuthorizedOpeningRpcClient(
        FakeExecutor(
            (
                {
                    "session_identity": True,
                    "capability_active": True,
                    "capability_contract": True,
                    "capability_membership": True,
                    "capability_membership_contract": True,
                    "login_contract": True,
                    "capability_acl_clean": True,
                    "login_acl_clean": True,
                },
            )
        )
    )  # type: ignore[arg-type]
    with pytest.raises(AuthorizedOpeningOperatorError) as incomplete_error:
        incomplete.attest_submitter_connection()
    assert incomplete_error.value.code == "invalid_configuration"

    extra = AuthorizedOpeningRpcClient(
        FakeExecutor(
            (
                {
                    "session_identity": True,
                    "capability_active": True,
                    "capability_contract": True,
                    "capability_membership": True,
                    "capability_membership_contract": True,
                    "login_contract": True,
                    "capability_acl_clean": True,
                    "login_acl_clean": True,
                    "object_ownership_clean": True,
                    "unexpected": True,
                },
            )
        )
    )  # type: ignore[arg-type]
    with pytest.raises(AuthorizedOpeningOperatorError) as extra_error:
        extra.attest_submitter_connection()
    assert extra_error.value.code == "invalid_configuration"


def test_retraction_rpc_result_is_safe_and_does_not_echo_reference() -> None:
    observation_id = UUID("00000000-0000-0000-0000-000000000001")
    fake = FakeExecutor(
        ({"accepted_observation_id": str(observation_id), "reason_code": "privacy_request"},)
    )
    client = AuthorizedOpeningRpcClient(fake)  # type: ignore[arg-type]
    reference = "f" * 64

    result = client.retract(observation_id, reference, "privacy_request")

    assert result.accepted_observation_id == observation_id
    assert result.reason_code == "privacy_request"
    sql, params = fake.calls[0]
    assert "ingest.retract_authorized_opening_v1" in sql.lower()
    assert reference in json.dumps(params)
    assert all(token not in sql.lower() for token in ("insert into", "update ", "delete from"))


def test_reviewer_input_validation_fails_before_rpc() -> None:
    with pytest.raises(AuthorizedOpeningOperatorError):
        validate_review_list_request(state="queued", limit=101)
    with pytest.raises(AuthorizedOpeningOperatorError):
        validate_review_request(
            target_state="accepted_statistics",
            reason_code="review_started",
            expected_revision=1,
        )
    with pytest.raises(AuthorizedOpeningOperatorError):
        validate_reviewer_reference("UPPERCASE-OR-NOT-A-HASH")


def test_database_errors_are_collapsed_without_echoing_details() -> None:
    class FailingExecutor:
        def query(
            self, _sql: str, _params: Mapping[str, object]
        ) -> tuple[Mapping[str, object], ...]:
            raise RuntimeError(f"secret={HASHES['evidenceSha256']} DSN password")

    client = AuthorizedOpeningRpcClient(FailingExecutor())  # type: ignore[arg-type]
    with pytest.raises(AuthorizedOpeningOperatorError) as error:
        client.submit(AuthorizedOpeningEnvelope.model_validate(envelope_payload()))

    assert error.value.code == "database_unavailable"
    assert "DSN" not in error.value.safe_message
    assert all(value not in error.value.safe_message for value in HASHES.values())


def test_safe_output_strips_opaque_fields() -> None:
    submission = SubmissionResult(UUID("00000000-0000-0000-0000-000000000001"), 2, "in_review")
    queue = (ReviewQueueItem(submission.submission_id, 2, "in_review"),)
    retraction = RetractionResult(submission.submission_id, "privacy_request")
    review = ReviewResult(
        submission.submission_id,
        3,
        "accepted_statistics",
        UUID("00000000-0000-0000-0000-000000000002"),
    )

    assert safe_submission_payload(submission) == {
        "submission_id": "00000000-0000-0000-0000-000000000001",
        "revision": 2,
        "state": "in_review",
    }
    assert safe_submission_payload(review) == {
        "submission_id": "00000000-0000-0000-0000-000000000001",
        "revision": 3,
        "state": "accepted_statistics",
        "accepted_observation_id": "00000000-0000-0000-0000-000000000002",
    }
    assert safe_review_queue_payload(queue) == {
        "reviews": [
            {
                "submission_id": "00000000-0000-0000-0000-000000000001",
                "revision": 2,
                "state": "in_review",
            }
        ]
    }
    assert safe_retraction_payload(retraction) == {
        "accepted_observation_id": "00000000-0000-0000-0000-000000000001",
        "reason_code": "privacy_request",
        "state": "retracted",
    }
    rendered = json.dumps(
        [
            safe_submission_payload(submission),
            safe_submission_payload(review),
            safe_review_queue_payload(queue),
            safe_retraction_payload(retraction),
        ]
    )
    assert all(value not in rendered for value in HASHES.values())


def test_cli_validates_before_configuration_or_rpc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_private_envelope(tmp_path, envelope_payload(discoveryPlatform="nostr"))

    def should_not_build_client(*, reviewer: bool) -> object:
        raise AssertionError(f"database client built before local validation: {reviewer}")

    monkeypatch.setattr("pokecrack_worker.cli.build_operator_client", should_not_build_client)
    result = runner.invoke(app, ["authorized-opening", "submit", str(path)])

    assert result.exit_code == 2
    assert json.loads(result.stderr)["error"] == "social_derived_rejected"
    assert all(value not in result.output for value in HASHES.values())


def test_cli_missing_submitter_dsn_is_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_private_envelope(tmp_path, envelope_payload())
    for name in (
        "AUTHORIZED_OPENING_SUBMITTER_DB_URL",
        "SUPABASE_DB_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    result = runner.invoke(app, ["authorized-opening", "submit", str(path)])

    assert result.exit_code == 2
    assert json.loads(result.stderr)["error"] == "invalid_configuration"
    assert all(value not in result.output for value in HASHES.values())


def test_cli_database_exception_does_not_echo_secret_or_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_private_envelope(tmp_path, envelope_payload())
    monkeypatch.setenv(
        "AUTHORIZED_OPENING_SUBMITTER_DB_URL",
        "postgresql://pokecrack_authorized_opening_submitter_login:secret@db.example/pokecrack?sslmode=require&options=-c%20role%3Dpokecrack_authorized_opening_submitter",
    )

    class FailingExecutor:
        def query(
            self, _sql: str, _params: Mapping[str, object]
        ) -> tuple[Mapping[str, object], ...]:
            raise RuntimeError(f"dsn secret and digest {HASHES['evidenceSha256']}")

    monkeypatch.setattr(
        "pokecrack_worker.cli.build_operator_client",
        lambda *, reviewer: AuthorizedOpeningRpcClient(FailingExecutor()),
    )
    result = runner.invoke(app, ["authorized-opening", "submit", str(path)])

    assert result.exit_code == 1
    assert json.loads(result.stderr)["error"] == "database_unavailable"
    assert "secret" not in result.output
    assert all(value not in result.output for value in HASHES.values())
    assert "Traceback" not in result.output
