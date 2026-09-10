"""Synthetic fixtures only; no publisher prose or media copied into tests."""

from datetime import UTC, datetime

import pytest

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters.hatena_numbered import parse_numbered_opening

URL = "https://www.kozaru02.com/entry/synthetic-opening"
PRODUCT = "MEGAドリームex"
DATE = "2026-01-10T08:11:34Z"
NOW = datetime(2026, 9, 10, tzinfo=UTC)
IMAGE = "https://cdn-ak.f.st-hatena.com/images/fotolife/k/kozaru02/20260110/"


def page(numbers=range(1, 11), *, date=DATE, extra="", product=PRODUCT):
    figures = "".join(
        f'<figure><img src="{IMAGE}{20260110000000 + n}.jpg">'
        f"<figcaption>{n}パック目</figcaption></figure>"
        for n in numbers
    )
    return (
        f'<link rel="canonical" href="{URL}">'
        f'<meta property="article:published_time" content="{date}">'
        f'<article><div class="entry-content"><p>{product}</p>{figures}{extra}</div></article>'
    )


def parse(document, **overrides):
    args = dict(expected_url=URL, product_label=PRODUCT, expected_pack_count=10, now=NOW)
    args.update(overrides)
    return parse_numbered_opening(document, **args)


def test_complete_captions_return_minimal_candidate():
    result = parse(page())
    assert result.pack_count == 10
    assert result.published_at == "2026-01-10T08:11:34+00:00"
    assert result.opening_country is None and result.opened_at is None
    assert result.statistics_eligible is False
    assert result.evidence_sha256 == parse(page()).evidence_sha256
    assert len(set(result.resource_sha256s)) == 10
    assert all(len(value) == 64 for value in result.resource_sha256s)


@pytest.mark.parametrize(
    "numbers", [range(1, 10), range(2, 11), [1] * 10, range(10, 0, -1), range(1, 12)]
)
def test_incomplete_or_duplicate_positions_fail(numbers):
    with pytest.raises(CollectorError):
        parse(page(numbers))


@pytest.mark.parametrize("wrapper", ["script", "style", "template", "noscript", "nav"])
def test_hidden_labels_do_not_complete_report(wrapper):
    with pytest.raises(CollectorError):
        parse(
            page(
                range(1, 10),
                extra=f"<{wrapper}><figure><figcaption>10パック目</figcaption></figure></{wrapper}>",
            )
        )


@pytest.mark.parametrize("attrs", ["hidden", 'aria-hidden="true"', 'style="display: none"'])
def test_hidden_elements_do_not_complete_report(attrs):
    with pytest.raises(CollectorError):
        parse(
            page(
                range(1, 10),
                extra=f"<div {attrs}><figure><figcaption>10パック目</figcaption></figure></div>",
            )
        )


@pytest.mark.parametrize(
    "extra", ["<p>10パック目</p>", "<!-- <figure><figcaption>10パック目</figcaption></figure> -->"]
)
def test_body_mentions_and_comments_are_not_captions(extra):
    with pytest.raises(CollectorError):
        parse(page(range(1, 10), extra=extra))


@pytest.mark.parametrize("date", ["", "2026-01-10", "2027-01-01T00:00:00Z", "invalid"])
def test_invalid_publication_fails(date):
    with pytest.raises(CollectorError):
        parse(page(date=date))


def test_identity_product_and_structure_drift_fail():
    cases = [
        page().replace(URL, URL + "-other"),
        page(product="other"),
        page() + f'<link rel="canonical" href="{URL}">',
        page() + f'<meta property="article:published_time" content="{DATE}">',
        page().replace("</figcaption>", "", 1),
        page().replace("</figure><figure>", ""),
        page().replace("</div></article>", ""),
        page().removesuffix("</article>"),
        page().replace("</div></article>", "</article></div>"),
        page().replace(
            "<figcaption>1パック目</figcaption>", "<figcaption><b>1パック目</figcaption></b>"
        ),
        page().replace('<div class="entry-content">', "<div>"),
        page().replace("<article>", "<aside>").replace("</article>", "</aside>"),
    ]
    for document in cases:
        with pytest.raises(CollectorError):
            parse(document)


def test_reviewed_layout_is_bounded():
    for overrides in (
        {"expected_url": "https://other.example/entry/x"},
        {"expected_pack_count": True},
        {"expected_pack_count": 1001},
        {"now": datetime(2026, 9, 10)},
        {"product_label": ""},
    ):
        with pytest.raises(CollectorError):
            parse(page(), **overrides)
    with pytest.raises(CollectorError):
        parse("x" * 1_000_001)


def test_fullwidth_and_inline_caption_markup():
    document = page().replace("1パック目", "<b>１</b>パック目")
    assert parse(document).pack_count == 10


def test_nested_figures_cannot_split_one_figure_into_multiple_records():
    with pytest.raises(CollectorError):
        parse(page().replace("</figure><figure>", "<figure></figure>"))


def test_hidden_caption_cannot_close_the_visible_caption():
    document = page().replace(
        "1パック目</figcaption>",
        "1パック目<template><figcaption>ignored</figcaption></template>invalid</figcaption>",
    )
    with pytest.raises(CollectorError):
        parse(document)


def test_navigation_product_text_is_not_opening_product_evidence():
    with pytest.raises(CollectorError):
        parse(page(product="unrelated", extra=f"<nav>{PRODUCT}</nav>"))


@pytest.mark.parametrize(
    "replacement",
    [
        "",
        '<img src="https://other.example/image.jpg">',
        f'<img src="{IMAGE}20260110000001.jpg?resize=100">',
        f'<img src="{IMAGE}20260110000001.jpg#fragment">',
        f'<img src="{IMAGE}20260111000001.jpg">',
        f'<img src="{IMAGE}20260110000001.jpg"><img src="{IMAGE}20260110000002.jpg">',
    ],
)
def test_numbered_resource_must_be_singular_and_reviewed(replacement):
    with pytest.raises(CollectorError):
        parse(page().replace(f'<img src="{IMAGE}20260110000001.jpg">', replacement, 1))


def test_reused_numbered_resource_fails():
    with pytest.raises(CollectorError):
        parse(page().replace("20260110000002.jpg", "20260110000001.jpg"))


def test_decorative_resources_do_not_change_opening_identity():
    original = parse(page())
    decorated = parse(page(extra='<figure><img src="https://other.example/logo.jpg"></figure>'))
    assert original == decorated


def test_resource_keys_survive_page_reposting_but_evidence_keys_do_not():
    other_url = URL + "-repost"
    first = parse(page())
    second = parse(page().replace(URL, other_url), expected_url=other_url)
    assert first.resource_sha256s == second.resource_sha256s
    assert first.evidence_sha256 != second.evidence_sha256
