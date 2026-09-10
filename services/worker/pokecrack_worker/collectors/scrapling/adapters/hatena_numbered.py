"""Pure numbered-caption extraction; not source approval or cohort admission."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser

from pokecrack_worker.collectors.base import CollectorError

ROOT = "https://www.kozaru02.com/entry/"
VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
HIDDEN = frozenset({"script", "style", "template", "noscript", "nav"})
RESOURCE_URL = re.compile(
    r"https://cdn-ak[.]f[.]st-hatena[.]com/images/fotolife/k/kozaru02/"
    r"(?P<day>[0-9]{8})/(?P=day)[0-9]{6}[.]jpg"
)


def _normal(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split()).casefold()


@dataclass(frozen=True, slots=True)
class NumberedOpeningCandidate:
    canonical_url: str
    published_at: str
    product_label: str
    pack_count: int
    evidence_sha256: str
    resource_sha256s: tuple[str, ...]
    # Caption enumeration alone does not prove cross-page cohort independence.
    opening_country: None = None
    opened_at: None = None
    statistics_eligible: bool = False


class _Captions(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool]] = []
        self.canonicals: list[str | None] = []
        self.dates: list[str | None] = []
        self.body_count = 0
        self.body_parts: list[str] = []
        self.caption: list[str] | None = None
        self.caption_depth: int | None = None
        self.numbers: list[int] = []
        self.figure_serial = 0
        self.caption_figure = 0
        self.numbered_figures: list[int] = []
        self.figure_images: dict[int, list[str | None]] = {}
        self.malformed = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        hidden = (
            any(node[1] for node in self.stack)
            or tag in HIDDEN
            or "hidden" in a
            or a.get("aria-hidden") == "true"
            or bool(
                re.search(
                    r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", a.get("style") or "", re.I
                )
            )
        )
        in_article = any(node[0] == "article" for node in self.stack)
        body = tag == "div" and "entry-content" in (a.get("class") or "").split()
        body = body and in_article and not hidden
        if not hidden:
            if tag == "figure":
                if any(node[0] == "figure" for node in self.stack):
                    self.malformed = True
                self.figure_serial += 1
                self.figure_images[self.figure_serial] = []
            if (
                tag == "img"
                and any(node[2] for node in self.stack)
                and any(node[0] == "figure" for node in self.stack)
            ):
                # Read references only: never dereference an image or retain it.
                self.figure_images[self.figure_serial].append(a.get("src"))
            if tag == "link" and a.get("rel") == "canonical":
                self.canonicals.append(a.get("href"))
            if tag == "meta" and a.get("property") == "article:published_time":
                self.dates.append(a.get("content"))
            if body:
                self.body_count += 1
            if (
                tag == "figcaption"
                and any(node[2] for node in self.stack)
                and self.stack
                and self.stack[-1][0] == "figure"
            ):
                if self.caption is not None:
                    self.malformed = True
                self.caption = []
                self.caption_depth = len(self.stack)
                self.caption_figure = self.figure_serial
        if tag not in VOID:
            self.stack.append((tag, hidden, body))
            if len(self.stack) > 128:
                raise CollectorError("numbered report nesting exceeds bound")

    def handle_data(self, data: str) -> None:
        if not any(node[1] for node in self.stack):
            if any(node[2] for node in self.stack):
                self.body_parts.append(data)
            if self.caption is not None:
                self.caption.append(data)

    def handle_endtag(self, tag: str) -> None:
        matching = [i for i, node in enumerate(self.stack) if node[0] == tag]
        if not matching:
            return
        index = matching[-1]
        # Do not silently repair crossed source markup into complete evidence.
        if index != len(self.stack) - 1:
            self.malformed = True
        if tag == "figcaption" and self.caption is not None and index == self.caption_depth:
            text = _normal("".join(self.caption))
            if match := re.fullmatch(r"([0-9]{1,4})パック目", text):
                self.numbers.append(int(match[1]))
                self.numbered_figures.append(self.caption_figure)
            elif "パック目" in text:
                self.malformed = True
            self.caption = None
            self.caption_depth = None
        elif self.caption_depth is not None and index <= self.caption_depth:
            self.malformed = True
            self.caption = None
            self.caption_depth = None
        self.stack = self.stack[:index]


def parse_numbered_opening(
    document: str,
    *,
    expected_url: str,
    product_label: str,
    expected_pack_count: int,
    now: datetime,
) -> NumberedOpeningCandidate:
    """Caller supplies reviewed layout, never a count inferred from box contents.

    This parser has no network or database access. Its result needs independent
    cohort binding and the normal source policy/admission gates before publication.
    """
    if (
        not re.fullmatch(re.escape(ROOT) + r"[a-z0-9-]{1,120}", expected_url)
        or not product_label.strip()
        or len(product_label) > 100
        or type(expected_pack_count) is not int
        or not 1 <= expected_pack_count <= 1000
        or now.utcoffset() is None
    ):
        raise CollectorError("invalid reviewed numbered-report layout")
    if len(document.encode("utf-8")) > 1_000_000:
        raise CollectorError("numbered report exceeds response bound")
    parser = _Captions()
    parser.feed(document)
    parser.close()
    if (
        parser.malformed
        or parser.caption is not None
        or parser.body_count != 1
        or any(node[2] or node[0] == "article" for node in parser.stack)
        or parser.canonicals != [expected_url]
        or len(parser.dates) != 1
    ):
        raise CollectorError("numbered report identity or structure drifted")
    try:
        date = datetime.fromisoformat(parser.dates[0] or "")
        if date.utcoffset() is None or date > now:
            raise ValueError("publication must be timezone-aware and not future")
    except ValueError as error:
        raise CollectorError("invalid numbered report publication date") from error
    if _normal(product_label) not in _normal("".join(parser.body_parts)):
        raise CollectorError("numbered report product mismatch")
    if (
        parser.numbers != list(range(1, expected_pack_count + 1))
        or len(set(parser.numbered_figures)) != expected_pack_count
    ):
        raise CollectorError("numbered report has missing, repeated or reordered captions")
    published = date.astimezone(UTC).isoformat()
    resources = []
    for figure in parser.numbered_figures:
        images = parser.figure_images.get(figure, [])
        if len(images) != 1 or images[0] is None or not RESOURCE_URL.fullmatch(images[0]):
            raise CollectorError("numbered figure has missing or ambiguous resource identity")
        resources.append(
            hashlib.sha256(("hatena-numbered-image-v1:" + images[0]).encode()).hexdigest()
        )
    if len(set(resources)) != len(resources):
        raise CollectorError("numbered figures repeat the same resource")
    evidence = json.dumps(
        [expected_url, published, _normal(product_label), parser.numbers, resources],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return NumberedOpeningCandidate(
        expected_url,
        published,
        product_label,
        len(parser.numbers),
        hashlib.sha256(evidence.encode()).hexdigest(),
        tuple(resources),
    )
