from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from pokecrack_worker.collectors.base import (
    PUBLIC_COLLECTOR_USER_AGENT,
    CollectionService,
    FetchResponse,
)
from pokecrack_worker.collectors.scrapling.adapters.public_studies import (
    POKESHOW_GUATEMALA_MEGA_EVOLUTION_EVIDENCE_EXCERPT,
    POKESHOW_GUATEMALA_MEGA_EVOLUTION_EVIDENCE_SHA256,
    POKESHOW_GUATEMALA_MEGA_EVOLUTION_POLICY_CONFIG,
    TCG_MARKET_PANAMA_CHAOS_RISING_EVIDENCE_EXCERPT,
    TCG_MARKET_PANAMA_CHAOS_RISING_EVIDENCE_SHA256,
    TCG_MARKET_PANAMA_CHAOS_RISING_POLICY_CONFIG,
    TCG_MARKET_PANAMA_PITCH_BLACK_EVIDENCE_EXCERPT,
    TCG_MARKET_PANAMA_PITCH_BLACK_EVIDENCE_SHA256,
    TCG_MARKET_PANAMA_PITCH_BLACK_POLICY_CONFIG,
    RobotsTxtChecker,
    pokeshow_guatemala_megaevolution_adapter,
    tcg_market_panama_chaos_rising_adapter,
    tcg_market_panama_pitch_black_adapter,
)
from pokecrack_worker.collectors.scrapling.registry import build_live_static_registry
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.config.source_policy import SourcePolicy, SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]
ROBOTS_URL = "https://www.youtube.com/robots.txt"
DATABASE_MIGRATION = (
    ROOT / "supabase" / "migrations" / "20261009000000_panama_guatemala_youtube_coverage.sql"
).read_text(encoding="utf-8")


class FixtureHTTPClient:
    def __init__(self, responses: Mapping[str, FetchResponse]) -> None:
        self.responses = dict(responses)
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls.append((url, timeout_seconds))
        return self.responses[url]


def _html(url: str, body: str) -> FetchResponse:
    return FetchResponse(
        status_code=200,
        url=url,
        headers={"content-type": "text/html; charset=utf-8"},
        body=body.encode("utf-8"),
    )


def _policy(source_key: str) -> SourcePolicy:
    document = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    return SourcePolicy.model_validate(document["sources"][source_key])


AMERICAS_STUDIES = (
    {
        "source_key": "www.youtube.com#tcg-market-panama-chaos-rising-6",
        "study_key": "tcg-market-chaos-rising-pa-6-v1",
        "adapter_factory": tcg_market_panama_chaos_rising_adapter,
        "policy_config": TCG_MARKET_PANAMA_CHAOS_RISING_POLICY_CONFIG,
        "fixture": "tcg_market_panama_chaos_rising_youtube.html",
        "excerpt": TCG_MARKET_PANAMA_CHAOS_RISING_EVIDENCE_EXCERPT,
        "sha256": TCG_MARKET_PANAMA_CHAOS_RISING_EVIDENCE_SHA256,
        "title": "¡Nuestro PRIMER OPENING de Pokémon TCG! ¿Vale la pena Chaos Rising Booster Bundle?",
        "video_id": "fHQpNECg4y4",
        "channel_id": "UCa68xVUUIKE8dvcfxCcdyrQ",
        "observed_at": datetime(2026, 8, 3, 0, 15, 39, tzinfo=UTC),
        "country_code": "PA",
        "set_language": "und",
        "set_language_basis": "source_does_not_state_card_language",
        "pack_count": 6,
        "official_url": "https://www.pokemon.com/us/pokemon-tcg/product-gallery/mega-evolution-chaos-rising-booster-bundle",
    },
    {
        "source_key": "www.youtube.com#tcg-market-panama-pitch-black-4",
        "study_key": "tcg-market-pitch-black-pa-4-v1",
        "adapter_factory": tcg_market_panama_pitch_black_adapter,
        "policy_config": TCG_MARKET_PANAMA_PITCH_BLACK_POLICY_CONFIG,
        "fixture": "tcg_market_panama_pitch_black_youtube.html",
        "excerpt": TCG_MARKET_PANAMA_PITCH_BLACK_EVIDENCE_EXCERPT,
        "sha256": TCG_MARKET_PANAMA_PITCH_BLACK_EVIDENCE_SHA256,
        "title": "¡Abrimos la Build & Battle de Pitch Black! ¿Nos salió una carta increíble? | Pokémon TCG",
        "video_id": "6kb1MvcnMJE",
        "channel_id": "UCa68xVUUIKE8dvcfxCcdyrQ",
        "observed_at": datetime(2026, 8, 5, 19, 9, 10, tzinfo=UTC),
        "country_code": "PA",
        "set_language": "und",
        "set_language_basis": "source_does_not_state_card_language",
        "pack_count": 4,
        "official_url": "https://www.pokemon.com/us/news/pokemon-tcg-mega-evolution-pitch-black-product-showcase",
    },
    {
        "source_key": "www.youtube.com#pokeshow-guatemala-megaevolution-3",
        "study_key": "pokeshow-mega-evolution-gt-3-v1",
        "adapter_factory": pokeshow_guatemala_megaevolution_adapter,
        "policy_config": POKESHOW_GUATEMALA_MEGA_EVOLUTION_POLICY_CONFIG,
        "fixture": "pokeshow_guatemala_megaevolution_youtube.html",
        "excerpt": POKESHOW_GUATEMALA_MEGA_EVOLUTION_EVIDENCE_EXCERPT,
        "sha256": POKESHOW_GUATEMALA_MEGA_EVOLUTION_EVIDENCE_SHA256,
        "title": "🦆 El Poder del Pato 💪 | Apertura MegaEvolution + Noticias y Pokeguamazos | PokéShow de Maddi",
        "video_id": "DWRdhUuIUvI",
        "channel_id": "UChG8m-xoKqrXJDCEoE2i9Jg",
        "observed_at": datetime(2025, 10, 6, 17, 21, 33, tzinfo=UTC),
        "country_code": "GT",
        "set_language": "und",
        "set_language_basis": "source_does_not_state_card_language",
        "pack_count": 3,
        "official_url": "https://www.pokemoncenter.com/search/megacards",
    },
)


def test_central_america_worker_configs_are_pinned_in_database_migration() -> None:
    migration_configs = [
        json.loads(match.group(1))
        for match in re.finditer(r"'(\{.*?\})'::jsonb", DATABASE_MIGRATION, re.DOTALL)
    ]

    for study in AMERICAS_STUDIES:
        assert _policy(str(study["source_key"])).config in migration_configs


@pytest.mark.parametrize("study", AMERICAS_STUDIES, ids=lambda study: str(study["study_key"]))
def test_central_america_coverage_is_hash_pinned_and_language_unknown(
    study: Mapping[str, object],
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[str(study["study_key"])]
    policy = _policy(str(study["source_key"]))
    body = (ROOT / "services" / "worker" / "fixtures" / str(study["fixture"])).read_text(
        encoding="utf-8"
    )
    factory = study["adapter_factory"]
    candidate = factory(  # type: ignore[operator]
        client=FixtureHTTPClient({identity.fetch_url: _html(identity.fetch_url, body)})
    ).collect(identity.fetch_url, policy)[0]

    assert policy.config == study["policy_config"]
    assert policy.config["country_code"] == study["country_code"]
    assert policy.config["set_language"] == study["set_language"] == "und"
    assert policy.config["set_language_basis"] == study["set_language_basis"]
    assert policy.config["pack_count"] == study["pack_count"]
    assert policy.config["set_official_url"] == study["official_url"]
    assert policy.config["denominator_basis"] == "source_product_opening_plus_official_product_spec"
    assert policy.config["denominator_complete"] is True
    assert (
        not {
            "qualifying_hit_pack_count",
            "qualifying_metric",
            "metric_version",
        }
        & policy.config.keys()
    )
    assert candidate.external_id == study["video_id"]
    assert candidate.source_url == identity.fetch_url
    assert candidate.title == study["title"]
    assert candidate.published_at == study["observed_at"]
    assert candidate.text == study["excerpt"]
    assert candidate.content_sha256 == study["sha256"]
    assert candidate.media_urls == ()
    assert candidate.metadata == {
        "study_key": str(study["study_key"]),
        "parser_version": identity.parser_version,
    }


@pytest.mark.parametrize("study", AMERICAS_STUDIES, ids=lambda study: str(study["study_key"]))
def test_central_america_live_route_is_exact_and_static_only(
    study: Mapping[str, object],
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[str(study["study_key"])]
    policy = _policy(str(study["source_key"]))
    fixture_path = ROOT / "services" / "worker" / "fixtures" / str(study["fixture"])
    client = FixtureHTTPClient(
        {
            ROBOTS_URL: FetchResponse(
                status_code=200,
                url=ROBOTS_URL,
                headers={"content-type": "text/plain; charset=utf-8"},
                body=b"User-agent: *\nAllow: /watch\n",
            ),
            identity.fetch_url: _html(
                identity.fetch_url,
                fixture_path.read_text(encoding="utf-8"),
            ),
        }
    )
    service = CollectionService(
        policies=SourcePolicyRegistry([policy]),
        http_adapters=build_live_static_registry(http_client=client),
        robots=RobotsTxtChecker(client=client, followup_delay_seconds=0),
    )

    candidates = service.collect_url(identity.fetch_url, route="static")

    assert len(candidates) == 1
    assert client.calls == [(ROBOTS_URL, 30.0), (identity.fetch_url, 30.0)]
    assert PUBLIC_COLLECTOR_USER_AGENT
    assert candidates[0].media_urls == ()


def test_central_america_youtube_policies_fail_closed_outside_exact_reviewed_urls() -> None:
    registry = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml")

    for study in AMERICAS_STUDIES:
        identity = PUBLIC_STUDIES_BY_KEY[str(study["study_key"])]
        assert registry.resolve(identity.fetch_url).config == study["policy_config"]
        assert registry.allows(identity.fetch_url, "static")
        assert not registry.allows(f"{identity.fetch_url}&si=unreviewed", "static")

    assert not registry.allows("https://www.youtube.com/watch?v=unreviewed", "static")
