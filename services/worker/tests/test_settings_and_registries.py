from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pokecrack_worker.config.registries import RarityTaxonomy, YouTubeQueryRegistry
from pokecrack_worker.config.settings import AIProviderName, DataMode, Settings
from pokecrack_worker.config.source_policy import (
    CollectorRoute,
    InMemoryPolicyAuditSink,
    PolicyDeniedError,
    SourcePolicy,
    SourcePolicyRegistry,
)
from pokecrack_worker.models import CollectorType

ROOT = Path(__file__).resolve().parents[3]


def test_settings_default_to_network_free_demo_fixture_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "DATA_MODE",
        "AI_PROVIDER",
        "SUPABASE_DB_URL",
        "AI_API_KEY",
        "AI_EXTRACT_MODEL",
        "AI_VALIDATE_MODEL",
        "AI_ESCALATE_MODEL",
        "YOUTUBE_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.data_mode is DataMode.DEMO
    assert settings.ai_provider is AIProviderName.FIXTURE
    assert settings.supabase_db_url is None
    assert settings.youtube_api_key is None
    assert settings.scrapling_save_raw_html is False
    assert settings.scrapling_dynamic_enabled is False
    assert settings.worker_max_concurrency == 1
    assert settings.ai_max_text_chars == 20_000
    assert settings.scrapling_max_raw_text_chars == 20_000


def test_live_and_http_ai_modes_fail_closed_without_required_configuration() -> None:
    with pytest.raises(ValidationError, match="SUPABASE_DB_URL"):
        Settings(_env_file=None, data_mode="live")

    with pytest.raises(ValidationError, match="AI_API_KEY.*AI_EXTRACT_MODEL"):
        Settings(_env_file=None, ai_provider="http")


def test_worker_concurrency_above_one_is_rejected_until_pooling_is_implemented() -> None:
    with pytest.raises(ValidationError, match="worker_max_concurrency"):
        Settings(_env_file=None, worker_max_concurrency=2)


def test_network_ai_mode_requires_nonzero_cost_rates_for_budget_accounting() -> None:
    with pytest.raises(ValidationError, match="AI_INPUT_PER_MILLION_AUD"):
        Settings(
            _env_file=None,
            ai_provider="openai_compatible",
            ai_api_key="fixture-secret",
            ai_extract_model="extract",
            ai_validate_model="validate",
            ai_escalate_model="escalate",
        )


def test_unknown_and_disabled_sources_emit_auditable_fail_closed_denials() -> None:
    audit = InMemoryPolicyAuditSink()
    registry = SourcePolicyRegistry(
        [SourcePolicy(domain="disabled.example", enabled=False, routes={"static"})],
        audit_sink=audit,
    )

    with pytest.raises(PolicyDeniedError) as unknown:
        registry.require("https://unknown.example/opening/1", CollectorRoute.STATIC)
    with pytest.raises(PolicyDeniedError) as disabled:
        registry.require("https://disabled.example/opening/1", CollectorRoute.STATIC)

    assert unknown.value.event.reason == "unknown_domain"
    assert disabled.value.event.reason == "source_disabled"
    assert [event.outcome for event in audit.events] == ["denied", "denied"]
    assert all(event.event_type == "source_policy_decision" for event in audit.events)


def test_owned_policy_registries_are_explicit_and_safe_by_default() -> None:
    sources = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml")
    queries = YouTubeQueryRegistry.from_yaml(ROOT / "config" / "youtube-queries.yaml")
    taxonomy = RarityTaxonomy.from_yaml(ROOT / "config" / "rarity-taxonomy.yaml")

    assert sources.default == "disabled"
    public = sources.require("https://example.com/", "static")
    assert public.adapter == "example_public"
    assert public.collector is CollectorType.SCRAPLING_HTTP
    assert public.access_mode == "public"
    assert public.min_delay_seconds == 1
    assert public.max_pages_per_run == 1
    assert public.dynamic_allowed is False
    assert public.login_required is False
    assert public.statistics_eligible_default is False
    assert public.retention_days == 30
    assert public.version == "1"
    assert public.config == {}
    assert public.reason
    assert not sources.allows("https://disabled.example/item", "static")
    assert {policy.collector for policy in sources.policies} == set(CollectorType)
    reddit = sources.resolve("https://reddit.com/r/pkmntcg/comments/fixture")
    assert reddit.collector is CollectorType.OPENCLI_AUTHENTICATED
    assert reddit.login_required is True
    assert reddit.browser_profile == "social-western"
    assert reddit.statistics_eligible_default is False
    assert reddit.max_pages_per_run == 3
    bypass = sources.resolve("https://access-control-bypass.example/item")
    assert bypass.collector is CollectorType.DISABLED
    assert "bypass" in bypass.reason.casefold()
    assert sources.require("https://api.tcgdex.net/v2/en/sets", "catalog").metadata_only
    assert sources.require(
        "https://youtube.googleapis.com/youtube/v3/search", "youtube"
    ).metadata_only

    assert queries.default_enabled is False
    assert len(queries.queries) == 5
    assert all(query.metadata_only for query in queries.queries)
    assert taxonomy.baseline_priority == (
        ("set_id", "language", "product_type"),
        ("set_id", "language"),
        ("set_id",),
    )
    assert {"special_illustration_rare", "hyper_rare"} <= set(taxonomy.chase_categories)
    assert taxonomy.resolve("Special Illustration Rare").key == "special_illustration_rare"
    assert taxonomy.resolve("not-a-real-rarity").key == "unknown"
