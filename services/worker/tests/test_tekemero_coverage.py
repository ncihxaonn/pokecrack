from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_nanjakorya_coverage import FixtureClient

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters import tekemero_coverage as source
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY, PUBLIC_STUDY_COVERAGE_KEYS
from pokecrack_worker.config.source_policy import SourcePolicyRegistry
from pokecrack_worker.deduplication.fingerprints import content_sha256

ROOT = Path(__file__).resolve().parents[3]
TITLE = "ムニキスゼロ 30パック synthetic opening"
OPENING = "Synthetic self-purchased sealed box, all 30パック opened."


def document() -> str:
    metadata = json.dumps(
        {
            "@type": "BlogPosting",
            "headline": TITLE,
            "datePublished": source.PUBLICATION,
            "dateModified": "2026-08-29T16:40:20+09:00",
            "mainEntityOfPage": {"@type": "WebPage", "@id": source.IDENTITY.source_url},
        }
    )
    return (
        '<html><head><link rel="canonical" href="' + source.IDENTITY.source_url + '">'
        '<script type="application/ld+json">' + metadata + "</script></head><body>"
        '<main id="single-main"><article id="post-447" class="post-447 type-post">'
        "<h1>" + TITLE + '</h1><section class="single-post-main"><div class="content">'
        "<p>" + OPENING + "</p><p>Synthetic unrelated commentary.</p>"
        "</div></section></article></main></body></html>"
    )


@pytest.fixture
def reviewed_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source, "TITLE_SHA256", content_sha256(TITLE))
    monkeypatch.setattr(source, "OPENING_SHA256", content_sha256(OPENING))
    parsed = source._Evidence()
    parsed.feed(document())
    parsed.close()
    monkeypatch.setattr(source, "BODY_SHA256", parsed.body_sha256)


def test_only_approved_minimal_complete_cohort_is_collected(reviewed_fixture: None) -> None:
    assert PUBLIC_STUDIES_BY_KEY[source.IDENTITY.study_key] == source.IDENTITY
    assert source.IDENTITY.study_key in PUBLIC_STUDY_COVERAGE_KEYS
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        source.IDENTITY.source_url
    )
    assert policy.enabled and policy.config == source.POLICY_CONFIG
    client = FixtureClient(document())
    items = source.tekemero_munikis_zero_adapter(client=client).collect(
        source.IDENTITY.fetch_url, policy
    )
    assert len(items) == 1
    assert items[0].title == TITLE
    assert items[0].text == "30パック"
    assert items[0].content_sha256 == source.EVIDENCE_SHA256
    assert items[0].media_urls == ()
    assert client.calls == [source.IDENTITY.fetch_url]
    assert (
        not {"qualifying_hit_pack_count", "qualifying_metric", "metric_version"}
        & policy.config.keys()
    )


def test_other_reports_aliases_and_changed_contract_cannot_fetch(reviewed_fixture: None) -> None:
    registry = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml")
    policy = registry.resolve(source.IDENTITY.source_url)
    client = FixtureClient(document())
    adapter = source.tekemero_munikis_zero_adapter(client=client)
    for url in (
        "https://tekemero.com/?p=447",
        "https://tekemero.com/260715-01/",
        source.IDENTITY.fetch_url.rstrip("/"),
        source.IDENTITY.fetch_url + "?page=2",
    ):
        assert not registry.allows(url, "static")
        with pytest.raises(CollectorError):
            adapter.collect(url, policy)
    for field, value in (
        ("pack_count", 40),
        ("set_language", "en"),
        ("opening_country", "JP"),
        ("observed_at", "2026-08-29T07:40:20Z"),
    ):
        with pytest.raises(CollectorError):
            adapter.collect(
                source.IDENTITY.fetch_url,
                policy.model_copy(update={"config": {**policy.config, field: value}}),
            )
    assert not registry.resolve("https://not-an-approved-source.example/").enabled
    assert client.calls == []


def test_reviewed_facts_are_not_synthetic_and_body_is_pinned() -> None:
    assert source.TITLE_SHA256 == "f55b0821fb41a66088b925b5d89f36a3d78c2d4e1417d53fe4f8681b98b39b42"
    assert (
        source.OPENING_SHA256 == "29a5a4d3cf31a546b13f84649839d2329aa15f2e2834ec80ec9ffaf382004bfa"
    )
    assert source.POLICY_CONFIG["pack_count"] == 30
    assert source.POLICY_CONFIG["geography_basis"] == "product_market"
    assert source.POLICY_CONFIG["opening_country"] is None
    assert source.POLICY_CONFIG["opened_at"] is None
    assert source.BODY_SHA256 == "1d70d72e779134e2cc5030b7075ee8d03283bec3991da606f95b03c2e927c8d8"
    with pytest.raises(CollectorError):
        source.verify_document(document())


def test_synthetic_complete_report_and_original_date(reviewed_fixture: None) -> None:
    source.verify_document(document())
    source.verify_document(
        document().replace("2026-08-29T16:40:20+09:00", "2026-09-01T00:00:00+09:00")
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("all 30", "only 20"),
        ("sealed", "unsealed"),
        ("self-purchased", "copied comparison"),
        ("Synthetic unrelated commentary.", "The opening report above is fictional."),
        (source.PUBLICATION, "2026-08-29T16:40:20+09:00"),
        ('rel="canonical"', 'rel="alternate"'),
        ('id="post-447"', 'id="post-438"'),
        ('class="post-447 type-post"', 'class="recommendation"'),
        ('class="single-post-main"', 'class="sidebar"'),
        ('class="content"', 'class="comparison"'),
        ("<p>Synthetic self", "<p hidden>Synthetic self"),
        ("<p>Synthetic self", '<p aria-hidden="true">Synthetic self'),
        ("<p>Synthetic self", '<p style="display:none">Synthetic self'),
        ("<article id=", "<article hidden id="),
        ("<h1>", "<h1 hidden>"),
        ('type="application/ld+json"', 'type="application/ld+json" hidden'),
        ('"@type": "BlogPosting"', '"@type": "WebPage"'),
        ("</article>", ""),
        ("</div></section>", "</section>"),
    ],
)
def test_changed_hidden_or_missing_evidence_rejects(
    reviewed_fixture: None, old: str, new: str
) -> None:
    assert old in document()
    with pytest.raises(CollectorError):
        source.verify_document(document().replace(old, new))


def test_outside_duplicate_and_commented_facts_do_not_pass(reviewed_fixture: None) -> None:
    opening = "<p>" + OPENING + "</p>"
    for changed in (
        document().replace(opening, "").replace("</main>", "</main>" + opening),
        document().replace(opening, opening * 2),
        document().replace(opening, "<!--" + opening + "-->"),
        document().replace(opening, "<template>" + opening + "</template>"),
        document().replace(
            "</head>", '<link rel="canonical" href="' + source.IDENTITY.source_url + '"></head>'
        ),
    ):
        with pytest.raises(CollectorError):
            source.verify_document(changed)


def test_line_breaks_and_html_implicit_paragraph_closure(reviewed_fixture: None) -> None:
    source.verify_document(document().replace("box, all", "box,<br>all"))
    source.verify_document(document().replace("<p>Synthetic self", "<p><p>Synthetic self"))
