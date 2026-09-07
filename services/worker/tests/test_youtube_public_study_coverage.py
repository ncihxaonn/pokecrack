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
    CollectorError,
    FetchResponse,
)
from pokecrack_worker.collectors.scrapling.adapters.public_studies import (
    INDIGO_GEEK_MEGA_EVIDENCE_EXCERPT,
    INDIGO_GEEK_MEGA_EVIDENCE_SHA256,
    INDIGO_GEEK_MEGA_POLICY_CONFIG,
    POKEHANNA_ASCENDED_HEROES_EVIDENCE_EXCERPT,
    POKEHANNA_ASCENDED_HEROES_EVIDENCE_SHA256,
    POKEHANNA_ASCENDED_HEROES_POLICY_CONFIG,
    RobotsTxtChecker,
    indigo_geek_megaevolucion_adapter,
    pokehanna_ascended_heroes_adapter,
)
from pokecrack_worker.collectors.scrapling.registry import build_live_static_registry
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.config.source_policy import SourcePolicy, SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]
ROBOTS_URL = "https://www.youtube.com/robots.txt"
DATABASE_MIGRATION = (
    ROOT / "supabase" / "migrations" / "20261008000000_canada_mexico_youtube_coverage.sql"
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
    raw_sources = document["sources"]
    raw_policy = raw_sources[source_key]
    return SourcePolicy.model_validate(raw_policy)


YOUTUBE_STUDIES = (
    {
        "source_key": "www.youtube.com#indigo-geek-mx-50",
        "study_key": "indigo-geek-megaevolucion-mx-50-v1",
        "adapter_factory": indigo_geek_megaevolucion_adapter,
        "policy_config": INDIGO_GEEK_MEGA_POLICY_CONFIG,
        "fixture": "indigo_geek_megaevolucion_youtube.html",
        "excerpt": INDIGO_GEEK_MEGA_EVIDENCE_EXCERPT,
        "sha256": INDIGO_GEEK_MEGA_EVIDENCE_SHA256,
        "title": "Abrimos 50 SOBRES de la nueva expansión de Pokémon JCC: Megaevolución",
        "video_id": "KNCSNJNcjJ8",
        "channel_id": "UCGri3BoVzarWIYCzg8MEQjw",
        "observed_at": datetime(2025, 9, 12, 13, 0, 41, tzinfo=UTC),
        "country_code": "MX",
        "pack_count": 50,
        "official_url": "https://tcg.pokemon.com/es-mx/expansions/mega-evolution/",
    },
    {
        "source_key": "www.youtube.com#pokehanna-ca-9",
        "study_key": "pokehanna-ascended-heroes-ca-9-v1",
        "adapter_factory": pokehanna_ascended_heroes_adapter,
        "policy_config": POKEHANNA_ASCENDED_HEROES_POLICY_CONFIG,
        "fixture": "pokehanna_ascended_heroes_youtube.html",
        "excerpt": POKEHANNA_ASCENDED_HEROES_EVIDENCE_EXCERPT,
        "sha256": POKEHANNA_ASCENDED_HEROES_EVIDENCE_SHA256,
        "title": "Opening The Ascended Heroes ETB! (Pokémon card opening)",
        "video_id": "Jj0IxqUYat8",
        "channel_id": "UC6stWaGoj-9rsEOzYv56ftQ",
        "observed_at": datetime(2026, 4, 5, 18, 0, 15, tzinfo=UTC),
        "country_code": "CA",
        "pack_count": 9,
        "official_url": "https://www.pokemon.com/us/pokemon-tcg/product-gallery/mega-evolution-ascended-heroes-elite-trainer-box",
    },
)


@pytest.mark.parametrize("study", YOUTUBE_STUDIES, ids=lambda study: str(study["study_key"]))
def test_youtube_coverage_adapters_emit_hash_pinned_metadata_only_facts(
    study: Mapping[str, object],
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[str(study["study_key"])]
    fixture_path = ROOT / "services" / "worker" / "fixtures" / str(study["fixture"])
    body = fixture_path.read_text(encoding="utf-8")
    policy = _policy(str(study["source_key"]))
    factory = study["adapter_factory"]
    assert callable(factory)

    candidate = factory(  # type: ignore[operator]
        client=FixtureHTTPClient({identity.fetch_url: _html(identity.fetch_url, body)})
    ).collect(identity.fetch_url, policy)[0]

    assert policy.config == study["policy_config"]
    assert policy.config["country_code"] == study["country_code"]
    assert policy.config["pack_count"] == study["pack_count"]
    assert policy.config["set_official_url"] == study["official_url"]
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
    assert len(candidate.text or "") <= 300
    assert candidate.content_sha256 == study["sha256"]
    assert candidate.media_urls == ()
    assert candidate.metadata == {
        "study_key": str(study["study_key"]),
        "parser_version": identity.parser_version,
    }


def test_youtube_duplicate_domain_config_uses_explicit_exact_fetch_urls() -> None:
    document = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    sources = document["sources"]
    expected = {
        "www.youtube.com#indigo-geek-mx-50": "https://www.youtube.com/watch?v=KNCSNJNcjJ8",
        "www.youtube.com#pokehanna-ca-9": "https://www.youtube.com/watch?v=Jj0IxqUYat8",
    }

    for key, fetch_url in expected.items():
        assert sources[key]["domain"] == "www.youtube.com"
        assert sources[key]["config"]["fetch_url"] == fetch_url
    assert len({sources[key]["config"]["fetch_url"] for key in expected}) == 2


def test_youtube_worker_configs_are_pinned_in_database_migration() -> None:
    migration_configs = [
        json.loads(match.group(1))
        for match in re.finditer(r"'(\{.*?\})'::jsonb", DATABASE_MIGRATION, re.DOTALL)
    ]
    for study in YOUTUBE_STUDIES:
        policy = _policy(str(study["source_key"]))
        assert policy.config in migration_configs


@pytest.mark.parametrize("study", YOUTUBE_STUDIES, ids=lambda study: str(study["study_key"]))
def test_youtube_coverage_collection_checks_robots_and_uses_static_watch_only(
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


@pytest.mark.parametrize("study", YOUTUBE_STUDIES, ids=lambda study: str(study["study_key"]))
def test_youtube_coverage_adapters_fail_closed_on_description_drift(
    study: Mapping[str, object],
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[str(study["study_key"])]
    fixture_path = ROOT / "services" / "worker" / "fixtures" / str(study["fixture"])
    body = fixture_path.read_text(encoding="utf-8")
    if str(study["study_key"]).startswith("indigo"):
        drifted = body.replace("50 sobres", "49 sobres", 1)
    else:
        drifted = body.replace("all the packs", "some packs", 1)
    policy = _policy(str(study["source_key"]))
    factory = study["adapter_factory"]
    assert callable(factory)

    with pytest.raises(CollectorError, match="evidence"):
        factory(  # type: ignore[operator]
            client=FixtureHTTPClient({identity.fetch_url: _html(identity.fetch_url, drifted)})
        ).collect(identity.fetch_url, policy)
