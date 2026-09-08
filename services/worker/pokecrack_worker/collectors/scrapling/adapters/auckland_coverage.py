"""One organizer-reported event segment; no inferred sets, language or hit rate."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.deduplication.fingerprints import content_sha256

from .public_studies import ReviewedPublicStudyAdapter

IDENTITY = PUBLIC_STUDIES_BY_KEY["auckland-show-mighty-ape-nz-105-v1"]
TITLE_FRAGMENT = "Auckland Card Show 2025 Recap"
PUBLISHED_AT = "2025-09-30T00:08:20.972Z"
EVIDENCE_EXCERPT = "105 packs"
EVIDENCE_SHA256 = content_sha256(EVIDENCE_EXCERPT)
MAX_RESPONSE_BYTES = 2_000_000
# Hashes bind admission to reviewed visible facts without retaining article prose.
SEGMENT_SHA256 = "e9e68018bfe5228ab529b9885be1b8ed68912f9ce22621b6865ef182bceddb52"
EVENT_SHA256 = "d7435f63b8dea7ed23ca91174b4ba25cc288e1665b3b704384f94144b628ed23"
POLICY_CONFIG: dict[str, object] = {
    "study_key": "auckland-show-mighty-ape-nz-105-v1",
    "canonical_url": "https://www.aucklandcardshow.com/post/auckland-card-show-2025-recap",
    "collector_version": "public-study-auckland-show-v1",
    "parser_version": "auckland-show-105-evidence-v1",
    "country_code": "NZ",
    "country_name": "New Zealand",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "publisher_country_url": "https://www.aucklandcardshow.com/about",
    "opening_country": "NZ",
    "opened_on": "2025-08-10",
    "set_external_id": "mixed-pokemon-tcg-2025",
    "set_language": "und",
    "set_scope": "mixed_multi_expansion",
    "set_name": "Mixed Pokémon TCG expansions",
    "product_scope": "all",
    "pack_count": 105,
    "observed_at": "2025-09-30T00:08:20.972Z",
    "denominator_complete": True,
    "cohort_id": "auckland-card-show-2025-mighty-ape-105",
    "robots_url": "https://www.aucklandcardshow.com/robots.txt",
    "robots_checked_at": "2026-09-09",
    "terms_url": "https://www.aucklandcardshow.com/terms-of-use",
    "terms_checked_at": "2026-09-09",
    "terms_status": "public_site_policy_reviewed",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}


class _Evidence(HTMLParser):
    """Use visible paragraphs only; Wix hydration JSON is not opening evidence."""

    VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []
        self.paragraph: list[str] | None = None
        self.paragraphs: list[str] = []
        self.dates: list[str | None] = []
        self.canonicals: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        hidden = (
            any(item[1] for item in self.stack)
            or tag in {"script", "style", "template", "noscript", "iframe"}
            or "hidden" in attributes
            or attributes.get("aria-hidden") == "true"
            or bool(
                re.search(
                    r"display\s*:\s*none|visibility\s*:\s*hidden",
                    attributes.get("style") or "",
                    re.I,
                )
            )
        )
        if not hidden:
            if tag == "meta" and attributes.get("property") == "article:published_time":
                self.dates.append(attributes.get("content"))
            if tag == "link" and attributes.get("rel") == "canonical":
                self.canonicals.append(attributes.get("href"))
            if tag == "p" and any(item[0] == "main" for item in self.stack):
                if self.paragraph is not None:
                    raise CollectorError("public study paragraph structure drifted")
                self.paragraph = []
        if tag not in self.VOID:
            self.stack.append((tag, hidden))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.paragraph is not None and not any(item[1] for item in self.stack):
            self.paragraph.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1][0] != tag:
            raise CollectorError("public study markup structure drifted")
        hidden = any(item[1] for item in self.stack)
        self.stack.pop()
        if tag == "p" and self.paragraph is not None and not hidden:
            self.paragraphs.append(" ".join("".join(self.paragraph).split()))
            self.paragraph = None


def verify_document(document: str) -> None:
    parser = _Evidence()
    parser.feed(document)
    parser.close()
    if parser.stack or parser.paragraph is not None:
        raise CollectorError("public study markup is incomplete")
    if parser.dates != [PUBLISHED_AT] or parser.canonicals != [IDENTITY.source_url]:
        raise CollectorError("public study date or canonical identity drifted")
    segments = [p for p in parser.paragraphs if "Mighty Ape" in p and "packs" in p]
    # Exclude other giveaways, attendance, approximate crowd counts and other games.
    if len(segments) != 1 or re.findall(r"\b(\d+) packs\s+opened\b", segments[0]) != ["105"]:
        raise CollectorError("public study exact complete segment denominator drifted")
    if "Pokémon" not in segments[0]:
        raise CollectorError("public study game identity drifted")
    events = [
        p for p in parser.paragraphs if "Auckland Showgrounds" in p and "August 9th to 10th" in p
    ]
    if len(events) != 1 or content_sha256(events[0]) != EVENT_SHA256:
        raise CollectorError("public study event identity drifted")
    if content_sha256(segments[0]) != SEGMENT_SHA256:
        raise CollectorError("public study complete opening evidence drifted")


def auckland_show_mighty_ape_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=IDENTITY,
        expected_policy_config=POLICY_CONFIG,
        title_tokens=(TITLE_FRAGMENT,),
        content_tags=("main",),
        evidence_patterns=(re.compile(r"\b105 packs\b"),),
        expected_evidence_sha256=EVIDENCE_SHA256,
        document_validator=verify_document,
        max_response_bytes=MAX_RESPONSE_BYTES,
    )
