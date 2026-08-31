"""Bounded Bluesky Jetstream v2 activity discovery.

This module intentionally keeps the network boundary narrow: one fixed secure
WebSocket endpoint, one fixed post collection, one fixed set of operations, and
one short stream window.  It emits only public post identity, a small text
excerpt, a record hash, and the record timestamp.  It does not fetch profiles,
resolve handles, infer geography, or promote a post into an opening or rate.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any, Final, Protocol
from urllib.parse import urlencode, urlsplit, urlunsplit

from websockets.exceptions import InvalidStatus
from websockets.typing import Subprotocol

from pokecrack_worker.config.bluesky import (
    BLUESKY_POST_COLLECTION,
    BlueskyKeywordRegistry,
)
from pokecrack_worker.config.source_policy import CollectorRoute, SourcePolicyRegistry

BLUESKY_JETSTREAM_URL: Final = (
    "wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents"
)
BLUESKY_POLICY_URL: Final = BLUESKY_JETSTREAM_URL.replace("wss://", "https://", 1)
BLUESKY_SUBPROTOCOL: Final = "xrpc.v1.json"
BLUESKY_COLLECTOR_VERSION: Final = "bluesky-jetstream-v1"
BLUESKY_PARSER_VERSION: Final = "bluesky-jetstream-parser-v1"

# Production observed 1,139,364 bytes over 40 seconds (28,484 B/s).  A fixed
# 10-second slice projects to about 285 KiB at that rate, leaving roughly 7.36x
# headroom below the unchanged 2 MiB stream ceiling for high-volume bursts.
# The setting is intentionally not operator-adjustable.
BLUESKY_STREAM_WINDOW_SECONDS: Final = 10.0
BLUESKY_MAX_MESSAGE_BYTES: Final = 256 * 1024
BLUESKY_MAX_STREAM_BYTES: Final = 2 * 1024 * 1024
BLUESKY_MAX_EVENTS: Final = 10_000
BLUESKY_MAX_CANDIDATES: Final = 100
BLUESKY_MAX_DELETIONS: Final = 100
BLUESKY_MAX_EXCERPT_CHARS: Final = 500
BLUESKY_MAX_RECORD_BYTES: Final = 64 * 1024
BLUESKY_MAX_CURSOR: Final = 9_223_372_036_854_775_807
BLUESKY_CONNECT_TIMEOUT_SECONDS: Final = 10.0
BLUESKY_CLOSE_TIMEOUT_SECONDS: Final = 5.0

_DID_PATTERN = re.compile(r"^did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}$")
_RKEY_PATTERN = re.compile(r"^[A-Za-z0-9._:%~-]{1,240}$")
_REV_PATTERN = re.compile(r"^[A-Za-z0-9]{1,128}$")
_CID_PATTERN = re.compile(r"^[A-Za-z0-9+/=._:-]{1,256}$")
_AT_URI_PATTERN = re.compile(
    r"^at://did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}/app\.bsky\.feed\.post/"
    r"[A-Za-z0-9._:%~-]{1,240}$"
)


class BlueskyError(RuntimeError):
    """Base error at the fixed Bluesky boundary."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class BlueskyTransportError(BlueskyError):
    def __init__(self, code: str = "bluesky_transport_error") -> None:
        super().__init__(code, retryable=True)


class BlueskyInvalidMessage(BlueskyError):
    def __init__(self, code: str = "bluesky_invalid_message") -> None:
        super().__init__(code, retryable=False)


class BlueskyConsumerTooSlowError(BlueskyError):
    def __init__(self) -> None:
        super().__init__("bluesky_consumer_too_slow", retryable=True)


class BlueskyCursorTooOldError(BlueskyError):
    def __init__(self) -> None:
        super().__init__("bluesky_cursor_too_old", retryable=False)


Cursor = int


def _cursor(value: object, *, field: str = "cursor") -> Cursor:
    """Accept the integer or canonical decimal text returned by a DB driver."""

    if isinstance(value, bool):
        raise BlueskyInvalidMessage(f"bluesky_{field}_invalid")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value and value.isascii() and value.isdecimal():
        if value != "0" and value.startswith("0"):
            raise BlueskyInvalidMessage(f"bluesky_{field}_invalid")
        parsed = int(value)
    else:
        raise BlueskyInvalidMessage(f"bluesky_{field}_invalid")
    if not 0 <= parsed <= BLUESKY_MAX_CURSOR:
        raise BlueskyInvalidMessage(f"bluesky_{field}_invalid")
    return parsed


def _required_text(value: object, *, code: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise BlueskyInvalidMessage(code)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise BlueskyInvalidMessage(code)
    return value


def _did(value: object) -> str:
    candidate = _required_text(value, code="bluesky_did_invalid", maximum=256)
    if _DID_PATTERN.fullmatch(candidate) is None:
        raise BlueskyInvalidMessage("bluesky_did_invalid")
    return candidate


def _rkey(value: object) -> str:
    candidate = _required_text(value, code="bluesky_rkey_invalid", maximum=240)
    if _RKEY_PATTERN.fullmatch(candidate) is None:
        raise BlueskyInvalidMessage("bluesky_rkey_invalid")
    return candidate


def _record_bytes(record: Mapping[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise BlueskyInvalidMessage("bluesky_record_invalid") from None
    if not encoded:
        raise BlueskyInvalidMessage("bluesky_record_invalid")
    return encoded


def _published_at(record: Mapping[str, Any]) -> datetime | None:
    value = record.get("createdAt")
    if value is None:
        raise BlueskyInvalidMessage("bluesky_created_at_invalid")
    candidate = _required_text(value, code="bluesky_created_at_invalid", maximum=80)
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        raise BlueskyInvalidMessage("bluesky_created_at_invalid") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BlueskyInvalidMessage("bluesky_created_at_invalid")
    try:
        normalized = parsed.astimezone(UTC)
    except (OverflowError, ValueError):
        raise BlueskyInvalidMessage("bluesky_created_at_out_of_range") from None
    if not datetime(2000, 1, 1, tzinfo=UTC) <= normalized <= datetime.now(UTC) + timedelta(days=1):
        raise BlueskyInvalidMessage("bluesky_created_at_out_of_range")
    return normalized


def _bounded_excerpt(value: str) -> str | None:
    """Normalize harmless Unicode/control variation before retaining 500 chars."""

    normalized = unicodedata.normalize("NFKC", value)
    cleaned = "".join(
        "\n"
        if character in "\r\n"
        else "\t"
        if character == "\t"
        else " "
        if unicodedata.category(character).startswith("C")
        else character
        for character in normalized
    )
    excerpt = cleaned[:BLUESKY_MAX_EXCERPT_CHARS]
    return excerpt or None


def _frame_payload(raw: object) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise BlueskyInvalidMessage()
    if raw.get("$type") != "message" or set(raw) != {"$type", "payload"}:
        # Error frames are not message envelopes in Jetstream v2.  Keep the
        # error classification explicit without retaining its message text.
        if raw.get("error") == "ConsumerTooSlow":
            raise BlueskyConsumerTooSlowError()
        if raw.get("error") == "CursorTooOld":
            raise BlueskyCursorTooOldError()
        raise BlueskyInvalidMessage()
    payload = raw.get("payload")
    if not isinstance(payload, Mapping):
        raise BlueskyInvalidMessage()
    return payload


def _error_from_payload(payload: Mapping[str, Any]) -> None:
    error = payload.get("error")
    if error == "ConsumerTooSlow":
        raise BlueskyConsumerTooSlowError()
    if error == "CursorTooOld":
        raise BlueskyCursorTooOldError()


def _is_cursor_too_old_handshake(error: InvalidStatus) -> bool:
    """Recognize only Jetstream's structured stale-cursor HTTP rejection.

    Jetstream v2 rejects a cursor below its replay floor before upgrading the
    WebSocket.  websockets 14 and 15 expose that response as ``InvalidStatus``
    with a ``Response`` containing the HTTP status and body.  Treating every
    HTTP 400 (or an error message's text) as stale would hide unrelated
    outages, so require the exact documented status and XRPC error name.
    """

    response = error.response
    if response.status_code != 400:
        return False
    body = response.body
    if not isinstance(body, bytes) or not 1 <= len(body) <= BLUESKY_MAX_MESSAGE_BYTES:
        return False
    try:
        decoded: object = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(decoded, Mapping) and decoded.get("error") == "CursorTooOld"


@dataclass(frozen=True, slots=True)
class BlueskyCommitEvent:
    """Validated commit envelope; raw record data never leaves this boundary."""

    seq: Cursor
    did: str
    time: datetime
    rev: str
    operation: str
    collection: str
    rkey: str
    record: Mapping[str, Any] | None
    record_fingerprint: bytes | None = field(repr=False)
    published_at: datetime | None
    candidate_record_within_bound: bool
    candidate_timestamp_valid: bool


def parse_jetstream_message(raw: bytes | str | Mapping[str, Any]) -> BlueskyCommitEvent | None:
    """Parse one bounded v2 frame, returning only approved post commits.

    Frames for other collections are ignored after their small structural
    envelope is validated.  Relevant malformed frames fail closed, while an
    in-band upstream error receives a typed retry disposition. Candidate-level
    exceptions are an oversized but otherwise valid record and
    an untrusted record ``createdAt`` with invalid syntax or range.  Their
    otherwise validated commits are returned so the collector can advance the
    cursor, but the records are marked ineligible for candidate retention.
    Every other relevant envelope or record error still fails closed.
    """

    if isinstance(raw, bytes):
        if not 1 <= len(raw) <= BLUESKY_MAX_MESSAGE_BYTES:
            raise BlueskyInvalidMessage("bluesky_message_too_large")
        try:
            decoded: object = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BlueskyInvalidMessage() from None
    elif isinstance(raw, str):
        encoded = raw.encode("utf-8")
        if not 1 <= len(encoded) <= BLUESKY_MAX_MESSAGE_BYTES:
            raise BlueskyInvalidMessage("bluesky_message_too_large")
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            raise BlueskyInvalidMessage() from None
    else:
        try:
            encoded = json.dumps(
                raw,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            raise BlueskyInvalidMessage("bluesky_message_invalid") from None
        if not 1 <= len(encoded) <= BLUESKY_MAX_MESSAGE_BYTES:
            raise BlueskyInvalidMessage("bluesky_message_too_large")
        decoded = raw

    envelope = _frame_payload(decoded)
    _error_from_payload(envelope)
    if envelope.get("$type") != "network.bsky.jetstream.subscribeEvents#commit":
        return None
    required = {"$type", "seq", "did", "time", "rev", "operation", "collection", "rkey"}
    if not required <= set(envelope):
        raise BlueskyInvalidMessage()
    seq = _cursor(envelope.get("seq"), field="sequence")
    raw_time = envelope.get("time")
    if not isinstance(raw_time, str):
        raise BlueskyInvalidMessage("bluesky_time_invalid")
    try:
        event_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except ValueError:
        raise BlueskyInvalidMessage("bluesky_time_invalid") from None
    if event_time.tzinfo is None or event_time.utcoffset() is None:
        raise BlueskyInvalidMessage("bluesky_time_invalid")
    event_time = event_time.astimezone(UTC)
    if not datetime(2000, 1, 1, tzinfo=UTC) <= event_time <= datetime.now(UTC) + timedelta(days=1):
        raise BlueskyInvalidMessage("bluesky_time_out_of_range")
    did = _did(envelope.get("did"))
    rev = _required_text(envelope.get("rev"), code="bluesky_revision_invalid", maximum=128)
    if _REV_PATTERN.fullmatch(rev) is None:
        raise BlueskyInvalidMessage("bluesky_revision_invalid")
    operation = envelope.get("operation")
    if operation not in {"create", "update", "delete"}:
        raise BlueskyInvalidMessage("bluesky_operation_invalid")
    collection = _required_text(
        envelope.get("collection"), code="bluesky_collection_invalid", maximum=256
    )
    rkey = _rkey(envelope.get("rkey"))
    if collection != BLUESKY_POST_COLLECTION:
        return None
    record: Mapping[str, Any] | None
    record_fingerprint: bytes | None = None
    published_at: datetime | None = None
    candidate_record_within_bound = True
    candidate_timestamp_valid = True
    if operation == "delete":
        if "record" in envelope or "cid" in envelope:
            raise BlueskyInvalidMessage("bluesky_delete_payload_invalid")
        record = None
    else:
        if not isinstance(envelope.get("record"), Mapping):
            raise BlueskyInvalidMessage("bluesky_record_invalid")
        if envelope.get("record", {}).get("$type") != BLUESKY_POST_COLLECTION:
            raise BlueskyInvalidMessage("bluesky_record_invalid")
        cid = envelope.get("cid")
        if not isinstance(cid, str) or _CID_PATTERN.fullmatch(cid) is None:
            raise BlueskyInvalidMessage("bluesky_cid_invalid")
        parsed_record = dict(envelope["record"])
        record_bytes = _record_bytes(parsed_record)
        record_fingerprint = hashlib.sha256(record_bytes).digest()
        candidate_record_within_bound = len(record_bytes) <= BLUESKY_MAX_RECORD_BYTES
        text_value = parsed_record.get("text")
        if not isinstance(text_value, str) or len(text_value) > 10_000:
            raise BlueskyInvalidMessage("bluesky_record_text_invalid")
        try:
            published_at = _published_at(parsed_record)
        except BlueskyInvalidMessage as error:
            if error.code not in {
                "bluesky_created_at_invalid",
                "bluesky_created_at_out_of_range",
            }:
                raise
            # A post controls its own createdAt value.  Keep the validated
            # commit cursor moving, but suppress this record from the retained
            # candidate set instead of letting one poison value replay forever.
            candidate_timestamp_valid = False
        # Oversized record material remains only in the already bounded raw
        # transport frame while this iteration is active. The event/cache keeps
        # a fixed-size fingerprint for duplicate-sequence conflict detection,
        # never the decoded record or a persistable candidate hash.
        record = parsed_record if candidate_record_within_bound else None
    return BlueskyCommitEvent(
        seq=seq,
        did=did,
        time=event_time,
        rev=rev,
        operation=operation,
        collection=collection,
        rkey=rkey,
        record=record,
        record_fingerprint=record_fingerprint,
        published_at=published_at,
        candidate_record_within_bound=candidate_record_within_bound,
        candidate_timestamp_valid=candidate_timestamp_valid,
    )


@dataclass(frozen=True, slots=True)
class BlueskyCandidate:
    cursor: Cursor
    at_uri: str
    public_url: str
    text_excerpt: str | None
    record_sha256: str
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class BlueskyDeletion:
    at_uri: str
    cursor: Cursor


@dataclass(frozen=True, slots=True)
class BlueskyJetstreamResult:
    start_cursor: Cursor | None
    end_cursor: Cursor | None
    events_seen: int
    bytes_seen: int
    candidates: tuple[BlueskyCandidate, ...]
    deletions: tuple[BlueskyDeletion, ...]


class BlueskyJetstreamTransport(Protocol):
    def iter_messages(
        self,
        *,
        start_cursor: Cursor | None,
        max_events: int,
        max_bytes: int,
        window_seconds: float,
    ) -> Iterable[bytes]: ...


class WebsocketsBlueskyJetstreamTransport:
    """Official endpoint transport with frame, byte, and wall-time ceilings."""

    def __init__(
        self,
        *,
        stream_window_seconds: float = BLUESKY_STREAM_WINDOW_SECONDS,
        max_message_bytes: int = BLUESKY_MAX_MESSAGE_BYTES,
    ) -> None:
        if stream_window_seconds != BLUESKY_STREAM_WINDOW_SECONDS:
            raise ValueError("Bluesky transport requires the reviewed fixed stream window")
        if not 1 <= max_message_bytes <= BLUESKY_MAX_MESSAGE_BYTES:
            raise ValueError("Bluesky message cap is outside the approved bound")
        self.stream_window_seconds = stream_window_seconds
        self.max_message_bytes = max_message_bytes

    def iter_messages(
        self,
        *,
        start_cursor: Cursor | None,
        max_events: int,
        max_bytes: int,
        window_seconds: float,
    ) -> tuple[bytes, ...]:
        if window_seconds != self.stream_window_seconds:
            raise ValueError("Bluesky transport requires its fixed stream window")
        if not 1 <= max_events <= BLUESKY_MAX_EVENTS:
            raise ValueError("Bluesky event cap is outside the approved bound")
        if not 1 <= max_bytes <= BLUESKY_MAX_STREAM_BYTES:
            raise ValueError("Bluesky stream byte cap is outside the approved bound")
        if start_cursor is not None:
            start_cursor = _cursor(start_cursor, field="start_cursor")
        return asyncio.run(
            self._receive(
                start_cursor=start_cursor,
                max_events=max_events,
                max_bytes=max_bytes,
                window_seconds=window_seconds,
            )
        )

    async def _receive(
        self,
        *,
        start_cursor: Cursor | None,
        max_events: int,
        max_bytes: int,
        window_seconds: float,
    ) -> tuple[bytes, ...]:
        try:
            import websockets
        except ImportError:
            raise BlueskyTransportError("bluesky_transport_unavailable") from None

        query: list[tuple[str, str]] = [
            ("kinds", "commit"),
            ("collections", BLUESKY_POST_COLLECTION),
            ("maxMessageSizeBytes", str(self.max_message_bytes)),
        ]
        if start_cursor is not None:
            query.append(("cursor", str(start_cursor)))
        parsed = urlsplit(BLUESKY_JETSTREAM_URL)
        uri = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))
        started = monotonic()
        messages: list[bytes] = []
        bytes_seen = 0
        try:
            async with websockets.connect(
                uri,
                subprotocols=[Subprotocol(BLUESKY_SUBPROTOCOL)],
                proxy=None,
                open_timeout=BLUESKY_CONNECT_TIMEOUT_SECONDS,
                close_timeout=BLUESKY_CLOSE_TIMEOUT_SECONDS,
                ping_interval=20,
                ping_timeout=10,
                max_size=self.max_message_bytes,
                max_queue=16,
                compression=None,
            ) as socket:
                while len(messages) < max_events:
                    remaining = window_seconds - (monotonic() - started)
                    if remaining <= 0:
                        break
                    try:
                        message = await asyncio.wait_for(socket.recv(), timeout=remaining)
                    except TimeoutError:
                        break
                    if isinstance(message, str):
                        encoded = message.encode("utf-8")
                    elif isinstance(message, bytes):
                        encoded = message
                    else:
                        raise BlueskyTransportError("bluesky_binary_message_invalid")
                    if not 1 <= len(encoded) <= self.max_message_bytes:
                        raise BlueskyTransportError("bluesky_message_too_large")
                    if len(encoded) > max_bytes - bytes_seen:
                        # Preserve the complete prefix.  The next scheduled
                        # slice resumes inclusively from its checkpoint, so
                        # the first event that would exceed the byte budget is
                        # replayed rather than silently skipped.
                        break
                    messages.append(encoded)
                    bytes_seen += len(encoded)
        except BlueskyError:
            raise
        except InvalidStatus as error:
            if _is_cursor_too_old_handshake(error):
                raise BlueskyCursorTooOldError() from None
            raise BlueskyTransportError() from None
        except TimeoutError:
            raise BlueskyTransportError("bluesky_request_timeout") from None
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Do not expose endpoint/library details or upstream payloads.
            if type(error).__name__ == "ConnectionClosedOK":
                return tuple(messages)
            raise BlueskyTransportError() from None
        return tuple(messages)


class BlueskyJetstreamCollector:
    """Collect one fixed-size, keyword-filtered Jetstream slice."""

    def __init__(
        self,
        *,
        transport: BlueskyJetstreamTransport,
        keywords: BlueskyKeywordRegistry,
        policies: SourcePolicyRegistry | None = None,
    ) -> None:
        if policies is not None:
            policies.require(BLUESKY_POLICY_URL, CollectorRoute.BLUESKY_JETSTREAM)
        if keywords.collection != BLUESKY_POST_COLLECTION:
            raise ValueError("Bluesky keyword registry collection is not approved")
        self.transport = transport
        self.keywords = keywords

    def collect(self, *, start_cursor: Cursor | None = None) -> BlueskyJetstreamResult:
        if start_cursor is not None:
            start_cursor = _cursor(start_cursor, field="start_cursor")
        messages = self.transport.iter_messages(
            start_cursor=start_cursor,
            max_events=BLUESKY_MAX_EVENTS,
            max_bytes=BLUESKY_MAX_STREAM_BYTES,
            window_seconds=BLUESKY_STREAM_WINDOW_SECONDS,
        )
        events_seen = 0
        bytes_seen = 0
        end_cursor = start_cursor
        seen_events: dict[Cursor, BlueskyCommitEvent] = {}
        candidates: dict[str, BlueskyCandidate] = {}
        deletions: dict[str, BlueskyDeletion] = {}
        for raw in messages:
            if events_seen >= BLUESKY_MAX_EVENTS:
                raise BlueskyTransportError("bluesky_event_limit_exceeded")
            if not isinstance(raw, bytes):
                raise BlueskyTransportError("bluesky_message_invalid")
            if not 1 <= len(raw) <= BLUESKY_MAX_MESSAGE_BYTES:
                raise BlueskyTransportError("bluesky_message_too_large")
            next_bytes_seen = bytes_seen + len(raw)
            if next_bytes_seen > BLUESKY_MAX_STREAM_BYTES:
                # A transport implementation may return a prefix larger than
                # its advertised budget. Keep the already validated prefix so
                # the checkpoint can advance without exceeding the cap.
                break
            event = parse_jetstream_message(raw)
            if event is None:
                events_seen += 1
                bytes_seen = next_bytes_seen
                continue
            previous_event = seen_events.get(event.seq)
            if previous_event is not None:
                if event != previous_event:
                    raise BlueskyInvalidMessage("bluesky_sequence_conflict")
                events_seen += 1
                bytes_seen = next_bytes_seen
                continue
            seen_events[event.seq] = event
            if start_cursor is not None and event.seq <= start_cursor:
                events_seen += 1
                bytes_seen = next_bytes_seen
                continue
            if end_cursor is not None and event.seq < end_cursor:
                raise BlueskyInvalidMessage("bluesky_sequence_non_monotonic")
            at_uri = f"at://{event.did}/{BLUESKY_POST_COLLECTION}/{event.rkey}"
            if _AT_URI_PATTERN.fullmatch(at_uri) is None:
                raise BlueskyInvalidMessage("bluesky_at_uri_invalid")
            candidate: BlueskyCandidate | None = None
            if event.operation == "delete":
                if at_uri in candidates or at_uri in deletions:
                    # The database stores one immutable observation per
                    # sequence while its bounded completion contract permits
                    # each identity only once per list. Return the fully
                    # processed prefix so a later inclusive slice persists
                    # this event rather than collapsing it into prior state.
                    break
                if len(deletions) >= BLUESKY_MAX_DELETIONS:
                    # Return the fully processed prefix. The checkpoint remains
                    # before this event so the inclusive next slice retries it.
                    break
            else:
                if event.candidate_record_within_bound:
                    assert event.record is not None
                    assert event.record_fingerprint is not None
                    text_value = event.record.get("text")
                    assert isinstance(text_value, str)
                    if event.candidate_timestamp_valid and self.keywords.matches(text_value):
                        candidate = BlueskyCandidate(
                            cursor=event.seq,
                            at_uri=at_uri,
                            public_url=f"https://bsky.app/profile/{event.did}/post/{event.rkey}",
                            text_excerpt=_bounded_excerpt(text_value),
                            record_sha256=event.record_fingerprint.hex(),
                            published_at=event.published_at,
                        )
                        if at_uri in candidates or at_uri in deletions:
                            # Preserve every matching event across bounded slices;
                            # never advance the checkpoint past an event omitted
                            # from the exact completion payload.
                            break
                        if len(candidates) >= BLUESKY_MAX_CANDIDATES:
                            # Do not advance beyond an event omitted from the exact
                            # completion payload; the next inclusive slice resumes it.
                            break

            events_seen += 1
            bytes_seen = next_bytes_seen
            end_cursor = event.seq if end_cursor is None else max(end_cursor, event.seq)
            if event.operation == "delete":
                deletions[at_uri] = BlueskyDeletion(at_uri=at_uri, cursor=event.seq)
                continue
            if candidate is None:
                continue
            candidates[at_uri] = candidate
        return BlueskyJetstreamResult(
            start_cursor=start_cursor,
            end_cursor=end_cursor,
            events_seen=events_seen,
            bytes_seen=bytes_seen,
            candidates=tuple(candidates.values()),
            deletions=tuple(deletions.values()),
        )


# Friendly aliases for callers that prefer the shorter names used in the
# worker's other official collectors.
BlueskyCollector = BlueskyJetstreamCollector
HTTPXBlueskyJetstreamTransport = WebsocketsBlueskyJetstreamTransport


__all__ = [
    "BLUESKY_COLLECTOR_VERSION",
    "BLUESKY_JETSTREAM_URL",
    "BLUESKY_MAX_CANDIDATES",
    "BLUESKY_MAX_DELETIONS",
    "BLUESKY_MAX_EVENTS",
    "BLUESKY_MAX_EXCERPT_CHARS",
    "BLUESKY_MAX_MESSAGE_BYTES",
    "BLUESKY_MAX_STREAM_BYTES",
    "BLUESKY_PARSER_VERSION",
    "BLUESKY_POLICY_URL",
    "BLUESKY_STREAM_WINDOW_SECONDS",
    "BLUESKY_SUBPROTOCOL",
    "BlueskyCandidate",
    "BlueskyCollector",
    "BlueskyCommitEvent",
    "BlueskyConsumerTooSlowError",
    "BlueskyCursorTooOldError",
    "BlueskyDeletion",
    "BlueskyError",
    "BlueskyInvalidMessage",
    "BlueskyJetstreamCollector",
    "BlueskyJetstreamResult",
    "BlueskyJetstreamTransport",
    "BlueskyTransportError",
    "HTTPXBlueskyJetstreamTransport",
    "WebsocketsBlueskyJetstreamTransport",
    "parse_jetstream_message",
]
