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
    ANDREE_INSANE_CARDS_COSMIC_ECLIPSE_EVIDENCE_EXCERPT,
    ANDREE_INSANE_CARDS_COSMIC_ECLIPSE_EVIDENCE_SHA256,
    ANDREE_INSANE_CARDS_COSMIC_ECLIPSE_POLICY_CONFIG,
    COFRE_LAB_CHILLING_REIGN_EVIDENCE_EXCERPT,
    COFRE_LAB_CHILLING_REIGN_EVIDENCE_SHA256,
    COFRE_LAB_CHILLING_REIGN_POLICY_CONFIG,
    GRINGO_GAMEPLAYS_SILVER_TEMPEST_EVIDENCE_EXCERPT,
    GRINGO_GAMEPLAYS_SILVER_TEMPEST_EVIDENCE_SHA256,
    GRINGO_GAMEPLAYS_SILVER_TEMPEST_POLICY_CONFIG,
    POKEYABROS_PERFECT_ORDER_EVIDENCE_EXCERPT,
    POKEYABROS_PERFECT_ORDER_EVIDENCE_SHA256,
    POKEYABROS_PERFECT_ORDER_POLICY_CONFIG,
    THEKEIPLAY_LOST_ORIGIN_EVIDENCE_EXCERPT,
    THEKEIPLAY_LOST_ORIGIN_EVIDENCE_SHA256,
    THEKEIPLAY_LOST_ORIGIN_POLICY_CONFIG,
    RobotsTxtChecker,
    andree_insane_cards_cosmic_eclipse_adapter,
    cofre_lab_chilling_reign_adapter,
    gringo_gameplays_silver_tempest_adapter,
    pokeyabros_perfect_order_adapter,
    thekeiplay_lost_origin_adapter,
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


AMERICAS_PHASE_TWO_STUDIES = (
    {
        "source_key": "www.youtube.com#cofre-lab-chilling-reign-cr-4",
        "study_key": "cofre-lab-chilling-reign-cr-4-v1",
        "adapter_factory": cofre_lab_chilling_reign_adapter,
        "policy_config": COFRE_LAB_CHILLING_REIGN_POLICY_CONFIG,
        "fixture": "cofre_lab_chilling_reign_youtube.html",
        "excerpt": COFRE_LAB_CHILLING_REIGN_EVIDENCE_EXCERPT,
        "sha256": COFRE_LAB_CHILLING_REIGN_EVIDENCE_SHA256,
        "title": "Unboxing Pre Release *Chilling Reign- *Reinado Escalofriante #pokemon tcg",
        "video_id": "15eGmqByP0I",
        "observed_at": datetime(2021, 6, 6, 5, 54, 3, tzinfo=UTC),
        "country_code": "CR",
        "set_external_id": "swsh6",
        "pack_count": 4,
        "drift_token": "El día de hoy estaremos haciendo Unboxing del Pre Release",
        "drift_replacement": "El día de hoy mostramos el producto",
    },
    {
        "source_key": "www.youtube.com#pokeyabros-perfect-order-co-2",
        "study_key": "pokeyabros-perfect-order-co-2-v1",
        "adapter_factory": pokeyabros_perfect_order_adapter,
        "policy_config": POKEYABROS_PERFECT_ORDER_POLICY_CONFIG,
        "fixture": "pokeyabros_perfect_order_youtube.html",
        "excerpt": POKEYABROS_PERFECT_ORDER_EVIDENCE_EXCERPT,
        "sha256": POKEYABROS_PERFECT_ORDER_EVIDENCE_SHA256,
        "title": "🎁¿PREMIO O FRACASO? #579 BOOSTER PACK OPENING PERFECT ORDER",
        "video_id": "n_PdWg27x-o",
        "observed_at": datetime(2026, 9, 4, 14, 0, 23, tzinfo=UTC),
        "country_code": "CO",
        "set_external_id": "me03",
        "pack_count": 2,
        "drift_token": "Abrimos dos boosters de Pokémon TCG",
        "drift_replacement": "Abrimos boosters de Pokémon TCG",
    },
    {
        "source_key": "www.youtube.com#andree-insane-cards-cosmic-eclipse-ec-20",
        "study_key": "andree-insane-cards-cosmic-eclipse-ec-20-v1",
        "adapter_factory": andree_insane_cards_cosmic_eclipse_adapter,
        "policy_config": ANDREE_INSANE_CARDS_COSMIC_ECLIPSE_POLICY_CONFIG,
        "fixture": "andree_insane_cards_cosmic_eclipse_youtube.html",
        "excerpt": ANDREE_INSANE_CARDS_COSMIC_ECLIPSE_EVIDENCE_EXCERPT,
        "sha256": ANDREE_INSANE_CARDS_COSMIC_ECLIPSE_EVIDENCE_SHA256,
        "title": (
            "🔥 Buscando a #Charizard Ep6: Abriendo 20 #CosmicEclipse Booster Packs "
            "LA MEJOR APERTURA DE YOUTUBE!"
        ),
        "video_id": "wDDCbJKFTCw",
        "observed_at": datetime(2023, 6, 27, 21, 0, 7, tzinfo=UTC),
        "country_code": "EC",
        "set_external_id": "sm12",
        "pack_count": 20,
        "drift_token": "20 de boosters de #CosmicEclipse",
        "drift_replacement": "boosters de #CosmicEclipse",
    },
    {
        "source_key": "www.youtube.com#thekeiplay-lost-origin-pe-36",
        "study_key": "thekeiplay-lost-origin-pe-36-v1",
        "adapter_factory": thekeiplay_lost_origin_adapter,
        "policy_config": THEKEIPLAY_LOST_ORIGIN_POLICY_CONFIG,
        "fixture": "thekeiplay_lost_origin_youtube.html",
        "excerpt": THEKEIPLAY_LOST_ORIGIN_EVIDENCE_EXCERPT,
        "sha256": THEKEIPLAY_LOST_ORIGIN_EVIDENCE_SHA256,
        "title": "MEGA Apertura!!!😱 Booster Box 💥LOST ORIGIN (Origen Perdido)",
        "video_id": "YKHGiYIhsQU",
        "observed_at": datetime(2022, 9, 5, 18, 0, 12, tzinfo=UTC),
        "country_code": "PE",
        "set_external_id": "swsh11",
        "pack_count": 36,
        "drift_token": "Apertura Completa de una Booster Box",
        "drift_replacement": "Apertura parcial de una Booster Box",
    },
    {
        "source_key": "www.youtube.com#gringo-gameplays-silver-tempest-uy-36",
        "study_key": "gringo-gameplays-silver-tempest-uy-36-v1",
        "adapter_factory": gringo_gameplays_silver_tempest_adapter,
        "policy_config": GRINGO_GAMEPLAYS_SILVER_TEMPEST_POLICY_CONFIG,
        "fixture": "gringo_gameplays_silver_tempest_youtube.html",
        "excerpt": GRINGO_GAMEPLAYS_SILVER_TEMPEST_EVIDENCE_EXCERPT,
        "sha256": GRINGO_GAMEPLAYS_SILVER_TEMPEST_EVIDENCE_SHA256,
        "title": "TCG Pokémon Uruguay  Unboxing  Booster BOX Silver Tempest + Codigos TCG Live",
        "video_id": "lYzM0jtPLKw",
        "observed_at": datetime(2023, 3, 30, 17, 14, 2, tzinfo=UTC),
        "country_code": "UY",
        "set_external_id": "swsh12",
        "pack_count": 36,
        "drift_token": "Booster BOX Silver Tempest",
        "drift_replacement": "Producto Silver Tempest",
    },
)


@pytest.mark.parametrize(
    "study", AMERICAS_PHASE_TWO_STUDIES, ids=lambda study: str(study["study_key"])
)
def test_americas_phase_two_adapters_emit_exact_coverage_facts(
    study: Mapping[str, object],
) -> None:
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


@pytest.mark.parametrize(
    "study", AMERICAS_PHASE_TWO_STUDIES, ids=lambda study: str(study["study_key"])
)
def test_americas_phase_two_routes_are_exact_static_only(study: Mapping[str, object]) -> None:
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


@pytest.mark.parametrize(
    "study", AMERICAS_PHASE_TWO_STUDIES, ids=lambda study: str(study["study_key"])
)
def test_americas_phase_two_adapters_fail_closed_on_evidence_drift(
    study: Mapping[str, object],
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[str(study["study_key"])]
    fixture_path = ROOT / "services" / "worker" / "fixtures" / str(study["fixture"])
    body = fixture_path.read_text(encoding="utf-8")
    drifted = body.replace(str(study["drift_token"]), str(study["drift_replacement"]), 1)
    assert drifted != body
    policy = _policy(str(study["source_key"]))
    factory = study["adapter_factory"]

    with pytest.raises(CollectorError, match="title|evidence"):
        factory(  # type: ignore[operator]
            client=FixtureHTTPClient({identity.fetch_url: _html(identity.fetch_url, drifted)})
        ).collect(identity.fetch_url, policy)


def test_americas_phase_two_policies_fail_closed_outside_exact_watch_pages() -> None:
    registry = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml")

    for study in AMERICAS_PHASE_TWO_STUDIES:
        identity = PUBLIC_STUDIES_BY_KEY[str(study["study_key"])]
        assert registry.resolve(identity.fetch_url).config == study["policy_config"]
        assert registry.allows(identity.fetch_url, "static")
        assert not registry.allows(f"{identity.fetch_url}&si=unreviewed", "static")

    assert not registry.allows("https://www.youtube.com/watch?v=unreviewed", "static")
