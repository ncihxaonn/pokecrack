"""Pure parser for a reviewed 100-pack Star Birth report; no network/admission."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from pokecrack_worker.collectors.base import CollectorError

SOURCE_URL = "https://nanjakorya.com/1123"
PUBLISHED_AT = "2022-02-22T05:40:46+09:00"
EXPECTED_GROUPS = (
    (1, 10, (2, 0, 1, 0)),
    (11, 20, (0, 1, 0, 1)),
    (21, 30, (1, 0, 0, 0)),
    (31, 50, (3, 2, 0, 0)),
    (51, 60, (2, 1, 1, 0)),
    (61, 70, (3, 0, 0, 0)),
    (71, 80, (1, 1, 1, 0)),
    (81, 90, (2, 0, 0, 0)),
    (91, 100, (2, 1, 1, 0)),
)
RARITIES = ("RR", "RRR", "SR", "HR")


class _Sections(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.article_depth = 0
        self.hidden: list[str] = []
        self.active: str | None = None
        self.parts: list[str] = []
        self.blocks: list[tuple[str, str]] = []
        self.dates: list[str | None] = []

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
        if self.article_depth and tag in {"h1", "h2", "h3", "p"}:
            if self.active is not None:
                raise CollectorError("nested evidence blocks are not supported")
            self.active, self.parts = tag, []

    def handle_data(self, data: str) -> None:
        if self.active is not None and not self.hidden:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template", "noscript"} and self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if self.hidden:
            return
        if tag == self.active:
            self.blocks.append((tag, "".join("".join(self.parts).split())))
            self.active, self.parts = None, []
        if tag == "article" and self.article_depth:
            self.article_depth -= 1


@dataclass(frozen=True, slots=True)
class StarBirthReport:
    pack_count: int
    rarity_card_counts: tuple[int, int, int, int]
    source_published_at: str
    evidence_sha256: str
    # Publication time is NOT the time the packs were physically opened.
    opening_country: None = None
    opened_at: None = None
    statistics_eligible: bool = False


def parse_star_birth_report(document: str) -> StarBirthReport:
    if len(document.encode("utf-8")) > 524288:
        raise CollectorError("public study response exceeds reviewed bound")
    parser = _Sections()
    parser.feed(document)
    parser.close()
    if parser.hidden:
        raise CollectorError("public study hidden markup is incomplete")
    if parser.dates != [PUBLISHED_AT]:
        raise CollectorError("public study publication identity drifted")
    titles = [text for tag, text in parser.blocks if tag == "h1"]
    if titles != ["バラ100パック開けてみた結果【ポケカ-スターバース編】"]:
        raise CollectorError("public study title identity drifted")
    groups: list[tuple[int, int, tuple[int, ...]]] = []
    current: tuple[int, int] | None = None
    observed: tuple[int, ...] | None = None

    def finish() -> None:
        nonlocal current, observed
        if current is not None:
            if observed is None:
                raise CollectorError("public study opening segment has no counts")
            groups.append((*current, observed))
        current, observed = None, None

    for tag, text in parser.blocks:
        if tag in {"h1", "h2", "h3"}:
            finish()
            match = re.fullmatch(r"(\d+)〜(\d+)パック目(（プレミアムボックス）)?", text)
            if tag == "h3" and match:
                current = int(match[1]), int(match[2])
                if bool(match[3]) != (current == (31, 50)):
                    raise CollectorError("public study premium-box segment attribution drifted")
        elif current is not None and text.startswith("（"):
            if observed is not None or not re.fullmatch(
                r"（(?:RRR|RR|SR|HR)[：:]?\d+枚(?:、(?:RRR|RR|SR|HR)[：:]?\d+枚)*）", text
            ):
                raise CollectorError("public study segment count structure drifted")
            pairs = re.findall(r"(RRR|RR|SR|HR)[：:]?(\d+)枚", text)
            values = dict(pairs)
            if len(values) != len(pairs):
                raise CollectorError("public study duplicate rarity counts")
            observed = tuple(int(values.get(rarity, "0")) for rarity in RARITIES)
    finish()
    if tuple(groups) != EXPECTED_GROUPS:
        raise CollectorError("public study opening segments drifted")
    counts = tuple(sum(group[2][index] for group in groups) for index in range(4))
    if counts != (16, 6, 4, 1):
        raise CollectorError("public study rarity totals drifted")
    evidence = json.dumps({"source": SOURCE_URL, "published": PUBLISHED_AT, "groups": groups,
                           "premium_box_range": [31, 50]},
                          ensure_ascii=True, separators=(",", ":"))
    return StarBirthReport(100, (16, 6, 4, 1), PUBLISHED_AT,
                           hashlib.sha256(evidence.encode()).hexdigest())
