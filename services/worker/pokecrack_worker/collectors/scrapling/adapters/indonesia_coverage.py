"""Exact first-box evidence from BIKUHIME; no inferred hit probabilities."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY

from .public_studies import ReviewedPublicStudyAdapter

IDENTITY = PUBLIC_STUDIES_BY_KEY["bikuhime-hantaman-pertama-a-id-20-v1"]
POLICY_CONFIG: dict[str, object] = {
    "study_key": "bikuhime-hantaman-pertama-a-id-20-v1",
    "canonical_url": "https://bikuhime.wordpress.com/2020/05/17/yang-perlu-diketahui-sebelum-beli-booster-box-pokemon-tcg-bag-1/",
    "collector_version": "public-study-bikuhime-hantaman-pertama-a-v1",
    "parser_version": "bikuhime-hantaman-pertama-a-evidence-v1",
    "country_code": "ID",
    "country_name": "Indonesia",
    "geography_basis": "product_market",
    "geography_confidence": "tier_b",
    "set_external_id": "hantaman-pertama-set-a",
    "set_language": "id",
    "set_name": "Hantaman Pertama Set A",
    "product_scope": "booster_box",
    "pack_count": 20,
    "observed_at": "2020-05-17T07:23:58Z",
    "denominator_complete": True,
    "set_official_url": "https://asia.pokemon-card.com/id/archive/card/sun_moon_series/1st_booster_pack_seta.html",
    "robots_url": "https://bikuhime.wordpress.com/robots.txt",
    "robots_checked_at": "2026-09-08",
    "terms_url": "https://wordpress.com/tos/",
    "terms_checked_at": "2026-09-08",
    "terms_status": "public_site_policy_reviewed",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}
TITLE = "Yang Perlu Diketahui Sebelum Beli Booster Box Pokemon TCG (Bag. 1)"
FIRST_BOX = "Hantaman Pertama Set A (pembelian pertama)"
EVIDENCE_EXCERPT = FIRST_BOX + "\n1 booster box = 20 booster pack"
EVIDENCE_SHA256 = "693653031f398c3006a7aa6d3b476c968f5b3f67d6452e73d904ed1ef377b328"


class _EvidenceTable(HTMLParser):
    """Read a bounded HTML document in memory; retain no article or hit rows."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.article_depth = 0
        self.hidden_depth = 0
        self.table_depth = 0
        self.table_count = 0
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.cell: list[str] | None = None
        self.publication: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in {"script", "style", "template", "noscript"}:
            self.hidden_depth += 1
        if self.hidden_depth:
            return
        if tag == "meta" and attributes.get("property") == "article:published_time":
            self.publication.append(attributes.get("content"))
        if tag == "article":
            self.article_depth += 1
        if not self.article_depth:
            return
        if tag == "table":
            self.table_depth += 1
            self.table_count += 1
        if self.table_depth and tag == "tr":
            self.row = []
        if self.table_depth and tag in {"td", "th"}:
            if attributes.get("colspan", "1") != "1" or attributes.get("rowspan", "1") != "1":
                raise CollectorError("public study merged table cells are not reviewed")
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None and not self.hidden_depth:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1
            return
        if self.hidden_depth:
            return
        if self.table_depth and tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if self.table_depth and tag == "tr":
            self.rows.append(self.row)
        if tag == "table" and self.table_depth:
            self.table_depth -= 1
        if tag == "article" and self.article_depth:
            self.article_depth -= 1


def _verify_document(document: str) -> None:
    parser = _EvidenceTable()
    parser.feed(document)
    parser.close()
    if parser.publication != ["2020-05-17T07:23:58+00:00"]:
        raise CollectorError("public study publication identity drifted")
    expected_headers = [
        "Tipe",
        FIRST_BOX,
        "Hantaman Pertama set B (pembelian pertama)",
        "Hantaman Pertama set A (pembelian kedua)",
        "%",
    ]
    if (
        parser.table_count != 1
        or len(parser.rows) != 7
        or any(len(row) != 5 for row in parser.rows)
        or parser.rows[0] != expected_headers
    ):
        raise CollectorError("public study first-box column identity drifted")
    # Validate the complete first box, not the other two boxes or the author's
    # estimated odds. These card totals are only a scope check, never a numerator.
    if [(row[0], row[1]) for row in parser.rows[1:]] != [
        ("C", "61"),
        ("U", "24"),
        ("R", "12"),
        ("RR", "2"),
        ("UR", "1"),
        ("SR", "0"),
    ]:
        raise CollectorError("public study first-box completeness evidence drifted")


def bikuhime_hantaman_pertama_a_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=IDENTITY,
        expected_policy_config=POLICY_CONFIG,
        title_tokens=(TITLE,),
        evidence_patterns=tuple(
            re.compile(re.escape(part)) for part in EVIDENCE_EXCERPT.split("\n")
        ),
        expected_evidence_sha256=EVIDENCE_SHA256,
        document_validator=_verify_document,
    )
