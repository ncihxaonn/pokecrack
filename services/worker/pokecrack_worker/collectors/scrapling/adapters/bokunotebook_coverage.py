"""One reviewed Thai-language pack; never infer a physical opening country."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.deduplication.fingerprints import content_sha256

from .public_studies import ReviewedPublicStudyAdapter

IDENTITY = PUBLIC_STUDIES_BY_KEY["bokunotebook-vstar-universe-th-1-v1"]
TITLE = "タイ語版ポケモンカードをタイのドンキホーテで買って開封してみる。"
EVIDENCE_EXCERPT = "1パック\nVSTARユニバース\n全部で10枚"
EVIDENCE_SHA256 = content_sha256(EVIDENCE_EXCERPT)
PUBLISHED_AT = "2026-07-01T21:01:46+09:00"
POLICY_CONFIG: dict[str, object] = {
    "study_key": IDENTITY.study_key,
    "canonical_url": IDENTITY.source_url,
    "collector_version": IDENTITY.collector_version,
    "parser_version": IDENTITY.parser_version,
    "country_code": "TH",
    "country_name": "Thailand",
    "geography_basis": "product_market",
    "geography_confidence": "tier_b",
    "set_external_id": "s12a",
    "set_language": "th",
    "set_name": "จักรวาลแห่ง VSTAR",
    "product_scope": "all",
    "pack_count": 1,
    "observed_at": "2026-07-01T12:01:46Z",
    "denominator_complete": True,
    "set_official_url": "https://asia.pokemon-card.com/th/archive/special/card/s12a/index.html",
    "robots_url": "https://bokunotebook.com/robots.txt",
    "robots_checked_at": "2026-09-08",
    "terms_url": "https://bokunotebook.com/privacy-policy",
    "terms_checked_at": "2026-09-08",
    "terms_status": "public_site_policy_reviewed",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
    "opening_country": None,
    "opened_at": None,
    "observed_card_count": 10,
}


class _Evidence(HTMLParser):
    """Read visible blocks of the exact article, excluding navigation and embeds."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []
        self.article_count = 0
        self.inside = False
        self.active: str | None = None
        self.parts: list[str] = []
        self.blocks: list[tuple[str, str]] = []
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
            if tag == "article":
                if self.inside:
                    raise CollectorError("public study article identity drifted")
                # WordPress renders separate related-post articles after the report.
                # They must neither supply evidence nor invalidate the exact report.
                if attributes.get("id") == "post-13725":
                    self.article_count += 1
                    self.inside = True
            if self.inside and tag in {"h1", "h2", "h3", "p"}:
                if self.active:
                    raise CollectorError("public study nested evidence blocks")
                self.active, self.parts = tag, []
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.stack.append((tag, hidden))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1][0] == tag:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.inside and self.active and not any(item[1] for item in self.stack):
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack[-1][0] != tag:
            raise CollectorError("public study markup structure drifted")
        hidden = any(item[1] for item in self.stack)
        self.stack.pop()
        if hidden:
            return
        if self.inside and tag == self.active:
            self.blocks.append((tag, "".join("".join(self.parts).split())))
            self.active, self.parts = None, []
        if tag == "article":
            self.inside = False


def verify_document(document: str) -> None:
    parser = _Evidence()
    parser.feed(document)
    parser.close()
    if parser.stack or parser.inside or parser.active or parser.article_count != 1:
        raise CollectorError("public study incomplete or duplicate article")
    if parser.dates != [PUBLISHED_AT] or parser.canonicals != [IDENTITY.source_url]:
        raise CollectorError("public study publication or canonical identity drifted")
    if [text for tag, text in parser.blocks if tag == "h1"] != [TITLE]:
        raise CollectorError("public study title identity drifted")
    paragraphs = [text for tag, text in parser.blocks if tag == "p"]
    purchases = [
        m[1]
        for text in paragraphs
        for m in re.finditer(r"なんとなく(\d+)パック買ってみました", text)
    ]
    confirmations = [
        m[1] for text in paragraphs for m in re.finditer(r"とりあえず(\d+)パック買った", text)
    ]
    if purchases != ["1"] or confirmations != ["1"]:
        raise CollectorError("public study complete pack denominator drifted")
    if sum("どうやらVSTARユニバースというパック" in text for text in paragraphs) != 1:
        raise CollectorError("public study product version drifted")
    in_opening = False
    openings = 0
    card_counts: list[str] = []
    for tag, text in parser.blocks:
        if tag in {"h1", "h2", "h3"}:
            in_opening = tag == "h3" and text == "早速開封してみる"
            openings += int(in_opening)
        elif in_opening and tag == "p" and "開封したところ" in text:
            card_counts.extend(re.findall(r"全部で(\d+)枚入っていました", text))
    if openings != 1 or card_counts != ["10"]:
        raise CollectorError("public study actual opened-card evidence drifted")


def bokunotebook_vstar_universe_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=IDENTITY,
        expected_policy_config=POLICY_CONFIG,
        title_tokens=(TITLE,),
        evidence_patterns=tuple(
            re.compile(re.escape(part)) for part in EVIDENCE_EXCERPT.split("\n")
        ),
        expected_evidence_sha256=EVIDENCE_SHA256,
        document_validator=verify_document,
        max_response_bytes=524288,
    )
