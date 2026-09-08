from __future__ import annotations

from pathlib import Path

import pytest
from test_nanjakorya_coverage import FixtureClient

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters import auckland_coverage as source
from pokecrack_worker.config.public_studies import PUBLIC_STUDY_COVERAGE_KEYS
from pokecrack_worker.config.source_policy import SourcePolicyRegistry
from pokecrack_worker.deduplication.fingerprints import content_sha256

ROOT = Path(__file__).resolve().parents[3]
# Invented minimal test prose, not a retained copy of the publisher's article.
EVENT = "August 9th to 10th 2025: Auckland Showgrounds"
SEGMENT = "Pokémon with Mighty Ape: 105 packs opened."


def document() -> str:
    return (
        '<html><head><link rel="canonical" href="' + source.IDENTITY.source_url + '">'
        '<meta property="article:published_time" content="' + source.PUBLISHED_AT + '">'
        "</head><body><main><h1>" + source.TITLE_FRAGMENT + "</h1>"
        "<p>" + EVENT + "</p><p>Sponsors include Mighty Ape.</p>"
        "<h2>Sunday</h2><p>" + SEGMENT + "</p></main></body></html>"
    )


@pytest.fixture
def reviewed_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    # Production hashes stay immutable; synthetic evidence gets its own test hashes.
    monkeypatch.setattr(source, "SEGMENT_SHA256", content_sha256(SEGMENT))
    monkeypatch.setattr(source, "EVENT_SHA256", content_sha256(EVENT))


def test_production_hashes_are_not_synthetic() -> None:
    assert (
        source.SEGMENT_SHA256 == "e9e68018bfe5228ab529b9885be1b8ed68912f9ce22621b6865ef182bceddb52"
    )
    assert source.EVENT_SHA256 == "d7435f63b8dea7ed23ca91174b4ba25cc288e1665b3b704384f94144b628ed23"
    with pytest.raises(CollectorError):
        source.verify_document(document())


def test_large_transport_is_isolated_to_the_reviewed_adapter() -> None:
    from pokecrack_worker.collectors.scrapling.backend import ScraplingBackend
    from pokecrack_worker.collectors.scrapling.http import ScraplingHTTPClient
    from pokecrack_worker.collectors.scrapling.registry import build_live_static_registry

    normal = ScraplingHTTPClient.live()
    reviewed = ScraplingHTTPClient(backend=ScraplingBackend(max_response_bytes=2_000_000))
    registry = build_live_static_registry(http_client=normal, auckland_http_client=reviewed)
    for name in registry.names:
        adapter = registry.get(name)
        assert adapter.client is (reviewed if name == source.IDENTITY.adapter else normal)
    assert normal.backend.max_response_bytes == 1_000_000


def test_exact_segment_is_one_coverage_cohort(reviewed_fixture: None) -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        source.IDENTITY.fetch_url
    )
    client = FixtureClient(document())
    item = source.auckland_show_mighty_ape_adapter(client=client).collect(
        source.IDENTITY.fetch_url, policy
    )[0]
    assert policy.config == source.POLICY_CONFIG
    assert source.IDENTITY.study_key in PUBLIC_STUDY_COVERAGE_KEYS
    assert policy.config["pack_count"] == 105
    assert policy.config["set_language"] == "und"
    assert policy.config["set_scope"] == "mixed_multi_expansion"
    assert policy.config["opening_country"] == "NZ"
    assert "qualifying_hit_pack_count" not in policy.config
    assert item.title == source.TITLE_FRAGMENT
    assert item.text == "105 packs"
    assert item.content_sha256 == source.EVIDENCE_SHA256
    assert item.media_urls == ()
    assert client.calls == [source.IDENTITY.fetch_url]


@pytest.mark.parametrize(
    "old,new",
    [
        ("105 packs opened", "104 packs opened"),
        ("105 packs opened", "106 packs opened"),
        ("105 packs opened", "about 105 packs opened"),
        ("105 packs opened", "planned 105 packs opened"),
        ("105 packs opened", "105 packs unopened"),
        ("Pokémon with", "Lorcana with"),
        ("Auckland Showgrounds", "Different venue"),
        ("August 9th to 10th", "August 8th to 9th"),
        ("2025: Auckland", "2024: Auckland"),
        (source.PUBLISHED_AT, "2025-10-01T00:00:00Z"),
        ('rel="canonical"', 'rel="alternate"'),
        ("<p>Pokémon", "<p hidden>Pokémon"),
        ("<p>Pokémon", '<p aria-hidden="true">Pokémon'),
        ("<p>Pokémon", '<p style="display: none">Pokémon'),
        ("</main>", ""),
    ],
)
def test_drift_rejects_even_with_same_105_excerpt(
    reviewed_fixture: None, old: str, new: str
) -> None:
    with pytest.raises(CollectorError):
        source.verify_document(document().replace(old, new))


def test_duplicate_hidden_and_outside_facts_reject(reviewed_fixture: None) -> None:
    for changed in (
        document().replace("</main>", "<p>" + SEGMENT + "</p></main>"),
        document().replace("<p>" + SEGMENT + "</p>", "<script>" + SEGMENT + "</script>"),
        document()
        .replace("<p>" + SEGMENT + "</p>", "")
        .replace("</main>", "</main><p>" + SEGMENT + "</p>"),
        document().replace(
            "</head>",
            '<meta property="article:published_time" content="' + source.PUBLISHED_AT + '"></head>',
        ),
        document().replace("</main>", "<p>" + EVENT + "</p></main>"),
        document() + document(),
    ):
        with pytest.raises(CollectorError):
            source.verify_document(changed)


def test_inline_markup_preserves_facts(reviewed_fixture: None) -> None:
    source.verify_document(
        document().replace("105 packs opened", "<strong>105 packs</strong> <em>opened</em>")
    )


def test_only_reviewed_url_and_exact_config_can_fetch(reviewed_fixture: None) -> None:
    registry = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml")
    policy = registry.resolve(source.IDENTITY.fetch_url)
    client = FixtureClient(document())
    adapter = source.auckland_show_mighty_ape_adapter(client=client)
    for url in (
        source.IDENTITY.fetch_url + "?page=2",
        source.IDENTITY.fetch_url + "/",
        "https://www.aucklandcardshow.com/post/another-report",
    ):
        assert not registry.allows(url, "static")
        with pytest.raises(CollectorError):
            adapter.collect(url, policy)
    with pytest.raises(CollectorError):
        adapter.collect(
            source.IDENTITY.fetch_url,
            policy.model_copy(update={"config": {**source.POLICY_CONFIG, "set_language": "en"}}),
        )
    assert client.calls == []


def test_bounded_page_size(reviewed_fixture: None) -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        source.IDENTITY.fetch_url
    )
    for padding, accepted in ((1_500_000, True), (2_000_000, False)):
        client = FixtureClient(document().replace("</head>", "<!--" + "x" * padding + "--></head>"))
        adapter = source.auckland_show_mighty_ape_adapter(client=client)
        if accepted:
            assert len(adapter.collect(source.IDENTITY.fetch_url, policy)) == 1
        else:
            with pytest.raises(CollectorError):
                adapter.collect(source.IDENTITY.fetch_url, policy)
