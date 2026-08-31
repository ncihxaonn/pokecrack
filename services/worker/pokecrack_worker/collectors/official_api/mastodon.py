"""Bounded, read-only Mastodon public hashtag discovery.

Only one reviewed Mastodon instance and seven reviewed hashtags are reachable.
The endpoint is deliberately REST-only: no login, bearer token, browser,
proxy, redirect, arbitrary URL, or arbitrary hashtag is accepted.  A status
is reduced at the boundary to an opaque id, timestamp, and approved tag keys;
content, accounts, profiles, links, media, and opening-like fields never
leave this module.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from threading import RLock
from typing import Any, Final, Protocol
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx

from pokecrack_worker.collectors.official_api.tcgdex import APIResponse
from pokecrack_worker.config.mastodon import (
    MASTODON_APPROVED_TAGS,
    MASTODON_HASHTAG_BASE_URL,
    MASTODON_INSTANCE_KEY,
    MASTODON_INSTANCE_URL,
    MastodonInstance,
    MastodonRegistry,
)

MASTODON_COLLECTOR_VERSION: Final = "mastodon-public-hashtag-v1"
MASTODON_COMPLETION_VERSION: Final = "1.0.0"
MASTODON_MAX_PAGES: Final = 2
MASTODON_MAX_STATUSES: Final = 80
MASTODON_MAX_STATUSES_PER_PAGE: Final = 40
MASTODON_MAX_RESPONSE_BYTES: Final = 2 * 1024 * 1024
MASTODON_CONNECT_TIMEOUT_SECONDS: Final = 10.0
MASTODON_READ_TIMEOUT_SECONDS: Final = 15.0
MASTODON_USER_AGENT: Final = "PokecrackMetadataCollector/0.1 (+https://pokecrack.vercel.app)"
MASTODON_MIN_REQUEST_INTERVAL_SECONDS: Final = 2.0
# Kept as a source-gate alias for callers that already import the old name.
MASTODON_SOURCE_GATE_SECONDS: Final = MASTODON_MIN_REQUEST_INTERVAL_SECONDS
MASTODON_MAX_STATUS_ID_LENGTH: Final = 160
MASTODON_MAX_TAGS_PER_STATUS: Final = 40
MASTODON_MAX_LINK_HEADER_BYTES: Final = 16 * 1024
MASTODON_MAX_RATE_LIMIT: Final = 100_000
MASTODON_MAX_RATE_RESET_SECONDS: Final = 7 * 24 * 60 * 60
MASTODON_MIN_PUBLISHED_AT: Final = datetime(2000, 1, 1, tzinfo=UTC)
_CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
_ISO_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:0[0-9]|1[0-9]|2[0-3]):[0-5][0-9])$"
)
_REL_PATTERN = re.compile(r"(?:^|;)\s*rel\s*=\s*(?:\"([^\"]+)\"|([^;\s]+))", re.I)


class MastodonError(RuntimeError):
    """Base error whose code and retry disposition can cross the job boundary."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class MastodonTransportError(MastodonError):
    def __init__(self, code: str = "mastodon_transport_error") -> None:
        super().__init__(code, retryable=True)


class MastodonHTTPError(MastodonError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(
            f"mastodon_http_{status_code}",
            retryable=status_code in {408, 425, 429} or status_code >= 500,
        )


class MastodonRateLimited(MastodonError):
    def __init__(self, retry_at: datetime | None = None) -> None:
        self.retry_at = retry_at
        super().__init__("mastodon_rate_limited", retryable=True)


class MastodonInvalidResponse(MastodonError):
    def __init__(self, code: str = "mastodon_invalid_response") -> None:
        super().__init__(code, retryable=False)


class MastodonPreflightError(MastodonInvalidResponse):
    def __init__(self, code: str = "mastodon_preflight_failed") -> None:
        super().__init__(code)


class MastodonRequestLimiter:
    """Serialize every Mastodon request in a process at the fixed 2s spacing."""

    __slots__ = ("_clock", "_last_started", "_lock", "_sleeper")

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._clock = clock or time.monotonic
        self._sleeper = sleeper or time.sleep
        self._lock = RLock()
        self._last_started: float | None = None

    def wait(self) -> None:
        """Wait before a request starts; callers cannot lower this interval."""

        with self._lock:
            now = self._clock()
            if self._last_started is not None:
                next_start = self._last_started + MASTODON_MIN_REQUEST_INTERVAL_SECONDS
                delay = next_start - now
                if delay > 0:
                    self._sleeper(delay)
                    # A test clock or interrupted sleeper may not advance. Keep
                    # the reservation monotonic so the next call remains safe.
                    now = max(self._clock(), next_start)
            self._last_started = now


_DEFAULT_MASTODON_REQUEST_LIMITER = MastodonRequestLimiter()


@dataclass(frozen=True, slots=True)
class MastodonStatus:
    """The only status data allowed past the Mastodon parser boundary."""

    status_id: str
    status_key_sha256: str
    published_at: datetime
    matched_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MastodonRateLimit:
    limit: int | None
    remaining: int | None
    reset_at: datetime | None


@dataclass(frozen=True, slots=True)
class MastodonPublicHashtagResult:
    instance_key: str
    tag_key: str
    start_status_id: str | None
    end_status_id: str | None
    incomplete: bool
    requests_made: int
    statuses_seen: int
    bytes_seen: int
    candidates: tuple[MastodonStatus, ...]
    rate_limit: MastodonRateLimit

    @property
    def rate_limit_limit(self) -> int | None:
        return self.rate_limit.limit

    @property
    def rate_limit_remaining(self) -> int | None:
        return self.rate_limit.remaining

    @property
    def rate_limit_reset_at(self) -> datetime | None:
        return self.rate_limit.reset_at


class MastodonTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> APIResponse: ...


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(raw: bytes, *, code: str) -> object:
    if not 1 <= len(raw) <= MASTODON_MAX_RESPONSE_BYTES:
        raise MastodonInvalidResponse("mastodon_response_too_large")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise MastodonInvalidResponse(code) from None


def _status_id(value: object, *, code: str = "mastodon_status_id_invalid") -> str:
    """Validate an opaque status id without numeric conversion or ordering."""

    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= MASTODON_MAX_STATUS_ID_LENGTH
        or value != value.strip()
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        raise MastodonInvalidResponse(code)
    return value


def _timestamp(value: object, *, now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise MastodonInvalidResponse("mastodon_clock_invalid")
    if not isinstance(value, str) or not 1 <= len(value) <= 80:
        raise MastodonInvalidResponse("mastodon_created_at_invalid")
    if _CONTROL_CHARACTER_PATTERN.search(value) is not None:
        raise MastodonInvalidResponse("mastodon_created_at_invalid")
    if _ISO_TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise MastodonInvalidResponse("mastodon_created_at_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise MastodonInvalidResponse("mastodon_created_at_invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MastodonInvalidResponse("mastodon_created_at_invalid")
    try:
        normalized = parsed.astimezone(UTC)
    except (OverflowError, ValueError):
        raise MastodonInvalidResponse("mastodon_created_at_invalid") from None
    if not MASTODON_MIN_PUBLISHED_AT <= normalized <= now.astimezone(UTC) + timedelta(days=1):
        raise MastodonInvalidResponse("mastodon_created_at_out_of_range")
    return normalized


def _hash_status(instance_key: str, status_id: str) -> str:
    return hashlib.sha256(f"{instance_key}\n{status_id}".encode()).hexdigest()


def parse_mastodon_status(
    raw_status: object,
    *,
    instance_key: str = MASTODON_INSTANCE_KEY,
    registry: MastodonRegistry | None = None,
    now: datetime | None = None,
) -> MastodonStatus:
    """Parse only the bounded public activity fields.

    Deliberately do not read ``content``, ``account``, ``media_attachments``,
    ``url``, ``uri``, ``reblog`` contents, or any other unapproved field.  The
    presence of those upstream fields therefore cannot cause retention.
    """

    if not isinstance(raw_status, Mapping):
        raise MastodonInvalidResponse("mastodon_status_invalid")
    if instance_key != MASTODON_INSTANCE_KEY:
        raise MastodonInvalidResponse("mastodon_instance_key_invalid")
    active_registry = registry or MastodonRegistry.reviewed()
    if now is None:
        now = datetime.now(UTC)
    if raw_status.get("visibility") != "public":
        raise MastodonInvalidResponse("mastodon_visibility_not_public")
    if "reblog" not in raw_status or raw_status.get("reblog") is not None:
        raise MastodonInvalidResponse("mastodon_reblog_not_null")
    status_id = _status_id(raw_status.get("id"))
    published_at = _timestamp(raw_status.get("created_at"), now=now)
    raw_tags = raw_status.get("tags")
    if not isinstance(raw_tags, list) or len(raw_tags) > MASTODON_MAX_TAGS_PER_STATUS:
        raise MastodonInvalidResponse("mastodon_tags_invalid")
    matched_tags = active_registry.matched_tag_keys(raw_tags)
    return MastodonStatus(
        status_id=status_id,
        status_key_sha256=_hash_status(instance_key, status_id),
        published_at=published_at,
        matched_tags=matched_tags,
    )


def _header(headers: Mapping[str, str], name: str) -> str | None:
    expected = name.casefold()
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise MastodonInvalidResponse("mastodon_header_invalid")
        if key.casefold() == expected:
            return value
    return None


def _rate_limit_integer(value: str | None, *, field: str) -> int | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 7
        or not value.isascii()
        or not value.isdecimal()
    ):
        raise MastodonInvalidResponse(f"mastodon_{field}_invalid")
    try:
        parsed = int(value)
    except ValueError:
        raise MastodonInvalidResponse(f"mastodon_{field}_invalid") from None
    if not 0 <= parsed <= MASTODON_MAX_RATE_LIMIT:
        raise MastodonInvalidResponse(f"mastodon_{field}_invalid")
    return parsed


def _rate_limit_reset(value: str | None, *, now: datetime) -> datetime | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 80
        or _CONTROL_CHARACTER_PATTERN.search(value) is not None
    ):
        raise MastodonInvalidResponse("mastodon_rate_limit_reset_invalid")
    parsed: datetime
    if value.isascii() and value.isdecimal():
        if len(value) > 10:
            raise MastodonInvalidResponse("mastodon_rate_limit_reset_invalid")
        try:
            seconds = int(value)
        except ValueError:
            raise MastodonInvalidResponse("mastodon_rate_limit_reset_invalid") from None
        if not 0 <= seconds <= 4_102_444_800:  # 2100-01-01 UTC
            raise MastodonInvalidResponse("mastodon_rate_limit_reset_invalid")
        try:
            parsed = datetime.fromtimestamp(seconds, UTC)
        except (OverflowError, OSError, ValueError):
            raise MastodonInvalidResponse("mastodon_rate_limit_reset_invalid") from None
    else:
        if _ISO_TIMESTAMP_PATTERN.fullmatch(value) is None:
            raise MastodonInvalidResponse("mastodon_rate_limit_reset_invalid")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise MastodonInvalidResponse("mastodon_rate_limit_reset_invalid") from None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise MastodonInvalidResponse("mastodon_rate_limit_reset_invalid")
        parsed = parsed.astimezone(UTC)
    now_utc = now.astimezone(UTC)
    if parsed < MASTODON_MIN_PUBLISHED_AT or parsed > now_utc + timedelta(
        seconds=MASTODON_MAX_RATE_RESET_SECONDS
    ):
        raise MastodonInvalidResponse("mastodon_rate_limit_reset_out_of_range")
    return parsed


def parse_rate_limit_headers(headers: Mapping[str, str], *, now: datetime) -> MastodonRateLimit:
    if now.tzinfo is None or now.utcoffset() is None:
        raise MastodonInvalidResponse("mastodon_clock_invalid")
    limit = _rate_limit_integer(_header(headers, "x-ratelimit-limit"), field="rate_limit_limit")
    remaining = _rate_limit_integer(
        _header(headers, "x-ratelimit-remaining"), field="rate_limit_remaining"
    )
    if limit is not None and remaining is not None and remaining > limit:
        raise MastodonInvalidResponse("mastodon_rate_limit_remaining_invalid")
    reset_at = _rate_limit_reset(_header(headers, "x-ratelimit-reset"), now=now)
    if remaining == 0:
        if reset_at is None:
            raise MastodonInvalidResponse("mastodon_rate_limit_reset_missing")
        if reset_at <= now.astimezone(UTC):
            raise MastodonInvalidResponse("mastodon_rate_limit_reset_expired")
    return MastodonRateLimit(limit=limit, remaining=remaining, reset_at=reset_at)


def _retry_after(value: str | None, *, now: datetime) -> datetime | None:
    """Parse a bounded Retry-After value without silently weakening a 429."""

    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 80
        or _CONTROL_CHARACTER_PATTERN.search(value) is not None
    ):
        raise MastodonInvalidResponse("mastodon_retry_after_invalid")
    now_utc = now.astimezone(UTC)
    if value.isascii() and value.isdecimal():
        if len(value) > 7:
            raise MastodonInvalidResponse("mastodon_retry_after_invalid")
        try:
            seconds = int(value)
        except ValueError:
            raise MastodonInvalidResponse("mastodon_retry_after_invalid") from None
        if seconds > MASTODON_MAX_RATE_RESET_SECONDS:
            raise MastodonInvalidResponse("mastodon_retry_after_out_of_range")
        retry_at = now_utc + timedelta(seconds=seconds)
    else:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            raise MastodonInvalidResponse("mastodon_retry_after_invalid") from None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise MastodonInvalidResponse("mastodon_retry_after_invalid")
        try:
            retry_at = parsed.astimezone(UTC)
        except (OverflowError, ValueError):
            raise MastodonInvalidResponse("mastodon_retry_after_invalid") from None
    if retry_at > now_utc + timedelta(seconds=MASTODON_MAX_RATE_RESET_SECONDS):
        raise MastodonInvalidResponse("mastodon_retry_after_out_of_range")
    return retry_at


def _validate_instance_payload(payload: object, *, instance: MastodonInstance) -> None:
    if not isinstance(payload, Mapping) or payload.get("domain") != instance.domain:
        raise MastodonPreflightError("mastodon_instance_domain_mismatch")
    configuration = payload.get("configuration")
    if not isinstance(configuration, Mapping):
        raise MastodonPreflightError("mastodon_instance_configuration_missing")
    timelines = configuration.get("timelines_access")
    if not isinstance(timelines, Mapping):
        raise MastodonPreflightError("mastodon_instance_timelines_access_missing")
    hashtag_feeds = timelines.get("hashtag_feeds")
    if not isinstance(hashtag_feeds, Mapping):
        raise MastodonPreflightError("mastodon_instance_hashtag_access_missing")
    if hashtag_feeds.get("local") != "public" or hashtag_feeds.get("remote") != "public":
        raise MastodonPreflightError("mastodon_instance_hashtag_access_not_public")


def _same_origin(parsed: Any, instance: MastodonInstance) -> bool:
    try:
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == instance.domain
        and parsed.username is None
        and parsed.password is None
        and port in {None, 443}
    )


def _hashtag_url(instance: MastodonInstance, tag_value: str, *, min_id: str | None) -> str:
    if tag_value not in MASTODON_APPROVED_TAGS:
        raise ValueError("Mastodon hashtag value is not approved")
    if min_id is not None:
        _status_id(min_id, code="mastodon_min_id_invalid")
    base = urlsplit(instance.hashtag_base_url)
    path = f"{base.path.rstrip('/')}/{quote(tag_value, safe='')}"
    query: list[tuple[str, str]] = [("limit", str(MASTODON_MAX_STATUSES_PER_PAGE))]
    if min_id is not None:
        query.append(("min_id", min_id))
    return urlunsplit((base.scheme, base.netloc, path, urlencode(query), ""))


def _parse_link_segments(value: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if (
        not isinstance(value, str)
        or not 1 <= len(value.encode("utf-8")) <= MASTODON_MAX_LINK_HEADER_BYTES
    ):
        raise MastodonInvalidResponse("mastodon_link_header_invalid")
    segments: list[tuple[str, tuple[str, ...]]] = []
    # URLs in this fixed endpoint cannot contain commas; split only complete
    # angle-bracket references and retain no header text beyond this call.
    for segment in value.split(","):
        candidate = segment.strip()
        if not candidate.startswith("<") or ">" not in candidate:
            raise MastodonInvalidResponse("mastodon_link_header_invalid")
        closing = candidate.find(">")
        uri = candidate[1:closing]
        attrs = candidate[closing + 1 :]
        match = _REL_PATTERN.search(attrs)
        if match is None:
            continue
        raw_relations = match.group(1) or match.group(2) or ""
        relations = tuple(item.casefold() for item in raw_relations.split() if item)
        segments.append((uri, relations))
    return tuple(segments)


def _forward_link(
    headers: Mapping[str, str],
    *,
    instance: MastodonInstance,
    tag_value: str,
) -> tuple[str, str] | None:
    raw = _header(headers, "link")
    if raw is None:
        return None
    expected_path = urlsplit(_hashtag_url(instance, tag_value, min_id=None)).path
    links = _parse_link_segments(raw)
    candidates: list[tuple[int, str, str]] = []
    for uri, relations in links:
        parsed = urlsplit(uri)
        if not _same_origin(parsed, instance):
            raise MastodonInvalidResponse("mastodon_link_origin_invalid")
        if parsed.fragment or parsed.path != expected_path:
            raise MastodonInvalidResponse("mastodon_link_path_invalid")
        query = parse_qsl(parsed.query, keep_blank_values=True)
        keys = [key for key, _value in query]
        if len(keys) != len(set(keys)) or any(
            key not in {"min_id", "max_id", "limit"} for key in keys
        ):
            raise MastodonInvalidResponse("mastodon_link_query_invalid")
        limit = next((value for key, value in query if key == "limit"), None)
        if limit != str(MASTODON_MAX_STATUSES_PER_PAGE):
            raise MastodonInvalidResponse("mastodon_link_limit_invalid")
        has_min_id = "min_id" in keys
        has_max_id = "max_id" in keys
        if has_min_id and has_max_id:
            raise MastodonInvalidResponse("mastodon_link_query_invalid")
        if has_max_id:
            # Mastodon normally emits this older-page link as ``rel=next``.
            # Validate it as an official bounded boundary, but never follow
            # it: forward discovery uses only min_id semantics.
            if "next" not in relations or "prev" in relations:
                raise MastodonInvalidResponse("mastodon_link_relation_invalid")
            max_id = next(value for key, value in query if key == "max_id")
            _status_id(max_id, code="mastodon_link_max_id_invalid")
            continue
        if not has_min_id:
            continue
        min_id = next(value for key, value in query if key == "min_id")
        _status_id(min_id, code="mastodon_link_min_id_invalid")
        # Mastodon's documented forward relation is prev; accept next only as
        # a compatibility form when it still carries min_id and remains fixed.
        relation_rank = 0 if "prev" in relations else 1 if "next" in relations else 2
        if relation_rank < 2:
            candidates.append((relation_rank, uri, min_id))
    if not candidates:
        return None
    unique_candidates = {(uri, min_id) for _rank, uri, min_id in candidates}
    if len(unique_candidates) > 1:
        raise MastodonInvalidResponse("mastodon_link_progress_ambiguous")
    _rank, uri, min_id = min(candidates)
    return uri, min_id


class HTTPXMastodonTransport:
    """Fixed-origin HTTPX transport with identity encoding and no redirects."""

    def __init__(self, *, max_response_bytes: int = MASTODON_MAX_RESPONSE_BYTES) -> None:
        if not 1 <= max_response_bytes <= MASTODON_MAX_RESPONSE_BYTES:
            raise ValueError("Mastodon response cap is outside the approved bound")
        self.max_response_bytes = max_response_bytes

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> APIResponse:
        _validate_transport_url(url)
        if (
            connect_timeout_seconds != MASTODON_CONNECT_TIMEOUT_SECONDS
            or read_timeout_seconds != MASTODON_READ_TIMEOUT_SECONDS
        ):
            raise ValueError("Mastodon transport requires the fixed connect/read timeouts")
        return asyncio.run(self._get(url, headers=headers))

    async def _get(self, url: str, *, headers: Mapping[str, str]) -> APIResponse:
        allowed_headers = {"accept", "accept-encoding", "user-agent"}
        normalized_headers: dict[str, str] = {}
        for name, value in headers.items():
            if not isinstance(name, str) or not isinstance(value, str):
                raise ValueError("Mastodon transport headers must be text")
            normalized_name = name.casefold()
            if normalized_name not in allowed_headers:
                raise ValueError(
                    "Mastodon transport does not accept authentication or proxy headers"
                )
            if normalized_name in normalized_headers:
                raise ValueError("Mastodon transport received duplicate headers")
            normalized_headers[normalized_name] = value
        configured_user_agent = normalized_headers.get("user-agent")
        if configured_user_agent is not None and configured_user_agent != MASTODON_USER_AGENT:
            raise ValueError("Mastodon transport requires the fixed User-Agent")
        wire_headers = {
            "Accept": normalized_headers.get("accept", "application/json"),
            "Accept-Encoding": "identity",
            "User-Agent": MASTODON_USER_AGENT,
        }
        accept = normalized_headers.get("accept")
        if accept is not None and accept.casefold().strip() != "application/json":
            raise ValueError("Mastodon transport requires an application/json response")
        configured_encoding = normalized_headers.get("accept-encoding")
        if configured_encoding is not None and configured_encoding.casefold().strip() != "identity":
            raise ValueError("Mastodon transport requires identity response encoding")
        timeout = httpx.Timeout(
            timeout=MASTODON_READ_TIMEOUT_SECONDS,
            connect=MASTODON_CONNECT_TIMEOUT_SECONDS,
            read=MASTODON_READ_TIMEOUT_SECONDS,
        )
        try:
            async with asyncio.timeout(
                MASTODON_CONNECT_TIMEOUT_SECONDS + MASTODON_READ_TIMEOUT_SECONDS
            ):
                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    async with client.stream("GET", url, headers=wire_headers) as response:
                        content_type = response.headers.get("content-type", "")
                        if (
                            response.status_code == 200
                            and content_type.split(";", 1)[0].strip().casefold()
                            != "application/json"
                        ):
                            raise MastodonInvalidResponse("mastodon_content_type_invalid")
                        content_encoding = response.headers.get("content-encoding", "")
                        if content_encoding.casefold().strip() not in {"", "identity"}:
                            raise MastodonInvalidResponse("mastodon_content_encoding_invalid")
                        declared_length = response.headers.get("content-length")
                        if declared_length is not None:
                            if not declared_length.isascii() or not declared_length.isdecimal():
                                raise MastodonInvalidResponse("mastodon_content_length_invalid")
                            try:
                                declared_length_value = int(declared_length)
                            except ValueError:
                                raise MastodonInvalidResponse(
                                    "mastodon_content_length_invalid"
                                ) from None
                            if declared_length_value > self.max_response_bytes:
                                raise MastodonInvalidResponse("mastodon_response_too_large")
                        body = bytearray()
                        async for chunk in response.aiter_raw(chunk_size=64 * 1024):
                            if len(body) + len(chunk) > self.max_response_bytes:
                                raise MastodonInvalidResponse("mastodon_response_too_large")
                            body.extend(chunk)
                        return APIResponse(
                            response.status_code, dict(response.headers), bytes(body)
                        )
        except MastodonError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise MastodonTransportError("mastodon_request_timeout") from None
        except httpx.HTTPError:
            raise MastodonTransportError() from None


def _validate_transport_url(url: str) -> None:
    parsed = urlsplit(url)
    instance_path = urlsplit(MASTODON_INSTANCE_URL).path
    hashtag_prefix = urlsplit(MASTODON_HASHTAG_BASE_URL).path
    allowed_hashtag_paths = {
        f"{hashtag_prefix}{quote(value, safe='')}" for value in MASTODON_APPROVED_TAGS
    }
    if not _same_origin(parsed, MastodonInstance()) or parsed.fragment:
        raise ValueError("Mastodon transport accepts only fixed same-origin endpoints")
    if parsed.path == instance_path:
        if parsed.query:
            raise ValueError("Mastodon instance URL must not contain a query")
        return
    if parsed.path not in allowed_hashtag_paths:
        raise ValueError("Mastodon transport accepts only fixed same-origin endpoints")
    query = parse_qsl(parsed.query, keep_blank_values=True)
    keys = [key for key, _value in query]
    if len(keys) != len(set(keys)) or any(key not in {"limit", "min_id"} for key in keys):
        raise ValueError("Mastodon hashtag URL query is not approved")
    limit = next((value for key, value in query if key == "limit"), None)
    if limit != str(MASTODON_MAX_STATUSES_PER_PAGE):
        raise ValueError("Mastodon hashtag URL requires the fixed limit")
    min_id = next((value for key, value in query if key == "min_id"), None)
    if min_id is not None:
        _status_id(min_id, code="mastodon_min_id_invalid")


class MastodonPublicHashtagCollector:
    """Collect two bounded forward pages after a strict instance preflight."""

    def __init__(
        self,
        *,
        transport: MastodonTransport,
        registry: MastodonRegistry,
        limiter: MastodonRequestLimiter | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.transport = transport
        self.registry = registry
        self.limiter = limiter or _DEFAULT_MASTODON_REQUEST_LIMITER
        self.clock = clock or (lambda: datetime.now(UTC))

    def collect(
        self,
        *,
        instance_key: str,
        tag_key: str,
        start_status_id: str | None,
        now: datetime | None = None,
    ) -> MastodonPublicHashtagResult:
        instance = self.registry.require_instance(instance_key)
        tag = self.registry.require_tag(tag_key)
        if start_status_id is not None:
            start_status_id = _status_id(start_status_id, code="mastodon_start_status_id_invalid")
        if now is None:
            now = datetime.now(UTC)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Mastodon collection clock must be timezone-aware")

        preflight = self._request(instance.instance_url)
        preflight_received_at = self._response_time()
        if preflight.status_code == 429:
            raise MastodonRateLimited(_safe_retry_at(preflight.headers, now=preflight_received_at))
        if preflight.status_code != 200:
            raise MastodonHTTPError(preflight.status_code)
        _validate_instance_payload(
            _json(preflight.body, code="mastodon_instance_json_invalid"), instance=instance
        )

        current_url = _hashtag_url(instance, tag.value, min_id=start_status_id)
        current_min_id = start_status_id
        seen_urls: set[str] = set()
        candidates: dict[str, MastodonStatus] = {}
        requests_made = 0
        statuses_seen = 0
        bytes_seen = 0
        end_status_id: str | None = start_status_id
        incomplete = False
        rate_limit = parse_rate_limit_headers(preflight.headers, now=preflight_received_at)

        if rate_limit.remaining == 0:
            return MastodonPublicHashtagResult(
                instance_key=instance_key,
                tag_key=tag_key,
                start_status_id=start_status_id,
                end_status_id=end_status_id,
                incomplete=True,
                requests_made=0,
                statuses_seen=0,
                bytes_seen=0,
                candidates=(),
                rate_limit=rate_limit,
            )

        while requests_made < MASTODON_MAX_PAGES:
            if current_url in seen_urls:
                incomplete = True
                break
            seen_urls.add(current_url)
            response = self._request(current_url)
            response_received_at = self._response_time()
            requests_made += 1
            if response.status_code == 429:
                raise MastodonRateLimited(
                    _safe_retry_at(response.headers, now=response_received_at)
                )
            rate_limit = parse_rate_limit_headers(
                response.headers,
                now=response_received_at,
            )
            if response.status_code != 200:
                raise MastodonHTTPError(response.status_code)
            if len(response.body) > MASTODON_MAX_RESPONSE_BYTES - bytes_seen:
                raise MastodonInvalidResponse("mastodon_run_response_too_large")
            bytes_seen += len(response.body)
            decoded = _json(response.body, code="mastodon_timeline_json_invalid")
            if not isinstance(decoded, list) or len(decoded) > MASTODON_MAX_STATUSES_PER_PAGE:
                raise MastodonInvalidResponse("mastodon_page_status_limit_exceeded")
            if statuses_seen + len(decoded) > MASTODON_MAX_STATUSES:
                raise MastodonInvalidResponse("mastodon_status_limit_exceeded")
            statuses_seen += len(decoded)
            invalid_status = False
            page_status_ids: list[str | None] = []
            for raw_status in decoded:
                if isinstance(raw_status, Mapping):
                    try:
                        page_status_ids.append(_status_id(raw_status.get("id")))
                    except MastodonInvalidResponse:
                        page_status_ids.append(None)
                        invalid_status = True
                else:
                    page_status_ids.append(None)
                    invalid_status = True
                try:
                    status = parse_mastodon_status(
                        raw_status,
                        instance_key=instance_key,
                        registry=self.registry,
                        now=response_received_at,
                    )
                except MastodonInvalidResponse:
                    invalid_status = True
                    continue
                if tag_key not in status.matched_tags:
                    continue
                existing = candidates.get(status.status_key_sha256)
                if existing is not None and existing != status:
                    raise MastodonInvalidResponse("mastodon_status_identity_conflict")
                candidates[status.status_key_sha256] = status
            page_end_status_id = page_status_ids[-1] if page_status_ids else None
            page_ids_complete = bool(page_status_ids) and all(
                value is not None for value in page_status_ids
            )
            if page_end_status_id is not None and page_ids_complete:
                end_status_id = page_end_status_id
            if invalid_status:
                incomplete = True

            if not decoded:
                break
            forward = _forward_link(
                response.headers,
                instance=instance,
                tag_value=tag.value,
            )
            if forward is None:
                if page_end_status_id is None or not page_ids_complete:
                    break
                next_url = _hashtag_url(instance, tag.value, min_id=page_end_status_id)
                next_min_id = page_end_status_id
            else:
                next_url, next_min_id = forward
            if next_min_id == current_min_id:
                incomplete = True
                break
            if rate_limit.remaining == 0:
                incomplete = True
                break
            if requests_made >= MASTODON_MAX_PAGES:
                incomplete = True
                break
            current_url = next_url
            current_min_id = next_min_id

        return MastodonPublicHashtagResult(
            instance_key=instance_key,
            tag_key=tag_key,
            start_status_id=start_status_id,
            end_status_id=end_status_id,
            incomplete=incomplete,
            requests_made=requests_made,
            statuses_seen=statuses_seen,
            bytes_seen=bytes_seen,
            candidates=tuple(candidates.values()),
            rate_limit=rate_limit,
        )

    def _response_time(self) -> datetime:
        received_at = self.clock()
        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise ValueError("Mastodon response clock must be timezone-aware")
        return received_at.astimezone(UTC)

    def _request(self, url: str) -> APIResponse:
        self.limiter.wait()
        return self.transport.get(
            url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": MASTODON_USER_AGENT,
            },
            connect_timeout_seconds=MASTODON_CONNECT_TIMEOUT_SECONDS,
            read_timeout_seconds=MASTODON_READ_TIMEOUT_SECONDS,
        )


def _safe_retry_at(headers: Mapping[str, str], *, now: datetime) -> datetime:
    """Return the strongest server retry boundary or fail closed."""

    retry_after = _retry_after(_header(headers, "retry-after"), now=now)
    rate = parse_rate_limit_headers(headers, now=now)
    now_utc = now.astimezone(UTC)
    candidates = [
        value for value in (retry_after, rate.reset_at) if value is not None and value > now_utc
    ]
    if not candidates:
        raise MastodonInvalidResponse("mastodon_retry_after_missing")
    return max(candidates)


# Short aliases mirror the source-specific collector naming used elsewhere.
MastodonCollector = MastodonPublicHashtagCollector
WebsocketsMastodonTransport = HTTPXMastodonTransport
MastodonAPIResponse = APIResponse

__all__ = [
    "MASTODON_COLLECTOR_VERSION",
    "MASTODON_COMPLETION_VERSION",
    "MASTODON_CONNECT_TIMEOUT_SECONDS",
    "MASTODON_MAX_PAGES",
    "MASTODON_MAX_RATE_LIMIT",
    "MASTODON_MAX_RESPONSE_BYTES",
    "MASTODON_MAX_STATUSES",
    "MASTODON_MAX_STATUSES_PER_PAGE",
    "MASTODON_MIN_REQUEST_INTERVAL_SECONDS",
    "MASTODON_READ_TIMEOUT_SECONDS",
    "MASTODON_SOURCE_GATE_SECONDS",
    "MASTODON_USER_AGENT",
    "MastodonAPIResponse",
    "MastodonCollector",
    "MastodonError",
    "MastodonHTTPError",
    "MastodonInvalidResponse",
    "MastodonPreflightError",
    "MastodonPublicHashtagCollector",
    "MastodonPublicHashtagResult",
    "MastodonRequestLimiter",
    "MastodonRateLimit",
    "MastodonRateLimited",
    "MastodonStatus",
    "MastodonTransport",
    "MastodonTransportError",
    "HTTPXMastodonTransport",
    "WebsocketsMastodonTransport",
    "parse_mastodon_status",
    "parse_rate_limit_headers",
]
