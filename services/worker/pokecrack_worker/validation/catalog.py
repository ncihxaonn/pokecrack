from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class MatchStatus(StrEnum):
    MATCHED = "matched"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class CatalogSet:
    set_id: str
    name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CatalogCard:
    card_id: str
    set_id: str
    name: str
    collector_number: str | None
    rarity_key: str | None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CatalogMatch[T]:
    status: MatchStatus
    value: T | None = None
    candidates: tuple[T, ...] = ()


@runtime_checkable
class CatalogMatcher(Protocol):
    def match_set(self, name: str) -> CatalogMatch[CatalogSet]: ...

    def match_card(
        self, set_id: str, name: str, collector_number: str | None = None
    ) -> CatalogMatch[CatalogCard]: ...


def normalize_catalog_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    words = re.sub(r"[^\w]+", " ", unaccented.casefold(), flags=re.UNICODE)
    return " ".join(words.split())


def _finish_match[T](candidates: Sequence[T]) -> CatalogMatch[T]:
    unique = tuple(dict.fromkeys(candidates))
    if len(unique) == 1:
        return CatalogMatch(MatchStatus.MATCHED, value=unique[0], candidates=unique)
    if not unique:
        return CatalogMatch(MatchStatus.NOT_FOUND)
    return CatalogMatch(MatchStatus.AMBIGUOUS, candidates=unique)


class InMemoryCatalogMatcher:
    """Deterministic exact/alias matcher suitable for cached catalog snapshots."""

    def __init__(self, *, sets: Sequence[CatalogSet], cards: Sequence[CatalogCard]) -> None:
        self._sets = tuple(sets)
        self._cards = tuple(cards)

    def match_set(self, name: str) -> CatalogMatch[CatalogSet]:
        query = normalize_catalog_text(name)
        if not query:
            return CatalogMatch(MatchStatus.NOT_FOUND)
        canonical = [item for item in self._sets if normalize_catalog_text(item.name) == query]
        if canonical:
            return _finish_match(canonical)
        aliases = [
            item
            for item in self._sets
            if any(normalize_catalog_text(alias) == query for alias in item.aliases)
        ]
        return _finish_match(aliases)

    def match_card(
        self, set_id: str, name: str, collector_number: str | None = None
    ) -> CatalogMatch[CatalogCard]:
        query = normalize_catalog_text(name)
        number = normalize_catalog_text(collector_number) if collector_number else None
        cards = [item for item in self._cards if item.set_id == set_id]
        if number is not None:
            cards = [
                item
                for item in cards
                if item.collector_number is not None
                and normalize_catalog_text(item.collector_number) == number
            ]
        canonical = [item for item in cards if normalize_catalog_text(item.name) == query]
        if canonical:
            return _finish_match(canonical)
        aliases = [
            item
            for item in cards
            if any(normalize_catalog_text(alias) == query for alias in item.aliases)
        ]
        return _finish_match(aliases)
