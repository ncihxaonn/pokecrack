"""Synthetic feed fixtures; no publisher content retained."""

import pytest

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters.hatena_discovery import (
    discover_numbered_candidates,
)

ROOT = "https://www.kozaru02.com/entry/"


def feed(*entries):
    return '<feed xmlns="http://www.w3.org/2005/Atom">' + "".join(entries) + "</feed>"


def entry(slug, *, rel="alternate"):
    return f'<entry><link rel="{rel}" href="{ROOT}{slug}" /></entry>'


def test_stable_unique_candidates_without_counts():
    assert discover_numbered_candidates(feed(entry("b"), entry("a"), entry("a"))) == (
        ROOT + "a",
        ROOT + "b",
    )


def test_default_alternate_relation():
    assert discover_numbered_candidates(feed(f'<entry><link href="{ROOT}a" /></entry>')) == (
        ROOT + "a",
    )


@pytest.mark.parametrize("rel", ["self", "next", "enclosure", "related"])
def test_other_relations_are_not_candidates(rel):
    assert discover_numbered_candidates(feed(entry("a", rel=rel))) == ()


@pytest.mark.parametrize("suffix", ["a?x=1", "a#x", "../api/x", "a/b", "%61", ""])
def test_only_reviewed_canonical_article_routes(suffix):
    assert discover_numbered_candidates(feed(entry(suffix))) == ()


def test_content_and_external_links_are_not_discovery_authority():
    document = feed(
        f'<entry><content><link href="{ROOT}a" /></content>'
        '<link href="https://other.example/entry/a" /></entry>',
        f'<link rel="next" href="{ROOT}next" />',
    )
    assert discover_numbered_candidates(document) == ()


def test_ambiguous_entry_is_skipped_without_losing_other_entries():
    assert discover_numbered_candidates(
        feed(
            f'<entry><link href="{ROOT}a" /><link href="{ROOT}b" /></entry>',
            entry("c"),
        )
    ) == (ROOT + "c",)


@pytest.mark.parametrize(
    "document",
    [
        "x" * 1_000_001,
        "<feed>",
        "<feed />",
        "<rss />",
        '<!DOCTYPE feed [<!ENTITY x "value">]>' + feed(),
        feed(*(entry(str(n)) for n in range(201))),
    ],
)
def test_invalid_or_unbounded_feed_fails(document):
    with pytest.raises(CollectorError):
        discover_numbered_candidates(document)


def test_valid_empty_feed_is_not_an_error():
    assert discover_numbered_candidates(feed()) == ()
