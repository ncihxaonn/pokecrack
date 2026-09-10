"""One explicitly approved complete 30-pack report; no weights or media retained."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.deduplication.fingerprints import content_sha256

from .public_studies import ReviewedPublicStudyAdapter

IDENTITY = PUBLIC_STUDIES_BY_KEY["tekemero-munikis-zero-jp-30-v1"]
PUBLICATION = "2026-07-15T15:48:03+09:00"
TITLE_SHA256 = "f55b0821fb41a66088b925b5d89f36a3d78c2d4e1417d53fe4f8681b98b39b42"
OPENING_SHA256 = "29a5a4d3cf31a546b13f84649839d2329aa15f2e2834ec80ec9ffaf382004bfa"
# Observed by the read-only MAM parser probe; source body is never retained.
BODY_SHA256 = "1d70d72e779134e2cc5030b7075ee8d03283bec3991da606f95b03c2e927c8d8"
EVIDENCE_EXCERPT = "30パック"
EVIDENCE_SHA256 = content_sha256(EVIDENCE_EXCERPT)
POLICY_CONFIG: dict[str, object] = {
    "study_key": IDENTITY.study_key,
    "canonical_url": IDENTITY.source_url,
    "collector_version": IDENTITY.collector_version,
    "parser_version": IDENTITY.parser_version,
    "country_code": "JP",
    "country_name": "Japan",
    "geography_basis": "product_market",
    "geography_confidence": "tier_b",
    "opening_country": None,
    "opened_at": None,
    "set_external_id": "M3",
    "set_language": "ja",
    "set_name": "ムニキスゼロ",
    "set_official_url": "https://www.pokemon-card.com/ex/m3/",
    "product_scope": "booster_box",
    "pack_count": 30,
    "observed_at": "2026-07-15T06:48:03Z",
    "observed_at_basis": "original_article_publication_not_opening_time",
    "denominator_complete": True,
    "cohort_id": "tekemero-post-447-m3-complete-box",
    "robots_url": "https://tekemero.com/robots.txt",
    "robots_checked_at": "2026-09-09",
    "terms_url": "https://tekemero.com/privacy-policy/",
    "terms_checked_at": "2026-09-09",
    "terms_status": "privacy_policy_reviewed_no_separate_terms_found",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}


class _Evidence(HTMLParser):
    """Bind facts to the primary body; accommodate HTML's implicit p closing."""

    VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
    BLOCK = frozenset("p h1 h2 h3 h4 div section article ul ol li table tr td th br".split())

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        # tag, hidden, primary article, primary section, primary body
        self.stack: list[tuple[str, bool, bool, bool, bool, bool, bool]] = []
        self.canonicals: list[str | None] = []
        self.article_count = 0
        self.body_count = 0
        self.body_parts: list[str] = []
        self.paragraph: list[str] | None = None
        self.paragraphs: list[str] = []
        self.title: list[str] | None = None
        self.titles: list[str] = []
        self.jsonld: list[str] | None = None
        self.publications: list[str | None] = []

    def _finish_paragraph(self) -> None:
        if self.paragraph is not None:
            self.paragraphs.append(" ".join("".join(self.paragraph).split()))
            self.paragraph = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        ancestor_hidden = any(frame[1] for frame in self.stack)
        own_hidden = (
            "hidden" in a
            or a.get("aria-hidden") == "true"
            or bool(
                re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", a.get("style") or "", re.I)
            )
        )
        hidden = (
            ancestor_hidden
            or own_hidden
            or tag in {"script", "style", "template", "noscript", "iframe"}
        )
        classes = (a.get("class") or "").split()
        primary = (
            tag == "article"
            and a.get("id") == "post-447"
            and {"post-447", "type-post"} <= set(classes)
        )
        if primary and not hidden:
            self.article_count += 1
        in_article = any(frame[2] for frame in self.stack) or primary
        section = in_article and tag == "section" and "single-post-main" in classes
        in_section = any(frame[3] for frame in self.stack) or section
        body = in_section and tag == "div" and "content" in classes
        in_body = any(frame[4] for frame in self.stack) or body
        if body and not hidden:
            self.body_count += 1
        if (
            tag == "script"
            and a.get("type") == "application/ld+json"
            and not (ancestor_hidden or own_hidden)
        ):
            self.jsonld = []
        if not hidden:
            if tag == "link" and a.get("rel") == "canonical":
                self.canonicals.append(a.get("href"))
            if tag == "br" and in_body:
                self.body_parts.append("\n")
                if self.paragraph is not None:
                    self.paragraph.append("\n")
            elif tag in self.BLOCK and in_body:
                self._finish_paragraph()
                self.body_parts.append("\n")
            if tag == "p" and in_body:
                # WordPress emits unclosed p tags around blocks. A new p
                # closes the old one in HTML; no content escapes the body.
                self.paragraph = []
            if tag == "h1" and in_article:
                self.title = []
        if tag not in self.VOID:
            self.stack.append((tag, hidden, in_article, in_section, in_body, primary, body))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.jsonld is not None:
            self.jsonld.append(data)
            return
        if any(frame[1] for frame in self.stack):
            return
        if any(frame[4] for frame in self.stack):
            self.body_parts.append(data)
        if self.paragraph is not None:
            self.paragraph.append(data)
        if self.title is not None:
            self.title.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.jsonld is not None:
            try:
                value = json.loads("".join(self.jsonld))
            except ValueError as error:
                raise CollectorError("public study metadata malformed") from error
            self.jsonld = None
            nodes = (
                value
                if isinstance(value, list)
                else value.get("@graph", [value])
                if isinstance(value, dict)
                else []
            )
            for node in nodes:
                if not isinstance(node, dict) or node.get("@type") != "BlogPosting":
                    continue
                main = node.get("mainEntityOfPage")
                if main == {"@type": "WebPage", "@id": IDENTITY.source_url}:
                    title = node.get("headline")
                    if (
                        not isinstance(title, str)
                        or content_sha256(" ".join(title.split())) != TITLE_SHA256
                    ):
                        raise CollectorError("public study metadata title drifted")
                    self.publications.append(node.get("datePublished"))
        hidden = any(frame[1] for frame in self.stack)
        if not hidden:
            if tag in self.BLOCK:
                self._finish_paragraph()
                if any(frame[4] for frame in self.stack):
                    self.body_parts.append("\n")
            if tag == "h1" and self.title is not None:
                self.titles.append(" ".join("".join(self.title).split()))
                self.title = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                if any((frame[5] or frame[6]) and frame[0] != tag for frame in self.stack[index:]):
                    raise CollectorError("public study primary container not closed")
                del self.stack[index:]
                break

    @property
    def body_sha256(self) -> str:
        return content_sha256(" ".join("".join(self.body_parts).split()))


def verify_document(document: str) -> None:
    parsed = _Evidence()
    parsed.feed(document)
    parsed.close()
    if (
        parsed.stack
        or parsed.jsonld is not None
        or parsed.article_count != 1
        or parsed.body_count != 1
    ):
        raise CollectorError("public study article structure drifted")
    if parsed.canonicals != [IDENTITY.source_url] or parsed.publications != [PUBLICATION]:
        raise CollectorError("public study canonical or original date drifted")
    if [content_sha256(title) for title in parsed.titles] != [TITLE_SHA256]:
        raise CollectorError("public study primary title drifted")
    if [content_sha256(p) for p in parsed.paragraphs].count(OPENING_SHA256) != 1:
        raise CollectorError("public study complete opening drifted")
    if not BODY_SHA256 or parsed.body_sha256 != BODY_SHA256:
        raise CollectorError("public study body evidence drifted")


def tekemero_munikis_zero_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=IDENTITY,
        expected_policy_config=POLICY_CONFIG,
        title_tokens=("ムニキスゼロ", "30パック"),
        content_tags=("main",),
        evidence_patterns=(re.compile(re.escape(EVIDENCE_EXCERPT)),),
        expected_evidence_sha256=EVIDENCE_SHA256,
        document_validator=verify_document,
    )
