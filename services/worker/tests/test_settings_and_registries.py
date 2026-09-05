from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pokecrack_worker.collectors.scrapling.adapters.public_studies import TCGTALK_POLICY_CONFIG
from pokecrack_worker.config.registries import (
    REQUIRED_YOUTUBE_QUERIES,
    RarityTaxonomy,
    YouTubeQueryRegistry,
)
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
        "NOSTR_SUPABASE_DB_URL",
        "BLUESKY_SUPABASE_DB_URL",
        "AI_API_KEY",
        "AI_EXTRACT_MODEL",
        "AI_VALIDATE_MODEL",
        "AI_ESCALATE_MODEL",
        "YOUTUBE_API_KEY",
        "MATON_API_KEY",
        "YOUTUBE_MATON_CONNECTION_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.data_mode is DataMode.DEMO
    assert settings.ai_provider is AIProviderName.FIXTURE
    assert settings.supabase_db_url is None
    assert settings.nostr_supabase_db_url is None
    assert settings.bluesky_supabase_db_url is None
    assert settings.youtube_api_key is None
    assert settings.maton_api_key is None
    assert settings.youtube_maton_connection_id is None
    assert settings.youtube_collection_enabled is False
    assert settings.public_study_collection_enabled is False
    assert settings.scrapling_save_raw_html is False
    assert settings.scrapling_dynamic_enabled is False
    assert settings.worker_max_concurrency == 1
    assert settings.ai_max_text_chars == 20_000
    assert settings.scrapling_max_raw_text_chars == 20_000
    assert settings.schedule_catalog_sync == "0 2,14 * * *"


def test_live_and_http_ai_modes_fail_closed_without_required_configuration() -> None:
    with pytest.raises(ValidationError, match="SUPABASE_DB_URL"):
        Settings(_env_file=None, data_mode="live")

    with pytest.raises(ValidationError, match="AI_API_KEY.*AI_EXTRACT_MODEL"):
        Settings(_env_file=None, ai_provider="http")


def test_nostr_role_requires_only_its_dedicated_live_database_and_flag() -> None:
    with pytest.raises(ValidationError, match="NOSTR_SUPABASE_DB_URL"):
        Settings(
            _env_file=None,
            data_mode="live",
            worker_id="nostr-collector-test",
            worker_role="nostr-collector",
            nostr_collection_enabled=True,
        )

    settings = Settings(
        _env_file=None,
        data_mode="live",
        worker_id="nostr-collector-test",
        worker_role="nostr-collector",
        nostr_collection_enabled=True,
        nostr_supabase_db_url="postgresql://nostr.example.invalid/pokecrack",
    )
    assert settings.supabase_db_url is None
    assert settings.nostr_supabase_db_url is not None

    with pytest.raises(ValidationError, match="requires NOSTR_COLLECTION_ENABLED"):
        Settings(
            _env_file=None,
            worker_id="nostr-collector-test",
            worker_role="nostr-collector",
            nostr_supabase_db_url="postgresql://nostr.example.invalid/pokecrack",
        )

    with pytest.raises(ValidationError, match="allows only NOSTR_COLLECTION_ENABLED"):
        Settings(
            _env_file=None,
            worker_id="nostr-collector-test",
            worker_role="nostr-collector",
            nostr_collection_enabled=True,
            mastodon_collection_enabled=True,
            nostr_supabase_db_url="postgresql://nostr.example.invalid/pokecrack",
        )


def test_bluesky_role_requires_only_its_dedicated_live_database_and_flag() -> None:
    with pytest.raises(ValidationError, match="BLUESKY_SUPABASE_DB_URL"):
        Settings(
            _env_file=None,
            data_mode="live",
            worker_id="bluesky-collector-test",
            worker_role="bluesky-collector",
            bluesky_collection_enabled=True,
        )

    settings = Settings(
        _env_file=None,
        data_mode="live",
        worker_id="bluesky-collector-test",
        worker_role="bluesky-collector",
        bluesky_collection_enabled=True,
        bluesky_supabase_db_url="postgresql://bluesky.example.invalid/pokecrack",
    )
    assert settings.supabase_db_url is None
    assert settings.nostr_supabase_db_url is None
    assert settings.bluesky_supabase_db_url is not None

    with pytest.raises(ValidationError, match="requires BLUESKY_COLLECTION_ENABLED"):
        Settings(
            _env_file=None,
            worker_id="bluesky-collector-test",
            worker_role="bluesky-collector",
            bluesky_supabase_db_url="postgresql://bluesky.example.invalid/pokecrack",
        )

    with pytest.raises(ValidationError, match="allows only BLUESKY_COLLECTION_ENABLED"):
        Settings(
            _env_file=None,
            worker_id="bluesky-collector-test",
            worker_role="bluesky-collector",
            bluesky_collection_enabled=True,
            mastodon_collection_enabled=True,
            bluesky_supabase_db_url="postgresql://bluesky.example.invalid/pokecrack",
        )


def test_bluesky_role_rejects_worker_ids_outside_the_database_contract() -> None:
    with pytest.raises(ValidationError, match="WORKER_ID matching"):
        Settings(
            _env_file=None,
            worker_id="worker-1",
            worker_role="bluesky-collector",
            bluesky_collection_enabled=True,
            bluesky_supabase_db_url="postgresql://bluesky.example.invalid/pokecrack",
        )


def test_nostr_role_rejects_worker_ids_outside_the_database_contract() -> None:
    with pytest.raises(ValidationError, match="WORKER_ID matching"):
        Settings(
            _env_file=None,
            worker_id="worker-1",
            worker_role="nostr-collector",
            nostr_collection_enabled=True,
            nostr_supabase_db_url="postgresql://nostr.example.invalid/pokecrack",
        )


@pytest.mark.parametrize("role", (None, "collector", "scheduler", "watchdog"))
def test_shared_roles_cannot_enable_nostr_collection(role: str | None) -> None:
    with pytest.raises(ValidationError, match="NOSTR_COLLECTION_ENABLED.*collector"):
        Settings(
            _env_file=None,
            worker_role=role,
            nostr_collection_enabled=True,
            supabase_db_url="postgresql://db.example.invalid/pokecrack",
        )


def test_youtube_enablement_requires_one_credential_path_only_in_the_collector() -> None:
    with pytest.raises(ValidationError, match="YOUTUBE_API_KEY or Maton OAuth"):
        Settings(_env_file=None, youtube_collection_enabled=True, worker_role="collector")
    with pytest.raises(ValidationError, match="YOUTUBE_API_KEY or Maton OAuth"):
        Settings(
            _env_file=None,
            youtube_collection_enabled=True,
            youtube_api_key="   ",
            worker_role="collector",
        )

    scheduler = Settings(
        _env_file=None,
        youtube_collection_enabled=True,
        worker_role="scheduler",
    )
    assert scheduler.youtube_api_key is None

    maton = Settings(
        _env_file=None,
        youtube_collection_enabled=True,
        maton_api_key="fixture-maton-secret",
        youtube_maton_connection_id="ba16a50a-9e24-4fb6-9ce3-6cf7d52643da",
        worker_role="collector",
    )
    assert maton.youtube_api_key is None
    assert maton.maton_api_key is not None
    assert str(maton.youtube_maton_connection_id) == "ba16a50a-9e24-4fb6-9ce3-6cf7d52643da"


def test_youtube_rejects_partial_or_ambiguous_maton_configuration() -> None:
    with pytest.raises(ValidationError, match="configured together"):
        Settings(_env_file=None, maton_api_key="fixture-maton-secret")
    with pytest.raises(ValidationError, match="configured together"):
        Settings(
            _env_file=None,
            youtube_maton_connection_id="ba16a50a-9e24-4fb6-9ce3-6cf7d52643da",
        )
    with pytest.raises(ValidationError, match="exactly one YouTube credential path"):
        Settings(
            _env_file=None,
            youtube_api_key="fixture-youtube-secret",
            maton_api_key="fixture-maton-secret",
            youtube_maton_connection_id="ba16a50a-9e24-4fb6-9ce3-6cf7d52643da",
        )
    with pytest.raises(ValidationError, match="must not be the nil UUID"):
        Settings(
            _env_file=None,
            maton_api_key="fixture-maton-secret",
            youtube_maton_connection_id="00000000-0000-0000-0000-000000000000",
        )


def test_blank_optional_credentials_and_connection_id_normalize_to_missing() -> None:
    settings = Settings(
        _env_file=None,
        youtube_api_key="  ",
        maton_api_key="\t",
        youtube_maton_connection_id="  ",
    )

    assert settings.youtube_api_key is None
    assert settings.maton_api_key is None
    assert settings.youtube_maton_connection_id is None


def test_public_study_enablement_requires_scrapling_and_exact_daily_schedule() -> None:
    with pytest.raises(ValidationError, match="SCRAPLING_ENABLED"):
        Settings(
            _env_file=None,
            public_study_collection_enabled=True,
            scrapling_enabled=False,
            worker_role="collector",
        )
    with pytest.raises(ValidationError, match="SCHEDULE_PUBLIC_COLLECTION"):
        Settings(
            _env_file=None,
            public_study_collection_enabled=True,
            worker_role="scheduler",
            schedule_public_collection="0 4 * * *",
        )

    scheduler = Settings(
        _env_file=None,
        public_study_collection_enabled=True,
        scrapling_enabled=False,
        worker_role="scheduler",
    )
    assert scheduler.public_study_collection_enabled is True


@pytest.mark.parametrize(
    ("field", "schedule"),
    (
        ("schedule_official_api", "* * * * *"),
        ("schedule_official_api", "0 */12 * * *"),
        ("schedule_official_api", " 0 */6 * * *"),
        ("schedule_official_api", "0 */6 * * * "),
        ("schedule_cleanup", "30 3 * * 0"),
        ("schedule_cleanup", " 30 3 * * *"),
        ("schedule_cleanup", "30 3 * * * "),
    ),
)
def test_youtube_enablement_rejects_collection_or_retention_schedule_drift(
    field: str,
    schedule: str,
) -> None:
    expected_name = (
        "SCHEDULE_OFFICIAL_API" if field == "schedule_official_api" else "SCHEDULE_CLEANUP"
    )
    with pytest.raises(ValidationError, match=expected_name):
        Settings(
            _env_file=None,
            youtube_collection_enabled=True,
            worker_role="scheduler",
            **{field: schedule},
        )


@pytest.mark.parametrize(
    "schedule",
    ("30 3 * * 0", " 30 3 * * *", "30 3 * * * "),
)
def test_bluesky_enablement_rejects_retention_schedule_drift(schedule: str) -> None:
    with pytest.raises(ValidationError, match="BLUESKY_COLLECTION_ENABLED.*SCHEDULE_CLEANUP"):
        Settings(
            _env_file=None,
            worker_id="bluesky-collector-test",
            worker_role="bluesky-collector",
            bluesky_collection_enabled=True,
            bluesky_supabase_db_url="postgresql://bluesky.example.invalid/pokecrack",
            schedule_cleanup=schedule,
        )


def test_worker_concurrency_above_one_is_rejected_until_pooling_is_implemented() -> None:
    with pytest.raises(ValidationError, match="worker_max_concurrency"):
        Settings(_env_file=None, worker_max_concurrency=2)


def test_raw_html_env_false_parses_but_true_remains_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCRAPLING_SAVE_RAW_HTML", "false")
    assert Settings(_env_file=None).scrapling_save_raw_html is False

    monkeypatch.setenv("SCRAPLING_SAVE_RAW_HTML", "true")
    with pytest.raises(ValidationError, match="SCRAPLING_SAVE_RAW_HTML must remain false"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("field", "drifted_value"),
    (
        ("metadata_only", False),
        ("max_results", 50),
        ("published_within_days", 3650),
        ("order", "relevance"),
    ),
)
def test_youtube_version_one_registry_rejects_query_parameter_drift(
    field: str,
    drifted_value: object,
) -> None:
    queries = [
        {
            "name": name,
            "query": query,
            "enabled": False,
            "metadata_only": True,
            "max_results": 25,
            "published_within_days": 30,
            "order": "date",
        }
        for name, query in REQUIRED_YOUTUBE_QUERIES
    ]
    queries[0][field] = drifted_value

    with pytest.raises(ValidationError):
        YouTubeQueryRegistry.from_mapping(
            {
                "version": 1,
                "default_enabled": False,
                "queries": queries,
            }
        )


@pytest.mark.parametrize(
    "values",
    (
        {"worker_lease_seconds": 59},
        {"worker_lease_seconds": 86_401},
        {"worker_max_attempts": 101},
    ),
)
def test_worker_queue_settings_match_the_database_rpc_bounds(values: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


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
    tcgdex = sources.require("https://api.tcgdex.net/v2/en/sets", "catalog")
    assert tcgdex.metadata_only
    assert tcgdex.min_delay_seconds == 10
    assert tcgdex.max_pages_per_run == 1
    assert tcgdex.max_concurrency == 1
    assert tcgdex.requests_per_minute == 6
    assert tcgdex.config == {"collector_version": "tcgdex-sets-v1"}
    comicbook = sources.require(
        "https://comicbook.com/gaming/feature/"
        "pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates",
        "static",
    )
    wargamer = sources.require(
        "https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview",
        "static",
    )
    cardchill = sources.require(
        "https://cardchill.com/article/"
        "ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real",
        "static",
    )
    bleedingcool = sources.require(
        "https://bleedingcool.com/games/"
        "opening-pokemon-tcg-mega-evolution-phantasmal-flames-products/",
        "static",
    )
    tcgtalk = sources.require(
        "https://tcgtalk.com/blog/"
        "perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232",
        "static",
    )
    assert comicbook.config["study_key"] == "comicbook-perfect-order-us-55-v1"
    assert comicbook.config["pack_count"] == 55
    assert comicbook.config["qualifying_hit_pack_count"] == 1
    assert wargamer.config["study_key"] == "wargamer-chaos-rising-gb-17-v1"
    assert wargamer.config["pack_count"] == 17
    assert wargamer.config["qualifying_hit_pack_count"] == 0
    assert cardchill.config["study_key"] == "cardchill-ascended-heroes-gb-90-v1"
    assert cardchill.config["pack_count"] == 90
    assert cardchill.config["qualifying_hit_pack_count"] == 1
    assert cardchill.config["product_scope"] == "etb"
    assert bleedingcool.config["study_key"] == "bleedingcool-phantasmal-flames-us-36-v1"
    assert bleedingcool.config["pack_count"] == 36
    assert bleedingcool.config["qualifying_hit_pack_count"] == 1
    assert bleedingcool.config["product_scope"] == "booster_box"
    assert tcgtalk.config["study_key"] == "tcgtalk-perfect-order-sg-54-v1"
    assert tcgtalk.config["country_code"] == "SG"
    assert tcgtalk.config["country_name"] == "Singapore"
    assert tcgtalk.config["geography_basis"] == "publisher_country"
    assert tcgtalk.config["geography_confidence"] == "tier_b"
    assert tcgtalk.config["set_external_id"] == "me03"
    assert tcgtalk.config["product_scope"] == "booster_bundle"
    assert tcgtalk.config["pack_count"] == 54
    assert tcgtalk.config["qualifying_hit_pack_count"] == 1
    assert tcgtalk.config["observed_at"] == "2026-03-25T12:40:00Z"
    assert tcgtalk.config == TCGTALK_POLICY_CONFIG
    assert all(
        policy.statistics_eligible_default
        and policy.metadata_only is False
        and policy.retain_raw_html is False
        and policy.min_delay_seconds == 30
        and policy.max_pages_per_run == 2
        and policy.max_concurrency == 1
        for policy in (comicbook, wargamer, cardchill, bleedingcool, tcgtalk)
    )
    youtube_api = sources.require("https://youtube.googleapis.com/youtube/v3/search", "youtube")
    assert youtube_api.metadata_only
    assert youtube_api.retention_days == 28
    assert youtube_api.max_pages_per_run == 1
    assert youtube_api.config == {
        "metadata_only": True,
        "media_download": False,
        "max_response_bytes": 2_097_152,
        "query_allowlist": [name for name, _query in REQUIRED_YOUTUBE_QUERIES],
    }
    youtube_identity = sources.resolve("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert youtube_identity.enabled is True
    assert youtube_identity.retention_days == 730
    assert youtube_identity.adapter == "richards_bricks_charizard_upc_study"
    assert not sources.allows("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "static")
    assert sources.allows("https://www.youtube.com/watch?v=OON-ICjlrd4", "static")

    assert queries.default_enabled is False
    assert len(queries.queries) == 5
    assert all(query.metadata_only for query in queries.queries)
    assert all(query.enabled is False and query.region_code is None for query in queries.queries)
    assert queries.require("pokemon-tcg-pack-opening").query == "Pokemon TCG pack opening"
    assert taxonomy.baseline_priority == (
        ("set_id", "language", "product_type"),
        ("set_id", "language"),
        ("set_id",),
    )
    assert {"special_illustration_rare", "hyper_rare"} <= set(taxonomy.chase_categories)
    assert taxonomy.resolve("Special Illustration Rare").key == "special_illustration_rare"
    assert taxonomy.resolve("not-a-real-rarity").key == "unknown"
