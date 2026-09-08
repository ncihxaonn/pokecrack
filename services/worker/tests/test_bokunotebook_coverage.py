from __future__ import annotations

from pathlib import Path

import pytest
from test_nanjakorya_coverage import FixtureClient

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters.bokunotebook_coverage import (
    EVIDENCE_EXCERPT,
    EVIDENCE_SHA256,
    IDENTITY,
    POLICY_CONFIG,
    PUBLISHED_AT,
    TITLE,
    bokunotebook_vstar_universe_adapter,
    verify_document,
)
from pokecrack_worker.config.public_studies import PUBLIC_STUDY_COVERAGE_KEYS
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]


def document() -> str:
    # Synthetic structural fixture: no article body or media copied from the source.
    return (
        '<html><head><link rel="canonical" href="' + IDENTITY.source_url + '">'
        '<meta property="article:published_time" content="' + PUBLISHED_AT + '">'
        '</head><body><article id="post-13725"><h1>' + TITLE + "</h1>"
        "<p>なんとなく1パック買ってみました</p><p>とりあえず1パック買った</p>"
        "<p>どうやらVSTARユニバースというパック</p><h3>早速開封してみる</h3>"
        "<p>開封したところ<br>全部で10枚入っていました</p>"
        "<h3>ポケモンの名前を調べてみる</h3></article></body></html>"
    )


def test_complete_report_is_minimal_coverage_not_rate() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        IDENTITY.fetch_url
    )
    client = FixtureClient(document())
    item = bokunotebook_vstar_universe_adapter(client=client).collect(IDENTITY.fetch_url, policy)[0]
    assert policy.config == POLICY_CONFIG
    assert IDENTITY.study_key in PUBLIC_STUDY_COVERAGE_KEYS
    assert policy.config["pack_count"] == 1
    assert policy.config["opening_country"] is None
    assert policy.config["opened_at"] is None
    assert policy.config["geography_basis"] == "product_market"
    assert "qualifying_hit_pack_count" not in policy.config
    assert item.text == EVIDENCE_EXCERPT
    assert item.content_sha256 == EVIDENCE_SHA256
    assert item.media_urls == ()
    assert client.calls == [IDENTITY.fetch_url]


@pytest.mark.parametrize(
    "old,new",
    [
        ("なんとなく1パック", "なんとなく2パック"),
        ("とりあえず1パック", "とりあえず2パック"),
        ("全部で10枚", "全部で9枚"),
        ("開封したところ", "未開封"),
        ("VSTARユニバース", "別のセット"),
        ("早速開封してみる", "商品仕様"),
        ("post-13725", "post-12345"),
        (PUBLISHED_AT, "2026-07-07T21:01:49+09:00"),
        ('rel="canonical"', 'rel="alternate"'),
        ("<p>なんとなく", "<p hidden>なんとなく"),
        ("<p>とりあえず", '<p aria-hidden="true">とりあえず'),
        ("<p>開封したところ", '<p style="display: none">開封したところ'),
        ("</article>", ""),
    ],
)
def test_evidence_drift_rejects_admission(old: str, new: str) -> None:
    with pytest.raises(CollectorError):
        verify_document(document().replace(old, new))


def test_duplicate_or_outside_article_facts_do_not_prove_denominator() -> None:
    for changed in (
        document().replace(
            "</head>",
            '<meta property="article:published_time" content="' + PUBLISHED_AT + '"></head>',
        ),
        document().replace("</article>", "<p>なんとなく1パック買ってみました</p></article>"),
        document()
        .replace("<p>なんとなく1パック買ってみました</p>", "")
        .replace("</article>", "</article><p>なんとなく1パック買ってみました</p>"),
        document().replace(
            "<p>なんとなく1パック買ってみました</p>",
            "<script>なんとなく1パック買ってみました</script>",
        ),
    ):
        with pytest.raises(CollectorError):
            verify_document(changed)


def test_related_wordpress_articles_cannot_supply_facts() -> None:
    related = (
        '<article class="related-entry-card"><p>なんとなく99パック買ってみました</p></article>'
    )
    verify_document(document().replace("</body>", related + "</body>"))
    with pytest.raises(CollectorError):
        verify_document(document().replace("</body>", document() + "</body>"))


def test_unknown_routes_and_policy_drift_fail_before_network() -> None:
    registry = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml")
    policy = registry.resolve(IDENTITY.fetch_url)
    client = FixtureClient(document())
    adapter = bokunotebook_vstar_universe_adapter(client=client)
    for url in (
        IDENTITY.fetch_url + "?page=2",
        IDENTITY.fetch_url + "/",
        "https://bokunotebook.com/archives/1",
    ):
        assert not registry.allows(url, "static")
        with pytest.raises(CollectorError):
            adapter.collect(url, policy)
    with pytest.raises(CollectorError):
        adapter.collect(
            IDENTITY.fetch_url,
            policy.model_copy(update={"config": {**POLICY_CONFIG, "pack_count": 10}}),
        )
    assert client.calls == []
