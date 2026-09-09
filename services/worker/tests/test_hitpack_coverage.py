from __future__ import annotations

from pathlib import Path

import pytest
from test_nanjakorya_coverage import FixtureClient

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters import hitpack_coverage as source
from pokecrack_worker.config.public_studies import PUBLIC_STUDY_COVERAGE_KEYS
from pokecrack_worker.config.source_policy import SourcePolicyRegistry
from pokecrack_worker.deduplication.fingerprints import content_sha256

ROOT = Path(__file__).resolve().parents[3]
# Synthetic test prose only. Production paragraph hashes bind to the real report.
INTRO = "Our 36-pack original box; 753 packs belong to an independent comparison."
OPENING = "We opened all 36 balíčků from one sealed Pitch Black booster box."


def document() -> str:
    return (
        '<html><head><link rel="canonical" href="' + source.IDENTITY.source_url + '">'
        '<meta property="article:published_time" content="' + source.SOURCE_DATE + '">'
        '</head><body><main id="content"><div class="news-item-detail"><h1>'
        + source.TITLE
        + '</h1><div class="text"><p>'
        + INTRO
        + "</p><p>"
        + OPENING
        + "</p></div></div></main></body></html>"
    )


@pytest.fixture
def reviewed_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source, "INTRO_SHA256", content_sha256(INTRO))
    monkeypatch.setattr(source, "OPENING_SHA256", content_sha256(OPENING))
    parser = source._Evidence()
    parser.feed(document())
    parser.close()
    monkeypatch.setattr(source, "ARTICLE_SHA256", parser.article_sha256)


def test_production_hashes_are_not_synthetic() -> None:
    assert source.INTRO_SHA256 == "d623f777eef4e435ff0de6163569dd262eafdd58d6e0d502bc939a8f52c1a89d"
    assert (
        source.OPENING_SHA256 == "4c1640753b045b0c5e900a426717d45bfba572f99baddd62227dc79eec9da689"
    )
    assert (
        source.EVIDENCE_SHA256 == "b7aca4213dc83f3fde4407985da20807f6cc4cb230db7ebadff32c2915f571ee"
    )
    assert len(source.ARTICLE_SHA256) == 64
    with pytest.raises(CollectorError):
        source.verify_document(document())


def test_one_complete_original_cohort_not_comparison_or_rate(reviewed_fixture: None) -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        source.IDENTITY.fetch_url
    )
    client = FixtureClient(document())
    item = source.hitpack_pitch_black_adapter(client=client).collect(
        source.IDENTITY.fetch_url, policy
    )[0]
    assert policy.config == source.POLICY_CONFIG
    assert source.IDENTITY.study_key in PUBLIC_STUDY_COVERAGE_KEYS
    assert policy.config["pack_count"] == 36
    assert policy.config["country_code"] == "CZ"
    assert policy.config["geography_basis"] == "publisher_country"
    assert policy.config["opening_country"] is None
    assert policy.config["opened_at"] is None
    assert policy.config["set_language"] == "und"
    assert policy.config["publication_time_precision"] == "day"
    assert (
        not {"qualifying_hit_pack_count", "qualifying_metric", "metric_version"}
        & policy.config.keys()
    )
    assert item.title == source.TITLE
    assert item.text == "36 balíčků"
    assert item.content_sha256 == source.EVIDENCE_SHA256
    assert item.media_urls == ()
    assert client.calls == [source.IDENTITY.fetch_url]


@pytest.mark.parametrize(
    "old,new",
    [
        ("36 balíčků", "35 balíčků"),
        ("opened all", "planned to open"),
        ("opened all", "opened about"),
        ("sealed", "unsealed"),
        ("original box", "retail inventory"),
        ("753 packs", "789 packs"),
        ("Pitch Black booster", "Different booster"),
        (source.SOURCE_DATE, "29.7.2026"),
        ('rel="canonical"', 'rel="alternate"'),
        ('id="content"', 'id="sidebar"'),
        ('class="news-item-detail"', 'class="recommended"'),
        ("<p>We", "<p hidden>We"),
        ("<p>We", '<p aria-hidden="true">We'),
        ("<p>We", '<p style="display: none">We'),
        ("<p>We", '<p style="visibility: hidden">We'),
        ("</main>", ""),
    ],
)
def test_drift_fails_closed(reviewed_fixture: None, old: str, new: str) -> None:
    with pytest.raises(CollectorError):
        source.verify_document(document().replace(old, new))


def test_added_contradictions_duplicate_hidden_and_outside_facts_reject(
    reviewed_fixture: None,
) -> None:
    for changed in (
        document().replace("</p></div>", "</p><p>This report is fictional.</p></div>"),
        document().replace("<p>" + OPENING + "</p>", "<script>" + OPENING + "</script>"),
        document()
        .replace("<p>" + OPENING + "</p>", "")
        .replace("</main>", "</main><p>" + OPENING + "</p>"),
        document().replace("</p></div>", "</p><p>" + OPENING + "</p></div>"),
        document().replace(
            "</head>",
            '<meta property="article:published_time" content="' + source.SOURCE_DATE + '"></head>',
        ),
        document() + document(),
    ):
        with pytest.raises(CollectorError):
            source.verify_document(changed)


def test_inline_markup_and_unrelated_navigation_preserve_evidence(reviewed_fixture: None) -> None:
    source.verify_document(document().replace("36 balíčků", "<strong>36 balíčků</strong>"))
    source.verify_document(document().replace("</main>", "</main><nav>New navigation</nav>"))


def test_only_exact_url_and_config_can_fetch(reviewed_fixture: None) -> None:
    registry = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml")
    policy = registry.resolve(source.IDENTITY.fetch_url)
    client = FixtureClient(document())
    adapter = source.hitpack_pitch_black_adapter(client=client)
    for url in (
        source.IDENTITY.fetch_url + "?page=2",
        source.IDENTITY.fetch_url.rstrip("/"),
        "https://www.hitpack.cz/nase-novinky/another-opening/",
    ):
        assert not registry.allows(url, "static")
        with pytest.raises(CollectorError):
            adapter.collect(url, policy)
    for field, value in (("pack_count", 789), ("set_language", "en"), ("opening_country", "CZ")):
        with pytest.raises(CollectorError):
            adapter.collect(
                source.IDENTITY.fetch_url,
                policy.model_copy(update={"config": {**policy.config, field: value}}),
            )
    assert client.calls == []


def test_bounded_transport_and_failures(reviewed_fixture: None) -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        source.IDENTITY.fetch_url
    )
    from pokecrack_worker.collectors.base import FetchResponse

    class ResponseClient:
        def __init__(self, response: FetchResponse) -> None:
            self.response = response

        def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
            return self.response

    for response in (
        FetchResponse(
            403, source.IDENTITY.fetch_url, {"content-type": "text/html"}, document().encode()
        ),
        FetchResponse(
            200,
            source.IDENTITY.fetch_url + "?redirected=1",
            {"content-type": "text/html"},
            document().encode(),
        ),
        FetchResponse(200, source.IDENTITY.fetch_url, {"content-type": "text/html"}, b"\xff"),
        FetchResponse(
            200,
            source.IDENTITY.fetch_url,
            {"content-type": "text/html"},
            document().encode() + b" " * 1_000_000,
        ),
    ):
        with pytest.raises(CollectorError):
            source.hitpack_pitch_black_adapter(client=ResponseClient(response)).collect(
                source.IDENTITY.fetch_url, policy
            )
