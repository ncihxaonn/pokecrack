"""One original complete 36-pack report; the cited 753-pack study is not additive."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.deduplication.fingerprints import content_sha256

from .public_studies import ReviewedPublicStudyAdapter

IDENTITY = PUBLIC_STUDIES_BY_KEY["hitpack-pitch-black-cz-36-v1"]
TITLE = "Pokémon Pitch Black pull rates: co padlo z 36 boosterů?"
SOURCE_DATE = "28.7.2026"
EVIDENCE_EXCERPT = "36 balíčků"
EVIDENCE_SHA256 = content_sha256(EVIDENCE_EXCERPT)
INTRO_SHA256 = "d623f777eef4e435ff0de6163569dd262eafdd58d6e0d502bc939a8f52c1a89d"
OPENING_SHA256 = "4c1640753b045b0c5e900a426717d45bfba572f99baddd62227dc79eec9da689"
# Bound to the visible original article by the 2026-09-09 MAM-only HTTP probe.
ARTICLE_SHA256 = "1eeab92597b44a5b38c550641c388736ff7cda0544857bc2a15af368634379ad"
POLICY_CONFIG: dict[str, object] = {
    "study_key": IDENTITY.study_key,
    "canonical_url": IDENTITY.source_url,
    "collector_version": IDENTITY.collector_version,
    "parser_version": IDENTITY.parser_version,
    "country_code": "CZ",
    "country_name": "Czechia",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "publisher_country_url": "https://www.hitpack.cz/obchodni-podminky/",
    "publisher_country_review_method": "source_business_identity_matched_to_official_ares_country",
    "publisher_country_checked_at": "2026-09-09",
    "opening_country": None,
    "opened_at": None,
    "set_external_id": "me05",
    "set_language": "und",
    "set_language_basis": "opening_report_does_not_state_card_language",
    "set_name": "Pitch Black",
    "product_scope": "booster_box",
    "pack_count": 36,
    "observed_at": "2026-07-28T00:00:00Z",
    "source_publication_date": "2026-07-28",
    "publication_time_precision": "day",
    "observed_at_basis": "publication_date_utc_day_bucket_not_exact_timestamp",
    "denominator_complete": True,
    "cohort_id": "hitpack-pitch-black-box-20260728",
    "robots_url": "https://www.hitpack.cz/robots.txt",
    "robots_checked_at": "2026-09-09",
    "terms_url": "https://www.hitpack.cz/obchodni-podminky/",
    "terms_checked_at": "2026-09-09",
    "terms_status": "public_site_policy_reviewed",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}


class _Evidence(HTMLParser):
    """Only the visible original article container may supply opening evidence."""

    VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
    BLOCK = frozenset("p h1 h2 h3 div li ul ol table tr td th br".split())

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool, bool]] = []
        self.paragraph: list[str] | None = None
        self.paragraphs: list[str] = []
        self.article_parts: list[str] = []
        self.dates: list[str | None] = []
        self.canonicals: list[str | None] = []
        self.article_containers = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        hidden = (
            any(frame[1] for frame in self.stack)
            or tag in {"script", "style", "template", "noscript", "iframe"}
            or "hidden" in a
            or a.get("aria-hidden") == "true"
            or bool(
                re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", a.get("style") or "", re.I)
            )
        )
        in_main = any(frame[2] for frame in self.stack) or (
            tag == "main" and a.get("id") == "content"
        )
        article = in_main and tag == "div" and "news-item-detail" in (a.get("class") or "").split()
        if article and not hidden:
            self.article_containers += 1
        inside_article = any(frame[3] for frame in self.stack) or article
        if not hidden:
            if tag == "meta" and a.get("property") == "article:published_time":
                self.dates.append(a.get("content"))
            if tag == "link" and a.get("rel") == "canonical":
                self.canonicals.append(a.get("href"))
            if tag == "p" and inside_article:
                if self.paragraph is not None:
                    raise CollectorError("public study paragraph structure drifted")
                self.paragraph = []
            if inside_article and tag == "br":
                self.article_parts.append("\n")
                if self.paragraph is not None:
                    self.paragraph.append("\n")
        if tag not in self.VOID:
            self.stack.append((tag, hidden, in_main, inside_article))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if any(frame[1] for frame in self.stack):
            return
        if any(frame[3] for frame in self.stack):
            self.article_parts.append(data)
        if self.paragraph is not None:
            self.paragraph.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1][0] != tag:
            raise CollectorError("public study markup structure drifted")
        _, hidden, _, inside_article = self.stack.pop()
        if tag == "p" and self.paragraph is not None and not hidden:
            self.paragraphs.append(" ".join("".join(self.paragraph).split()))
            self.paragraph = None
        if inside_article and not hidden and tag in self.BLOCK:
            self.article_parts.append("\n")

    @property
    def article_sha256(self) -> str:
        return content_sha256(" ".join("".join(self.article_parts).split()))


def verify_document(document: str) -> None:
    parser = _Evidence()
    parser.feed(document)
    parser.close()
    if parser.stack or parser.paragraph is not None or parser.article_containers != 1:
        raise CollectorError("public study article structure drifted")
    if parser.canonicals != [IDENTITY.source_url] or parser.dates != [SOURCE_DATE]:
        raise CollectorError("public study canonical or publication date drifted")
    hashes = [content_sha256(p) for p in parser.paragraphs]
    if hashes.count(INTRO_SHA256) != 1 or hashes.count(OPENING_SHA256) != 1:
        raise CollectorError("public study original complete opening drifted")
    if not ARTICLE_SHA256 or parser.article_sha256 != ARTICLE_SHA256:
        raise CollectorError("public study article evidence drifted")


def hitpack_pitch_black_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=IDENTITY,
        expected_policy_config=POLICY_CONFIG,
        title_tokens=(TITLE,),
        content_tags=("main",),
        evidence_patterns=(re.compile(re.escape(EVIDENCE_EXCERPT)),),
        expected_evidence_sha256=EVIDENCE_SHA256,
        document_validator=verify_document,
    )
