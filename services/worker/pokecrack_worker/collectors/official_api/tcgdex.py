"""Incremental, cache-aware TCGdex catalog synchronization."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from pokecrack_worker.config.registries import RarityTaxonomy
from pokecrack_worker.config.source_policy import CollectorRoute, SourcePolicyRegistry
from pokecrack_worker.validation.catalog import CatalogCard, CatalogSet


class TCGdexError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class APIResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class TCGdexTransport(Protocol):
    def get(self, url: str, *, headers: dict[str, str], timeout_seconds: float) -> APIResponse: ...


@dataclass(frozen=True, slots=True)
class CatalogSnapshot:
    language: str
    sets: tuple[CatalogSet, ...]
    cards: tuple[CatalogCard, ...]
    etag: str | None
    last_modified: str | None
    content_sha256: str
    synced_at: datetime


class TCGdexCache(Protocol):
    def get(self, language: str) -> CatalogSnapshot | None: ...

    def put(self, snapshot: CatalogSnapshot) -> None: ...


class InMemoryTCGdexCache:
    def __init__(self) -> None:
        self._snapshots: dict[str, CatalogSnapshot] = {}

    def get(self, language: str) -> CatalogSnapshot | None:
        return self._snapshots.get(language)

    def put(self, snapshot: CatalogSnapshot) -> None:
        self._snapshots[snapshot.language] = snapshot


@dataclass(frozen=True, slots=True)
class TCGdexSyncResult:
    changed: bool
    snapshot: CatalogSnapshot
    status_code: int


@dataclass(frozen=True, slots=True)
class TCGdexSyncAttempt:
    """Nonfatal scheduler-facing result for one bounded sync attempt."""

    result: TCGdexSyncResult | None
    error_code: str | None = None
    retryable: bool = False


def _header(headers: Mapping[str, str], name: str) -> str | None:
    expected = name.casefold()
    return next((value for key, value in headers.items() if key.casefold() == expected), None)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TCGdexError(f"TCGdex {field} must be a non-empty string")
    return value.strip()


class TCGdexClient:
    """Catalog-only client. Network use requires an injected transport and policy."""

    def __init__(
        self,
        *,
        transport: TCGdexTransport,
        cache: TCGdexCache,
        policies: SourcePolicyRegistry,
        taxonomy: RarityTaxonomy,
        base_url: str = "https://api.tcgdex.net/v2",
        timeout_seconds: float = 30,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.transport = transport
        self.cache = cache
        self.policies = policies
        self.taxonomy = taxonomy
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._clock = clock or (lambda: datetime.now(UTC))

    def _map(self, payload: object) -> tuple[tuple[CatalogSet, ...], tuple[CatalogCard, ...]]:
        sets_value: object
        top_cards: list[object] = []
        if isinstance(payload, list):
            sets_value = payload
        elif isinstance(payload, Mapping):
            sets_value = payload.get("sets")
            top_cards_value = payload.get("cards", [])
            if isinstance(top_cards_value, list):
                top_cards.extend(top_cards_value)
        else:
            raise TCGdexError("TCGdex response must be an object or array")
        if not isinstance(sets_value, list):
            raise TCGdexError("TCGdex response sets must be an array")
        sets: list[CatalogSet] = []
        cards: list[CatalogCard] = []
        for raw_set in sets_value:
            if not isinstance(raw_set, Mapping):
                raise TCGdexError("TCGdex set must be an object")
            set_id = _text(raw_set.get("id"), "set id")
            name = _text(raw_set.get("name"), "set name")
            aliases_value = raw_set.get("aliases", [])
            aliases = (
                tuple(str(alias) for alias in aliases_value)
                if isinstance(aliases_value, list)
                else ()
            )
            sets.append(CatalogSet(set_id=set_id, name=name, aliases=aliases))
            nested = raw_set.get("cards", [])
            if isinstance(nested, list):
                top_cards.extend(nested)
        for raw_card in top_cards:
            if not isinstance(raw_card, Mapping):
                raise TCGdexError("TCGdex card must be an object")
            card_id = _text(raw_card.get("id"), "card id")
            set_id_value = raw_card.get("set_id") or raw_card.get("setId")
            if set_id_value is None and "-" in card_id:
                set_id_value = card_id.rsplit("-", maxsplit=1)[0]
            set_id = _text(set_id_value, "card set id")
            rarity_value = raw_card.get("rarity")
            rarity_key = self.taxonomy.resolve(
                rarity_value if isinstance(rarity_value, str) else None
            ).key
            aliases_value = raw_card.get("aliases", [])
            cards.append(
                CatalogCard(
                    card_id=card_id,
                    set_id=set_id,
                    name=_text(raw_card.get("name"), "card name"),
                    collector_number=(
                        str(raw_card.get("localId"))
                        if raw_card.get("localId") is not None
                        else None
                    ),
                    rarity_key=rarity_key,
                    aliases=(
                        tuple(str(alias) for alias in aliases_value)
                        if isinstance(aliases_value, list)
                        else ()
                    ),
                )
            )
        return tuple(sets), tuple(cards)

    def sync(self, *, language: str = "en") -> TCGdexSyncResult:
        if not language.isalpha() or not 2 <= len(language) <= 8:
            raise ValueError("TCGdex language must be an alphabetic language code")
        url = f"{self.base_url}/{language.casefold()}/sets"
        self.policies.require(url, CollectorRoute.CATALOG)
        previous = self.cache.get(language.casefold())
        headers: dict[str, str] = {}
        if previous and previous.etag:
            headers["If-None-Match"] = previous.etag
        elif previous and previous.last_modified:
            headers["If-Modified-Since"] = previous.last_modified
        response = self.transport.get(url, headers=headers, timeout_seconds=self.timeout_seconds)
        if response.status_code == 304:
            if previous is None:
                raise TCGdexError("TCGdex returned 304 without a cached snapshot")
            return TCGdexSyncResult(False, previous, 304)
        if response.status_code != 200:
            raise TCGdexError(f"TCGdex HTTP status {response.status_code}")
        try:
            payload: Any = json.loads(response.body)
        except json.JSONDecodeError as error:
            raise TCGdexError(f"TCGdex returned invalid JSON: {error}") from error
        sets, cards = self._map(payload)
        digest = hashlib.sha256(response.body).hexdigest()
        if previous and previous.content_sha256 == digest:
            refreshed = CatalogSnapshot(
                language=previous.language,
                sets=previous.sets,
                cards=previous.cards,
                etag=_header(response.headers, "etag"),
                last_modified=_header(response.headers, "last-modified"),
                content_sha256=previous.content_sha256,
                synced_at=self._clock(),
            )
            self.cache.put(refreshed)
            return TCGdexSyncResult(False, refreshed, 200)
        snapshot = CatalogSnapshot(
            language=language.casefold(),
            sets=sets,
            cards=cards,
            etag=_header(response.headers, "etag"),
            last_modified=_header(response.headers, "last-modified"),
            content_sha256=digest,
            synced_at=self._clock(),
        )
        self.cache.put(snapshot)
        return TCGdexSyncResult(True, snapshot, 200)

    def sync_safe(self, *, language: str = "en") -> TCGdexSyncAttempt:
        """Return a classified nonfatal failure instead of failing a collector run."""

        try:
            return TCGdexSyncAttempt(result=self.sync(language=language))
        except TCGdexError as error:
            message = str(error)
            if message.startswith("TCGdex HTTP status "):
                try:
                    status = int(message.rsplit(" ", maxsplit=1)[-1])
                except ValueError:
                    status = 0
                return TCGdexSyncAttempt(
                    result=None,
                    error_code="http_error",
                    retryable=status == 429 or status >= 500,
                )
            return TCGdexSyncAttempt(
                result=None,
                error_code="invalid_response",
                retryable=False,
            )
