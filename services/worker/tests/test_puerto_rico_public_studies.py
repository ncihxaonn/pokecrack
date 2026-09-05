from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pokecrack_worker.collectors.base import CollectionService, CollectorError, FetchResponse
from pokecrack_worker.collectors.scrapling.adapters.public_studies import (
    RICHARDS_BRICKS_CHARIZARD_EVIDENCE_EXCERPT,
    RICHARDS_BRICKS_CHARIZARD_EVIDENCE_SHA256,
    RICHARDS_BRICKS_CHARIZARD_POLICY_CONFIG,
    RICHARDS_BRICKS_MEGA_EVOLUTION_EVIDENCE_EXCERPT,
    RICHARDS_BRICKS_MEGA_EVOLUTION_EVIDENCE_SHA256,
    RICHARDS_BRICKS_MEGA_EVOLUTION_POLICY_CONFIG,
    RobotsTxtChecker,
    richards_bricks_charizard_upc_adapter,
    richards_bricks_mega_evolution_box_adapter,
)
from pokecrack_worker.collectors.scrapling.registry import build_live_static_registry
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]
WINDOW_START = datetime(2025, 9, 6, tzinfo=UTC)
WINDOW_END = datetime(2026, 9, 5, 23, 59, 59, 999999, tzinfo=UTC)


class FixtureHTTPClient:
    def __init__(self, responses: Mapping[str, FetchResponse]) -> None:
        self.responses = dict(responses)
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls.append((url, timeout_seconds))
        return self.responses[url]


def _response(url: str, body: str, content_type: str) -> FetchResponse:
    return FetchResponse(
        status_code=200,
        url=url,
        headers={"content-type": content_type},
        body=body.encode("utf-8"),
    )


PUERTO_RICO_STUDIES = (
    (
        "richards-bricks-charizard-upc-pr-18-v1",
        richards_bricks_charizard_upc_adapter,
        RICHARDS_BRICKS_CHARIZARD_POLICY_CONFIG,
        ROOT / "services" / "worker" / "fixtures" / "richards_bricks_charizard_upc.html",
        RICHARDS_BRICKS_CHARIZARD_EVIDENCE_EXCERPT,
        RICHARDS_BRICKS_CHARIZARD_EVIDENCE_SHA256,
        "OON-ICjlrd4",
        datetime(2025, 12, 24, 11, 3, 10, tzinfo=UTC),
        "https://www.youtube.com/robots.txt",
        18,
    ),
    (
        "richards-bricks-mega-evolution-box-pr-36-v1",
        richards_bricks_mega_evolution_box_adapter,
        RICHARDS_BRICKS_MEGA_EVOLUTION_POLICY_CONFIG,
        ROOT / "services" / "worker" / "fixtures" / "richards_bricks_mega_evolution_box.html",
        RICHARDS_BRICKS_MEGA_EVOLUTION_EVIDENCE_EXCERPT,
        RICHARDS_BRICKS_MEGA_EVOLUTION_EVIDENCE_SHA256,
        "p_8k9ZkHV_0",
        datetime(2025, 10, 20, 15, 30, 33, tzinfo=UTC),
        "https://m.youtube.com/robots.txt",
        36,
    ),
)


@pytest.mark.parametrize(
    (
        "study_key",
        "adapter_factory",
        "expected_config",
        "fixture_path",
        "expected_excerpt",
        "expected_sha256",
        "video_id",
        "observed_at",
        "robots_url",
        "pack_count",
    ),
    PUERTO_RICO_STUDIES,
)
def test_puerto_rico_youtube_studies_are_exact_date_bounded_coverage(
    study_key: str,
    adapter_factory: object,
    expected_config: Mapping[str, object],
    fixture_path: Path,
    expected_excerpt: str,
    expected_sha256: str,
    video_id: str,
    observed_at: datetime,
    robots_url: str,
    pack_count: int,
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[study_key]
    body = fixture_path.read_text(encoding="utf-8")
    client = FixtureHTTPClient(
        {identity.fetch_url: _response(identity.fetch_url, body, "text/html; charset=utf-8")}
    )
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        identity.fetch_url
    )

    candidate = adapter_factory(client=client).collect(identity.fetch_url, policy)[0]  # type: ignore[operator]

    assert policy.config == expected_config
    assert policy.config["country_code"] == "PR"
    assert policy.config["country_name"] == "Puerto Rico"
    assert policy.config["geography_basis"] == "publisher_country"
    assert policy.config["geography_confidence"] == "tier_b"
    assert policy.config["publisher_channel_id"] == "UCP2PM8ZRJ_fiKlzJNGc02pQ"
    assert policy.config["publisher_country_evidence"] == 'country:"Puerto Rico"'
    assert policy.config["publisher_country_checked_at"] == "2026-09-05"
    assert policy.config["geography_review_method"] == "manual_static_channel_about_review"
    assert policy.config["pack_count"] == pack_count
    assert policy.config["denominator_complete"] is True
    assert WINDOW_START <= observed_at <= WINDOW_END
    assert policy.config["observed_at"] == observed_at.isoformat().replace("+00:00", "Z")
    assert (
        not {
            "qualifying_hit_pack_count",
            "qualifying_metric",
            "metric_version",
        }
        & policy.config.keys()
    )
    assert candidate.source_url == identity.fetch_url
    assert candidate.external_id == video_id
    assert candidate.published_at == observed_at
    assert candidate.text == expected_excerpt
    assert candidate.content_sha256 == expected_sha256
    assert candidate.media_urls == ()
    assert "sir" not in candidate.text.casefold()
    assert "illustration rare" not in candidate.text.casefold()
    assert candidate.metadata == {
        "study_key": study_key,
        "parser_version": identity.parser_version,
    }

    if pack_count == 18:
        assert policy.config["set_external_id"] == "mixed-tpci-2025"
        assert policy.config["set_scope"] == "mixed_multi_expansion"
    else:
        assert policy.config["set_external_id"] == "me01"
        assert policy.config["set_scope"] == "single_expansion"


@pytest.mark.parametrize(
    ("study_key", "adapter_factory", "fixture_path", "date_text"),
    (
        (
            "richards-bricks-charizard-upc-pr-18-v1",
            richards_bricks_charizard_upc_adapter,
            ROOT / "services" / "worker" / "fixtures" / "richards_bricks_charizard_upc.html",
            "2025-12-24T03:03:10-08:00",
        ),
        (
            "richards-bricks-mega-evolution-box-pr-36-v1",
            richards_bricks_mega_evolution_box_adapter,
            ROOT / "services" / "worker" / "fixtures" / "richards_bricks_mega_evolution_box.html",
            "2025-10-20T08:30:33-07:00",
        ),
    ),
)
def test_puerto_rico_youtube_adapters_fail_closed_on_publication_date_drift(
    study_key: str,
    adapter_factory: object,
    fixture_path: Path,
    date_text: str,
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[study_key]
    body = fixture_path.read_text(encoding="utf-8").replace(
        date_text,
        date_text.replace("2025-", "2024-", 1),
    )
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        identity.fetch_url
    )
    adapter = adapter_factory(  # type: ignore[operator]
        client=FixtureHTTPClient(
            {identity.fetch_url: _response(identity.fetch_url, body, "text/html")}
        )
    )

    with pytest.raises(CollectorError, match="publication date"):
        adapter.collect(identity.fetch_url, policy)


@pytest.mark.parametrize(
    ("study_key", "adapter_factory", "fixture_path", "old_text", "new_text"),
    (
        (
            "richards-bricks-charizard-upc-pr-18-v1",
            richards_bricks_charizard_upc_adapter,
            ROOT / "services" / "worker" / "fixtures" / "richards_bricks_charizard_upc.html",
            "Booster Pack (18)",
            "Booster Pack (17)",
        ),
        (
            "richards-bricks-mega-evolution-box-pr-36-v1",
            richards_bricks_mega_evolution_box_adapter,
            ROOT / "services" / "worker" / "fixtures" / "richards_bricks_mega_evolution_box.html",
            "36 booster packs from the Pokémon TCG: Mega Evolution expansion",
            "35 booster packs from the Pokémon TCG: Mega Evolution expansion",
        ),
    ),
)
def test_puerto_rico_youtube_adapters_fail_closed_on_pack_denominator_drift(
    study_key: str,
    adapter_factory: object,
    fixture_path: Path,
    old_text: str,
    new_text: str,
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[study_key]
    body = fixture_path.read_text(encoding="utf-8").replace(old_text, new_text)
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        identity.fetch_url
    )
    adapter = adapter_factory(  # type: ignore[operator]
        client=FixtureHTTPClient(
            {identity.fetch_url: _response(identity.fetch_url, body, "text/html")}
        )
    )

    with pytest.raises(CollectorError, match="evidence"):
        adapter.collect(identity.fetch_url, policy)


@pytest.mark.parametrize(
    ("study_key", "adapter_factory", "fixture_path", "old_text", "new_text", "error"),
    (
        (
            "richards-bricks-charizard-upc-pr-18-v1",
            richards_bricks_charizard_upc_adapter,
            ROOT / "services" / "worker" / "fixtures" / "richards_bricks_charizard_upc.html",
            '"videoId": "OON-ICjlrd4"',
            '"videoId": "unreviewed-video"',
            "video identity",
        ),
        (
            "richards-bricks-mega-evolution-box-pr-36-v1",
            richards_bricks_mega_evolution_box_adapter,
            ROOT / "services" / "worker" / "fixtures" / "richards_bricks_mega_evolution_box.html",
            '"channelId": "UCP2PM8ZRJ_fiKlzJNGc02pQ"',
            '"channelId": "unreviewed-channel"',
            "publisher identity",
        ),
    ),
)
def test_puerto_rico_youtube_adapters_fail_closed_on_identity_drift(
    study_key: str,
    adapter_factory: object,
    fixture_path: Path,
    old_text: str,
    new_text: str,
    error: str,
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[study_key]
    body = fixture_path.read_text(encoding="utf-8").replace(old_text, new_text)
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        identity.fetch_url
    )
    adapter = adapter_factory(  # type: ignore[operator]
        client=FixtureHTTPClient(
            {identity.fetch_url: _response(identity.fetch_url, body, "text/html")}
        )
    )

    with pytest.raises(CollectorError, match=error):
        adapter.collect(identity.fetch_url, policy)


@pytest.mark.parametrize(
    ("study_key", "fixture_path", "robots_url"),
    (
        (
            "richards-bricks-charizard-upc-pr-18-v1",
            ROOT / "services" / "worker" / "fixtures" / "richards_bricks_charizard_upc.html",
            "https://www.youtube.com/robots.txt",
        ),
        (
            "richards-bricks-mega-evolution-box-pr-36-v1",
            ROOT / "services" / "worker" / "fixtures" / "richards_bricks_mega_evolution_box.html",
            "https://m.youtube.com/robots.txt",
        ),
    ),
)
def test_puerto_rico_youtube_collection_requests_only_robots_and_watch_page(
    study_key: str,
    fixture_path: Path,
    robots_url: str,
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[study_key]
    client = FixtureHTTPClient(
        {
            robots_url: _response(
                robots_url,
                "User-agent: *\nAllow: /\nDisallow: /api/\n",
                "text/plain; charset=utf-8",
            ),
            identity.fetch_url: _response(
                identity.fetch_url,
                fixture_path.read_text(encoding="utf-8"),
                "text/html; charset=utf-8",
            ),
        }
    )
    service = CollectionService(
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
        http_adapters=build_live_static_registry(http_client=client),
        robots=RobotsTxtChecker(client=client, followup_delay_seconds=0),
    )

    candidates = service.collect_url(identity.fetch_url, route="static")

    assert len(candidates) == 1
    assert candidates[0].media_urls == ()
    assert client.calls == [(robots_url, 30.0), (identity.fetch_url, 30.0)]
