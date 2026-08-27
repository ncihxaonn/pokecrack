from __future__ import annotations

import asyncio
import inspect
import json
import threading
from datetime import UTC, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from pokecrack_worker.config.settings import Settings
from pokecrack_worker.extraction.budget import (
    BudgetedAIProvider,
    BudgetLedger,
    BudgetLimits,
    BudgetPausedError,
)
from pokecrack_worker.extraction.models import ExtractorOutput, ProductType
from pokecrack_worker.extraction.providers import (
    AICompletion,
    AIHTTPError,
    AIProvider,
    AIRequest,
    AIResponseError,
    FixtureAIProvider,
    FixtureResponse,
    HTTPResponse,
    OpenAICompatibleProvider,
    Pricing,
    SchemaValidationError,
    TokenUsage,
    UrllibHTTPTransport,
    build_ai_provider,
)
from pokecrack_worker.extraction.service import AIExtractor
from pokecrack_worker.validation.catalog import CatalogCard, CatalogSet, InMemoryCatalogMatcher
from pokecrack_worker.validation.decisions import resolve_evidence
from pokecrack_worker.validation.models import ValidatorOutput
from pokecrack_worker.validation.pipeline import EvidencePipeline, PipelineStatus
from pokecrack_worker.validation.prechecks import run_prechecks
from pokecrack_worker.validation.service import VALIDATOR_SYSTEM_PROMPT, AIValidator

WORKER = Path(__file__).resolve().parents[1]


def extractor_payload(*, confidence: float = 0.95) -> dict[str, object]:
    return {
        "content_type": "video",
        "decision": "candidate",
        "set": {
            "name": "Paldea Evolved",
            "confidence": confidence,
            "evidence_reference": "title",
        },
        "product": {
            "name": "Synthetic booster bundle",
            "type": "booster_bundle",
            "confidence": confidence,
            "evidence_reference": "description",
        },
        "opening": {
            "pack_count": 6,
            "is_complete": True,
            "opened_at": "2026-08-25T00:00:00Z",
            "confidence": confidence,
            "evidence_reference": "six synthetic packs",
        },
        "location": {
            "country_code": "AU",
            "region": None,
            "confidence": confidence,
            "evidence_reference": "Australia",
        },
        "purchase": {
            "retailer": None,
            "batch_code": None,
            "confidence": 0.0,
            "evidence_reference": None,
        },
        "hits": [],
        "evidence_tier_candidate": "B",
        "overall_confidence": confidence,
        "missing_fields": ["purchase.retailer", "purchase.batch_code"],
        "warnings": ["synthetic_fixture"],
    }


def validator_payload(*, confidence: float = 0.95) -> dict[str, object]:
    return {
        "verdict": "accept",
        "observed": {
            "set_name": "Paldea Evolved",
            "product_name": "Synthetic booster bundle",
            "product_type": "booster_bundle",
            "pack_count": 6,
            "is_complete": True,
            "hits": [],
            "country_code": "AU",
            "region": None,
            "retailer": None,
            "batch_code": None,
            "opened_at": "2026-08-25T00:00:00Z",
        },
        "overall_confidence": confidence,
        "eligible_for_statistics": True,
        "evidence_tier": "B",
        "field_checks": [
            {
                "field": "opening.pack_count",
                "status": "verified",
                "confidence": confidence,
                "evidence_reference": "six synthetic packs",
            },
            *[
                {
                    "field": field,
                    "status": "verified",
                    "confidence": confidence,
                    "evidence_reference": "synthetic source evidence",
                }
                for field in (
                    "set.name",
                    "product.name",
                    "product.type",
                    "opening.is_complete",
                    "opening.opened_at",
                    "location.country_code",
                    "hits",
                    "evidence_tier",
                )
            ],
            *[
                {
                    "field": field,
                    "status": "not_applicable",
                    "confidence": confidence,
                    "evidence_reference": None,
                }
                for field in (
                    "location.region",
                    "purchase.retailer",
                    "purchase.batch_code",
                )
            ],
        ],
        "contradictions": [],
        "missing_required_fields": [],
        "duplicate_suspected": False,
        "rejection_reasons": [],
    }


def test_prompt_files_are_versioned_null_not_guess_no_cot_and_match_runtime_schemas() -> None:
    extractor_schema = json.loads(
        (WORKER / "prompts" / "extractor.schema.json").read_text(encoding="utf-8")
    )
    validator_schema = json.loads(
        (WORKER / "prompts" / "validator.schema.json").read_text(encoding="utf-8")
    )

    assert extractor_schema == ExtractorOutput.json_schema()
    assert validator_schema == ValidatorOutput.json_schema()
    assert set(extractor_schema["properties"]) == {
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
    assert set(validator_schema["properties"]) == {
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
    assert "reasoning" not in extractor_schema["properties"]
    assert "reasoning" not in validator_schema["properties"]

    for name in ("extractor.md", "validator.md", "escalation.md"):
        text = (WORKER / "prompts" / name).read_text(encoding="utf-8").casefold()
        assert "prompt_version:" in text
        assert "null" in text
        assert "do not guess" in text
        assert "chain-of-thought" in text
        assert "do not" in text


def test_validator_prompt_uses_only_validator_schema_field_names() -> None:
    text = (WORKER / "prompts" / "validator.md").read_text(encoding="utf-8")
    assert "contradictions" in text
    assert "rejection_reasons" in text
    assert "conflict_codes" not in text
    assert "contradictions" in VALIDATOR_SYSTEM_PROMPT
    assert "rejection_reasons" in VALIDATOR_SYSTEM_PROMPT
    assert "conflict_codes" not in VALIDATOR_SYSTEM_PROMPT


def test_validator_parser_rejects_boolean_string_coercion() -> None:
    payload = validator_payload()
    payload["eligible_for_statistics"] = "false"

    with pytest.raises(SchemaValidationError, match="expected boolean"):
        ValidatorOutput.from_mapping(payload)


def test_validator_schema_rejects_non_finite_confidence() -> None:
    payload = validator_payload()
    payload["overall_confidence"] = float("nan")
    validator = AIValidator(FixtureAIProvider([payload]))

    with pytest.raises(SchemaValidationError, match="finite"):
        validator.validate("Synthetic opening.", ExtractorOutput.from_mapping(extractor_payload()))


def test_validator_rejects_legacy_payload_without_strict_verdict_or_observed_facts() -> None:
    legacy = {
        "decision": "accept",
        "evidence_tier": "B",
        "confidence": 0.99,
    }
    with pytest.raises(ValueError, match="strict validator schema"):
        ValidatorOutput.from_mapping(legacy)


def test_validator_rejects_verdict_without_independently_observed_facts() -> None:
    extraction = ExtractorOutput.from_mapping(extractor_payload())
    payload = validator_payload()
    payload.pop("observed")
    validator = AIValidator(FixtureAIProvider([payload]))

    with pytest.raises(ValueError, match="observed"):
        validator.validate("Six synthetic Paldea Evolved packs.", extraction)


def test_provider_protocol_exposes_async_extract_validate_and_escalate() -> None:
    assert inspect.iscoroutinefunction(AIProvider.extract)
    assert inspect.iscoroutinefunction(AIProvider.validate)
    assert inspect.iscoroutinefunction(AIProvider.escalate)
    assert inspect.iscoroutinefunction(BudgetedAIProvider.extract)
    assert inspect.iscoroutinefunction(BudgetedAIProvider.validate)
    assert inspect.iscoroutinefunction(BudgetedAIProvider.escalate)
    provider = FixtureAIProvider([extractor_payload()])
    request = AIRequest(
        operation="extract",
        system_prompt="synthetic",
        input_text="synthetic",
        schema_name="extractor_output",
        schema=ExtractorOutput.json_schema(),
        decoder=ExtractorOutput.from_mapping,
    )

    completion = asyncio.run(provider.extract(request))

    assert completion.output.pack_count == 6


def test_product_type_uses_exact_shared_vocabulary() -> None:
    assert tuple(item.value for item in ProductType) == (
        "booster_box",
        "etb",
        "booster_bundle",
        "other",
        "unknown",
    )


def test_budget_reservation_accounts_for_the_full_request_payload() -> None:
    calls = 0

    def transport(
        _url: str, _headers: dict[str, str], _body: bytes, _timeout: float
    ) -> HTTPResponse:
        nonlocal calls
        calls += 1
        envelope = {
            "id": "fixture-response",
            "choices": [{"message": {"content": json.dumps(extractor_payload())}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        return HTTPResponse(200, json.dumps(envelope).encode())

    limit = Decimal("0.0042")
    settings = Settings(
        _env_file=None,
        ai_provider="openai_compatible",
        ai_api_key="fixture-secret",
        ai_extract_model="configured-extractor",
        ai_validate_model="configured-validator",
        ai_escalate_model="configured-escalator",
        ai_daily_budget_aud=limit,
        ai_monthly_soft_budget_aud=limit,
        ai_input_per_million_aud=Decimal("1"),
        ai_output_per_million_aud=Decimal("1"),
    )
    provider = build_ai_provider(
        settings,
        operation="extract",
        transport=transport,
        budget_ledger=BudgetLedger(BudgetLimits(limit, limit)),
    )
    request = AIRequest(
        operation="extract",
        system_prompt="synthetic",
        input_text="synthetic",
        schema_name="extractor_output",
        schema=ExtractorOutput.json_schema(),
        decoder=ExtractorOutput.from_mapping,
    )

    with pytest.raises(BudgetPausedError):
        provider.complete(request)
    assert calls == 0


def test_zero_budget_factory_provider_pauses_before_network_dispatch() -> None:
    calls = 0

    def transport(
        _url: str, _headers: dict[str, str], _body: bytes, _timeout: float
    ) -> HTTPResponse:
        nonlocal calls
        calls += 1
        envelope = {
            "id": "fixture-response",
            "choices": [{"message": {"content": json.dumps(extractor_payload())}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        return HTTPResponse(200, json.dumps(envelope).encode())

    settings = Settings(
        _env_file=None,
        ai_provider="openai_compatible",
        ai_api_key="fixture-secret",
        ai_extract_model="configured-extractor",
        ai_validate_model="configured-validator",
        ai_escalate_model="configured-escalator",
        ai_daily_budget_aud=Decimal("0"),
        ai_monthly_soft_budget_aud=Decimal("0"),
        ai_input_per_million_aud=Decimal("1"),
        ai_output_per_million_aud=Decimal("1"),
    )
    ledger = BudgetLedger(BudgetLimits(Decimal("0"), Decimal("0")))
    provider = build_ai_provider(
        settings,
        operation="extract",
        transport=transport,
        budget_ledger=ledger,
    )
    request = AIRequest(
        operation="extract",
        system_prompt="synthetic",
        input_text="synthetic",
        schema_name="extractor_output",
        schema=ExtractorOutput.json_schema(),
        decoder=ExtractorOutput.from_mapping,
    )

    assert isinstance(provider, BudgetedAIProvider)
    with pytest.raises(BudgetPausedError):
        provider.complete(request)
    assert calls == 0


def test_network_provider_factory_rejects_ledger_limits_that_bypass_settings() -> None:
    settings = Settings(
        _env_file=None,
        ai_provider="openai_compatible",
        ai_api_key="fixture-secret",
        ai_extract_model="configured-extractor",
        ai_validate_model="configured-validator",
        ai_escalate_model="configured-escalator",
        ai_daily_budget_aud=Decimal("1"),
        ai_monthly_soft_budget_aud=Decimal("10"),
        ai_input_per_million_aud=Decimal("1"),
        ai_output_per_million_aud=Decimal("1"),
    )
    bypass = BudgetLedger(BudgetLimits(Decimal("999"), Decimal("999")))

    with pytest.raises(ValueError, match="budget ledger limits"):
        build_ai_provider(settings, operation="extract", budget_ledger=bypass)


def test_network_provider_factory_requires_a_shared_budget_ledger() -> None:
    settings = Settings(
        _env_file=None,
        ai_provider="openai_compatible",
        ai_api_key="fixture-secret",
        ai_extract_model="configured-extractor",
        ai_validate_model="configured-validator",
        ai_escalate_model="configured-escalator",
        ai_input_per_million_aud=Decimal("1"),
        ai_output_per_million_aud=Decimal("1"),
    )

    with pytest.raises(ValueError, match="shared budget ledger"):
        build_ai_provider(settings, operation="extract")


def test_env_settings_build_real_operation_provider_without_hardcoded_model() -> None:
    settings = Settings(
        _env_file=None,
        ai_provider="openai_compatible",
        ai_api_key="fixture-secret",
        ai_extract_model="configured-extractor",
        ai_validate_model="configured-validator",
        ai_escalate_model="configured-escalator",
        ai_input_per_million_aud=Decimal("1"),
        ai_output_per_million_aud=Decimal("1"),
        ai_request_timeout_seconds=17,
        ai_max_retries=0,
        ai_max_output_tokens=1234,
    )

    provider = build_ai_provider(
        settings,
        operation="validate",
        transport=lambda url, headers, body, timeout: HTTPResponse(500, b"fixture"),
        budget_ledger=BudgetLedger(
            BudgetLimits(settings.ai_daily_budget_aud, settings.ai_monthly_soft_budget_aud)
        ),
    )

    assert isinstance(provider, BudgetedAIProvider)
    assert isinstance(provider.provider, OpenAICompatibleProvider)
    assert provider.provider.model == "configured-validator"
    assert provider.provider.timeout_seconds == 17
    assert provider.provider.max_retries == 0
    assert provider.provider.max_output_tokens == 1234
    assert "model=" not in str(inspect.signature(build_ai_provider))


def test_provider_http_error_does_not_echo_response_payload() -> None:
    secret = b"provider-response-secret"
    provider = build_ai_provider(
        Settings(
            _env_file=None,
            ai_provider="openai_compatible",
            ai_api_key="fixture-secret",
            ai_extract_model="configured-extractor",
            ai_validate_model="configured-validator",
            ai_escalate_model="configured-escalator",
            ai_input_per_million_aud=Decimal("1"),
            ai_output_per_million_aud=Decimal("1"),
            ai_max_retries=0,
        ),
        operation="extract",
        transport=lambda url, headers, body, timeout: HTTPResponse(400, secret),
        budget_ledger=BudgetLedger(BudgetLimits(Decimal("5"), Decimal("50"))),
    )
    request = AIRequest(
        operation="extract",
        system_prompt="synthetic",
        input_text="synthetic",
        schema_name="extractor_output",
        schema=ExtractorOutput.json_schema(),
        decoder=ExtractorOutput.from_mapping,
    )

    with pytest.raises(AIHTTPError) as caught:
        provider.complete(request)
    assert secret.decode() not in str(caught.value)


def test_budgeted_provider_rejects_inner_network_retries() -> None:
    inner = OpenAICompatibleProvider(
        api_key="fixture-key",
        model="fixture-model",
        max_retries=1,
        pricing=Pricing(Decimal("1"), Decimal("1")),
        transport=lambda _url, _headers, _body, _timeout: HTTPResponse(500, b"fixture"),
    )

    with pytest.raises(ValueError, match="internal retries"):
        BudgetedAIProvider(
            provider=inner,
            ledger=BudgetLedger(BudgetLimits(Decimal("1"), Decimal("10"))),
            estimated_cost_aud=Decimal("0.01"),
        )


@pytest.mark.parametrize(
    "usage",
    [None, {"prompt_tokens": 0, "completion_tokens": 0}],
)
def test_missing_or_zero_network_usage_consumes_reservation_and_blocks_another_dispatch(
    usage: dict[str, int] | None,
) -> None:
    now = datetime(2026, 8, 25, tzinfo=UTC)
    calls = 0

    def transport(
        _url: str, _headers: dict[str, str], _body: bytes, _timeout: float
    ) -> HTTPResponse:
        nonlocal calls
        calls += 1
        envelope = {
            "id": "untrusted-usage",
            "choices": [{"message": {"content": json.dumps(extractor_payload())}}],
        }
        if usage is not None:
            envelope["usage"] = usage
        return HTTPResponse(200, json.dumps(envelope).encode())

    request = AIRequest(
        operation="extract",
        system_prompt="synthetic",
        input_text="synthetic",
        schema_name="extractor_output",
        schema=ExtractorOutput.json_schema(),
        decoder=ExtractorOutput.from_mapping,
    )
    inner = OpenAICompatibleProvider(
        api_key="fixture-key",
        model="fixture-model",
        max_retries=0,
        max_output_tokens=16,
        pricing=Pricing(Decimal("1"), Decimal("1")),
        transport=transport,
        clock=lambda: now,
    )
    estimate = inner.estimated_max_cost(request)
    ledger = BudgetLedger(BudgetLimits(estimate, estimate))
    provider = BudgetedAIProvider(
        provider=inner,
        ledger=ledger,
        estimated_cost_aud=inner.estimated_max_cost,
        clock=lambda: now,
    )

    with pytest.raises(AIResponseError, match="usage"):
        provider.complete(request)
    with pytest.raises(BudgetPausedError):
        provider.complete(request)

    assert calls == 1
    assert ledger.snapshot(now).daily_spend_aud == estimate


def test_failed_paid_capable_dispatch_consumes_the_conservative_reservation() -> None:
    now = datetime(2026, 8, 25, tzinfo=UTC)

    class TimeoutProvider:
        provider_name = "openai_compatible"
        model = "fixture-model"
        max_retries = 0

        def complete(self, _request: AIRequest[object]) -> AICompletion[object]:
            raise TimeoutError("synthetic timeout")

        async def extract(self, request: AIRequest[object]) -> AICompletion[object]:
            return self.complete(request)

        async def validate(self, request: AIRequest[object]) -> AICompletion[object]:
            return self.complete(request)

        async def escalate(self, request: AIRequest[object]) -> AICompletion[object]:
            return self.complete(request)

    ledger = BudgetLedger(BudgetLimits(Decimal("0.01"), Decimal("1")))
    provider = BudgetedAIProvider(
        provider=TimeoutProvider(),
        ledger=ledger,
        estimated_cost_aud=Decimal("0.01"),
        clock=lambda: now,
    )
    request = AIRequest(
        operation="extract",
        system_prompt="synthetic",
        input_text="synthetic",
        schema_name="extractor_output",
        schema=ExtractorOutput.json_schema(),
        decoder=ExtractorOutput.from_mapping,
    )

    with pytest.raises(TimeoutError, match="synthetic timeout"):
        provider.complete(request)

    snapshot = ledger.snapshot(now)
    assert snapshot.daily_spend_aud == Decimal("0.01")
    assert ledger.run_count == 1


def test_budgeted_provider_records_usage_and_hard_pause_does_not_consume_fixture() -> None:
    now = datetime(2026, 8, 25, tzinfo=UTC)
    ledger = BudgetLedger(BudgetLimits(Decimal("1"), Decimal("10")))
    inner = FixtureAIProvider(
        [FixtureResponse(extractor_payload(), TokenUsage(10, 5))],
        clock=lambda: now,
    )
    provider = BudgetedAIProvider(
        provider=inner,
        ledger=ledger,
        estimated_cost_aud=Decimal("0"),
        clock=lambda: now,
    )
    request = AIRequest(
        operation="extract",
        system_prompt="synthetic",
        input_text="synthetic",
        schema_name="extractor_output",
        schema=ExtractorOutput.json_schema(),
        decoder=ExtractorOutput.from_mapping,
    )

    provider.complete(request)
    assert ledger.run_count == 1

    paused_inner = FixtureAIProvider([extractor_payload()], clock=lambda: now)
    paused = BudgetedAIProvider(
        provider=paused_inner,
        ledger=BudgetLedger(BudgetLimits(Decimal("0"), Decimal("0"))),
        estimated_cost_aud=Decimal("0.01"),
        clock=lambda: now,
    )
    pipeline = EvidencePipeline(
        extractor=AIExtractor(paused),
        validator=AIValidator(FixtureAIProvider([validator_payload()])),
        catalog=InMemoryCatalogMatcher(sets=[CatalogSet("sv2", "Paldea Evolved")], cards=[]),
    )

    result = pipeline.process("Six synthetic Paldea Evolved packs.")

    assert result.status is PipelineStatus.BUDGET_PAUSED
    assert result.extraction is None
    assert result.ai_runs == ()
    assert paused_inner.remaining == 1


def test_budget_reservation_prevents_concurrent_calls_from_both_passing_limit() -> None:
    now = datetime(2026, 8, 25, tzinfo=UTC)
    ledger = BudgetLedger(BudgetLimits(Decimal("0.015"), Decimal("1")))
    request = AIRequest(
        operation="extract",
        system_prompt="synthetic",
        input_text="synthetic",
        schema_name="extractor_output",
        schema=ExtractorOutput.json_schema(),
        decoder=ExtractorOutput.from_mapping,
    )
    pricing = Pricing(input_per_million_aud=Decimal("1000"))
    started = threading.Event()
    release = threading.Event()

    class BlockingProvider:
        def __init__(self) -> None:
            self.inner = FixtureAIProvider(
                [FixtureResponse(extractor_payload(), TokenUsage(10, 0))],
                pricing=pricing,
                clock=lambda: now,
            )

        def complete(self, provider_request: AIRequest[object]):
            started.set()
            assert release.wait(1)
            return self.inner.complete(provider_request)

    first = BudgetedAIProvider(
        provider=BlockingProvider(),
        ledger=ledger,
        estimated_cost_aud=Decimal("0.01"),
        clock=lambda: now,
    )
    second = BudgetedAIProvider(
        provider=FixtureAIProvider(
            [FixtureResponse(extractor_payload(), TokenUsage(10, 0))],
            pricing=pricing,
            clock=lambda: now,
        ),
        ledger=ledger,
        estimated_cost_aud=Decimal("0.01"),
        clock=lambda: now,
    )
    first_errors: list[BaseException] = []

    def run_first() -> None:
        try:
            first.complete(request)
        except BaseException as error:
            first_errors.append(error)

    thread = threading.Thread(target=run_first)
    thread.start()
    assert started.wait(1)
    try:
        with pytest.raises(BudgetPausedError):
            second.complete(request)
    finally:
        release.set()
        thread.join(timeout=2)

    assert not thread.is_alive()
    assert first_errors == []
    assert ledger.snapshot(now).daily_spend_aud == Decimal("0.01")


def test_pipeline_default_threshold_rejects_below_configured_acceptance_default() -> None:
    pipeline = EvidencePipeline(
        extractor=AIExtractor(FixtureAIProvider([extractor_payload(confidence=0.91)])),
        validator=AIValidator(FixtureAIProvider([validator_payload(confidence=0.99)])),
        catalog=InMemoryCatalogMatcher(sets=[CatalogSet("sv2", "Paldea Evolved")], cards=[]),
    )

    result = pipeline.process("Six synthetic Paldea Evolved packs.")

    assert result.status is PipelineStatus.COMPLETED
    assert result.decision.reason_codes == ("low_confidence",)
    assert result.decision.eligible_for_rates is False


def _pipeline(extractor: dict[str, object], validator: dict[str, object]) -> EvidencePipeline:
    return EvidencePipeline(
        extractor=AIExtractor(FixtureAIProvider([extractor])),
        validator=AIValidator(FixtureAIProvider([validator])),
        catalog=InMemoryCatalogMatcher(sets=[CatalogSet("sv2", "Paldea Evolved")], cards=[]),
    )


def test_unsupported_product_escalation_consensus_never_becomes_rate_eligible() -> None:
    extraction_payload = extractor_payload()
    extraction_payload["location"]["country_code"] = "US"
    extraction = ExtractorOutput.from_mapping(extraction_payload)
    payload = validator_payload()
    payload["observed"]["country_code"] = "US"
    payload["observed"]["is_complete"] = False
    payload["observed"]["product_type"] = "other"
    validation = ValidatorOutput.from_mapping(payload)
    escalation = ValidatorOutput.from_mapping(json.loads(json.dumps(payload)))

    decision = resolve_evidence(extraction, validation, escalation=escalation)

    assert decision.status.value == "rejected"
    assert decision.eligible_for_rates is False
    assert "outside_scope_product" in decision.reason_codes
    assert "outside_scope_country" not in decision.reason_codes


def test_incomplete_validator_escalation_consensus_is_activity_only() -> None:
    extraction = ExtractorOutput.from_mapping(extractor_payload())
    payload = validator_payload()
    payload["observed"]["is_complete"] = False
    validation = ValidatorOutput.from_mapping(payload)
    escalation = ValidatorOutput.from_mapping(json.loads(json.dumps(payload)))

    decision = resolve_evidence(extraction, validation, escalation=escalation)

    assert decision.status.value == "activity_only"
    assert decision.eligible_for_rates is False
    assert "incomplete_opening" in decision.reason_codes


def test_lower_tier_validator_escalation_consensus_is_never_rate_eligible() -> None:
    extraction = ExtractorOutput.from_mapping(extractor_payload())
    payload = validator_payload()
    payload["evidence_tier"] = "C"
    validation = ValidatorOutput.from_mapping(payload)
    escalation = ValidatorOutput.from_mapping(json.loads(json.dumps(payload)))

    decision = resolve_evidence(extraction, validation, escalation=escalation)

    assert decision.status.value == "activity_only"
    assert decision.eligible_for_rates is False
    assert "validator_evidence_tier_ineligible" in decision.reason_codes


def test_rejecting_validator_escalation_consensus_cannot_become_accepted() -> None:
    extraction = ExtractorOutput.from_mapping(extractor_payload())
    payload = validator_payload()
    payload["verdict"] = "reject"
    payload["eligible_for_statistics"] = True
    payload["rejection_reasons"] = ["synthetic_rejection"]
    validation = ValidatorOutput.from_mapping(payload)
    escalation = ValidatorOutput.from_mapping(json.loads(json.dumps(payload)))

    decision = resolve_evidence(extraction, validation, escalation=escalation)

    assert decision.status.value == "rejected"
    assert decision.eligible_for_rates is False
    assert "validator_rejected" in decision.reason_codes


def test_activity_only_validator_escalation_consensus_cannot_become_rate_eligible() -> None:
    extraction = ExtractorOutput.from_mapping(extractor_payload())
    payload = validator_payload()
    payload["verdict"] = "activity_only"
    payload["eligible_for_statistics"] = True
    validation = ValidatorOutput.from_mapping(payload)
    escalation = ValidatorOutput.from_mapping(json.loads(json.dumps(payload)))

    decision = resolve_evidence(extraction, validation, escalation=escalation)

    assert decision.status.value == "activity_only"
    assert decision.eligible_for_rates is False
    assert "validator_activity_only" in decision.reason_codes


def test_pipeline_rejects_escalation_consensus_rarity_that_disagrees_with_catalog() -> None:
    extraction = extractor_payload()
    extraction["hits"] = [
        {
            "card_name": "Synthetic Pikachu",
            "collector_number": "001/100",
            "rarity": "rare",
            "quantity": 1,
            "confidence": 0.99,
            "evidence_reference": "pack frame 1",
        }
    ]
    validation = validator_payload()
    validation["observed"]["hits"] = [
        {
            "card_name": "Synthetic Pikachu",
            "collector_number": "001/100",
            "rarity_key": "common",
            "quantity": 1,
        }
    ]
    escalation = json.loads(json.dumps(validation))
    pipeline = EvidencePipeline(
        extractor=AIExtractor(FixtureAIProvider([extraction])),
        validator=AIValidator(FixtureAIProvider([validation])),
        escalation_validator=AIValidator(FixtureAIProvider([escalation])),
        catalog=InMemoryCatalogMatcher(
            sets=[CatalogSet("sv2", "Paldea Evolved")],
            cards=[
                CatalogCard(
                    "card-1",
                    "sv2",
                    "Synthetic Pikachu",
                    "001/100",
                    "rare",
                )
            ],
        ),
    )

    result = pipeline.process("Synthetic opening.")

    assert result.decision.status.value == "rejected"
    assert result.decision.eligible_for_rates is False
    assert "catalog_rarity_disagreement" in result.decision.reason_codes


def test_pipeline_rejects_validator_escalation_consensus_on_unknown_catalog_card() -> None:
    extraction = extractor_payload()
    extraction["hits"] = [
        {
            "card_name": "Synthetic Pikachu",
            "collector_number": "001/100",
            "rarity": "rare",
            "quantity": 1,
            "confidence": 0.99,
            "evidence_reference": "pack frame 1",
        }
    ]
    validation = validator_payload()
    validation["observed"]["hits"] = [
        {
            "card_name": "Synthetic Eevee",
            "collector_number": "999/100",
            "rarity_key": "common",
            "quantity": 1,
        }
    ]
    escalation = json.loads(json.dumps(validation))
    pipeline = EvidencePipeline(
        extractor=AIExtractor(FixtureAIProvider([extraction])),
        validator=AIValidator(FixtureAIProvider([validation])),
        escalation_validator=AIValidator(FixtureAIProvider([escalation])),
        catalog=InMemoryCatalogMatcher(
            sets=[CatalogSet("sv2", "Paldea Evolved")],
            cards=[
                CatalogCard(
                    "card-1",
                    "sv2",
                    "Synthetic Pikachu",
                    "001/100",
                    "rare",
                )
            ],
        ),
    )

    result = pipeline.process("Synthetic opening.")

    assert result.decision.status.value == "rejected"
    assert result.decision.eligible_for_rates is False
    assert "catalog_card_not_found" in result.decision.reason_codes


def test_pipeline_rejects_validator_escalation_consensus_on_ambiguous_catalog_card() -> None:
    extraction = extractor_payload()
    extraction["hits"] = [
        {
            "card_name": "Synthetic Pikachu",
            "collector_number": "001/100",
            "rarity": "rare",
            "quantity": 1,
            "confidence": 0.99,
            "evidence_reference": "pack frame 1",
        }
    ]
    validation = validator_payload()
    validation["observed"]["hits"] = [
        {
            "card_name": "Synthetic Eevee",
            "collector_number": "999/100",
            "rarity_key": "common",
            "quantity": 1,
        }
    ]
    escalation = json.loads(json.dumps(validation))
    pipeline = EvidencePipeline(
        extractor=AIExtractor(FixtureAIProvider([extraction])),
        validator=AIValidator(FixtureAIProvider([validation])),
        escalation_validator=AIValidator(FixtureAIProvider([escalation])),
        catalog=InMemoryCatalogMatcher(
            sets=[CatalogSet("sv2", "Paldea Evolved")],
            cards=[
                CatalogCard("card-1", "sv2", "Synthetic Pikachu", "001/100", "rare"),
                CatalogCard("card-2", "sv2", "Synthetic Eevee", "999/100", "common"),
                CatalogCard("card-3", "sv2", "Synthetic Eevee", "999/100", "common"),
            ],
        ),
    )

    result = pipeline.process("Synthetic opening.")

    assert result.decision.status.value == "rejected"
    assert result.decision.eligible_for_rates is False
    assert "catalog_card_ambiguous" in result.decision.reason_codes


def test_pipeline_rejects_validator_escalation_consensus_missing_catalog_rarity() -> None:
    extraction = extractor_payload()
    extraction["hits"] = [
        {
            "card_name": "Synthetic Pikachu",
            "collector_number": "001/100",
            "rarity": "rare",
            "quantity": 1,
            "confidence": 0.99,
            "evidence_reference": "pack frame 1",
        }
    ]
    validation = validator_payload()
    validation["observed"]["hits"] = [
        {
            "card_name": "Synthetic Pikachu",
            "collector_number": "001/100",
            "rarity_key": None,
            "quantity": 1,
        }
    ]
    escalation = json.loads(json.dumps(validation))
    pipeline = EvidencePipeline(
        extractor=AIExtractor(FixtureAIProvider([extraction])),
        validator=AIValidator(FixtureAIProvider([validation])),
        escalation_validator=AIValidator(FixtureAIProvider([escalation])),
        catalog=InMemoryCatalogMatcher(
            sets=[CatalogSet("sv2", "Paldea Evolved")],
            cards=[CatalogCard("card-1", "sv2", "Synthetic Pikachu", "001/100", "rare")],
        ),
    )

    result = pipeline.process("Synthetic opening.")

    assert result.decision.status.value == "rejected"
    assert result.decision.eligible_for_rates is False
    assert "catalog_rarity_disagreement" in result.decision.reason_codes


def test_pipeline_rejects_extractor_rarity_that_disagrees_with_catalog() -> None:
    extraction = extractor_payload()
    extraction["hits"] = [
        {
            "card_name": "Synthetic Pikachu",
            "collector_number": "001/100",
            "rarity": "common",
            "quantity": 1,
            "confidence": 0.99,
            "evidence_reference": "pack frame 1",
        }
    ]
    validation = validator_payload()
    validation["observed"]["hits"] = [
        {
            "card_name": "Synthetic Pikachu",
            "collector_number": "001/100",
            "rarity_key": "common",
            "quantity": 1,
        }
    ]
    validator = FixtureAIProvider([validation])
    pipeline = EvidencePipeline(
        extractor=AIExtractor(FixtureAIProvider([extraction])),
        validator=AIValidator(validator),
        catalog=InMemoryCatalogMatcher(
            sets=[CatalogSet("sv2", "Paldea Evolved")],
            cards=[
                CatalogCard(
                    "card-1",
                    "sv2",
                    "Synthetic Pikachu",
                    "001/100",
                    "rare",
                )
            ],
        ),
    )

    result = pipeline.process("Synthetic opening.")

    assert result.decision.status.value == "rejected"
    assert result.decision.eligible_for_rates is False
    assert "catalog_rarity_disagreement" in result.decision.reason_codes
    assert validator.remaining == 1


def test_resolution_rejects_rarity_disagreement_between_extractor_and_validator() -> None:
    extraction_payload = extractor_payload()
    extraction_payload["hits"] = [
        {
            "card_name": "Synthetic Pikachu",
            "collector_number": "001/100",
            "rarity": "rare",
            "quantity": 1,
            "confidence": 0.99,
            "evidence_reference": "pack frame 1",
        }
    ]
    validation_payload = validator_payload()
    validation_payload["observed"]["hits"] = [
        {
            "card_name": "Synthetic Pikachu",
            "collector_number": "001/100",
            "rarity_key": "common",
            "quantity": 1,
        }
    ]

    decision = resolve_evidence(
        ExtractorOutput.from_mapping(extraction_payload),
        ValidatorOutput.from_mapping(validation_payload),
    )

    assert decision.status.value == "rejected"
    assert decision.eligible_for_rates is False
    assert "unresolved_disagreement" in decision.reason_codes


def test_pipeline_rejects_validator_observations_that_disagree_with_extractor() -> None:
    validation = validator_payload()
    validation["observed"]["pack_count"] = 5

    result = _pipeline(extractor_payload(), validation).process("Synthetic opening.")

    assert result.decision.status.value == "rejected"
    assert result.decision.eligible_for_rates is False
    assert "unresolved_disagreement" in result.decision.reason_codes


def test_pipeline_rejects_validator_completeness_disagreement() -> None:
    validation = validator_payload()
    validation["observed"]["is_complete"] = False

    result = _pipeline(extractor_payload(), validation).process("Synthetic opening.")

    assert result.decision.status.value == "rejected"
    assert result.decision.eligible_for_rates is False
    assert "unresolved_disagreement" in result.decision.reason_codes


@pytest.mark.parametrize("country_code", ["US", "JP", "GB"])
def test_pipeline_accepts_complete_supported_global_country_facts(country_code: str) -> None:
    extraction = extractor_payload()
    extraction["location"]["country_code"] = country_code
    validation = validator_payload()
    validation["observed"]["country_code"] = country_code

    result = _pipeline(extraction, validation).process("Synthetic complete global opening.")

    assert result.decision.status.value == "accepted"
    assert result.decision.eligible_for_rates is True
    assert "outside_scope_country" not in result.decision.reason_codes


def test_pipeline_rejects_unsupported_product_before_validator() -> None:
    extraction = extractor_payload()
    extraction["product"]["type"] = "other"
    validator = FixtureAIProvider([validator_payload()])
    pipeline = EvidencePipeline(
        extractor=AIExtractor(FixtureAIProvider([extraction])),
        validator=AIValidator(validator),
        catalog=InMemoryCatalogMatcher(sets=[CatalogSet("sv2", "Paldea Evolved")], cards=[]),
    )

    result = pipeline.process("Synthetic unsupported product opening.")

    assert result.decision.status.value == "rejected"
    assert result.decision.eligible_for_rates is False
    assert validator.remaining == 1


def test_pipeline_demotes_unresolved_country_instead_of_inventing_australia() -> None:
    extraction = extractor_payload()
    extraction["location"]["country_code"] = None
    validation = validator_payload()
    validation["observed"]["country_code"] = None

    result = _pipeline(extraction, validation).process("Synthetic opening without a country.")

    assert result.decision.status.value == "activity_only"
    assert result.decision.eligible_for_rates is False
    assert "country_unresolved" in result.decision.reason_codes
    assert result.decision.selected is not None
    assert result.decision.selected.country_code is None


@pytest.mark.parametrize("country_code", ["USA", "us"])
def test_country_prechecks_reject_non_iso_shaped_values(country_code: str) -> None:
    extraction = extractor_payload()
    extraction["location"]["country_code"] = country_code

    result = run_prechecks(ExtractorOutput.from_mapping(extraction))

    assert result.passed is False
    assert [issue.code for issue in result.issues] == ["invalid_country_code"]


@pytest.mark.parametrize("country_code", ["USA", "us"])
def test_validator_schema_rejects_non_iso_shaped_country_values(country_code: str) -> None:
    validation = validator_payload()
    validation["observed"]["country_code"] = country_code

    with pytest.raises(SchemaValidationError, match="country_code"):
        ValidatorOutput.from_mapping(validation)


def test_pipeline_demotes_incomplete_duplicate_or_validator_ineligible_evidence() -> None:
    cases: list[tuple[dict[str, object], dict[str, object], str]] = []
    incomplete = extractor_payload()
    incomplete["opening"]["is_complete"] = False
    incomplete_validation = validator_payload()
    incomplete_validation["observed"]["is_complete"] = False
    cases.append((incomplete, incomplete_validation, "incomplete_opening"))
    duplicate = validator_payload()
    duplicate["duplicate_suspected"] = True
    cases.append((extractor_payload(), duplicate, "duplicate_suspected"))
    ineligible = validator_payload()
    ineligible["eligible_for_statistics"] = False
    cases.append((extractor_payload(), ineligible, "validator_ineligible"))

    for extraction, validation, expected_reason in cases:
        result = _pipeline(extraction, validation).process("Synthetic opening.")
        assert result.decision.status.value == "activity_only"
        assert result.decision.eligible_for_rates is False
        assert expected_reason in result.decision.reason_codes


def test_pipeline_demotes_incomplete_validator_field_coverage() -> None:
    validation = validator_payload()
    validation["field_checks"] = validation["field_checks"][:1]

    result = _pipeline(extractor_payload(), validation).process("Synthetic opening.")

    assert result.decision.status.value == "activity_only"
    assert result.decision.eligible_for_rates is False
    assert "validator_field_checks_incomplete" in result.decision.reason_codes


@pytest.mark.parametrize(
    ("field_status", "expected_status", "expected_reason"),
    [
        ("unsupported", "activity_only", "validator_field_unsupported"),
        ("contradicted", "rejected", "validator_field_contradicted"),
    ],
)
def test_pipeline_fails_closed_on_non_verified_validator_field_checks(
    field_status: str, expected_status: str, expected_reason: str
) -> None:
    validation = validator_payload()
    validation["field_checks"][0]["status"] = field_status

    result = _pipeline(extractor_payload(), validation).process("Synthetic opening.")

    assert result.decision.status.value == expected_status
    assert result.decision.eligible_for_rates is False
    assert expected_reason in result.decision.reason_codes


def test_pipeline_demotes_non_applicable_check_for_observed_statistics_fact() -> None:
    validation = validator_payload()
    validation["field_checks"][0]["status"] = "not_applicable"

    result = _pipeline(extractor_payload(), validation).process("Synthetic opening.")

    assert result.decision.status.value == "activity_only"
    assert result.decision.eligible_for_rates is False
    assert "validator_field_status_invalid" in result.decision.reason_codes


def test_pipeline_rejects_validator_field_below_field_confidence_threshold() -> None:
    validation = validator_payload(confidence=0.95)
    validation["field_checks"][0]["confidence"] = 0.84

    result = _pipeline(extractor_payload(), validation).process("Synthetic opening.")

    assert result.decision.status.value == "rejected"
    assert result.decision.eligible_for_rates is False
    assert "low_field_confidence" in result.decision.reason_codes


def test_pipeline_accepts_complete_australian_supported_agreement_for_statistics() -> None:
    result = _pipeline(extractor_payload(), validator_payload()).process(
        "Synthetic complete Australian booster bundle opening."
    )
    assert result.decision.status.value == "accepted"
    assert result.decision.eligible_for_rates is True
    assert result.decision.reason_codes == ()


def test_network_ai_provider_sends_a_finite_output_token_cap() -> None:
    captured: dict[str, object] = {}

    def transport(
        _url: str, _headers: dict[str, str], body: bytes, _timeout: float
    ) -> HTTPResponse:
        captured.update(json.loads(body))
        envelope = {
            "id": "fixture-response",
            "choices": [{"message": {"content": json.dumps(extractor_payload())}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
        }
        return HTTPResponse(200, json.dumps(envelope).encode())

    provider = OpenAICompatibleProvider(
        api_key="fixture-key",
        model="fixture-model",
        transport=transport,
    )
    request = AIRequest(
        operation="extract",
        system_prompt="synthetic",
        input_text="synthetic",
        schema_name="extractor_output",
        schema=ExtractorOutput.json_schema(),
        decoder=ExtractorOutput.from_mapping,
    )

    provider.complete(request)

    assert captured["max_completion_tokens"] == 4096


def test_settings_reject_internal_ai_retries_that_could_escape_one_reservation() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            ai_provider="openai_compatible",
            ai_base_url="https://ai.example.test/v1",
            ai_api_key="fixture-secret",
            ai_extract_model="fixture-extractor",
            ai_validate_model="fixture-validator",
            ai_escalate_model="fixture-escalator",
            ai_input_per_million_aud=Decimal("1"),
            ai_output_per_million_aud=Decimal("1"),
            ai_max_retries=1,
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "file:///tmp/provider",
        "http://api.example.com/v1",
        "https://user:password@api.example.com/v1",
        "https://api.example.com/v1?token=secret",
        "https://api.example.com/v1#fragment",
    ],
)
def test_network_ai_provider_rejects_unsafe_base_urls(base_url: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        OpenAICompatibleProvider(api_key="fixture-key", model="fixture-model", base_url=base_url)


def test_default_ai_transport_does_not_follow_redirects() -> None:
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
            requests.append(self.path)
            if self.path == "/start":
                self.send_response(302)
                self.send_header(
                    "Location",
                    f"http://127.0.0.1:{self.server.server_port}/redirect-target",
                )
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"redirect followed")

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
            requests.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"redirect followed")

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = UrllibHTTPTransport()(
            f"http://127.0.0.1:{server.server_port}/start",
            {"Content-Type": "application/json"},
            b"{}",
            2.0,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert response.status == 302
    assert requests == ["/start"]


def test_default_ai_transport_rejects_oversized_response_without_unbounded_read() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
            self.send_response(200)
            self.send_header("Content-Length", "65")
            self.end_headers()
            self.wfile.write(b"x" * 65)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(AIResponseError, match="byte cap"):
            UrllibHTTPTransport(max_response_bytes=64)(
                f"http://127.0.0.1:{server.server_port}/response",
                {"Content-Type": "application/json"},
                b"{}",
                2.0,
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
