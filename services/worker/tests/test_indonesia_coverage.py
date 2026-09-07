from __future__ import annotations

from pathlib import Path

import pytest

from pokecrack_worker.collectors.base import CollectorError, FetchResponse
from pokecrack_worker.collectors.scrapling.adapters.indonesia_coverage import (
    EVIDENCE_EXCERPT,
    EVIDENCE_SHA256,
    FIRST_BOX,
    IDENTITY,
    POLICY_CONFIG,
    TITLE,
    bikuhime_hantaman_pertama_a_adapter,
)
from pokecrack_worker.config.public_studies import PUBLIC_STUDY_COVERAGE_KEYS
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]


def document() -> str:
    # Synthetic markup, not a copied page or retained article.
    headers = [
        "Tipe",
        FIRST_BOX,
        "Hantaman Pertama set B (pembelian pertama)",
        "Hantaman Pertama set A (pembelian kedua)",
        "%",
    ]
    rows = [["C", "61"], ["U", "24"], ["R", "12"], ["RR", "2"], ["UR", "1"], ["SR", "0"]]
    table = "<tr>" + "".join(f"<td>{cell}</td>" for cell in headers) + "</tr>"
    table += "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in [*row, "0", "0", "0%"]) + "</tr>"
        for row in rows
    )
    return (
        '<meta property="article:published_time" content="2020-05-17T07:23:58+00:00">'
        f"<article><h1>{TITLE}</h1><p>1 booster box = 20 booster pack</p>"
        f"<table>{table}</table></article>"
    )


class FixtureClient:
    def __init__(self, body: str) -> None:
        self.body = body
        self.calls: list[str] = []

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls.append(url)
        return FetchResponse(
            status_code=200,
            url=url,
            headers={"content-type": "text/html"},
            body=self.body.encode(),
        )


def test_first_box_is_twenty_packs_without_rate_or_location_claim() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        IDENTITY.fetch_url
    )
    client = FixtureClient(document())
    item = bikuhime_hantaman_pertama_a_adapter(client=client).collect(IDENTITY.fetch_url, policy)[0]
    assert policy.config == POLICY_CONFIG
    assert policy.config["geography_basis"] == "product_market"
    assert policy.config["pack_count"] == 20
    assert IDENTITY.study_key in PUBLIC_STUDY_COVERAGE_KEYS
    assert "qualifying_hit_pack_count" not in policy.config
    assert item.text == EVIDENCE_EXCERPT
    assert item.content_sha256 == EVIDENCE_SHA256
    assert item.media_urls == ()
    assert client.calls == [IDENTITY.fetch_url]


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("20 booster pack", "19 booster pack"),
        (FIRST_BOX, "Hantaman Pertama Set A (pembelian kedua)"),
        ("2020-05-17T07:23:58+00:00", "2020-06-05T15:43:29+00:00"),
        ("article:published_time", "article:modified_time"),
        ("<td>61</td>", "<td>60</td>"),
        ("<td>61</td>", '<td colspan="2">61</td>'),
        ("<table>", "<template><table>"),
        ("<article>", "<aside>"),
        ("<table>", "<table></table><table>"),
    ],
)
def test_evidence_drift_fails_closed(before: str, after: str) -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        IDENTITY.fetch_url
    )
    with pytest.raises(CollectorError):
        bikuhime_hantaman_pertama_a_adapter(
            client=FixtureClient(document().replace(before, after))
        ).collect(IDENTITY.fetch_url, policy)


def test_policy_drift_and_arbitrary_url_fail_before_network() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        IDENTITY.fetch_url
    )
    client = FixtureClient(document())
    adapter = bikuhime_hantaman_pertama_a_adapter(client=client)
    with pytest.raises(CollectorError):
        adapter.collect(IDENTITY.fetch_url + "?box=2", policy)
    policy = policy.model_copy(update={"config": {**POLICY_CONFIG, "pack_count": 60}})
    with pytest.raises(CollectorError):
        adapter.collect(IDENTITY.fetch_url, policy)
    assert client.calls == []
