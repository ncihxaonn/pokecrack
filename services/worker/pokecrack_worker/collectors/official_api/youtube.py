"""YouTube Data API metadata discovery. Full video download is intentionally absent."""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx

from pokecrack_worker.collectors.official_api.tcgdex import APIResponse
from pokecrack_worker.config.registries import YouTubeQuery
from pokecrack_worker.config.source_policy import CollectorRoute, SourcePolicyRegistry
from pokecrack_worker.models import CollectorType, SourceItemCandidate, hash_author


class YouTubeError(RuntimeError):
    pass


class YouTubeCredentialsUnavailable(YouTubeError):
    pass


class YouTubeHTTPError(YouTubeError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"YouTube Data API HTTP status {status_code}")


@dataclass(frozen=True, slots=True)
class YouTubeDiscoveryFailure:
    query_name: str
    error_code: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class YouTubeDiscoveryResult:
    items: tuple[SourceItemCandidate, ...]
    failures: tuple[YouTubeDiscoveryFailure, ...]


class YouTubeTransport(Protocol):
    def get(self, url: str, *, params: dict[str, str], timeout_seconds: float) -> APIResponse: ...


class HTTPXYouTubeTransport:
    """Bounded no-redirect network path for metadata-only API responses."""

    def __init__(self, *, max_response_bytes: int = 2_000_000) -> None:
        if not 1 <= max_response_bytes <= 10_000_000:
            raise ValueError("max_response_bytes must be between 1 and 10000000")
        self.max_response_bytes = max_response_bytes

    def get(self, url: str, *, params: dict[str, str], timeout_seconds: float) -> APIResponse:
        try:
            with httpx.stream(
                "GET",
                url,
                params=params,
                timeout=timeout_seconds,
                follow_redirects=False,
            ) as response:
                declared_length = response.headers.get("content-length")
                if declared_length is not None:
                    try:
                        if int(declared_length) > self.max_response_bytes:
                            raise YouTubeError("YouTube Data API response exceeds byte cap")
                    except ValueError as error:
                        raise YouTubeError("YouTube Data API content length is invalid") from error
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > self.max_response_bytes:
                        raise YouTubeError("YouTube Data API response exceeds byte cap")
                return APIResponse(response.status_code, dict(response.headers), bytes(body))
        except httpx.HTTPError:
            raise YouTubeError("YouTube Data API request failed") from None


class YouTubeDataClient:
    media_download = False

    def __init__(
        self,
        *,
        api_key: str,
        transport: YouTubeTransport,
        policies: SourcePolicyRegistry,
        base_url: str = "https://youtube.googleapis.com/youtube/v3",
        timeout_seconds: float = 30,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not api_key:
            raise YouTubeCredentialsUnavailable(
                "YOUTUBE_API_KEY is required for YouTube Data API discovery"
            )
        self._api_key = api_key
        self.transport = transport
        self.policies = policies
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _thumbnail(snippet: Mapping[str, Any]) -> tuple[str, ...]:
        thumbnails = snippet.get("thumbnails")
        if not isinstance(thumbnails, Mapping):
            return ()
        for quality in ("maxres", "high", "medium", "default"):
            item = thumbnails.get(quality)
            if isinstance(item, Mapping) and isinstance(item.get("url"), str):
                return (item["url"],)
        return ()

    def discover(self, query: YouTubeQuery) -> tuple[SourceItemCandidate, ...]:
        endpoint = f"{self.base_url}/search"
        policy = self.policies.require(endpoint, CollectorRoute.YOUTUBE)
        published_after = self._clock().astimezone(UTC) - timedelta(
            days=query.published_within_days
        )
        params = {
            "part": "snippet",
            "type": "video",
            "q": query.query,
            "maxResults": str(query.max_results),
            "order": query.order,
            "publishedAfter": published_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "key": self._api_key,
        }
        if query.region_code:
            params["regionCode"] = query.region_code
        response = self.transport.get(endpoint, params=params, timeout_seconds=self.timeout_seconds)
        if response.status_code != 200:
            raise YouTubeHTTPError(response.status_code)
        try:
            payload: Any = json.loads(response.body)
        except json.JSONDecodeError as error:
            raise YouTubeError(f"YouTube Data API returned invalid JSON: {error}") from error
        if not isinstance(payload, Mapping) or not isinstance(payload.get("items"), list):
            raise YouTubeError("YouTube Data API response requires an items array")
        candidates: list[SourceItemCandidate] = []
        for raw_item in payload["items"]:
            if not isinstance(raw_item, Mapping):
                continue
            identity = raw_item.get("id")
            snippet = raw_item.get("snippet")
            if not isinstance(identity, Mapping) or not isinstance(snippet, Mapping):
                continue
            video_id = identity.get("videoId")
            if not isinstance(video_id, str) or not video_id:
                continue
            title = snippet.get("title")
            description = snippet.get("description")
            channel_id = snippet.get("channelId")
            channel_title = snippet.get("channelTitle")
            author_identity = channel_id if isinstance(channel_id, str) else channel_title
            metadata: dict[str, Any] = {
                "query_name": query.name,
                "metadata_only": True,
                "media_download": False,
            }
            candidates.append(
                SourceItemCandidate(
                    platform="youtube",
                    external_id=video_id,
                    source_url=f"https://www.youtube.com/watch?v={video_id}",
                    title=(html.unescape(title) if isinstance(title, str) else None),
                    text=(
                        html.unescape(description)[:20_000]
                        if isinstance(description, str)
                        else None
                    ),
                    published_at=(
                        snippet.get("publishedAt")
                        if isinstance(snippet.get("publishedAt"), str)
                        else None
                    ),
                    author_hash=(
                        hash_author(author_identity)
                        if isinstance(author_identity, str) and author_identity.strip()
                        else None
                    ),
                    media_urls=self._thumbnail(snippet),
                    metadata=metadata,
                    collector=CollectorType.OFFICIAL_API,
                    collector_version=str(
                        policy.config.get("collector_version", "youtube-data-v3")
                    ),
                    source_policy_version=policy.version,
                )
            )
        return tuple(candidates)

    def discover_many(self, queries: Sequence[YouTubeQuery]) -> YouTubeDiscoveryResult:
        """Run at most five approved query objects and isolate per-query failures."""

        if len(queries) > 5:
            raise ValueError("YouTube discovery is limited to five queries per run")
        items: list[SourceItemCandidate] = []
        failures: list[YouTubeDiscoveryFailure] = []
        identities: set[tuple[str, str | None, str]] = set()
        for query in queries:
            try:
                discovered = self.discover(query)
            except YouTubeHTTPError as error:
                failures.append(
                    YouTubeDiscoveryFailure(
                        query_name=query.name,
                        error_code="http_error",
                        retryable=error.status_code == 429 or error.status_code >= 500,
                    )
                )
                continue
            except YouTubeError:
                failures.append(
                    YouTubeDiscoveryFailure(
                        query_name=query.name,
                        error_code="invalid_response",
                        retryable=False,
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
