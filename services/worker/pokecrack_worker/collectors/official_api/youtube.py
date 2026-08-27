"""Bounded YouTube Data API discovery; video and page downloads are absent."""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic, sleep
from types import MappingProxyType
from typing import Any, Protocol

import httpx
from pydantic import SecretStr

from pokecrack_worker.collectors.official_api.tcgdex import APIResponse
from pokecrack_worker.config.registries import REQUIRED_YOUTUBE_QUERIES, YouTubeQuery
from pokecrack_worker.config.source_policy import CollectorRoute, SourcePolicyRegistry
from pokecrack_worker.models import CollectorType, SourceItemCandidate

YOUTUBE_SEARCH_URL = "https://youtube.googleapis.com/youtube/v3/search"
YOUTUBE_CHANNELS_URL = "https://youtube.googleapis.com/youtube/v3/channels"
YOUTUBE_OFFICIAL_ENDPOINTS = frozenset({YOUTUBE_SEARCH_URL, YOUTUBE_CHANNELS_URL})
YOUTUBE_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
YOUTUBE_TIMEOUT_SECONDS = 30.0
YOUTUBE_COLLECTOR_VERSION = "youtube-global-discovery-v1"
YOUTUBE_PARSER_VERSION = "youtube-metadata-v1"
YOUTUBE_APPROVED_QUERY_TEXT: Mapping[str, str] = MappingProxyType(dict(REQUIRED_YOUTUBE_QUERIES))
YOUTUBE_QUERY_ALLOWLIST = tuple(YOUTUBE_APPROVED_QUERY_TEXT)
_EXPECTED_POLICY_CONFIG: dict[str, Any] = {
    "metadata_only": True,
    "media_download": False,
    "discovery_scope": "global",
    "geography_status": "unresolved",
    "evidence_tier": "D",
    "statistics_eligible": False,
    "parser_version": YOUTUBE_PARSER_VERSION,
    "max_response_bytes": YOUTUBE_MAX_RESPONSE_BYTES,
    "query_allowlist": list(YOUTUBE_QUERY_ALLOWLIST),
}

_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHANNEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,128}$")
_CHANNEL_HASH_NAMESPACE = b"youtube-channel-v1\0"
_BATCH_CODE_PATTERN = re.compile(
    r"\b(?:batch|lot)\s+code\s*(?P<separator>[:#=\-])?\s*"
    r"(?P<code>[A-Z0-9][A-Z0-9_-]{1,31})\b",
    re.IGNORECASE,
)
_PRODUCT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("booster_box", re.compile(r"\bbooster[\s-]+box\b", re.IGNORECASE)),
    (
        "etb",
        re.compile(r"\b(?:etb|elite[\s-]+trainer[\s-]+box)\b", re.IGNORECASE),
    ),
    ("booster_bundle", re.compile(r"\bbooster[\s-]+bundle\b", re.IGNORECASE)),
)


class YouTubeError(RuntimeError):
    """Safe typed error whose code/retry disposition can cross the job boundary."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class YouTubeCredentialsUnavailable(YouTubeError):
    def __init__(self) -> None:
        super().__init__("credentials_unavailable", retryable=False)


class YouTubeHTTPError(YouTubeError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(
            "http_error",
            retryable=status_code in {408, 425, 429} or status_code >= 500,
        )


class YouTubeInvalidResponse(YouTubeError):
    def __init__(self, code: str = "invalid_response") -> None:
        super().__init__(code, retryable=False)


@dataclass(frozen=True, slots=True)
class YouTubeDiscoveryFailure:
    query_name: str
    error_code: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class YouTubeDiscoveryResult:
    items: tuple[SourceItemCandidate, ...]
    failures: tuple[YouTubeDiscoveryFailure, ...]


@dataclass(frozen=True, slots=True)
class _SearchItem:
    video_id: str
    channel_id: str
    title: str | None
    description: str | None
    published_at: datetime


class YouTubeTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        api_key: SecretStr,
        timeout_seconds: float,
    ) -> APIResponse: ...


class HTTPXYouTubeTransport:
    """Fixed-host, no-proxy, no-redirect transport with byte and wall-time caps."""

    def __init__(
        self,
        *,
        max_response_bytes: int = YOUTUBE_MAX_RESPONSE_BYTES,
        monotonic_clock: Callable[[], float] = monotonic,
        http_transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not 1 <= max_response_bytes <= YOUTUBE_MAX_RESPONSE_BYTES:
            raise ValueError(
                f"max_response_bytes must be between 1 and {YOUTUBE_MAX_RESPONSE_BYTES}"
            )
        self.max_response_bytes = max_response_bytes
        self._monotonic = monotonic_clock
        self._http_transport = http_transport

    def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        api_key: SecretStr,
        timeout_seconds: float,
    ) -> APIResponse:
        if url not in YOUTUBE_OFFICIAL_ENDPOINTS:
            raise ValueError("YouTube transport accepts only the fixed official endpoints")
        if not 0 < timeout_seconds <= 60:
            raise ValueError("YouTube timeout must be between 0 and 60 seconds")
        deadline = self._monotonic() + timeout_seconds
        timeout = httpx.Timeout(
            timeout=min(timeout_seconds, 10.0),
            connect=min(timeout_seconds, 10.0),
            read=min(timeout_seconds, 10.0),
            write=min(timeout_seconds, 10.0),
            pool=min(timeout_seconds, 10.0),
        )
        try:
            with httpx.Client(
                follow_redirects=False,
                trust_env=False,
                timeout=timeout,
                transport=self._http_transport,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
            ) as client:
                with client.stream(
                    "GET",
                    url,
                    params={**params, "key": api_key.get_secret_value()},
                ) as response:
                    if self._monotonic() > deadline:
                        raise YouTubeError("request_timeout", retryable=True)
                    declared_length = response.headers.get("content-length")
                    content_encoding = response.headers.get("content-encoding")
                    if content_encoding is not None and content_encoding.strip().casefold() not in {
                        "",
                        "identity",
                    }:
                        raise YouTubeInvalidResponse("unsupported_content_encoding")
                    if declared_length is not None:
                        try:
                            parsed_length = int(declared_length)
                        except ValueError as error:
                            raise YouTubeInvalidResponse("invalid_content_length") from error
                        if parsed_length < 0:
                            raise YouTubeInvalidResponse("invalid_content_length")
                        if parsed_length > self.max_response_bytes:
                            raise YouTubeInvalidResponse("response_too_large")
                    body = bytearray()
                    for chunk in response.iter_raw():
                        if self._monotonic() > deadline:
                            raise YouTubeError("request_timeout", retryable=True)
                        body.extend(chunk)
                        if len(body) > self.max_response_bytes:
                            raise YouTubeInvalidResponse("response_too_large")
                    if self._monotonic() > deadline:
                        raise YouTubeError("request_timeout", retryable=True)
                    return APIResponse(response.status_code, dict(response.headers), bytes(body))
        except YouTubeError:
            raise
        except httpx.TimeoutException:
            raise YouTubeError("request_timeout", retryable=True) from None
        except httpx.HTTPError:
            raise YouTubeError("network_error", retryable=True) from None


def _normalize_text(value: str, *, max_chars: int) -> str | None:
    decoded = unicodedata.normalize("NFKC", html.unescape(value))
    without_controls = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in decoded
    )
    normalized = " ".join(without_controls.split())
    return normalized[:max_chars] or None


def _activity_hints(
    title: str | None,
    description: str | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    text = " ".join(value for value in (title, description) if value)
    products = tuple(name for name, pattern in _PRODUCT_PATTERNS if pattern.search(text))
    batch_codes: list[str] = []
    for match in _BATCH_CODE_PATTERN.finditer(text):
        code = match.group("code").upper()
        # Without punctuation, require a digit so prose like "batch code shown"
        # cannot become an identifier. These remain unverified activity hints.
        if match.group("separator") is None and not any(character.isdigit() for character in code):
            continue
        if code not in batch_codes:
            batch_codes.append(code)
        if len(batch_codes) == 5:
            break
    return products, tuple(batch_codes)


def _hash_channel_id(channel_id: str) -> str:
    """Hash the validated case-sensitive opaque ID without person-name normalization."""

    if _CHANNEL_ID_PATTERN.fullmatch(channel_id) is None:
        raise YouTubeInvalidResponse("invalid_channel_id")
    return hashlib.sha256(_CHANNEL_HASH_NAMESPACE + channel_id.encode("ascii")).hexdigest()


def _json_mapping(body: bytes) -> Mapping[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise YouTubeInvalidResponse("duplicate_json_key")
            result[key] = value
        return result

    try:
        payload: Any = json.loads(body, object_pairs_hook=reject_duplicate_keys)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise YouTubeInvalidResponse() from error
    if not isinstance(payload, Mapping):
        raise YouTubeInvalidResponse()
    return payload


def _published_at(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise YouTubeInvalidResponse()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise YouTubeInvalidResponse() from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise YouTubeInvalidResponse()
    return parsed.astimezone(UTC)


def _parse_search_response(body: bytes, *, max_results: int) -> tuple[_SearchItem, ...]:
    payload = _json_mapping(body)
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or len(raw_items) > max_results:
        raise YouTubeInvalidResponse()
    items: list[_SearchItem] = []
    seen_video_ids: set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            raise YouTubeInvalidResponse()
        identity = raw_item.get("id")
        snippet = raw_item.get("snippet")
        if not isinstance(identity, Mapping) or not isinstance(snippet, Mapping):
            raise YouTubeInvalidResponse()
        video_id = identity.get("videoId")
        channel_id = snippet.get("channelId")
        title = snippet.get("title")
        description = snippet.get("description")
        if (
            identity.get("kind") != "youtube#video"
            or not isinstance(video_id, str)
            or _VIDEO_ID_PATTERN.fullmatch(video_id) is None
            or not isinstance(channel_id, str)
            or _CHANNEL_ID_PATTERN.fullmatch(channel_id) is None
            or not isinstance(title, str)
            or not isinstance(description, str)
        ):
            raise YouTubeInvalidResponse()
        if video_id in seen_video_ids:
            raise YouTubeInvalidResponse("duplicate_video_id")
        seen_video_ids.add(video_id)
        items.append(
            _SearchItem(
                video_id=video_id,
                channel_id=channel_id,
                title=_normalize_text(title, max_chars=500),
                description=_normalize_text(description, max_chars=20_000),
                published_at=_published_at(snippet.get("publishedAt")),
            )
        )
    return tuple(items)


def _parse_channel_countries(
    body: bytes,
    *,
    requested_ids: frozenset[str],
) -> Mapping[str, str]:
    payload = _json_mapping(body)
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or len(raw_items) > len(requested_ids):
        raise YouTubeInvalidResponse()
    countries: dict[str, str] = {}
    seen: set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            raise YouTubeInvalidResponse()
        channel_id = raw_item.get("id")
        snippet = raw_item.get("snippet")
        if (
            not isinstance(channel_id, str)
            or channel_id not in requested_ids
            or channel_id in seen
            or not isinstance(snippet, Mapping)
        ):
            raise YouTubeInvalidResponse()
        seen.add(channel_id)
        country = snippet.get("country")
        if country is None:
            continue
        if not isinstance(country, str) or re.fullmatch(r"[A-Z]{2}", country) is None:
            raise YouTubeInvalidResponse("invalid_channel_country")
        countries[channel_id] = country
    return countries


class YouTubeDataClient:
    media_download = False

    def __init__(
        self,
        *,
        api_key: str,
        transport: YouTubeTransport,
        policies: SourcePolicyRegistry,
        timeout_seconds: float = YOUTUBE_TIMEOUT_SECONDS,
        clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        if not api_key:
            raise YouTubeCredentialsUnavailable()
        if not 0 < timeout_seconds <= 60:
            raise ValueError("YouTube timeout must be between 0 and 60 seconds")
        self._api_key = SecretStr(api_key)
        self.transport = transport
        self.policies = policies
        self.timeout_seconds = timeout_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._monotonic = monotonic_clock
        self._sleeper = sleeper

    def _remaining_timeout(self, deadline: float) -> float:
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise YouTubeError("request_timeout", retryable=True)
        return remaining

    def _request(
        self,
        endpoint: str,
        params: dict[str, str],
        *,
        deadline: float,
    ) -> APIResponse:
        response = self.transport.get(
            endpoint,
            params=params,
            api_key=self._api_key,
            timeout_seconds=self._remaining_timeout(deadline),
        )
        self._remaining_timeout(deadline)
        if response.status_code != 200:
            raise YouTubeHTTPError(response.status_code)
        return response

    def discover(self, query: YouTubeQuery) -> tuple[SourceItemCandidate, ...]:
        request_started = self._monotonic()
        deadline = request_started + self.timeout_seconds
        policy = self.policies.require(YOUTUBE_SEARCH_URL, CollectorRoute.YOUTUBE)
        if (
            policy.version != YOUTUBE_COLLECTOR_VERSION
            or policy.min_delay_seconds != 2
            or policy.max_pages_per_run != 2
            or policy.max_concurrency != 1
            or policy.retention_days != 28
            or not policy.metadata_only
            or policy.statistics_eligible_default
            or policy.config != _EXPECTED_POLICY_CONFIG
            or YOUTUBE_APPROVED_QUERY_TEXT.get(query.name) != query.query
            or query.enabled is not False
            or query.metadata_only is not True
            or query.max_results != 25
            or query.region_code is not None
            or query.published_within_days != 30
            or query.order != "date"
        ):
            raise YouTubeInvalidResponse("source_policy_version_mismatch")
        published_after = self._clock().astimezone(UTC) - timedelta(
            days=query.published_within_days
        )
        # This is an English text-relevance hint, never a region or observed geography.
        search_response = self._request(
            YOUTUBE_SEARCH_URL,
            {
                "part": "snippet",
                "type": "video",
                "q": query.query,
                "maxResults": str(query.max_results),
                "order": query.order,
                "publishedAfter": published_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "relevanceLanguage": "en",
            },
            deadline=deadline,
        )
        search_items = _parse_search_response(search_response.body, max_results=query.max_results)
        self._remaining_timeout(deadline)
        channel_ids = frozenset(item.channel_id for item in search_items)
        countries: Mapping[str, str] = {}
        if channel_ids:
            now = self._monotonic()
            remaining_delay = policy.min_delay_seconds - (now - request_started)
            if remaining_delay > 0:
                if deadline - now <= remaining_delay:
                    raise YouTubeError("request_timeout", retryable=True)
                self._sleeper(remaining_delay)
                self._remaining_timeout(deadline)
            channels_response = self._request(
                YOUTUBE_CHANNELS_URL,
                {
                    "part": "snippet",
                    "id": ",".join(sorted(channel_ids)),
                    "maxResults": str(len(channel_ids)),
                },
                deadline=deadline,
            )
            countries = _parse_channel_countries(
                channels_response.body,
                requested_ids=channel_ids,
            )
            self._remaining_timeout(deadline)

        candidates: list[SourceItemCandidate] = []
        for item in search_items:
            product_hints, batch_hints = _activity_hints(item.title, item.description)
            country = countries.get(item.channel_id)
            metadata: dict[str, Any] = {
                "query_name": query.name,
                "metadata_only": True,
                "media_download": False,
                "discovery_scope": "global",
                "geography_status": (
                    "channel_country_proxy" if country is not None else "unresolved"
                ),
                "evidence_tier": "D",
                "statistics_eligible": False,
                "parser_version": YOUTUBE_PARSER_VERSION,
                "product_type_hints": list(product_hints),
                "batch_code_hints": list(batch_hints),
                "channel_country_code": country,
                "geography_basis": (
                    "youtube_channel_country" if country is not None else "unresolved"
                ),
            }
            try:
                candidate = SourceItemCandidate(
                    platform="youtube",
                    external_id=item.video_id,
                    source_url=f"https://www.youtube.com/watch?v={item.video_id}",
                    title=item.title,
                    text=item.description,
                    published_at=item.published_at,
                    author_hash=_hash_channel_id(item.channel_id),
                    media_urls=(),
                    metadata=metadata,
                    collector=CollectorType.OFFICIAL_API,
                    collector_version=YOUTUBE_COLLECTOR_VERSION,
                    source_policy_version=policy.version,
                )
            except (TypeError, ValueError) as error:
                raise YouTubeInvalidResponse() from error
            candidates.append(candidate)
        self._remaining_timeout(deadline)
        return tuple(candidates)

    def discover_many(self, queries: Sequence[YouTubeQuery]) -> YouTubeDiscoveryResult:
        """Compatibility batch helper; live scheduling uses one query per job."""

        if len(queries) > 5:
            raise ValueError("YouTube discovery is limited to five queries per run")
        items: list[SourceItemCandidate] = []
        failures: list[YouTubeDiscoveryFailure] = []
        identities: set[tuple[str, str | None, str]] = set()
        for query in queries:
            try:
                discovered = self.discover(query)
            except YouTubeError as error:
                failures.append(
                    YouTubeDiscoveryFailure(
                        query_name=query.name,
                        error_code=error.code,
                        retryable=error.retryable,
                    )
                )
                continue
            for item in discovered:
                identity = (item.platform, item.external_id, item.normalized_url or item.source_url)
                if identity in identities:
                    continue
                identities.add(identity)
                items.append(item)
        return YouTubeDiscoveryResult(tuple(items), tuple(failures))
