"""Bounded, conditional TCGdex English set-metadata synchronization."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

import httpx

from pokecrack_worker.config.source_policy import CollectorRoute, SourcePolicyRegistry

TCGDEX_SETS_URL = "https://api.tcgdex.net/v2/en/sets"
TCGDEX_TIMEOUT_SECONDS = 30.0
TCGDEX_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
TCGDEX_MAX_SETS = 1_000
TCGDEX_RAW_CHUNK_BYTES = 64 * 1024
TCGDEX_ETAG_PATTERN = re.compile(r'(?:W/)?"[\x21\x23-\x7e]*"')


class TCGdexError(RuntimeError):
    """Base error for the fixed, metadata-only TCGdex boundary."""


class TCGdexHTTPError(TCGdexError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"TCGdex HTTP status {status_code}")


class TCGdexResponseTooLarge(TCGdexError):
    """The response exceeded the fixed two-MiB production ceiling."""


class TCGdexTimeoutError(TCGdexError):
    """A transient connect/read or absolute-deadline timeout."""


class TCGdexNetworkError(TCGdexError):
    """A transient non-timeout transport failure."""


@dataclass(frozen=True, slots=True)
class APIResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class TCGdexTransport(Protocol):
    def get(self, url: str, *, headers: dict[str, str], timeout_seconds: float) -> APIResponse: ...


class HTTPXTCGdexTransport:
    """Fetch the one approved endpoint under an absolute, raw-byte deadline."""

    def __init__(
        self,
        *,
        max_response_bytes: int = TCGDEX_MAX_RESPONSE_BYTES,
        total_timeout_seconds: float = TCGDEX_TIMEOUT_SECONDS,
    ) -> None:
        if not 1 <= max_response_bytes <= TCGDEX_MAX_RESPONSE_BYTES:
            raise ValueError(
                f"max_response_bytes must be between 1 and {TCGDEX_MAX_RESPONSE_BYTES}"
            )
        if not 0 < total_timeout_seconds <= TCGDEX_TIMEOUT_SECONDS:
            raise ValueError(
                f"total_timeout_seconds must be greater than zero and at most "
                f"{TCGDEX_TIMEOUT_SECONDS}"
            )
        self.max_response_bytes = max_response_bytes
        self.total_timeout_seconds = total_timeout_seconds

    def get(self, url: str, *, headers: dict[str, str], timeout_seconds: float) -> APIResponse:
        if url != TCGDEX_SETS_URL:
            raise ValueError("TCGdex transport accepts only the fixed English sets endpoint")
        if timeout_seconds != TCGDEX_TIMEOUT_SECONDS:
            raise ValueError("TCGdex transport requires the fixed 30-second timeout")
        return asyncio.run(self._get(url, headers=headers))

    async def _get(self, url: str, *, headers: dict[str, str]) -> APIResponse:
        wire_headers = dict(headers)
        configured_encoding = next(
            (value for name, value in wire_headers.items() if name.casefold() == "accept-encoding"),
            None,
        )
        if configured_encoding is not None and configured_encoding.casefold().strip() != "identity":
            raise ValueError("TCGdex transport requires identity response encoding")
        wire_headers["Accept-Encoding"] = "identity"
        try:
            async with asyncio.timeout(self.total_timeout_seconds):
                async with httpx.AsyncClient(
                    timeout=self.total_timeout_seconds,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    async with client.stream("GET", url, headers=wire_headers) as response:
                        if response.status_code not in {200, 304}:
                            raise TCGdexHTTPError(response.status_code)
                        content_encoding = response.headers.get("content-encoding", "")
                        if content_encoding.casefold().strip() not in {"", "identity"}:
                            raise TCGdexError("TCGdex response encoding is not allowed")
                        declared_length = response.headers.get("content-length")
                        if declared_length is not None:
                            try:
                                parsed_length = int(declared_length)
                            except ValueError as error:
                                raise TCGdexError("TCGdex content length is invalid") from error
                            if parsed_length < 0:
                                raise TCGdexError("TCGdex content length is invalid")
                            if parsed_length > self.max_response_bytes:
                                raise TCGdexResponseTooLarge("TCGdex response exceeds the byte cap")
                        body = bytearray()
                        async for chunk in response.aiter_raw(chunk_size=TCGDEX_RAW_CHUNK_BYTES):
                            if len(chunk) > self.max_response_bytes - len(body):
                                raise TCGdexResponseTooLarge("TCGdex response exceeds the byte cap")
                            body.extend(chunk)
                        return APIResponse(
                            response.status_code,
                            dict(response.headers),
                            bytes(body),
                        )
        except TCGdexError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise TCGdexTimeoutError("TCGdex request exceeded its deadline") from None
        except httpx.HTTPError:
            raise TCGdexNetworkError("TCGdex request failed") from None


@dataclass(frozen=True, slots=True)
class TCGdexSetBrief:
    set_id: str
    name: str
    card_count_total: int
    card_count_official: int


@dataclass(frozen=True, slots=True)
class TCGdexSetsSnapshot:
    sets: tuple[TCGdexSetBrief, ...]
    etag: str | None
    content_sha256: str
    synced_at: datetime


class TCGdexSetsCache(Protocol):
    def get(self) -> TCGdexSetsSnapshot | None: ...

    def put(self, snapshot: TCGdexSetsSnapshot) -> None: ...


class InMemoryTCGdexSetsCache:
    """Fixture cache; live persistence belongs outside the HTTP/parser layer."""

    def __init__(self) -> None:
        self._snapshot: TCGdexSetsSnapshot | None = None

    def get(self) -> TCGdexSetsSnapshot | None:
        return self._snapshot

    def put(self, snapshot: TCGdexSetsSnapshot) -> None:
        self._snapshot = snapshot


class TCGdexSetsSyncOutcome(StrEnum):
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    NOT_MODIFIED = "not_modified"


@dataclass(frozen=True, slots=True)
class TCGdexSetsSyncResult:
    outcome: TCGdexSetsSyncOutcome
    snapshot: TCGdexSetsSnapshot
    status_code: int
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class TCGdexSetsSyncAttempt:
    """Classified result for a future scheduler/queue boundary."""

    result: TCGdexSetsSyncResult | None
    error_code: str | None = None
    retryable: bool = False


def _header(headers: Mapping[str, str], name: str) -> str | None:
    expected = name.casefold()
    return next((value for key, value in headers.items() if key.casefold() == expected), None)


def _bounded_etag(headers: Mapping[str, str]) -> str | None:
    value = _header(headers, "etag")
    if value is None:
        return None
    if len(value) > 512 or TCGDEX_ETAG_PATTERN.fullmatch(value) is None:
        raise TCGdexError("TCGdex ETag must be a bounded HTTP field value")
    return value


def _bounded_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise TCGdexError(f"TCGdex {field} must be a string")
    if not value or value != value.strip() or len(value) > 160:
        raise TCGdexError(f"TCGdex {field} must contain 1 to 160 characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise TCGdexError(f"TCGdex {field} must not contain control characters")
    return value


def _nonnegative_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000:
        raise TCGdexError(f"TCGdex {field} must be a nonnegative integer no greater than 1000000")
    return value


def parse_tcgdex_sets(payload: object) -> tuple[TCGdexSetBrief, ...]:
    """Parse the official top-level SetBrief array and no other response shape."""

    if not isinstance(payload, list) or not 1 <= len(payload) <= TCGDEX_MAX_SETS:
        raise TCGdexError(f"TCGdex sets response must contain 1 to {TCGDEX_MAX_SETS} items")
    sets: list[TCGdexSetBrief] = []
    identities: set[str] = set()
    for raw_set in payload:
        if not isinstance(raw_set, Mapping):
            raise TCGdexError("TCGdex set must be an object")
        set_id = _bounded_text(raw_set.get("id"), "set id")
        if set_id in identities:
            raise TCGdexError("TCGdex set ids must be unique")
        identities.add(set_id)
        name = _bounded_text(raw_set.get("name"), "set name")
        raw_count = raw_set.get("cardCount")
        if not isinstance(raw_count, Mapping):
            raise TCGdexError("TCGdex cardCount must be an object")
        total = _nonnegative_integer(raw_count.get("total"), "cardCount.total")
        official = _nonnegative_integer(raw_count.get("official"), "cardCount.official")
        if official > total:
            raise TCGdexError("TCGdex cardCount.official must not exceed cardCount.total")
        sets.append(
            TCGdexSetBrief(
                set_id=set_id,
                name=name,
                card_count_total=total,
                card_count_official=official,
            )
        )
    return tuple(sets)


class TCGdexSetsClient:
    """Synchronize only public English set metadata from one fixed URL."""

    def __init__(
        self,
        *,
        transport: TCGdexTransport,
        cache: TCGdexSetsCache,
        policies: SourcePolicyRegistry,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.transport = transport
        self.cache = cache
        self.policies = policies
        self._clock = clock or (lambda: datetime.now(UTC))

    def sync(self) -> TCGdexSetsSyncResult:
        self.policies.require(TCGDEX_SETS_URL, CollectorRoute.CATALOG)
        previous = self.cache.get()
        headers = {"Accept": "application/json"}
        if previous and previous.etag:
            headers["If-None-Match"] = previous.etag
        response = self.transport.get(
            TCGDEX_SETS_URL,
            headers=headers,
            timeout_seconds=TCGDEX_TIMEOUT_SECONDS,
        )
        checked_at = self._clock()
        if response.status_code == 304:
            if previous is None or "If-None-Match" not in headers:
                raise TCGdexError("TCGdex returned 304 without a sent cache validator")
            return TCGdexSetsSyncResult(
                outcome=TCGdexSetsSyncOutcome.NOT_MODIFIED,
                snapshot=previous,
                status_code=304,
                checked_at=checked_at,
            )
        if response.status_code != 200:
            # Fixture transports must obey the same boundary as the real transport.
            raise TCGdexHTTPError(response.status_code)
        try:
            payload: Any = json.loads(response.body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise TCGdexError("TCGdex returned invalid JSON") from error
        sets = parse_tcgdex_sets(payload)
        digest = hashlib.sha256(response.body).hexdigest()
        etag = _bounded_etag(response.headers)
        outcome = (
            TCGdexSetsSyncOutcome.UNCHANGED
            if previous is not None and previous.content_sha256 == digest
            else TCGdexSetsSyncOutcome.CHANGED
        )
        snapshot = TCGdexSetsSnapshot(
            sets=sets,
            etag=etag,
            content_sha256=digest,
            synced_at=checked_at,
        )
        self.cache.put(snapshot)
        return TCGdexSetsSyncResult(
            outcome=outcome,
            snapshot=snapshot,
            status_code=200,
            checked_at=checked_at,
        )

    def sync_safe(self) -> TCGdexSetsSyncAttempt:
        try:
            return TCGdexSetsSyncAttempt(result=self.sync())
        except TCGdexHTTPError as error:
            return TCGdexSetsSyncAttempt(
                result=None,
                error_code=f"http_{error.status_code}",
                retryable=error.status_code in {408, 429} or error.status_code >= 500,
            )
        except TCGdexTimeoutError:
            return TCGdexSetsSyncAttempt(
                result=None,
                error_code="request_timeout",
                retryable=True,
            )
        except TCGdexNetworkError:
            return TCGdexSetsSyncAttempt(
                result=None,
                error_code="network_error",
                retryable=True,
            )
        except TCGdexResponseTooLarge:
            return TCGdexSetsSyncAttempt(
                result=None,
                error_code="response_too_large",
                retryable=False,
            )
        except TCGdexError:
            return TCGdexSetsSyncAttempt(
                result=None,
                error_code="invalid_response",
                retryable=False,
            )
