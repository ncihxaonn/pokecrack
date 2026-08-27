"""Bounded YouTube Data API discovery; video and page downloads are absent."""

from __future__ import annotations

import html
import json
import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from types import MappingProxyType
from typing import Any, Protocol

import httpx
from pydantic import SecretStr

from pokecrack_worker.collectors.official_api.tcgdex import APIResponse
from pokecrack_worker.config.registries import REQUIRED_YOUTUBE_QUERIES, YouTubeQuery
from pokecrack_worker.config.source_policy import CollectorRoute, SourcePolicyRegistry
from pokecrack_worker.models import CollectorType, SourceItemCandidate

YOUTUBE_SEARCH_URL = "https://youtube.googleapis.com/youtube/v3/search"
YOUTUBE_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
YOUTUBE_TIMEOUT_SECONDS = 30.0
YOUTUBE_COLLECTOR_VERSION = "youtube-global-discovery-v1"
YOUTUBE_APPROVED_QUERY_TEXT: Mapping[str, str] = MappingProxyType(dict(REQUIRED_YOUTUBE_QUERIES))
YOUTUBE_QUERY_ALLOWLIST = tuple(YOUTUBE_APPROVED_QUERY_TEXT)
_EXPECTED_POLICY_CONFIG: dict[str, Any] = {
    "metadata_only": True,
    "media_download": False,
    "max_response_bytes": YOUTUBE_MAX_RESPONSE_BYTES,
    "query_allowlist": list(YOUTUBE_QUERY_ALLOWLIST),
}

_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


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
class _SearchItem:
    video_id: str
    title: str | None
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
        if url != YOUTUBE_SEARCH_URL:
            raise ValueError("YouTube transport accepts only the fixed search endpoint")
        if timeout_seconds != YOUTUBE_TIMEOUT_SECONDS:
            raise ValueError("YouTube transport requires the fixed 30-second timeout")
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
        title = snippet.get("title")
        if (
            identity.get("kind") != "youtube#video"
            or not isinstance(video_id, str)
            or _VIDEO_ID_PATTERN.fullmatch(video_id) is None
            or not isinstance(title, str)
        ):
            raise YouTubeInvalidResponse()
        if video_id in seen_video_ids:
            raise YouTubeInvalidResponse("duplicate_video_id")
        seen_video_ids.add(video_id)
        items.append(
            _SearchItem(
                video_id=video_id,
                title=_normalize_text(title, max_chars=500),
                published_at=_published_at(snippet.get("publishedAt")),
            )
        )
    return tuple(items)


class YouTubeDataClient:
    def __init__(
        self,
        *,
        api_key: str,
        transport: YouTubeTransport,
        policies: SourcePolicyRegistry,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not api_key:
            raise YouTubeCredentialsUnavailable()
        self._api_key = SecretStr(api_key)
        self.transport = transport
        self.policies = policies
        self._clock = clock or (lambda: datetime.now(UTC))

    def discover(self, query: YouTubeQuery) -> tuple[SourceItemCandidate, ...]:
        policy = self.policies.require(YOUTUBE_SEARCH_URL, CollectorRoute.YOUTUBE)
        if (
            policy.version != YOUTUBE_COLLECTOR_VERSION
            or policy.min_delay_seconds != 2
            or policy.max_pages_per_run != 1
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
        search_response = self.transport.get(
            YOUTUBE_SEARCH_URL,
            params={
                "part": "snippet",
                "type": "video",
                "q": query.query,
                "maxResults": str(query.max_results),
                "order": query.order,
                "publishedAfter": published_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "relevanceLanguage": "en",
                "fields": "items(id(kind,videoId),snippet(publishedAt,title))",
            },
            api_key=self._api_key,
            timeout_seconds=YOUTUBE_TIMEOUT_SECONDS,
        )
        if search_response.status_code != 200:
            raise YouTubeHTTPError(search_response.status_code)
        search_items = _parse_search_response(search_response.body, max_results=query.max_results)

        candidates: list[SourceItemCandidate] = []
        for item in search_items:
            try:
                candidate = SourceItemCandidate(
                    platform="youtube",
                    external_id=item.video_id,
                    source_url=f"https://www.youtube.com/watch?v={item.video_id}",
                    title=item.title,
                    text=None,
                    published_at=item.published_at,
                    author_hash=None,
                    media_urls=(),
                    metadata={},
                    collector=CollectorType.OFFICIAL_API,
                    collector_version=YOUTUBE_COLLECTOR_VERSION,
                    source_policy_version=policy.version,
                )
            except (TypeError, ValueError) as error:
                raise YouTubeInvalidResponse() from error
            candidates.append(candidate)
        return tuple(candidates)
