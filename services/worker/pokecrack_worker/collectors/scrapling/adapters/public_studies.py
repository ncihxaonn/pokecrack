"""Deterministic parsers for exact, reviewed public opening studies."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping, Sequence
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY, PublicStudyIdentity
from pokecrack_worker.config.source_policy import SourcePolicy
from pokecrack_worker.deduplication.fingerprints import content_sha256
from pokecrack_worker.deduplication.urls import canonicalize_url
from pokecrack_worker.models import CollectorType, SourceItemCandidate


def _header(headers: object, name: str) -> str:
    if not hasattr(headers, "items"):
        return ""
    expected = name.casefold()
    return next(
        (str(value) for key, value in headers.items() if str(key).casefold() == expected),
        "",
    )


def _require_exact_url(url: str, expected: str) -> str:
    requested = url.strip()
    # Validate the URL with the shared canonicalizer, but retain its exact path:
    # redirects are disabled, so the robots decision and network request must use
    # the same reviewed URL byte-for-byte.
    canonicalize_url(requested)
    if requested != expected:
        raise CollectorError("public study adapter accepts only its exact reviewed URL")
    return requested


class _VisibleTextParser(HTMLParser):
    _BLOCK_TAGS = frozenset(
        {
            "article",
            "br",
            "div",
            "h1",
            "h2",
            "h3",
            "li",
            "main",
            "p",
            "section",
            "ul",
        }
    )

    def __init__(self, *, content_tags: Sequence[str] = ("article",)) -> None:
        super().__init__(convert_charrefs=True)
        self.content_tags = frozenset(tag.casefold() for tag in content_tags)
        self.hidden_depth = 0
        self.content_depth = 0
        self.heading_depth = 0
        self.document_title_depth = 0
        self.text_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.document_title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized = tag.casefold()
        if normalized in {"script", "style", "noscript", "template"}:
            self.hidden_depth += 1
        elif not self.hidden_depth and normalized == "title":
            self.document_title_depth += 1
        elif not self.hidden_depth and normalized in self.content_tags:
            self.content_depth += 1
        elif not self.hidden_depth and self.content_depth and normalized == "h1":
            self.heading_depth += 1
        if not self.hidden_depth and self.content_depth and normalized == "br":
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized in {"script", "style", "noscript", "template"} and self.hidden_depth:
            self.hidden_depth -= 1
            return
        if self.hidden_depth:
            return
        if normalized == "title" and self.document_title_depth:
            self.document_title_depth -= 1
            self.document_title_parts.append("\n")
            return
        if normalized in self.content_tags and self.content_depth:
            self.text_parts.append("\n")
            self.content_depth -= 1
            return
        if self.content_depth and normalized == "h1" and self.heading_depth:
            self.heading_depth -= 1
            self.heading_parts.append("\n")
        if self.content_depth and normalized in self._BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.hidden_depth or not data.strip():
            return
        if self.document_title_depth:
            self.document_title_parts.append(data)
        if not self.content_depth:
            return
        self.text_parts.append(data)
        if self.heading_depth:
            self.heading_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.heading_parts).split())

    @property
    def document_title(self) -> str:
        return " ".join("".join(self.document_title_parts).split())

    @property
    def text(self) -> str:
        return " ".join("".join(self.text_parts).split())


class RobotsTxtChecker:
    """Fetch and evaluate same-origin robots.txt without retaining it."""

    def __init__(
        self,
        *,
        client: HTTPClient,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 64 * 1024,
        followup_delay_seconds: float = 30.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 0 <= followup_delay_seconds <= 120:
            raise ValueError("followup_delay_seconds must be between 0 and 120")
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.followup_delay_seconds = followup_delay_seconds
        self.sleeper = sleeper

    def allowed(self, url: str, *, user_agent: str) -> bool:
        try:
            requested_url = url.strip()
            canonicalize_url(requested_url)
            parsed = urlsplit(requested_url)
            if (
                parsed.scheme != "https"
                or parsed.hostname is None
                or parsed.port not in {None, 443}
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                return False
            robots_url = f"https://{parsed.hostname}/robots.txt"
            response = self.client.get(robots_url, timeout_seconds=self.timeout_seconds)
            if canonicalize_url(response.url) != robots_url or response.status_code != 200:
                return False
            if len(response.body) > self.max_response_bytes:
                return False
            if "text/plain" not in _header(response.headers, "content-type").casefold():
                return False
            document = response.body.decode("utf-8", errors="strict")
        except (CollectorError, UnicodeDecodeError, ValueError):
            return False
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(document.splitlines())
        allowed = parser.can_fetch(user_agent, requested_url)
        if allowed and self.followup_delay_seconds:
            self.sleeper(self.followup_delay_seconds)
        return allowed


class ReviewedPublicStudyAdapter:
    """Accept one page only when its policy and evidence remain exact."""

    def __init__(
        self,
        *,
        client: HTTPClient,
        identity: PublicStudyIdentity,
        expected_policy_config: Mapping[str, object],
        title_tokens: Sequence[str],
        evidence_patterns: Sequence[re.Pattern[str]],
        expected_evidence_sha256: str | None = None,
        allow_document_title: bool = False,
        content_tags: Sequence[str] = ("article",),
        evidence_validator: Callable[[str], None] | None = None,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 1_000_000,
    ) -> None:
        self.client = client
        self.identity = identity
        self.expected_policy_config = dict(expected_policy_config)
        self.title_tokens = tuple(title_tokens)
        self.evidence_patterns = tuple(evidence_patterns)
        self.expected_evidence_sha256 = expected_evidence_sha256
        self.allow_document_title = allow_document_title
        self.content_tags = tuple(content_tags)
        self.evidence_validator = evidence_validator
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes

    def collect(self, url: str, policy: SourcePolicy) -> tuple[SourceItemCandidate, ...]:
        identity = self.identity
        if (
            policy.domain != identity.domain
            or policy.collector is not CollectorType.SCRAPLING_HTTP
            or policy.version != identity.collector_version
            or policy.adapter != identity.adapter
            or policy.config != self.expected_policy_config
            or policy.statistics_eligible_default is not True
            or policy.metadata_only is not False
            or policy.retain_raw_html is not False
        ):
            raise CollectorError("public study source policy does not match the reviewed contract")
        requested_url = _require_exact_url(url, identity.fetch_url)
        response = self.client.get(requested_url, timeout_seconds=self.timeout_seconds)
        _require_exact_url(response.url, identity.fetch_url)
        if response.status_code != 200:
            raise CollectorError(f"public study HTTP status {response.status_code}")
        if len(response.body) > self.max_response_bytes:
            raise CollectorError("public study response exceeds configured byte cap")
        if "text/html" not in _header(response.headers, "content-type").casefold():
            raise CollectorError("public study expected text/html")

        try:
            document = response.body.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise CollectorError("public study must be strict UTF-8 HTML") from error
        parser = _VisibleTextParser(content_tags=self.content_tags)
        parser.feed(document)
        parser.close()
        title = parser.title
        if not title and self.allow_document_title:
            title = parser.document_title
        if not title or not all(token in title for token in self.title_tokens):
            raise CollectorError("public study title no longer proves the reviewed scope")
        matches = [pattern.search(parser.text) for pattern in self.evidence_patterns]
        if any(match is None for match in matches):
            raise CollectorError("public study evidence no longer matches the reviewed facts")
        if self.evidence_validator is not None:
            self.evidence_validator(parser.text)
        evidence_excerpt = "\n".join(match.group(0) for match in matches if match is not None)
        evidence_sha256 = content_sha256(evidence_excerpt)
        if (
            self.expected_evidence_sha256 is not None
            and evidence_sha256 != self.expected_evidence_sha256
        ):
            raise CollectorError("public study evidence hash no longer matches the reviewed facts")

        return (
            SourceItemCandidate(
                platform="web",
                external_id=identity.study_key,
                source_url=identity.source_url,
                title=title,
                text=evidence_excerpt,
                metadata={
                    "study_key": identity.study_key,
                    "parser_version": identity.parser_version,
                },
                collector=CollectorType.SCRAPLING_HTTP,
                collector_version=identity.collector_version,
                source_policy_version=policy.version,
            ),
        )


COMICBOOK_IDENTITY = PUBLIC_STUDIES_BY_KEY["comicbook-perfect-order-us-55-v1"]
COMICBOOK_POLICY_CONFIG: dict[str, object] = {
    "study_key": COMICBOOK_IDENTITY.study_key,
    "canonical_url": COMICBOOK_IDENTITY.source_url,
    "collector_version": COMICBOOK_IDENTITY.collector_version,
    "parser_version": COMICBOOK_IDENTITY.parser_version,
    "country_code": "US",
    "country_name": "United States",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "set_external_id": "me03",
    "product_scope": "all",
    "pack_count": 55,
    "qualifying_hit_pack_count": 1,
    "qualifying_metric": "sir_pack",
    "metric_version": "global-sir-v1",
    "observed_at": "2026-03-19T21:00:00Z",
    "denominator_complete": True,
}

WARGAMER_IDENTITY = PUBLIC_STUDIES_BY_KEY["wargamer-chaos-rising-gb-17-v1"]
WARGAMER_POLICY_CONFIG: dict[str, object] = {
    "study_key": WARGAMER_IDENTITY.study_key,
    "canonical_url": WARGAMER_IDENTITY.source_url,
    "collector_version": WARGAMER_IDENTITY.collector_version,
    "parser_version": WARGAMER_IDENTITY.parser_version,
    "country_code": "GB",
    "country_name": "United Kingdom",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "set_external_id": "me04",
    "product_scope": "all",
    "pack_count": 17,
    "qualifying_hit_pack_count": 0,
    "qualifying_metric": "sir_pack",
    "metric_version": "global-sir-v1",
    "observed_at": "2026-05-11T00:00:00Z",
    "denominator_complete": True,
}

CARDCHILL_IDENTITY = PUBLIC_STUDIES_BY_KEY["cardchill-ascended-heroes-gb-90-v1"]
CARDCHILL_POLICY_CONFIG: dict[str, object] = {
    "study_key": CARDCHILL_IDENTITY.study_key,
    "canonical_url": CARDCHILL_IDENTITY.source_url,
    "collector_version": CARDCHILL_IDENTITY.collector_version,
    "parser_version": CARDCHILL_IDENTITY.parser_version,
    "country_code": "GB",
    "country_name": "United Kingdom",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "set_external_id": "me02.5",
    "product_scope": "etb",
    "pack_count": 90,
    "qualifying_hit_pack_count": 1,
    "qualifying_metric": "sir_pack",
    "metric_version": "global-sir-v1",
    "observed_at": "2026-03-03T11:26:21Z",
    "denominator_complete": True,
}

BLEEDINGCOOL_IDENTITY = PUBLIC_STUDIES_BY_KEY["bleedingcool-phantasmal-flames-us-36-v1"]
BLEEDINGCOOL_POLICY_CONFIG: dict[str, object] = {
    "study_key": BLEEDINGCOOL_IDENTITY.study_key,
    "canonical_url": BLEEDINGCOOL_IDENTITY.source_url,
    "collector_version": BLEEDINGCOOL_IDENTITY.collector_version,
    "parser_version": BLEEDINGCOOL_IDENTITY.parser_version,
    "country_code": "US",
    "country_name": "United States",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "set_external_id": "me02",
    "product_scope": "booster_box",
    "pack_count": 36,
    "qualifying_hit_pack_count": 1,
    "qualifying_metric": "sir_pack",
    "metric_version": "global-sir-v1",
    "observed_at": "2026-01-03T16:12:04Z",
    "denominator_complete": True,
}

TCGTALK_IDENTITY = PUBLIC_STUDIES_BY_KEY["tcgtalk-perfect-order-sg-54-v1"]
TCGTALK_POLICY_CONFIG: dict[str, object] = {
    "study_key": TCGTALK_IDENTITY.study_key,
    "canonical_url": TCGTALK_IDENTITY.source_url,
    "collector_version": TCGTALK_IDENTITY.collector_version,
    "parser_version": TCGTALK_IDENTITY.parser_version,
    "country_code": "SG",
    "country_name": "Singapore",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "set_external_id": "me03",
    "product_scope": "booster_bundle",
    "pack_count": 54,
    "qualifying_hit_pack_count": 1,
    "qualifying_metric": "sir_pack",
    "metric_version": "global-sir-v1",
    "observed_at": "2026-03-25T12:40:00Z",
    "denominator_complete": True,
}
TCGTALK_EVIDENCE_EXCERPT = (
    "Based on community opening of 9 booster bundles (54 packs total)\n"
    "Out of 54 packs opened, the community pull rate held roughly true: 1 SIR per 54 packs "
    "in this particular opening, with the Meowth EX SIR being the pull."
)
TCGTALK_EVIDENCE_SHA256 = "217f21e0de947139a96b6466563c1d005300598b1dde933264255627c8f0b096"

POKESUP_IDENTITY = PUBLIC_STUDIES_BY_KEY["pokesup-abyss-eye-jp-30-v1"]
POKESUP_POLICY_CONFIG: dict[str, object] = {
    "study_key": POKESUP_IDENTITY.study_key,
    "canonical_url": POKESUP_IDENTITY.source_url,
    "collector_version": POKESUP_IDENTITY.collector_version,
    "parser_version": POKESUP_IDENTITY.parser_version,
    "country_code": "JP",
    "country_name": "Japan",
    "geography_basis": "product_market",
    "geography_confidence": "tier_b",
    "set_external_id": "M5",
    "set_language": "ja",
    "set_name": "アビスアイ",
    "product_scope": "booster_box",
    "pack_count": 30,
    "observed_at": "2026-05-22T12:01:44Z",
    "denominator_complete": True,
    "set_official_url": "https://www.pokemon-card.com/ex/m5/",
    "robots_url": "https://pokesup.com/robots.txt",
    "robots_checked_at": "2026-09-04",
    "terms_checked_at": "2026-09-04",
    "terms_status": "no_independent_terms_page",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}

POKESUP_TITLE = "ポケモンカード 拡張パック「アビスアイ」開封結果！レアリティ封入率検証（その1）"
POKESUP_OPENING_EXCERPT = (
    "拡張パック「アビスアイ」の開封結果になります。 "
    "箱開封から、順序変えずに開封していますので並び順の参考などにどうぞ。"
)
POKESUP_SECTION_HEADING = "アビスアイ開封（1箱目）"
POKESUP_PACK_LABELS = tuple(
    [f"左{index}パック" for index in range(1, 16)] + [f"右{index}パック" for index in range(1, 16)]
)
_POKESUP_PACK_LABEL_PATTERN = re.compile(r"(?<!\d)(?:左|右)\d{1,2}パック(?!\d)")


def _pokesup_pack_sequence_pattern() -> re.Pattern[str]:
    return re.compile(
        r"\s+".join(re.escape(label) for label in (POKESUP_SECTION_HEADING, *POKESUP_PACK_LABELS))
    )


def _validate_pokesup_pack_sequence(text: str) -> None:
    headings = list(re.finditer(re.escape(POKESUP_SECTION_HEADING), text))
    if len(headings) != 1:
        raise CollectorError("Pokesup M5 opening section is not unique")
    labels = tuple(_POKESUP_PACK_LABEL_PATTERN.findall(text[headings[0].end() :]))
    if labels != POKESUP_PACK_LABELS:
        raise CollectorError("Pokesup M5 pack sequence is incomplete or duplicated")


POKESUP_EVIDENCE_EXCERPT = (
    f"{POKESUP_TITLE}\n"
    f"{POKESUP_OPENING_EXCERPT}\n"
    f"{POKESUP_SECTION_HEADING} {' '.join(POKESUP_PACK_LABELS)}"
)
POKESUP_EVIDENCE_SHA256 = "254f7c0959b4e3fee4cde46391e69b3e9956b6205e1c49c4aee3089b0a3fea36"


def comicbook_perfect_order_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=COMICBOOK_IDENTITY,
        expected_policy_config=COMICBOOK_POLICY_CONFIG,
        title_tokens=("Opened 55 Packs", "Perfect Order", "Pull Rates"),
        evidence_patterns=(
            re.compile(r"In total, I opened 55 boosters from the upcoming Perfect Order lineup\."),
            re.compile(r"1 Special Illustration Rare"),
        ),
    )


def wargamer_chaos_rising_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=WARGAMER_IDENTITY,
        expected_policy_config=WARGAMER_POLICY_CONFIG,
        title_tokens=("opened Pokémon Chaos Rising packs early", "blessing and a curse"),
        evidence_patterns=(
            re.compile(
                r"after opening the 17 Pokémon Chaos Rising packs Wargamer was sent ahead of "
                r"release, my opinion remains positive on those fronts\."
            ),
            re.compile(r"missing out on any SIR mega hits\."),
        ),
    )


def cardchill_ascended_heroes_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=CARDCHILL_IDENTITY,
        expected_policy_config=CARDCHILL_POLICY_CONFIG,
        title_tokens=("Ripping 10 Ascended Heroes ETBs", "Mega Attack", "Pull Rate Real"),
        evidence_patterns=(
            re.compile(
                r"I finally sat down with a stack of 10 Ascended Heroes Elite Trainer Boxes\."
            ),
            re.compile(r"Out of 90 packs, I pulled 19 Double Rare \(ex\) cards\."),
            re.compile(r"Across 10 ETBs, I pulled exactly one SIR\."),
        ),
    )


def bleedingcool_phantasmal_flames_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=BLEEDINGCOOL_IDENTITY,
        expected_policy_config=BLEEDINGCOOL_POLICY_CONFIG,
        title_tokens=("Opening Pokémon TCG", "Phantasmal Flames Products"),
        evidence_patterns=(
            re.compile(r"Now, the meat and potatoes: the booster box\."),
            re.compile(
                r"A booster box contains 36 packs, which essentially guarantees some fire\."
            ),
            re.compile(
                r"My Secret Rare count here is a whopping eight, made up of five "
                r"Illustration Rares, two Full Art Trainer Supporters, and, the biggest hit, "
                r"a Special Illustration Rare ex\."
            ),
        ),
    )


def tcgtalk_perfect_order_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=TCGTALK_IDENTITY,
        expected_policy_config=TCGTALK_POLICY_CONFIG,
        title_tokens=("Perfect Order Pull Rates", "Singapore Collectors Can Expect"),
        evidence_patterns=(
            re.compile(r"Based on community opening of 9 booster bundles \(54 packs total\)"),
            re.compile(
                r"Out of 54 packs opened, the community pull rate held roughly true: 1 SIR per "
                r"54 packs in this particular opening, with the Meowth EX SIR being the pull\."
            ),
        ),
        expected_evidence_sha256=TCGTALK_EVIDENCE_SHA256,
        allow_document_title=True,
    )


def pokesup_abyss_eye_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=POKESUP_IDENTITY,
        expected_policy_config=POKESUP_POLICY_CONFIG,
        title_tokens=(POKESUP_TITLE,),
        evidence_patterns=(
            re.compile(re.escape(POKESUP_TITLE)),
            re.compile(re.escape(POKESUP_OPENING_EXCERPT)),
            _pokesup_pack_sequence_pattern(),
        ),
        expected_evidence_sha256=POKESUP_EVIDENCE_SHA256,
        content_tags=("main",),
        evidence_validator=_validate_pokesup_pack_sequence,
    )


__all__ = [
    "BLEEDINGCOOL_IDENTITY",
    "BLEEDINGCOOL_POLICY_CONFIG",
    "CARDCHILL_IDENTITY",
    "CARDCHILL_POLICY_CONFIG",
    "COMICBOOK_IDENTITY",
    "COMICBOOK_POLICY_CONFIG",
    "POKESUP_EVIDENCE_EXCERPT",
    "POKESUP_EVIDENCE_SHA256",
    "POKESUP_IDENTITY",
    "POKESUP_OPENING_EXCERPT",
    "POKESUP_PACK_LABELS",
    "POKESUP_POLICY_CONFIG",
    "POKESUP_SECTION_HEADING",
    "POKESUP_TITLE",
    "ReviewedPublicStudyAdapter",
    "RobotsTxtChecker",
    "TCGTALK_EVIDENCE_EXCERPT",
    "TCGTALK_EVIDENCE_SHA256",
    "TCGTALK_IDENTITY",
    "TCGTALK_POLICY_CONFIG",
    "WARGAMER_IDENTITY",
    "WARGAMER_POLICY_CONFIG",
    "bleedingcool_phantasmal_flames_adapter",
    "cardchill_ascended_heroes_adapter",
    "comicbook_perfect_order_adapter",
    "pokesup_abyss_eye_adapter",
    "tcgtalk_perfect_order_adapter",
    "wargamer_chaos_rising_adapter",
]
