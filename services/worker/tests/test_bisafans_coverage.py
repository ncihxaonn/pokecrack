from __future__ import annotations

from pathlib import Path

import pytest
from test_nanjakorya_coverage import FixtureClient

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters import bisafans_coverage as source
from pokecrack_worker.config.public_studies import PUBLIC_STUDY_COVERAGE_KEYS
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]


def document() -> str:
    return (
        "<html><head><title>Statistiken</title></head><body>"
        "<h1>Statistiken</h1><p>"
        + source.FIRST_EVIDENCE
        + "</p><p>"
        + source.SECOND_EVIDENCE
        + "</p></body></html>"
    )


def test_complete_display_is_coverage_only() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        source.IDENTITY.fetch_url
    )
    client = FixtureClient(document())
    item = source.bisafans_flying_fists_adapter(client=client).collect(
        source.IDENTITY.fetch_url, policy
    )[0]

    assert policy.config == source.POLICY_CONFIG
    assert source.IDENTITY.study_key in PUBLIC_STUDY_COVERAGE_KEYS
    assert policy.config["country_code"] == "DE"
    assert policy.config["geography_basis"] == "publisher_country"
    assert policy.config["set_external_id"] == "xy3"
    assert policy.config["set_language"] == "de"
    assert policy.config["pack_count"] == 36
    assert item.text == source.EVIDENCE_EXCERPT
    assert item.content_sha256 == source.EVIDENCE_SHA256
    assert item.media_urls == ()
    assert client.calls == [source.IDENTITY.fetch_url]
    assert (
        not {
            "qualifying_hit_pack_count",
            "qualifying_metric",
            "metric_version",
        }
        & policy.config.keys()
    )


@pytest.mark.parametrize(
    "old,new",
    [
        (source.FIRST_EVIDENCE, source.FIRST_EVIDENCE.replace("36", "35")),
        (source.SECOND_EVIDENCE, source.SECOND_EVIDENCE.replace("47", "46")),
        ("<h1>Statistiken</h1>", "<h1>Andere Seite</h1>"),
    ],
)
def test_evidence_or_title_drift_fails_closed(old: str, new: str) -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        source.IDENTITY.fetch_url
    )
    with pytest.raises(CollectorError):
        source.bisafans_flying_fists_adapter(
            client=FixtureClient(document().replace(old, new))
        ).collect(source.IDENTITY.fetch_url, policy)


def test_only_exact_url_and_config_can_fetch() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        source.IDENTITY.fetch_url
    )
    client = FixtureClient(document())
    adapter = source.bisafans_flying_fists_adapter(client=client)

    with pytest.raises(CollectorError):
        adapter.collect(source.IDENTITY.fetch_url + "?page=2", policy)
    with pytest.raises(CollectorError):
        adapter.collect(
            source.IDENTITY.fetch_url,
            policy.model_copy(update={"config": {**policy.config, "pack_count": 72}}),
        )
    assert client.calls == []
