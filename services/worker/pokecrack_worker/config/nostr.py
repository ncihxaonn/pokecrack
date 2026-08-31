"""Frozen public Nostr relay and hashtag registry.

The registry is deliberately static. Jobs select one reviewed relay key; they
cannot supply endpoints, filters, accounts, or arbitrary search terms.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

NOSTR_APPROVED_TAGS: tuple[str, ...] = (
    "pokemontcg",
    "PokemonTCG",
    "pokemoncards",
    "PokemonCards",
    "ポケカ",
    "ポケモンカード",
    "포켓몬카드",
    "宝可梦卡牌",
    "寶可夢卡牌",
)
NOSTR_RELAY_ROWS: tuple[tuple[str, str, str, str], ...] = (
    (
        "primal",
        "nostr_relay_primal",
        "wss://relay.primal.net/",
        "https://relay.primal.net/",
    ),
    ("nos_lol", "nostr_relay_nos_lol", "wss://nos.lol/", "https://nos.lol/"),
    (
        "nostr_net",
        "nostr_relay_nostr_net",
        "wss://relay.nostr.net/",
        "https://relay.nostr.net/",
    ),
)


def normalize_nostr_tag(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


class NostrRelay(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    source_key: str = Field(pattern=r"^nostr_relay_[a-z0-9_]{1,48}$")
    endpoint: str
    nip11_url: str

    @model_validator(mode="after")
    def validate_urls(self) -> Self:
        endpoint = urlsplit(self.endpoint)
        metadata = urlsplit(self.nip11_url)
        if (
            endpoint.scheme != "wss"
            or endpoint.path != "/"
            or endpoint.query
            or endpoint.fragment
            or metadata.scheme != "https"
            or metadata.path != "/"
            or metadata.query
            or metadata.fragment
            or endpoint.hostname != metadata.hostname
        ):
            raise ValueError("Nostr relay URLs must be matching secure origin roots")
        return self


class NostrRelayDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    default_enabled: Literal[False] = False
    protocol: Literal["nip01"] = "nip01"
    replay_overlap_seconds: Literal[300] = 300
    stream_window_seconds: Literal[15] = 15
    max_events: Literal[100] = 100
    max_message_bytes: Literal[262144] = 262144
    max_stream_bytes: Literal[2097152] = 2097152
    relays: tuple[NostrRelay, ...]
    tags: tuple[str, ...]

    @model_validator(mode="after")
    def validate_exact_inventory(self) -> Self:
        rows = tuple(
            (relay.key, relay.source_key, relay.endpoint, relay.nip11_url)
            for relay in self.relays
        )
        if rows != NOSTR_RELAY_ROWS:
            raise ValueError("Nostr registry must contain the exact reviewed relay inventory")
        if self.tags != NOSTR_APPROVED_TAGS:
            raise ValueError("Nostr registry must contain the exact approved tag inventory")
        if len({normalize_nostr_tag(tag) for tag in self.tags}) != 7:
            raise ValueError("Nostr tag variants must normalize to exactly seven tags")
        return self


class NostrRelayRegistry:
    __slots__ = ("_document", "_relays")

    def __init__(self, document: NostrRelayDocument) -> None:
        self._document = document
        self._relays = {relay.key: relay for relay in document.relays}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> NostrRelayRegistry:
        return cls(NostrRelayDocument.model_validate(value))

    @classmethod
    def from_yaml(cls, path: str | Path) -> NostrRelayRegistry:
        with Path(path).open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
        if not isinstance(value, Mapping):
            raise ValueError("Nostr relay YAML must contain a mapping")
        return cls.from_mapping(value)

    @property
    def relays(self) -> tuple[NostrRelay, ...]:
        return self._document.relays

    @property
    def tags(self) -> tuple[str, ...]:
        return self._document.tags

    def require(self, relay_key: str) -> NostrRelay:
        try:
            return self._relays[relay_key]
        except KeyError:
            raise ValueError("Nostr relay key is not approved") from None

    def matched_tags(self, raw_tags: object) -> tuple[str, ...]:
        if not isinstance(raw_tags, list):
            return ()
        approved = {normalize_nostr_tag(tag): tag for tag in self.tags}
        matches: set[str] = set()
        for item in raw_tags:
            if (
                isinstance(item, list)
                and len(item) >= 2
                and item[0] == "t"
                and isinstance(item[1], str)
            ):
                normalized = normalize_nostr_tag(item[1])
                if normalized in approved:
                    matches.add(normalized)
        return tuple(sorted(matches))


__all__ = [
    "NOSTR_APPROVED_TAGS",
    "NOSTR_RELAY_ROWS",
    "NostrRelay",
    "NostrRelayDocument",
    "NostrRelayRegistry",
    "normalize_nostr_tag",
]
