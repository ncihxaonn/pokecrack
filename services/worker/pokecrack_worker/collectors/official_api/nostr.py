"""Bounded, read-only NIP-01 discovery across reviewed public relays.

The collector never publishes an EVENT, logs a note, resolves a profile, or
persists raw content. It verifies every event before emitting only the minimum
private activity identity required for cross-relay dedupe and NIP-09 deletion.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any, Final, Protocol

from pokecrack_worker.config.nostr import NostrRelay, NostrRelayRegistry

NOSTR_COLLECTOR_VERSION: Final = "nostr-multi-relay-v1"
NOSTR_COMPLETION_VERSION: Final = "1.0.0"
NOSTR_STREAM_WINDOW_SECONDS: Final = 15.0
NOSTR_REPLAY_OVERLAP_SECONDS: Final = 300
NOSTR_MAX_EVENTS: Final = 100
NOSTR_MAX_CANDIDATES: Final = 100
NOSTR_MAX_DELETIONS: Final = 100
NOSTR_MAX_DELETE_TARGETS: Final = 16
NOSTR_MAX_MESSAGE_BYTES: Final = 256 * 1024
NOSTR_MAX_STREAM_BYTES: Final = 2 * 1024 * 1024
NOSTR_MAX_NIP11_BYTES: Final = 64 * 1024
NOSTR_MAX_CONTENT_BYTES: Final = 64 * 1024
NOSTR_CONNECT_TIMEOUT_SECONDS: Final = 10.0
NOSTR_MIN_PUBLISHED_AT: Final = datetime(2000, 1, 1, tzinfo=UTC)
_LOWER_HEX = frozenset("0123456789abcdef")


class NostrError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class NostrTransportError(NostrError):
    def __init__(self, code: str = "nostr_transport_error") -> None:
        super().__init__(code, retryable=True)


class NostrInvalidEvent(NostrError):
    def __init__(self, code: str = "nostr_event_invalid") -> None:
        super().__init__(code, retryable=False)


class NostrAccessDenied(NostrError):
    def __init__(self, code: str = "nostr_access_denied") -> None:
        super().__init__(code, retryable=False)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(raw: bytes, *, code: str) -> object:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise NostrInvalidEvent(code) from None


def _hex(value: object, *, length: int, code: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in _LOWER_HEX for character in value)
    ):
        raise NostrInvalidEvent(code)
    return value


def _canonical_event_bytes(event: Mapping[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            [
                0,
                event["pubkey"],
                event["created_at"],
                event["kind"],
                event["tags"],
                event["content"],
            ],
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise NostrInvalidEvent() from None
    if not 1 <= len(encoded) <= NOSTR_MAX_MESSAGE_BYTES:
        raise NostrInvalidEvent("nostr_event_too_large")
    return encoded


def _verify_signature(*, pubkey: str, signature: str, event_id: str) -> None:
    try:
        from coincurve import PublicKeyXOnly

        valid = PublicKeyXOnly(bytes.fromhex(pubkey)).verify(
            bytes.fromhex(signature), bytes.fromhex(event_id)
        )
    except (ImportError, ValueError):
        raise NostrInvalidEvent("nostr_signature_invalid") from None
    if not valid:
        raise NostrInvalidEvent("nostr_signature_invalid")


@dataclass(frozen=True, slots=True)
class NostrEvent:
    event_id: str
    pubkey: str
    signature: str
    published_at: datetime
    kind: int
    tags: tuple[tuple[str, ...], ...]
    content_sha256: str


def parse_nostr_event(raw_event: object, *, completion_time: datetime) -> NostrEvent:
    if not isinstance(raw_event, Mapping) or set(raw_event) != {
        "id",
        "pubkey",
        "created_at",
        "kind",
        "tags",
        "content",
        "sig",
    }:
        raise NostrInvalidEvent()
    event_id = _hex(raw_event.get("id"), length=64, code="nostr_event_id_invalid")
    pubkey = _hex(raw_event.get("pubkey"), length=64, code="nostr_pubkey_invalid")
    signature = _hex(raw_event.get("sig"), length=128, code="nostr_signature_invalid")
    created_at = raw_event.get("created_at")
    kind = raw_event.get("kind")
    content = raw_event.get("content")
    raw_tags = raw_event.get("tags")
    if isinstance(created_at, bool) or not isinstance(created_at, int):
        raise NostrInvalidEvent("nostr_created_at_invalid")
    if isinstance(kind, bool) or kind not in {1, 5}:
        raise NostrInvalidEvent("nostr_kind_invalid")
    if not isinstance(content, str) or len(content.encode("utf-8")) > NOSTR_MAX_CONTENT_BYTES:
        raise NostrInvalidEvent("nostr_content_invalid")
    if not isinstance(raw_tags, list) or len(raw_tags) > 64:
        raise NostrInvalidEvent("nostr_tags_invalid")
    tags: list[tuple[str, ...]] = []
    for raw_tag in raw_tags:
        if (
            not isinstance(raw_tag, list)
            or not 1 <= len(raw_tag) <= 16
            or any(
                not isinstance(value, str)
                or len(value) > 512
                or any(ord(character) < 32 or ord(character) == 127 for character in value)
                for value in raw_tag
            )
        ):
            raise NostrInvalidEvent("nostr_tags_invalid")
        tags.append(tuple(raw_tag))
    published_at = datetime.fromtimestamp(created_at, UTC)
    if not NOSTR_MIN_PUBLISHED_AT <= published_at <= completion_time + timedelta(days=1):
        raise NostrInvalidEvent("nostr_created_at_out_of_range")
    canonical = _canonical_event_bytes(raw_event)
    if hashlib.sha256(canonical).hexdigest() != event_id:
        raise NostrInvalidEvent("nostr_event_id_mismatch")
    _verify_signature(pubkey=pubkey, signature=signature, event_id=event_id)
    return NostrEvent(
        event_id=event_id,
        pubkey=pubkey,
        signature=signature,
        published_at=published_at,
        kind=kind,
        tags=tuple(tags),
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class NostrCandidate:
    event_id: str
    pubkey: str
    signature: str
    published_at: datetime
    content_sha256: str
    matched_tags: tuple[str, ...]
    relay_key: str


@dataclass(frozen=True, slots=True)
class NostrDeletion:
    event_id: str
    pubkey: str
    signature: str
    published_at: datetime
    relay_key: str
    target_event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NostrRelayResult:
    relay_key: str
    since: datetime
    until: datetime
    checkpoint: datetime | None
    incomplete: bool
    events_seen: int
    bytes_seen: int
    candidates: tuple[NostrCandidate, ...]
    deletions: tuple[NostrDeletion, ...]


class NostrRelayTransport(Protocol):
    def iter_messages(
        self,
        *,
        relay: NostrRelay,
        since: datetime,
        until: datetime,
        tags: Sequence[str],
        known_event_ids: Sequence[str],
    ) -> Iterable[bytes]: ...


class WebsocketsNostrRelayTransport:
    def iter_messages(
        self,
        *,
        relay: NostrRelay,
        since: datetime,
        until: datetime,
        tags: Sequence[str],
        known_event_ids: Sequence[str],
    ) -> tuple[bytes, ...]:
        return asyncio.run(
            self._receive(
                relay=relay,
                since=since,
                until=until,
                tags=tags,
                known_event_ids=known_event_ids,
            )
        )

    @staticmethod
    def _nip11(relay: NostrRelay) -> int:
        try:
            import httpx

            with httpx.Client(
                follow_redirects=False,
                trust_env=False,
                timeout=NOSTR_CONNECT_TIMEOUT_SECONDS,
                headers={"Accept": "application/nostr+json"},
            ) as client:
                with client.stream("GET", relay.nip11_url) as response:
                    if response.status_code != 200:
                        raise NostrTransportError("nostr_nip11_unavailable")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if len(body) + len(chunk) > NOSTR_MAX_NIP11_BYTES:
                            raise NostrTransportError("nostr_nip11_too_large")
                        body.extend(chunk)
        except NostrError:
            raise
        except Exception:
            raise NostrTransportError("nostr_nip11_unavailable") from None
        document = _json(bytes(body), code="nostr_nip11_invalid")
        if not isinstance(document, Mapping):
            raise NostrTransportError("nostr_nip11_invalid")
        supported = document.get("supported_nips")
        if not isinstance(supported, list) or not {1, 9, 11}.issubset(
            {value for value in supported if isinstance(value, int) and not isinstance(value, bool)}
        ):
            raise NostrAccessDenied("nostr_nip11_capability_drift")
        limitation = document.get("limitation", {})
        if not isinstance(limitation, Mapping):
            raise NostrTransportError("nostr_nip11_invalid")
        if limitation.get("auth_required") is True:
            raise NostrAccessDenied("nostr_auth_required")
        if limitation.get("payment_required") is True:
            raise NostrAccessDenied("nostr_payment_required")
        advertised = limitation.get("max_message_length", NOSTR_MAX_MESSAGE_BYTES)
        if isinstance(advertised, bool) or not isinstance(advertised, int) or advertised < 1024:
            raise NostrTransportError("nostr_nip11_limit_invalid")
        return min(int(advertised), NOSTR_MAX_MESSAGE_BYTES)

    async def _receive(
        self,
        *,
        relay: NostrRelay,
        since: datetime,
        until: datetime,
        tags: Sequence[str],
        known_event_ids: Sequence[str],
    ) -> tuple[bytes, ...]:
        try:
            import websockets
        except ImportError:
            raise NostrTransportError("nostr_transport_unavailable") from None
        max_message_bytes = await asyncio.to_thread(self._nip11, relay)
        subscription_id = hashlib.sha256(
            f"{relay.key}:{int(since.timestamp())}:{int(until.timestamp())}".encode()
        ).hexdigest()[:24]
        filters: list[dict[str, object]] = [
            {
                "kinds": [1],
                "#t": list(tags),
                "since": int(since.timestamp()),
                "until": int(until.timestamp()),
                "limit": NOSTR_MAX_EVENTS,
            }
        ]
        if known_event_ids:
            filters.append(
                {
                    "kinds": [5],
                    "#e": list(known_event_ids[:NOSTR_MAX_CANDIDATES]),
                    "since": int(since.timestamp()),
                    "until": int(until.timestamp()),
                    "limit": NOSTR_MAX_DELETIONS,
                }
            )
        request = json.dumps(
            ["REQ", subscription_id, *filters], ensure_ascii=False, separators=(",", ":")
        )
        messages: list[bytes] = []
        bytes_seen = 0
        started = monotonic()
        try:
            async with websockets.connect(
                relay.endpoint,
                proxy=None,
                open_timeout=NOSTR_CONNECT_TIMEOUT_SECONDS,
                close_timeout=5,
                ping_interval=20,
                ping_timeout=10,
                max_size=max_message_bytes,
                max_queue=16,
                compression=None,
            ) as socket:
                await socket.send(request)
                while True:
                    remaining = NOSTR_STREAM_WINDOW_SECONDS - (monotonic() - started)
                    if remaining <= 0:
                        raise NostrTransportError("nostr_eose_timeout")
                    try:
                        message = await asyncio.wait_for(socket.recv(), timeout=remaining)
                    except TimeoutError:
                        raise NostrTransportError("nostr_eose_timeout") from None
                    encoded = message.encode("utf-8") if isinstance(message, str) else message
                    if not isinstance(encoded, bytes) or not 1 <= len(encoded) <= max_message_bytes:
                        raise NostrTransportError("nostr_message_invalid")
                    if bytes_seen + len(encoded) > NOSTR_MAX_STREAM_BYTES:
                        raise NostrTransportError("nostr_stream_too_large")
                    decoded = _json(encoded, code="nostr_message_invalid")
                    if not isinstance(decoded, list) or not decoded:
                        raise NostrTransportError("nostr_message_invalid")
                    if decoded[0] == "EOSE" and decoded == ["EOSE", subscription_id]:
                        await socket.send(
                            json.dumps(["CLOSE", subscription_id], separators=(",", ":"))
                        )
                        return tuple(messages)
                    if decoded[0] in {"AUTH", "NOTICE", "CLOSED"}:
                        raise NostrAccessDenied("nostr_relay_denied")
                    if (
                        len(decoded) != 3
                        or decoded[0] != "EVENT"
                        or decoded[1] != subscription_id
                    ):
                        raise NostrTransportError("nostr_message_invalid")
                    messages.append(encoded)
                    bytes_seen += len(encoded)
                    # Exactly 100 events is an allowed, complete slice; wait
                    # for EOSE and reject only a relay that exceeds the cap.
                    if len(messages) > NOSTR_MAX_EVENTS:
                        raise NostrTransportError("nostr_result_limit_reached")
        except NostrError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            raise NostrTransportError() from None


class NostrRelayCollector:
    def __init__(self, *, transport: NostrRelayTransport, registry: NostrRelayRegistry) -> None:
        self.transport = transport
        self.registry = registry

    def collect(
        self,
        *,
        relay_key: str,
        since: datetime,
        until: datetime,
        checkpoint: datetime | None,
        known_event_ids: Sequence[str],
    ) -> NostrRelayResult:
        if since.tzinfo is None or until.tzinfo is None or since >= until:
            raise ValueError("Nostr collection window must be ordered and timezone-aware")
        relay = self.registry.require(relay_key)
        known = tuple(_hex(item, length=64, code="nostr_known_event_id_invalid") for item in known_event_ids)
        if len(known) > NOSTR_MAX_CANDIDATES or len(known) != len(set(known)):
            raise ValueError("Nostr known event IDs are invalid")
        raw_messages = self.transport.iter_messages(
            relay=relay,
            since=since,
            until=until,
            tags=self.registry.tags,
            known_event_ids=known,
        )
        candidates: dict[str, NostrCandidate] = {}
        deletions: dict[str, NostrDeletion] = {}
        bytes_seen = 0
        events_seen = 0
        for raw_message in raw_messages:
            if not isinstance(raw_message, bytes):
                raise NostrTransportError("nostr_message_invalid")
            bytes_seen += len(raw_message)
            if bytes_seen > NOSTR_MAX_STREAM_BYTES:
                raise NostrTransportError("nostr_stream_too_large")
            envelope = _json(raw_message, code="nostr_message_invalid")
            if (
                not isinstance(envelope, list)
                or len(envelope) != 3
                or envelope[0] != "EVENT"
                or not isinstance(envelope[1], str)
            ):
                raise NostrInvalidEvent("nostr_message_invalid")
            event = parse_nostr_event(envelope[2], completion_time=until)
            events_seen += 1
            if events_seen > NOSTR_MAX_EVENTS:
                raise NostrTransportError("nostr_event_limit_exceeded")
            # ``since`` already includes the reviewed replay overlap selected by
            # the database.  A relay must not widen that authorised window.
            if not since <= event.published_at <= until:
                raise NostrInvalidEvent("nostr_event_outside_window")
            if event.kind == 1:
                matched = self.registry.matched_tags([list(tag) for tag in event.tags])
                if not matched:
                    raise NostrInvalidEvent("nostr_tag_filter_mismatch")
                candidate_item = NostrCandidate(
                    event_id=event.event_id,
                    pubkey=event.pubkey,
                    signature=event.signature,
                    published_at=event.published_at,
                    content_sha256=event.content_sha256,
                    matched_tags=matched,
                    relay_key=relay.key,
                )
                previous = candidates.get(candidate_item.event_id)
                if previous is not None and previous != candidate_item:
                    raise NostrInvalidEvent("nostr_event_conflict")
                candidates[candidate_item.event_id] = candidate_item
                continue
            targets = tuple(
                tag[1]
                for tag in event.tags
                if len(tag) >= 2
                and tag[0] == "e"
                and len(tag[1]) == 64
                and all(character in _LOWER_HEX for character in tag[1])
                and tag[1] in known
            )
            targets = tuple(dict.fromkeys(targets))
            if not targets:
                continue
            if len(targets) > NOSTR_MAX_DELETE_TARGETS:
                raise NostrInvalidEvent("nostr_delete_targets_exceeded")
            deletion_item = NostrDeletion(
                event_id=event.event_id,
                pubkey=event.pubkey,
                signature=event.signature,
                published_at=event.published_at,
                relay_key=relay.key,
                target_event_ids=targets,
            )
            previous_delete = deletions.get(deletion_item.event_id)
            if previous_delete is not None and previous_delete != deletion_item:
                raise NostrInvalidEvent("nostr_event_conflict")
            deletions[deletion_item.event_id] = deletion_item
        return NostrRelayResult(
            relay_key=relay.key,
            since=since.astimezone(UTC),
            until=until.astimezone(UTC),
            checkpoint=checkpoint.astimezone(UTC) if checkpoint is not None else None,
            incomplete=False,
            events_seen=events_seen,
            bytes_seen=bytes_seen,
            candidates=tuple(candidates.values()),
            deletions=tuple(deletions.values()),
        )


__all__ = [
    "NOSTR_COLLECTOR_VERSION",
    "NOSTR_COMPLETION_VERSION",
    "NOSTR_MAX_CANDIDATES",
    "NOSTR_MAX_DELETIONS",
    "NOSTR_MAX_EVENTS",
    "NOSTR_MAX_MESSAGE_BYTES",
    "NOSTR_MAX_STREAM_BYTES",
    "NOSTR_REPLAY_OVERLAP_SECONDS",
    "NOSTR_STREAM_WINDOW_SECONDS",
    "NostrAccessDenied",
    "NostrCandidate",
    "NostrDeletion",
    "NostrError",
    "NostrInvalidEvent",
    "NostrRelayCollector",
    "NostrRelayResult",
    "NostrRelayTransport",
    "NostrTransportError",
    "WebsocketsNostrRelayTransport",
    "parse_nostr_event",
]
