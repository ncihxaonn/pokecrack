from __future__ import annotations

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
    CARTAS_POKEMON_ARGENTINA_PITCH_BLACK_EVIDENCE_EXCERPT,
    CARTAS_POKEMON_ARGENTINA_PITCH_BLACK_EVIDENCE_SHA256,
    CARTAS_POKEMON_ARGENTINA_PITCH_BLACK_POLICY_CONFIG,
    POKEMANIACO_LUCAS_PHANTASMAL_FLAMES_EVIDENCE_EXCERPT,
    POKEMANIACO_LUCAS_PHANTASMAL_FLAMES_EVIDENCE_SHA256,
    POKEMANIACO_LUCAS_PHANTASMAL_FLAMES_POLICY_CONFIG,
    RobotsTxtChecker,
    cartas_pokemon_argentina_pitch_black_adapter,
    pokemaniaco_lucas_phantasmal_flames_adapter,
)
from pokecrack_worker.collectors.scrapling.registry import build_live_static_registry
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.config.source_policy import SourcePolicy, SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]
ROBOTS_URL = "https://www.youtube.com/robots.txt"


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


SOUTH_AMERICA_STUDIES = (
    {
        "source_key": "www.youtube.com#cartas-pokemon-argentina-pitch-black-36",
        "study_key": "cartas-pokemon-argentina-pitch-black-ar-36-v1",
        "adapter_factory": cartas_pokemon_argentina_pitch_black_adapter,
        "policy_config": CARTAS_POKEMON_ARGENTINA_PITCH_BLACK_POLICY_CONFIG,
        "fixture": "cartas_pokemon_argentina_pitch_black_youtube.html",
        "excerpt": CARTAS_POKEMON_ARGENTINA_PITCH_BLACK_EVIDENCE_EXCERPT,
        "sha256": CARTAS_POKEMON_ARGENTINA_PITCH_BLACK_EVIDENCE_SHA256,
        "title": "Abrimos una caja de Pitch Black COMPLETA 😈",
        "video_id": "HcsWjycR1L0",
        "observed_at": datetime(2026, 7, 17, 18, 18, 50, tzinfo=UTC),
        "country_code": "AR",
        "set_external_id": "me05",
        "pack_count": 36,
    },
    {
        "source_key": "www.youtube.com#pokemaniaco-lucas-cl-36",
        "study_key": "pokemaniaco-lucas-phantasmal-flames-cl-36-v1",
        "adapter_factory": pokemaniaco_lucas_phantasmal_flames_adapter,
        "policy_config": POKEMANIACO_LUCAS_PHANTASMAL_FLAMES_POLICY_CONFIG,
        "fixture": "pokemaniaco_lucas_phantasmal_flames_youtube.html",
        "excerpt": POKEMANIACO_LUCAS_PHANTASMAL_FLAMES_EVIDENCE_EXCERPT,
        "sha256": POKEMANIACO_LUCAS_PHANTASMAL_FLAMES_EVIDENCE_SHA256,
        "title": "¡Apertura Anticipada! Booster Box completa de Phantasmal Flames -  Pokémon TCG",
        "video_id": "Meg4AO9CqHE",
        "observed_at": datetime(2025, 11, 13, 16, 0, 6, tzinfo=UTC),
        "country_code": "CL",
        "set_external_id": "me02",
        "pack_count": 36,
    },
)


@pytest.mark.parametrize("study", SOUTH_AMERICA_STUDIES, ids=lambda study: str(study["study_key"]))
def test_south_america_adapters_emit_exact_coverage_facts(study: Mapping[str, object]) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[str(study["study_key"])]
    fixture_path = ROOT / "services" / "worker" / "fixtures" / str(study["fixture"])
    policy = _policy(str(study["source_key"]))
    factory = study["adapter_factory"]
    candidate = factory(  # type: ignore[operator]
        client=FixtureHTTPClient(
            {
                identity.fetch_url: _html(
                    identity.fetch_url, fixture_path.read_text(encoding="utf-8")
                )
            }
        )
    ).collect(identity.fetch_url, policy)[0]

    assert policy.config == study["policy_config"]
    assert policy.config["country_code"] == study["country_code"]
    assert policy.config["set_external_id"] == study["set_external_id"]
    assert policy.config["set_language"] == "und"
    assert policy.config["pack_count"] == study["pack_count"]
    assert policy.config["denominator_complete"] is True
    assert (
        not {"qualifying_hit_pack_count", "qualifying_metric", "metric_version"}
        & policy.config.keys()
    )
    assert candidate.external_id == study["video_id"]
    assert candidate.source_url == identity.fetch_url
    assert candidate.title == study["title"]
    assert candidate.published_at == study["observed_at"]
    assert candidate.text == study["excerpt"]
    assert candidate.content_sha256 == study["sha256"]
    assert candidate.media_urls == ()


@pytest.mark.parametrize("study", SOUTH_AMERICA_STUDIES, ids=lambda study: str(study["study_key"]))
def test_south_america_routes_are_exact_static_only(study: Mapping[str, object]) -> None:
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
            identity.fetch_url: _html(identity.fetch_url, fixture_path.read_text(encoding="utf-8")),
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


@pytest.mark.parametrize("study", SOUTH_AMERICA_STUDIES, ids=lambda study: str(study["study_key"]))
def test_south_america_adapters_fail_closed_on_description_drift(
    study: Mapping[str, object],
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[str(study["study_key"])]
    fixture_path = ROOT / "services" / "worker" / "fixtures" / str(study["fixture"])
    body = fixture_path.read_text(encoding="utf-8")
    drifted = body.replace("Opening de Cartas Pokemon Pitch Black", "Opening removido", 1)
    drifted = drifted.replace("En este video abro 36 sobres", "En este video abro sobres", 1)
    policy = _policy(str(study["source_key"]))
    factory = study["adapter_factory"]

    with pytest.raises(CollectorError, match="evidence"):
        factory(  # type: ignore[operator]
            client=FixtureHTTPClient({identity.fetch_url: _html(identity.fetch_url, drifted)})
        ).collect(identity.fetch_url, policy)


def test_south_america_policies_fail_closed_outside_exact_watch_pages() -> None:
    registry = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml")

    for study in SOUTH_AMERICA_STUDIES:
        identity = PUBLIC_STUDIES_BY_KEY[str(study["study_key"])]
        assert registry.resolve(identity.fetch_url).config == study["policy_config"]
        assert registry.allows(identity.fetch_url, "static")
        assert not registry.allows(f"{identity.fetch_url}&si=unreviewed", "static")

    assert not registry.allows("https://www.youtube.com/watch?v=unreviewed", "static")
