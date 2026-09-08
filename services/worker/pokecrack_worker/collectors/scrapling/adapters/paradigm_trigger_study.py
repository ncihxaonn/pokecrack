"""Pure parser for one primary 100-pack report, not normalized hit-rate evidence."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser

from pokecrack_worker.collectors.base import CollectorError

SOURCE_URL = "https://nanjakorya.com/1823"
PUBLISHED_AT = "2022-10-21T20:10:35+09:00"
TITLE = "パラダイムトリガー開封結果まとめ"
HEADERS = ("No", "1枚目(C)", "2枚目(C)", "3枚目(C)", "4枚目", "5枚目(U)")
EXPECTED_RARITIES = (
    "U RR R U R U RRR U R U R U RR U R U U HR U R U R U U RRR RR RR U R U",
    "RR RRR U R U U U U R U",
    "RR U U R U RRR U RR U U RR U R U RR RR U RRR U R U R U R U U SR U U R",
    "R RR U U R U U RR RRR U RRR U R U U U R R R U U U R RR U RR U R U HR",
)
PURCHASE_GROUPS = (
    "■ローソンにて1箱購入",
    "■別店舗のローソンにて10パック限の購入",
    "■GEOにて1BOX購入",
    "■TUTAYAにて1BOX購入",
)


def _normalize(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split())


class _Tables(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden: list[str] = []
        self.article_depth = 0
        self.article_count = 0
        self.article_stack: list[int] = []
        self.title_owners: list[int] = []
        self.evidence_owners: list[int] = []
        self.dates: list[str | None] = []
        self.titles: list[str] = []
        self.groups: list[str] = []
        self.tables: list[list[list[str]]] = []
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: str | None = None
        self.block: str | None = None
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "template", "noscript"}:
            self.hidden.append(tag)
        if self.hidden:
            return
        attributes = dict(attrs)
        if tag == "meta" and attributes.get("property") == "article:published_time":
            self.dates.append(attributes.get("content"))
        if tag == "article":
            self.article_depth += 1
            self.article_count += 1
            self.article_stack.append(self.article_count)
        if not self.article_depth:
            return
        if tag == "table":
            if self.table is not None or self.block is not None:
                raise CollectorError("public study nested table structure")
            self.table = []
        elif tag == "tr" and self.table is not None:
            if self.row is not None:
                raise CollectorError("public study nested row structure")
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            if self.cell is not None:
                raise CollectorError("public study nested cell structure")
            self.cell, self.parts = tag, []
        elif tag in {"h1", "p"} and self.table is None:
            if self.block is not None:
                raise CollectorError("public study nested evidence block")
            self.block, self.parts = tag, []

    def handle_data(self, data: str) -> None:
        if not self.hidden and (self.cell is not None or self.block is not None):
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template", "noscript"} and self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if self.hidden:
            return
        if self.cell is not None and tag == self.cell:
            if self.row is None:
                raise CollectorError("public study cell outside row")
            self.row.append(_normalize("".join(self.parts)))
            self.cell, self.parts = None, []
        elif self.block is not None and tag == self.block:
            text = _normalize("".join(self.parts))
            if self.block == "h1":
                self.titles.append(text)
                self.title_owners.append(self.article_stack[-1])
            elif text.startswith("■"):
                # Keep each purchase label tied to the following table.
                if len(self.groups) != len(self.tables):
                    raise CollectorError("public study duplicate purchase label")
                self.groups.append(text)
                self.evidence_owners.append(self.article_stack[-1])
            self.block, self.parts = None, []
        elif tag == "tr" and self.row is not None:
            if self.cell is not None or self.table is None:
                raise CollectorError("public study incomplete row")
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            if self.row is not None or len(self.groups) != len(self.tables) + 1:
                raise CollectorError("public study incomplete or unattributed table")
            self.tables.append(self.table)
            self.evidence_owners.append(self.article_stack[-1])
            self.table = None
        elif tag == "article" and self.article_depth:
            if self.table is not None or self.block is not None:
                raise CollectorError("public study incomplete article")
            self.article_depth -= 1
            self.article_stack.pop()


@dataclass(frozen=True, slots=True)
class ParadigmTriggerReport:
    pack_count: int
    rarity_card_counts: tuple[int, int, int, int]
    source_published_at: str
    evidence_sha256: str
    opening_country: None = None
    opened_at: None = None
    statistics_eligible: bool = False


def parse_paradigm_trigger_report(document: str) -> ParadigmTriggerReport:
    if len(document.encode("utf-8")) > 524288:
        raise CollectorError("public study response exceeds reviewed bound")
    parser = _Tables()
    parser.feed(document)
    parser.close()
    if (
        parser.hidden
        or parser.article_depth
        or not parser.article_count
        or parser.table is not None
        or parser.row is not None
        or parser.cell is not None
        or parser.block is not None
    ):
        raise CollectorError("public study incomplete evidence structure")
    if parser.dates != [PUBLISHED_AT] or parser.titles != [TITLE]:
        raise CollectorError("public study publication identity drifted")
    # WordPress related-post cards are additional articles, not evidence. All
    # purchase labels and tables must still belong to the one titled report.
    if any(owner != parser.title_owners[0] for owner in parser.evidence_owners):
        raise CollectorError("public study tables belong to another article")
    if tuple(parser.groups) != PURCHASE_GROUPS or len(parser.tables) != 4:
        raise CollectorError("public study purchase group attribution drifted")
    observed: list[str] = []
    for table, expected in zip(parser.tables, EXPECTED_RARITIES, strict=True):
        rarities = expected.split()
        if len(table) != len(rarities) + 1 or tuple(table[0]) != HEADERS:
            raise CollectorError("public study table size or header drifted")
        for row, rarity in zip(table[1:], rarities, strict=True):
            if len(row) != 6 or not all(row) or row[0] != str(len(observed) + 1):
                raise CollectorError("public study pack numbering or completeness drifted")
            match = re.fullmatch(r"[^()]+\((U|R|RR|RRR|SR|HR)\)", row[4])
            if match is None or match[1] != rarity:
                raise CollectorError("public study reported rarity drifted")
            observed.append(rarity)
    counts = tuple(observed.count(rarity) for rarity in ("RR", "RRR", "SR", "HR"))
    if len(observed) != 100 or counts != (14, 7, 1, 2):
        raise CollectorError("public study reported totals drifted")
    # The source labels Terrakion both R and U. Do not correct source labels or
    # infer normalized rarity/pack rates from these native reported facts.
    evidence = json.dumps(
        {
            "source": SOURCE_URL,
            "published": PUBLISHED_AT,
            "groups": parser.groups,
            "rarities": observed,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return ParadigmTriggerReport(
        100, (14, 7, 1, 2), PUBLISHED_AT, hashlib.sha256(evidence.encode()).hexdigest()
    )
