"""Deterministic parsers for exact, reviewed public opening studies."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
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
            youtube_watch_query = bool(
                parsed.hostname in {"www.youtube.com", "m.youtube.com"}
                and parsed.path == "/watch"
                and re.fullmatch(r"v=[A-Za-z0-9_-]{6,64}", parsed.query)
            )
            if (
                parsed.scheme != "https"
                or parsed.hostname is None
                or parsed.port not in {None, 443}
                or parsed.username is not None
                or parsed.password is not None
                or (parsed.query and not youtube_watch_query)
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
        document_validator: Callable[[str], None] | None = None,
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
        self.document_validator = document_validator
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
        if self.document_validator is not None:
            self.document_validator(document)
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


def _youtube_video_details(document: str) -> tuple[Mapping[str, object], ...]:
    decoder = json.JSONDecoder()
    values: list[Mapping[str, object]] = []
    for match in re.finditer(r'"videoDetails"\s*:\s*', document):
        try:
            value, _end = decoder.raw_decode(document, match.end())
        except json.JSONDecodeError as error:
            raise CollectorError("YouTube videoDetails metadata is not valid JSON") from error
        if not isinstance(value, dict):
            raise CollectorError("YouTube videoDetails metadata is not an object")
        values.append(value)
    if not values:
        raise CollectorError("YouTube videoDetails metadata is missing")
    return tuple(values)


def _youtube_player_microformats(document: str) -> tuple[Mapping[str, object], ...]:
    decoder = json.JSONDecoder()
    values: list[Mapping[str, object]] = []
    for match in re.finditer(r'"playerMicroformatRenderer"\s*:\s*', document):
        try:
            value, _end = decoder.raw_decode(document, match.end())
        except json.JSONDecodeError as error:
            raise CollectorError("YouTube player microformat metadata is not valid JSON") from error
        if not isinstance(value, dict):
            raise CollectorError("YouTube player microformat metadata is not an object")
        values.append(value)
    return tuple(values)


def _youtube_publication_date(value: object) -> datetime:
    if not isinstance(value, str):
        raise CollectorError("public study publication date is missing")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise CollectorError("public study publication date is not ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CollectorError("public study publication date must include an offset")
    return parsed.astimezone(UTC)


class YouTubeWatchCoverageAdapter:
    """Parse only immutable metadata facts from one reviewed YouTube watch page."""

    def __init__(
        self,
        *,
        client: HTTPClient,
        identity: PublicStudyIdentity,
        expected_policy_config: Mapping[str, object],
        expected_title: str,
        evidence_lines: Sequence[str],
        evidence_pattern: re.Pattern[str],
        expected_video_id: str,
        expected_channel_id: str,
        expected_observed_at: datetime,
        expected_evidence_sha256: str,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 2_000_000,
    ) -> None:
        self.client = client
        self.identity = identity
        self.expected_policy_config = dict(expected_policy_config)
        self.expected_title = expected_title
        self.evidence_lines = tuple(evidence_lines)
        self.evidence_pattern = evidence_pattern
        self.expected_video_id = expected_video_id
        self.expected_channel_id = expected_channel_id
        self.expected_observed_at = expected_observed_at.astimezone(UTC)
        self.expected_evidence_sha256 = expected_evidence_sha256
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

        details = _youtube_video_details(document)
        matching_video = tuple(
            item for item in details if item.get("videoId") == self.expected_video_id
        )
        if not matching_video:
            raise CollectorError("public study video identity no longer matches the review")
        if any(item.get("channelId") != self.expected_channel_id for item in matching_video):
            raise CollectorError("public study publisher identity no longer matches the review")
        if any(item.get("title") != self.expected_title for item in matching_video):
            raise CollectorError("public study title no longer proves the reviewed scope")
        if any(
            not isinstance(item.get("shortDescription"), str)
            or self.evidence_pattern.search(str(item["shortDescription"])) is None
            for item in matching_video
        ):
            raise CollectorError("public study evidence no longer matches the reviewed facts")
        parsed_dates: list[datetime] = []
        for item in matching_video:
            if "publishDate" in item:
                parsed_dates.append(_youtube_publication_date(item["publishDate"]))

        matching_microformats = tuple(
            item
            for item in _youtube_player_microformats(document)
            if item.get("externalVideoId") == self.expected_video_id
        )
        for item in matching_microformats:
            published = _youtube_publication_date(item.get("publishDate"))
            uploaded = _youtube_publication_date(item.get("uploadDate"))
            if uploaded != published:
                raise CollectorError("public study publication date metadata conflicts")
            parsed_dates.append(published)
        if not parsed_dates:
            raise CollectorError("public study publication date is missing")
        if any(value != self.expected_observed_at for value in parsed_dates):
            raise CollectorError("public study publication date no longer matches the review")

        evidence_excerpt = "\n".join(self.evidence_lines)
        if content_sha256(evidence_excerpt) != self.expected_evidence_sha256:
            raise CollectorError("public study evidence hash no longer matches the reviewed facts")
        return (
            SourceItemCandidate(
                platform="web",
                external_id=self.expected_video_id,
                source_url=identity.fetch_url,
                title=self.expected_title,
                text=evidence_excerpt,
                published_at=self.expected_observed_at,
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
    f"{POKESUP_TITLE}\n{POKESUP_SECTION_HEADING} {' '.join(POKESUP_PACK_LABELS)}"
)
POKESUP_EVIDENCE_SHA256 = "e9e87b7bbab8483200fef8ffd7d927f339138f742876ca222af1f133f7523b08"

LIMITSEND_IDENTITY = PUBLIC_STUDIES_BY_KEY["limitsend-inferno-x-kr-30-v1"]
LIMITSEND_POLICY_CONFIG: dict[str, object] = {
    "study_key": LIMITSEND_IDENTITY.study_key,
    "canonical_url": LIMITSEND_IDENTITY.source_url,
    "collector_version": LIMITSEND_IDENTITY.collector_version,
    "parser_version": LIMITSEND_IDENTITY.parser_version,
    "country_code": "KR",
    "country_name": "South Korea",
    "geography_basis": "product_market",
    "geography_confidence": "tier_b",
    "set_external_id": "M2",
    "set_language": "ko",
    "set_name": "인페르노X",
    "product_scope": "booster_box",
    "pack_count": 30,
    "observed_at": "2026-08-20T14:20:28Z",
    "denominator_complete": True,
    "set_official_url": "https://pokemoncard.co.kr/card/838",
    "robots_url": "https://limitsend.tistory.com/robots.txt",
    "robots_checked_at": "2026-09-04",
    "terms_checked_at": "2026-09-04",
    "terms_status": "cc_by_nc_nd",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}
LIMITSEND_TITLE = "포켓몬카드 낱개팩 구매를 조심해야 하는 이유｜인페르노X 직접 개봉해보니"
LIMITSEND_BOX_EVIDENCE = "인페르노X의 공식 구성은 다음과 같습니다. 1팩 : 5장 1박스 : 30팩 총 150장"
LIMITSEND_COMPLETE_EVIDENCE = (
    "특히 직접 한 박스를 처음부터 끝까지 개봉하면서 팩의 상태와 나온 카드를 같이 "
    "비교해보니 상당히 재미있는 경험이었습니다."
)
LIMITSEND_EVIDENCE_EXCERPT = f"{LIMITSEND_BOX_EVIDENCE}\n{LIMITSEND_COMPLETE_EVIDENCE}"
LIMITSEND_EVIDENCE_SHA256 = "4af8a17aec4489a0f3fdd6a3e4c8fb8f7a77a60092825fba3279323b6c654406"

BUYFUNLIFE_IDENTITY = PUBLIC_STUDIES_BY_KEY["buyfunlife-ninja-spinner-tw-40-v1"]
BUYFUNLIFE_POLICY_CONFIG: dict[str, object] = {
    "study_key": BUYFUNLIFE_IDENTITY.study_key,
    "canonical_url": BUYFUNLIFE_IDENTITY.source_url,
    "collector_version": BUYFUNLIFE_IDENTITY.collector_version,
    "parser_version": BUYFUNLIFE_IDENTITY.parser_version,
    "country_code": "TW",
    "country_name": "Taiwan",
    "geography_basis": "product_market",
    "geography_confidence": "tier_b",
    "set_external_id": "M4",
    "set_language": "zh-TW",
    "set_name": "忍者飛旋",
    "product_scope": "value_bundle",
    "pack_count": 40,
    "observed_at": "2026-04-03T13:49:13Z",
    "denominator_complete": True,
    "set_official_url": "https://asia.pokemon-card.com/tw/archive/special/card/m4/",
    "robots_url": "https://buyfunlife.com/robots.txt",
    "robots_checked_at": "2026-09-04",
    "terms_checked_at": "2026-09-04",
    "terms_status": "site_disclaimer_reviewed",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}
BUYFUNLIFE_TITLE = "噴4000元大虧！寶可夢忍者飛旋加值組合開箱｜MUR機率多低？卡價分析（新手懶人包）"
BUYFUNLIFE_EVIDENCE_EXCERPT = "我買了一整盒《忍者飛旋》加值組合（售價 $2025），拆了 40 包"
BUYFUNLIFE_EVIDENCE_SHA256 = "2fd4475765c44e61e9603f0603ddf8b8ba7a1d9ff234726c5d6dd631d8937a3d"

ALLONLINE_IDENTITY = PUBLIC_STUDIES_BY_KEY["allonline-mega-dream-ex-th-10-v1"]
ALLONLINE_POLICY_CONFIG: dict[str, object] = {
    "study_key": ALLONLINE_IDENTITY.study_key,
    "canonical_url": ALLONLINE_IDENTITY.source_url,
    "collector_version": ALLONLINE_IDENTITY.collector_version,
    "parser_version": ALLONLINE_IDENTITY.parser_version,
    "country_code": "TH",
    "country_name": "Thailand",
    "geography_basis": "product_market",
    "geography_confidence": "tier_b",
    "set_external_id": "MA3",
    "set_language": "th",
    "set_name": "วิวัฒนาการเมก้า ดรีมex",
    "product_scope": "booster_box",
    "pack_count": 10,
    "observed_at": "2026-01-29T10:10:35Z",
    "denominator_complete": True,
    "set_official_url": "https://asia.pokemon-card.com/th/archives/6828/",
    "robots_url": "https://blog.allonline.7eleven.co.th/robots.txt",
    "robots_checked_at": "2026-09-04",
    "terms_checked_at": "2026-09-04",
    "terms_status": "allonline_terms_reviewed",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}
ALLONLINE_TITLE = "รีวิว การ์ดโปเกมอน วิวัฒนาการดรีมex ตามล่าหาความแรร์ เติมเด็คให้แข็งแกร่ง"
ALLONLINE_OPENING_EVIDENCE = "วันนี้จะขออาสาพาทุกคนไปเปิดกล่องรีวิว การ์ดเกม ชุด วิวัฒนาการดรีมex ซีรีส์ใหม่ล่าสุดนี้"
ALLONLINE_RESULT_EVIDENCE = "มาดูกันว่าตัวตึงที่ผมเปิดเจอมีตัวไหนบ้าง"
ALLONLINE_BOX_EVIDENCE = "1 กล่อง = 10 ซอง >> 1 ซอง = 10 ใบ รวมเป็น 100 ใบ ราคา 1,600 บาท"
ALLONLINE_EVIDENCE_EXCERPT = "\n".join(
    (ALLONLINE_OPENING_EVIDENCE, ALLONLINE_RESULT_EVIDENCE, ALLONLINE_BOX_EVIDENCE)
)
ALLONLINE_EVIDENCE_SHA256 = "5c4dfcf632018a5f56489b5e158885086c118c13edf5b129dfc530bd25d93478"

PONTOCOM_IDENTITY = PUBLIC_STUDIES_BY_KEY["pontocom-herois-excelsos-br-48-v1"]
PONTOCOM_CARD_RARITY_MAPPING = [
    {
        "card_name": "Mega Meganium ex",
        "card_number": "272/217",
        "official_url": (
            "https://www.pokemon.com/br/pokemon-estampas-ilustradas/"
            "cartas-de-pokemon/series/me2pt5/272/"
        ),
        "official_rarity_en": "Special Illustration Rare",
        "official_rarity_pt_br": "Ilustração Rara Especial",
        "normalized_rarity": "SIR",
        "counts_as_sir": True,
    },
    {
        "card_name": "Mawile",
        "card_number": "246/217",
        "official_url": (
            "https://www.pokemon.com/br/pokemon-estampas-ilustradas/"
            "cartas-de-pokemon/series/me2pt5/246/"
        ),
        "official_rarity_en": "Illustration Rare",
        "official_rarity_pt_br": "Ilustração Rara",
        "normalized_rarity": "IR",
        "counts_as_sir": False,
    },
    {
        "card_name": "Heliolisk",
        "card_number": "229/217",
        "official_url": (
            "https://www.pokemon.com/br/pokemon-estampas-ilustradas/"
            "cartas-de-pokemon/series/me2pt5/229/"
        ),
        "official_rarity_en": "Illustration Rare",
        "official_rarity_pt_br": "Ilustração Rara",
        "normalized_rarity": "IR",
        "counts_as_sir": False,
    },
]
PONTOCOM_POLICY_CONFIG: dict[str, object] = {
    "study_key": PONTOCOM_IDENTITY.study_key,
    "canonical_url": PONTOCOM_IDENTITY.source_url,
    "collector_version": PONTOCOM_IDENTITY.collector_version,
    "parser_version": PONTOCOM_IDENTITY.parser_version,
    "country_code": "BR",
    "country_name": "Brazil",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "set_external_id": "me02.5",
    "set_language": "pt-BR",
    "set_name": "Heróis Excelsos",
    "set_official_url": (
        "https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/"
    ),
    "product_scope": "four_pack_blister",
    "product_name": "Blister Quádruplo",
    "source_native_product": "12 Blisters Quadruplos",
    "pack_count": 48,
    "denominator_derivation": "12×4",
    "qualifying_hit_pack_count": 1,
    "qualifying_metric": "sir_pack",
    "metric_version": "global-sir-v1",
    "source_published_at": "2026-01-26T20:29:00-03:00",
    "observed_at": "2026-01-26T23:29:00Z",
    "denominator_complete": True,
    "video_url": "https://www.youtube.com/watch?v=idfg-A54S1k",
    "video_id": "idfg-A54S1k",
    "video_embed_url": "https://www.youtube.com/embed/idfg-A54S1k",
    "video_review_method": "manual_timestamped_video_review",
    "video_reviewed_at": "2026-09-05",
    "video_review_timestamps": [
        {"at": "00:07", "finding": "12 Blisters Quadruplos"},
        {
            "at": "02:34-02:58",
            "card_name": "Mega Meganium ex",
            "card_number": "272/217",
            "normalized_rarity": "SIR",
        },
        {
            "at": "16:49-16:56",
            "card_name": "Mawile",
            "card_number": "246/217",
            "normalized_rarity": "IR",
        },
        {
            "at": "19:49-20:08",
            "card_name": "Heliolisk",
            "card_number": "229/217",
            "normalized_rarity": "IR",
        },
        {"at": "22:07", "finding": "manual summary of two generic art cards"},
    ],
    "card_rarity_mapping": PONTOCOM_CARD_RARITY_MAPPING,
    "robots_url": "https://pontocomdesenvolvimento.net/robots.txt",
    "robots_checked_at": "2026-09-05",
    "robots_status": "404_not_found_live_collection_blocked",
    "terms_checked_at": "2026-09-05",
    "terms_status": "publisher_terms_not_found_in_review",
    "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
}
PONTOCOM_TITLE = "Heróis Excelsos: Vale a Pena ABRIR Uma CASE LACRADA?"
PONTOCOM_EVIDENCE_EXCERPT = (
    "ABRI uma CASE com 12 Blisters Quadruplos de Pokémon TCG – Heróis Excelsos "
    "ANTES DO LANÇAMENTO OFICIAL!"
)
PONTOCOM_EVIDENCE_SHA256 = "4788f28b2e61c0b1879d287da82e4c45712ba7ba0a84cb1599c32611e1968da6"
_PONTOCOM_YOUTUBE_EMBED = re.compile(
    r"<iframe\b[^>]*\bsrc\s*=\s*[\"']"
    r"https://(?:www\.)?youtube(?:-nocookie)?\.com/embed/idfg-A54S1k"
    r"(?:[?&#\"'\s])",
    re.IGNORECASE,
)


def _validate_pontocom_static_document(document: str) -> None:
    if _PONTOCOM_YOUTUBE_EMBED.search(document) is None:
        raise CollectorError("PontoCOM article does not contain the exact reviewed YouTube embed")


RICHARDS_BRICKS_CHARIZARD_IDENTITY = PUBLIC_STUDIES_BY_KEY["richards-bricks-charizard-upc-pr-18-v1"]
RICHARDS_BRICKS_CHARIZARD_POLICY_CONFIG: dict[str, object] = {
    "study_key": RICHARDS_BRICKS_CHARIZARD_IDENTITY.study_key,
    "canonical_url": RICHARDS_BRICKS_CHARIZARD_IDENTITY.source_url,
    "fetch_url": RICHARDS_BRICKS_CHARIZARD_IDENTITY.fetch_url,
    "collector_version": RICHARDS_BRICKS_CHARIZARD_IDENTITY.collector_version,
    "parser_version": RICHARDS_BRICKS_CHARIZARD_IDENTITY.parser_version,
    "country_code": "PR",
    "country_name": "Puerto Rico",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "publisher_country_url": "https://www.youtube.com/@Richards_Bricks/about",
    "publisher_channel_id": "UCP2PM8ZRJ_fiKlzJNGc02pQ",
    "publisher_country_evidence": 'country:"Puerto Rico"',
    "publisher_country_checked_at": "2026-09-05",
    "geography_review_method": "manual_static_channel_about_review",
    "set_external_id": "mixed-tpci-2025",
    "set_scope": "mixed_multi_expansion",
    "set_name": "Mixed English TPCI expansions",
    "product_name": "Mega Charizard X ex Ultra-Premium Collection",
    "product_scope": "all",
    "pack_count": 18,
    "observed_at": "2025-12-24T11:03:10Z",
    "denominator_complete": True,
    "robots_url": "https://www.youtube.com/robots.txt",
    "robots_checked_at": "2026-09-05",
    "robots_decision": "watch_route_not_disallowed",
    "terms_url": "https://www.youtube.com/static?template=terms",
    "terms_checked_at": "2026-09-05",
    "terms_effective_date": "2023-12-15",
    "terms_status": "public_browse_static_metadata_only",
    "rights_scope": "minimal_noncreative_facts_no_media_transcript_or_body_reuse",
}
RICHARDS_BRICKS_CHARIZARD_TITLE = "Abriendo el Mega Charizard X ex Ultra-Premium Collection"
RICHARDS_BRICKS_CHARIZARD_EVIDENCE_EXCERPT = f"{RICHARDS_BRICKS_CHARIZARD_TITLE}\nBooster Pack (18)"
RICHARDS_BRICKS_CHARIZARD_EVIDENCE_SHA256 = (
    "ee0ec8cb243d26d0fc8d46b4788bb8eff2205353466c0d8e0c3c2d7cd48293f1"
)

RICHARDS_BRICKS_MEGA_EVOLUTION_IDENTITY = PUBLIC_STUDIES_BY_KEY[
    "richards-bricks-mega-evolution-box-pr-36-v1"
]
RICHARDS_BRICKS_MEGA_EVOLUTION_POLICY_CONFIG: dict[str, object] = {
    "study_key": RICHARDS_BRICKS_MEGA_EVOLUTION_IDENTITY.study_key,
    "canonical_url": RICHARDS_BRICKS_MEGA_EVOLUTION_IDENTITY.source_url,
    "fetch_url": RICHARDS_BRICKS_MEGA_EVOLUTION_IDENTITY.fetch_url,
    "collector_version": RICHARDS_BRICKS_MEGA_EVOLUTION_IDENTITY.collector_version,
    "parser_version": RICHARDS_BRICKS_MEGA_EVOLUTION_IDENTITY.parser_version,
    "country_code": "PR",
    "country_name": "Puerto Rico",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "publisher_country_url": "https://www.youtube.com/@Richards_Bricks/about",
    "publisher_channel_id": "UCP2PM8ZRJ_fiKlzJNGc02pQ",
    "publisher_country_evidence": 'country:"Puerto Rico"',
    "publisher_country_checked_at": "2026-09-05",
    "geography_review_method": "manual_static_channel_about_review",
    "set_external_id": "me01",
    "set_scope": "single_expansion",
    "set_name": "Mega Evolution",
    "product_name": "Mega Evolution Booster Box",
    "product_scope": "booster_box",
    "pack_count": 36,
    "observed_at": "2025-10-20T15:30:33Z",
    "denominator_complete": True,
    "robots_url": "https://m.youtube.com/robots.txt",
    "robots_checked_at": "2026-09-05",
    "robots_decision": "watch_route_not_disallowed",
    "terms_url": "https://www.youtube.com/static?template=terms",
    "terms_checked_at": "2026-09-05",
    "terms_effective_date": "2023-12-15",
    "terms_status": "public_browse_static_metadata_only",
    "rights_scope": "minimal_noncreative_facts_no_media_transcript_or_body_reuse",
}
RICHARDS_BRICKS_MEGA_EVOLUTION_TITLE = "Mega Evolution Booster Box unboxing"
RICHARDS_BRICKS_MEGA_EVOLUTION_EVIDENCE_EXCERPT = (
    f"{RICHARDS_BRICKS_MEGA_EVOLUTION_TITLE}\n"
    "36 booster packs from the Pokémon TCG: Mega Evolution expansion"
)
RICHARDS_BRICKS_MEGA_EVOLUTION_EVIDENCE_SHA256 = (
    "97371af1d78a7d91e48e55a02f0376d4cd399297ea50fc150b3d966963e2d18c"
)

INDIGO_GEEK_MEGA_IDENTITY = PUBLIC_STUDIES_BY_KEY["indigo-geek-megaevolucion-mx-50-v1"]
INDIGO_GEEK_MEGA_POLICY_CONFIG: dict[str, object] = {
    "study_key": INDIGO_GEEK_MEGA_IDENTITY.study_key,
    "canonical_url": INDIGO_GEEK_MEGA_IDENTITY.source_url,
    "fetch_url": INDIGO_GEEK_MEGA_IDENTITY.fetch_url,
    "collector_version": INDIGO_GEEK_MEGA_IDENTITY.collector_version,
    "parser_version": INDIGO_GEEK_MEGA_IDENTITY.parser_version,
    "country_code": "MX",
    "country_name": "Mexico",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "publisher_country_url": "https://www.youtube.com/@IndigoGeek/about",
    "publisher_channel_id": "UCGri3BoVzarWIYCzg8MEQjw",
    "publisher_country_evidence": 'country:"Mexico"',
    "publisher_country_checked_at": "2026-09-05",
    "geography_review_method": "manual_static_channel_about_review",
    "set_external_id": "me01",
    "set_language": "es-MX",
    "set_name": "Megaevolución",
    "set_official_url": "https://tcg.pokemon.com/es-mx/expansions/mega-evolution/",
    "product_name": "ETB + Booster Box + Combina y Combate",
    "product_scope": "all",
    "pack_count": 50,
    "denominator_basis": "source_declared_complete_opening",
    "source_native_products": ["etb", "booster_box", "combina_y_combate"],
    "source_published_at": "2025-09-12T06:00:41-07:00",
    "observed_at": "2025-09-12T13:00:41Z",
    "denominator_complete": True,
    "robots_url": "https://www.youtube.com/robots.txt",
    "robots_checked_at": "2026-09-05",
    "robots_decision": "watch_route_not_disallowed",
    "terms_url": "https://www.youtube.com/static?template=terms",
    "terms_checked_at": "2026-09-05",
    "terms_effective_date": "2023-12-15",
    "terms_status": "public_browse_static_metadata_only",
    "rights_scope": "minimal_noncreative_facts_no_media_transcript_or_body_reuse",
}
INDIGO_GEEK_MEGA_TITLE = "Abrimos 50 SOBRES de la nueva expansión de Pokémon JCC: Megaevolución"
INDIGO_GEEK_MEGA_EVIDENCE_EXCERPT = (
    "Abrimos 50 SOBRES de la nueva expansión de Pokémon JCC: Megaevolución\n"
    "50 sobres · ETB · booster box · Combina y combate"
)
INDIGO_GEEK_MEGA_EVIDENCE_SHA256 = (
    "c270707bfa43c79b8362a4cf5cab1bad377f0da4402904e0af02fe62c7bdb1d2"
)

POKEHANNA_ASCENDED_HEROES_IDENTITY = PUBLIC_STUDIES_BY_KEY["pokehanna-ascended-heroes-ca-9-v1"]
POKEHANNA_ASCENDED_HEROES_POLICY_CONFIG: dict[str, object] = {
    "study_key": POKEHANNA_ASCENDED_HEROES_IDENTITY.study_key,
    "canonical_url": POKEHANNA_ASCENDED_HEROES_IDENTITY.source_url,
    "fetch_url": POKEHANNA_ASCENDED_HEROES_IDENTITY.fetch_url,
    "collector_version": POKEHANNA_ASCENDED_HEROES_IDENTITY.collector_version,
    "parser_version": POKEHANNA_ASCENDED_HEROES_IDENTITY.parser_version,
    "country_code": "CA",
    "country_name": "Canada",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "publisher_country_url": "https://www.youtube.com/@PokeHanna/about",
    "publisher_channel_id": "UC6stWaGoj-9rsEOzYv56ftQ",
    "publisher_country_evidence": 'country:"Canada"',
    "publisher_country_checked_at": "2026-09-05",
    "geography_review_method": "manual_static_channel_about_review",
    "set_external_id": "me02.5",
    "set_language": "en",
    "set_name": "Ascended Heroes",
    "set_official_url": "https://www.pokemon.com/us/pokemon-tcg/product-gallery/mega-evolution-ascended-heroes-elite-trainer-box",
    "product_name": "Ascended Heroes Elite Trainer Box",
    "product_scope": "etb",
    "pack_count": 9,
    "denominator_basis": "source_named_standard_etb_plus_official_9_pack_spec",
    "denominator_derivation": "one_standard_etb_x_9",
    "source_published_at": "2026-04-05T11:00:15-07:00",
    "observed_at": "2026-04-05T18:00:15Z",
    "denominator_complete": True,
    "robots_url": "https://www.youtube.com/robots.txt",
    "robots_checked_at": "2026-09-05",
    "robots_decision": "watch_route_not_disallowed",
    "terms_url": "https://www.youtube.com/static?template=terms",
    "terms_checked_at": "2026-09-05",
    "terms_effective_date": "2023-12-15",
    "terms_status": "public_browse_static_metadata_only",
    "rights_scope": "minimal_noncreative_facts_no_media_transcript_or_body_reuse",
}
POKEHANNA_ASCENDED_HEROES_TITLE = "Opening The Ascended Heroes ETB! (Pokémon card opening)"
POKEHANNA_ASCENDED_HEROES_EVIDENCE_EXCERPT = (
    "Opening The Ascended Heroes ETB! (Pokémon card opening)\n"
    "opening all the packs · Ascended Heroes Elite Trainer Box · standard ETB = 9 packs"
)
POKEHANNA_ASCENDED_HEROES_EVIDENCE_SHA256 = (
    "d9c012acf1e003942eebdefda80058358f85ca1c718e59e5edd4dcd25b9c3ce9"
)

TCG_MARKET_PANAMA_CHAOS_RISING_IDENTITY = PUBLIC_STUDIES_BY_KEY["tcg-market-chaos-rising-pa-6-v1"]
TCG_MARKET_PANAMA_CHAOS_RISING_POLICY_CONFIG: dict[str, object] = {
    "study_key": TCG_MARKET_PANAMA_CHAOS_RISING_IDENTITY.study_key,
    "canonical_url": TCG_MARKET_PANAMA_CHAOS_RISING_IDENTITY.source_url,
    "fetch_url": TCG_MARKET_PANAMA_CHAOS_RISING_IDENTITY.fetch_url,
    "collector_version": TCG_MARKET_PANAMA_CHAOS_RISING_IDENTITY.collector_version,
    "parser_version": TCG_MARKET_PANAMA_CHAOS_RISING_IDENTITY.parser_version,
    "country_code": "PA",
    "country_name": "Panama",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "publisher_country_url": "https://www.youtube.com/channel/UCa68xVUUIKE8dvcfxCcdyrQ/about",
    "publisher_channel_id": "UCa68xVUUIKE8dvcfxCcdyrQ",
    "publisher_country_evidence": (
        "channel name: TCG Market Panamá; video description: Contenido exclusivo desde Panamá"
    ),
    "publisher_country_checked_at": "2026-09-05",
    "geography_review_method": "manual_static_watch_and_channel_name_review",
    "set_external_id": "me04",
    "set_language": "und",
    "set_language_basis": "source_does_not_state_card_language",
    "set_name": "Chaos Rising",
    "set_official_url": (
        "https://www.pokemon.com/us/pokemon-tcg/product-gallery/"
        "mega-evolution-chaos-rising-booster-bundle"
    ),
    "product_name": "Chaos Rising Booster Bundle",
    "product_scope": "booster_bundle",
    "pack_count": 6,
    "denominator_basis": "source_product_opening_plus_official_product_spec",
    "denominator_derivation": "source_opening_plus_official_6_pack_bundle_spec",
    "source_published_at": "2026-08-02T17:15:39-07:00",
    "observed_at": "2026-08-03T00:15:39Z",
    "denominator_complete": True,
    "robots_url": "https://www.youtube.com/robots.txt",
    "robots_checked_at": "2026-09-05",
    "robots_decision": "watch_route_not_disallowed",
    "terms_url": "https://www.youtube.com/static?template=terms",
    "terms_checked_at": "2026-09-05",
    "terms_effective_date": "2023-12-15",
    "terms_status": "public_browse_static_metadata_only",
    "rights_scope": "minimal_noncreative_facts_no_media_transcript_or_body_reuse",
}
TCG_MARKET_PANAMA_CHAOS_RISING_TITLE = (
    "¡Nuestro PRIMER OPENING de Pokémon TCG! ¿Vale la pena Chaos Rising Booster Bundle?"
)
TCG_MARKET_PANAMA_CHAOS_RISING_EVIDENCE_EXCERPT = (
    "¡Nuestro PRIMER OPENING de Pokémon TCG! ¿Vale la pena Chaos Rising Booster Bundle?\n"
    "Opening del Booster Bundle · sobre por sobre · desde Panamá · official bundle = 6 packs"
)
TCG_MARKET_PANAMA_CHAOS_RISING_EVIDENCE_SHA256 = (
    "abb892071c34d353e811c9715174512bb47304ac72de2508d188e13956e3e4ef"
)

TCG_MARKET_PANAMA_PITCH_BLACK_IDENTITY = PUBLIC_STUDIES_BY_KEY["tcg-market-pitch-black-pa-4-v1"]
TCG_MARKET_PANAMA_PITCH_BLACK_POLICY_CONFIG: dict[str, object] = {
    "study_key": TCG_MARKET_PANAMA_PITCH_BLACK_IDENTITY.study_key,
    "canonical_url": TCG_MARKET_PANAMA_PITCH_BLACK_IDENTITY.source_url,
    "fetch_url": TCG_MARKET_PANAMA_PITCH_BLACK_IDENTITY.fetch_url,
    "collector_version": TCG_MARKET_PANAMA_PITCH_BLACK_IDENTITY.collector_version,
    "parser_version": TCG_MARKET_PANAMA_PITCH_BLACK_IDENTITY.parser_version,
    "country_code": "PA",
    "country_name": "Panama",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "publisher_country_url": "https://www.youtube.com/channel/UCa68xVUUIKE8dvcfxCcdyrQ/about",
    "publisher_channel_id": "UCa68xVUUIKE8dvcfxCcdyrQ",
    "publisher_country_evidence": (
        "channel name: TCG Market Panamá; video description: Contenido exclusivo desde Panamá"
    ),
    "publisher_country_checked_at": "2026-09-05",
    "geography_review_method": "manual_static_watch_and_channel_name_review",
    "set_external_id": "me05",
    "set_language": "und",
    "set_language_basis": "source_does_not_state_card_language",
    "set_name": "Pitch Black",
    "set_official_url": (
        "https://www.pokemon.com/us/news/pokemon-tcg-mega-evolution-pitch-black-product-showcase"
    ),
    "product_name": "Pitch Black Build & Battle Box",
    "product_scope": "build_and_battle",
    "pack_count": 4,
    "denominator_basis": "source_product_opening_plus_official_product_spec",
    "denominator_derivation": "source_opening_plus_official_4_pack_build_and_battle_spec",
    "source_published_at": "2026-08-05T12:09:10-07:00",
    "observed_at": "2026-08-05T19:09:10Z",
    "denominator_complete": True,
    "robots_url": "https://www.youtube.com/robots.txt",
    "robots_checked_at": "2026-09-05",
    "robots_decision": "watch_route_not_disallowed",
    "terms_url": "https://www.youtube.com/static?template=terms",
    "terms_checked_at": "2026-09-05",
    "terms_effective_date": "2023-12-15",
    "terms_status": "public_browse_static_metadata_only",
    "rights_scope": "minimal_noncreative_facts_no_media_transcript_or_body_reuse",
}
TCG_MARKET_PANAMA_PITCH_BLACK_TITLE = (
    "¡Abrimos la Build & Battle de Pitch Black! ¿Nos salió una carta increíble? | Pokémon TCG"
)
TCG_MARKET_PANAMA_PITCH_BLACK_EVIDENCE_EXCERPT = (
    "¡Abrimos la Build & Battle de Pitch Black! ¿Nos salió una carta increíble? | Pokémon TCG\n"
    "abrimos la Build & Battle · todo el contenido · official box = 4 packs"
)
TCG_MARKET_PANAMA_PITCH_BLACK_EVIDENCE_SHA256 = (
    "055d48674555e3a9dc79ced8f5886c7960ad200c7c8bdc4383a5623b5e583857"
)

POKESHOW_GUATEMALA_MEGA_EVOLUTION_IDENTITY = PUBLIC_STUDIES_BY_KEY[
    "pokeshow-mega-evolution-gt-3-v1"
]
POKESHOW_GUATEMALA_MEGA_EVOLUTION_POLICY_CONFIG: dict[str, object] = {
    "study_key": POKESHOW_GUATEMALA_MEGA_EVOLUTION_IDENTITY.study_key,
    "canonical_url": POKESHOW_GUATEMALA_MEGA_EVOLUTION_IDENTITY.source_url,
    "fetch_url": POKESHOW_GUATEMALA_MEGA_EVOLUTION_IDENTITY.fetch_url,
    "collector_version": POKESHOW_GUATEMALA_MEGA_EVOLUTION_IDENTITY.collector_version,
    "parser_version": POKESHOW_GUATEMALA_MEGA_EVOLUTION_IDENTITY.parser_version,
    "country_code": "GT",
    "country_name": "Guatemala",
    "geography_basis": "publisher_country",
    "geography_confidence": "tier_b",
    "publisher_country_url": "https://www.youtube.com/@pokeshowdemaddi/about",
    "publisher_channel_id": "UChG8m-xoKqrXJDCEoE2i9Jg",
    "publisher_country_evidence": 'country:"Guatemala"; video description: desde Guatemala',
    "publisher_country_checked_at": "2026-09-05",
    "geography_review_method": "manual_static_channel_about_review",
    "set_external_id": "me01",
    "set_language": "und",
    "set_language_basis": "source_does_not_state_card_language",
    "set_name": "Mega Evolution",
    "set_official_url": "https://www.pokemoncenter.com/search/megacards",
    "product_name": "Mega Evolution Tripack (promo variant unspecified)",
    "product_scope": "three_pack_blister",
    "pack_count": 3,
    "denominator_basis": "source_product_opening_plus_official_product_spec",
    "denominator_derivation": "source_opening_plus_official_3_pack_tripack_spec",
    "product_variant_claim": "not_claimed",
    "source_published_at": "2025-10-06T10:21:33-07:00",
    "observed_at": "2025-10-06T17:21:33Z",
    "denominator_complete": True,
    "robots_url": "https://www.youtube.com/robots.txt",
    "robots_checked_at": "2026-09-05",
    "robots_decision": "watch_route_not_disallowed",
    "terms_url": "https://www.youtube.com/static?template=terms",
    "terms_checked_at": "2026-09-05",
    "terms_effective_date": "2023-12-15",
    "terms_status": "public_browse_static_metadata_only",
    "rights_scope": "minimal_noncreative_facts_no_media_transcript_or_body_reuse",
}
POKESHOW_GUATEMALA_MEGA_EVOLUTION_TITLE = (
    "🦆 El Poder del Pato 💪 | Apertura MegaEvolution + Noticias y Pokeguamazos | PokéShow de Maddi"
)
POKESHOW_GUATEMALA_MEGA_EVOLUTION_EVIDENCE_EXCERPT = (
    "🦆 El Poder del Pato 💪 | Apertura MegaEvolution + Noticias y Pokeguamazos | "
    "PokéShow de Maddi\n"
    "Abriremos un Tripack de Mega Evolution · desde Guatemala · official tripack = 3 packs"
)
POKESHOW_GUATEMALA_MEGA_EVOLUTION_EVIDENCE_SHA256 = (
    "b6c535ad4e34f0df39c8b9823a8a6e624fbb9a66c2da8329996b484b04a9feeb"
)


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
            _pokesup_pack_sequence_pattern(),
        ),
        expected_evidence_sha256=POKESUP_EVIDENCE_SHA256,
        content_tags=("main",),
        evidence_validator=_validate_pokesup_pack_sequence,
    )


def limitsend_inferno_x_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=LIMITSEND_IDENTITY,
        expected_policy_config=LIMITSEND_POLICY_CONFIG,
        title_tokens=("포켓몬카드 낱개팩 구매", "인페르노X 직접 개봉해보니"),
        evidence_patterns=(
            re.compile(re.escape(LIMITSEND_BOX_EVIDENCE)),
            re.compile(re.escape(LIMITSEND_COMPLETE_EVIDENCE)),
        ),
        expected_evidence_sha256=LIMITSEND_EVIDENCE_SHA256,
        allow_document_title=True,
        content_tags=("article",),
    )


def buyfunlife_ninja_spinner_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=BUYFUNLIFE_IDENTITY,
        expected_policy_config=BUYFUNLIFE_POLICY_CONFIG,
        title_tokens=("寶可夢忍者飛旋加值組合開箱", "MUR機率多低"),
        evidence_patterns=(re.compile(re.escape(BUYFUNLIFE_EVIDENCE_EXCERPT)),),
        expected_evidence_sha256=BUYFUNLIFE_EVIDENCE_SHA256,
        content_tags=("body",),
    )


def allonline_mega_dream_ex_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=ALLONLINE_IDENTITY,
        expected_policy_config=ALLONLINE_POLICY_CONFIG,
        title_tokens=("รีวิว การ์ดโปเกมอน", "วิวัฒนาการดรีมex", "เติมเด็คให้แข็งแกร่ง"),
        evidence_patterns=(
            re.compile(re.escape(ALLONLINE_OPENING_EVIDENCE)),
            re.compile(re.escape(ALLONLINE_RESULT_EVIDENCE)),
            re.compile(re.escape(ALLONLINE_BOX_EVIDENCE)),
        ),
        expected_evidence_sha256=ALLONLINE_EVIDENCE_SHA256,
        content_tags=("body",),
    )


def pontocom_herois_excelsos_adapter(*, client: HTTPClient) -> ReviewedPublicStudyAdapter:
    return ReviewedPublicStudyAdapter(
        client=client,
        identity=PONTOCOM_IDENTITY,
        expected_policy_config=PONTOCOM_POLICY_CONFIG,
        title_tokens=(PONTOCOM_TITLE,),
        evidence_patterns=(re.compile(re.escape(PONTOCOM_EVIDENCE_EXCERPT)),),
        expected_evidence_sha256=PONTOCOM_EVIDENCE_SHA256,
        document_validator=_validate_pontocom_static_document,
    )


def richards_bricks_charizard_upc_adapter(*, client: HTTPClient) -> YouTubeWatchCoverageAdapter:
    return YouTubeWatchCoverageAdapter(
        client=client,
        identity=RICHARDS_BRICKS_CHARIZARD_IDENTITY,
        expected_policy_config=RICHARDS_BRICKS_CHARIZARD_POLICY_CONFIG,
        expected_title=RICHARDS_BRICKS_CHARIZARD_TITLE,
        evidence_lines=RICHARDS_BRICKS_CHARIZARD_EVIDENCE_EXCERPT.split("\n"),
        evidence_pattern=re.compile(r"(?m)^Booster Pack \(18\)$"),
        expected_video_id="OON-ICjlrd4",
        expected_channel_id="UCP2PM8ZRJ_fiKlzJNGc02pQ",
        expected_observed_at=datetime(2025, 12, 24, 11, 3, 10, tzinfo=UTC),
        expected_evidence_sha256=RICHARDS_BRICKS_CHARIZARD_EVIDENCE_SHA256,
    )


def richards_bricks_mega_evolution_box_adapter(
    *, client: HTTPClient
) -> YouTubeWatchCoverageAdapter:
    return YouTubeWatchCoverageAdapter(
        client=client,
        identity=RICHARDS_BRICKS_MEGA_EVOLUTION_IDENTITY,
        expected_policy_config=RICHARDS_BRICKS_MEGA_EVOLUTION_POLICY_CONFIG,
        expected_title=RICHARDS_BRICKS_MEGA_EVOLUTION_TITLE,
        evidence_lines=RICHARDS_BRICKS_MEGA_EVOLUTION_EVIDENCE_EXCERPT.split("\n"),
        evidence_pattern=re.compile(
            r"36 booster packs from the Pokémon TCG: Mega Evolution expansion"
        ),
        expected_video_id="p_8k9ZkHV_0",
        expected_channel_id="UCP2PM8ZRJ_fiKlzJNGc02pQ",
        expected_observed_at=datetime(2025, 10, 20, 15, 30, 33, tzinfo=UTC),
        expected_evidence_sha256=RICHARDS_BRICKS_MEGA_EVOLUTION_EVIDENCE_SHA256,
    )


def indigo_geek_megaevolucion_adapter(*, client: HTTPClient) -> YouTubeWatchCoverageAdapter:
    return YouTubeWatchCoverageAdapter(
        client=client,
        identity=INDIGO_GEEK_MEGA_IDENTITY,
        expected_policy_config=INDIGO_GEEK_MEGA_POLICY_CONFIG,
        expected_title=INDIGO_GEEK_MEGA_TITLE,
        evidence_lines=INDIGO_GEEK_MEGA_EVIDENCE_EXCERPT.split("\n"),
        evidence_pattern=re.compile(
            r"(?s)una ETB, una booster box y un paquete 'Combina y combate' "
            r"para probar nuestra suerte con 50 sobres\..*"
            r"03:30\s+Combina y Combate.*"
            r"23:14\s+Elite Trainer Box.*"
            r"34:58\s+Booster Box.*"
            r"01:10:09\s+Las mejores cartas"
        ),
        expected_video_id="KNCSNJNcjJ8",
        expected_channel_id="UCGri3BoVzarWIYCzg8MEQjw",
        expected_observed_at=datetime(2025, 9, 12, 13, 0, 41, tzinfo=UTC),
        expected_evidence_sha256=INDIGO_GEEK_MEGA_EVIDENCE_SHA256,
    )


def pokehanna_ascended_heroes_adapter(*, client: HTTPClient) -> YouTubeWatchCoverageAdapter:
    return YouTubeWatchCoverageAdapter(
        client=client,
        identity=POKEHANNA_ASCENDED_HEROES_IDENTITY,
        expected_policy_config=POKEHANNA_ASCENDED_HEROES_POLICY_CONFIG,
        expected_title=POKEHANNA_ASCENDED_HEROES_TITLE,
        evidence_lines=POKEHANNA_ASCENDED_HEROES_EVIDENCE_EXCERPT.split("\n"),
        evidence_pattern=re.compile(
            r"(?s)Unboxing and opening all the packs in the Ascended Heroes Elite Trainer Box\..*"
            r"0:25 opening everything in the box.*"
            r"4:47 opening Ascended Heroes packs.*"
            r"12:06 opening Ascended Heroes packs.*"
            r"18:40 recap of hits"
        ),
        expected_video_id="Jj0IxqUYat8",
        expected_channel_id="UC6stWaGoj-9rsEOzYv56ftQ",
        expected_observed_at=datetime(2026, 4, 5, 18, 0, 15, tzinfo=UTC),
        expected_evidence_sha256=POKEHANNA_ASCENDED_HEROES_EVIDENCE_SHA256,
    )


def tcg_market_panama_chaos_rising_adapter(*, client: HTTPClient) -> YouTubeWatchCoverageAdapter:
    return YouTubeWatchCoverageAdapter(
        client=client,
        identity=TCG_MARKET_PANAMA_CHAOS_RISING_IDENTITY,
        expected_policy_config=TCG_MARKET_PANAMA_CHAOS_RISING_POLICY_CONFIG,
        expected_title=TCG_MARKET_PANAMA_CHAOS_RISING_TITLE,
        evidence_lines=TCG_MARKET_PANAMA_CHAOS_RISING_EVIDENCE_EXCERPT.split("\n"),
        evidence_pattern=re.compile(
            r"(?s)Opening del Booster Bundle.*sobre por sobre.*desde Panamá"
        ),
        expected_video_id="fHQpNECg4y4",
        expected_channel_id="UCa68xVUUIKE8dvcfxCcdyrQ",
        expected_observed_at=datetime(2026, 8, 3, 0, 15, 39, tzinfo=UTC),
        expected_evidence_sha256=TCG_MARKET_PANAMA_CHAOS_RISING_EVIDENCE_SHA256,
    )


def tcg_market_panama_pitch_black_adapter(*, client: HTTPClient) -> YouTubeWatchCoverageAdapter:
    return YouTubeWatchCoverageAdapter(
        client=client,
        identity=TCG_MARKET_PANAMA_PITCH_BLACK_IDENTITY,
        expected_policy_config=TCG_MARKET_PANAMA_PITCH_BLACK_POLICY_CONFIG,
        expected_title=TCG_MARKET_PANAMA_PITCH_BLACK_TITLE,
        evidence_lines=TCG_MARKET_PANAMA_PITCH_BLACK_EVIDENCE_EXCERPT.split("\n"),
        evidence_pattern=re.compile(r"(?s)abrimos la Build & Battle.*todo el contenido"),
        expected_video_id="6kb1MvcnMJE",
        expected_channel_id="UCa68xVUUIKE8dvcfxCcdyrQ",
        expected_observed_at=datetime(2026, 8, 5, 19, 9, 10, tzinfo=UTC),
        expected_evidence_sha256=TCG_MARKET_PANAMA_PITCH_BLACK_EVIDENCE_SHA256,
    )


def pokeshow_guatemala_megaevolution_adapter(*, client: HTTPClient) -> YouTubeWatchCoverageAdapter:
    return YouTubeWatchCoverageAdapter(
        client=client,
        identity=POKESHOW_GUATEMALA_MEGA_EVOLUTION_IDENTITY,
        expected_policy_config=POKESHOW_GUATEMALA_MEGA_EVOLUTION_POLICY_CONFIG,
        expected_title=POKESHOW_GUATEMALA_MEGA_EVOLUTION_TITLE,
        evidence_lines=POKESHOW_GUATEMALA_MEGA_EVOLUTION_EVIDENCE_EXCERPT.split("\n"),
        evidence_pattern=re.compile(r"(?s)Abriremos un Tripack de Mega Evolution.*desde Guatemala"),
        expected_video_id="DWRdhUuIUvI",
        expected_channel_id="UChG8m-xoKqrXJDCEoE2i9Jg",
        expected_observed_at=datetime(2025, 10, 6, 17, 21, 33, tzinfo=UTC),
        expected_evidence_sha256=POKESHOW_GUATEMALA_MEGA_EVOLUTION_EVIDENCE_SHA256,
    )


__all__ = [
    "ALLONLINE_EVIDENCE_EXCERPT",
    "ALLONLINE_EVIDENCE_SHA256",
    "ALLONLINE_IDENTITY",
    "ALLONLINE_POLICY_CONFIG",
    "ALLONLINE_TITLE",
    "BLEEDINGCOOL_IDENTITY",
    "BLEEDINGCOOL_POLICY_CONFIG",
    "BUYFUNLIFE_EVIDENCE_EXCERPT",
    "BUYFUNLIFE_EVIDENCE_SHA256",
    "BUYFUNLIFE_IDENTITY",
    "BUYFUNLIFE_POLICY_CONFIG",
    "BUYFUNLIFE_TITLE",
    "CARDCHILL_IDENTITY",
    "CARDCHILL_POLICY_CONFIG",
    "COMICBOOK_IDENTITY",
    "COMICBOOK_POLICY_CONFIG",
    "LIMITSEND_EVIDENCE_EXCERPT",
    "LIMITSEND_EVIDENCE_SHA256",
    "LIMITSEND_IDENTITY",
    "LIMITSEND_POLICY_CONFIG",
    "LIMITSEND_TITLE",
    "POKESUP_EVIDENCE_EXCERPT",
    "POKESUP_EVIDENCE_SHA256",
    "POKESUP_IDENTITY",
    "POKESUP_PACK_LABELS",
    "POKESUP_POLICY_CONFIG",
    "POKESUP_SECTION_HEADING",
    "POKESUP_TITLE",
    "PONTOCOM_CARD_RARITY_MAPPING",
    "PONTOCOM_EVIDENCE_EXCERPT",
    "PONTOCOM_EVIDENCE_SHA256",
    "PONTOCOM_IDENTITY",
    "PONTOCOM_POLICY_CONFIG",
    "PONTOCOM_TITLE",
    "INDIGO_GEEK_MEGA_EVIDENCE_EXCERPT",
    "INDIGO_GEEK_MEGA_EVIDENCE_SHA256",
    "INDIGO_GEEK_MEGA_IDENTITY",
    "INDIGO_GEEK_MEGA_POLICY_CONFIG",
    "INDIGO_GEEK_MEGA_TITLE",
    "POKEHANNA_ASCENDED_HEROES_EVIDENCE_EXCERPT",
    "POKEHANNA_ASCENDED_HEROES_EVIDENCE_SHA256",
    "POKEHANNA_ASCENDED_HEROES_IDENTITY",
    "POKEHANNA_ASCENDED_HEROES_POLICY_CONFIG",
    "POKEHANNA_ASCENDED_HEROES_TITLE",
    "POKESHOW_GUATEMALA_MEGA_EVOLUTION_EVIDENCE_EXCERPT",
    "POKESHOW_GUATEMALA_MEGA_EVOLUTION_EVIDENCE_SHA256",
    "POKESHOW_GUATEMALA_MEGA_EVOLUTION_IDENTITY",
    "POKESHOW_GUATEMALA_MEGA_EVOLUTION_POLICY_CONFIG",
    "POKESHOW_GUATEMALA_MEGA_EVOLUTION_TITLE",
    "ReviewedPublicStudyAdapter",
    "RobotsTxtChecker",
    "RICHARDS_BRICKS_CHARIZARD_EVIDENCE_EXCERPT",
    "RICHARDS_BRICKS_CHARIZARD_EVIDENCE_SHA256",
    "RICHARDS_BRICKS_CHARIZARD_IDENTITY",
    "RICHARDS_BRICKS_CHARIZARD_POLICY_CONFIG",
    "RICHARDS_BRICKS_CHARIZARD_TITLE",
    "RICHARDS_BRICKS_MEGA_EVOLUTION_EVIDENCE_EXCERPT",
    "RICHARDS_BRICKS_MEGA_EVOLUTION_EVIDENCE_SHA256",
    "RICHARDS_BRICKS_MEGA_EVOLUTION_IDENTITY",
    "RICHARDS_BRICKS_MEGA_EVOLUTION_POLICY_CONFIG",
    "RICHARDS_BRICKS_MEGA_EVOLUTION_TITLE",
    "TCGTALK_EVIDENCE_EXCERPT",
    "TCGTALK_EVIDENCE_SHA256",
    "TCGTALK_IDENTITY",
    "TCGTALK_POLICY_CONFIG",
    "TCG_MARKET_PANAMA_CHAOS_RISING_EVIDENCE_EXCERPT",
    "TCG_MARKET_PANAMA_CHAOS_RISING_EVIDENCE_SHA256",
    "TCG_MARKET_PANAMA_CHAOS_RISING_IDENTITY",
    "TCG_MARKET_PANAMA_CHAOS_RISING_POLICY_CONFIG",
    "TCG_MARKET_PANAMA_CHAOS_RISING_TITLE",
    "TCG_MARKET_PANAMA_PITCH_BLACK_EVIDENCE_EXCERPT",
    "TCG_MARKET_PANAMA_PITCH_BLACK_EVIDENCE_SHA256",
    "TCG_MARKET_PANAMA_PITCH_BLACK_IDENTITY",
    "TCG_MARKET_PANAMA_PITCH_BLACK_POLICY_CONFIG",
    "TCG_MARKET_PANAMA_PITCH_BLACK_TITLE",
    "WARGAMER_IDENTITY",
    "WARGAMER_POLICY_CONFIG",
    "allonline_mega_dream_ex_adapter",
    "bleedingcool_phantasmal_flames_adapter",
    "buyfunlife_ninja_spinner_adapter",
    "cardchill_ascended_heroes_adapter",
    "comicbook_perfect_order_adapter",
    "limitsend_inferno_x_adapter",
    "pokesup_abyss_eye_adapter",
    "pontocom_herois_excelsos_adapter",
    "richards_bricks_charizard_upc_adapter",
    "richards_bricks_mega_evolution_box_adapter",
    "indigo_geek_megaevolucion_adapter",
    "pokehanna_ascended_heroes_adapter",
    "pokeshow_guatemala_megaevolution_adapter",
    "tcg_market_panama_chaos_rising_adapter",
    "tcg_market_panama_pitch_black_adapter",
    "tcgtalk_perfect_order_adapter",
    "wargamer_chaos_rising_adapter",
    "YouTubeWatchCoverageAdapter",
]
