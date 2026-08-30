"""Frozen, reviewable keyword and event filters for Bluesky discovery.

The YAML file is deliberately an inventory rather than an operator-controlled
query surface.  Every term, collection, and operation is pinned in this module;
changing the registry requires a code review and a version change.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

BLUESKY_POST_COLLECTION = "app.bsky.feed.post"
BLUESKY_FILTER_OPERATIONS: tuple[Literal["create", "update", "delete"], ...] = (
    "create",
    "update",
    "delete",
)

# Keep this list intentionally reviewable.  A post must contain at least one
# identity term and one opening/TCG term, which prevents a generic ``opening``
# post or an unrelated Pokémon game post from entering the activity cache.  It
# cannot create an opening, denominator, rate, geography, or public signal.
REQUIRED_BLUESKY_KEYWORDS: tuple[tuple[str, str, Literal["identity", "activity"]], ...] = (
    ("pokemon", "Pokemon", "identity"),
    ("pokemon-accented", "Pokémon", "identity"),
    ("pokemon-ja", "ポケモン", "identity"),
    ("pokemon-ko", "포켓몬", "identity"),
    ("pokemon-zh-simplified", "宝可梦", "identity"),
    ("pokemon-zh-traditional", "寶可夢", "identity"),
    ("tcg", "TCG", "activity"),
    ("trading-card", "trading card", "activity"),
    ("card", "card", "activity"),
    ("pack", "pack", "activity"),
    ("opening", "opening", "activity"),
    ("pulls", "pulls", "activity"),
    ("booster", "booster", "activity"),
    ("sobres", "sobres", "activity"),
    ("apertura", "apertura", "activity"),
    ("ouverture", "ouverture", "activity"),
    ("karten", "Karten", "activity"),
    ("pacotes", "pacotes", "activity"),
    ("abrindo", "abrindo", "activity"),
    ("pack-ja", "パック", "activity"),
    ("opening-ja", "開封", "activity"),
    ("pack-ko", "팩", "activity"),
    ("opening-ko", "개봉", "activity"),
    ("pack-zh-simplified", "卡包", "activity"),
    ("opening-zh-simplified", "开箱", "activity"),
    ("opening-zh-traditional", "開箱", "activity"),
)


def normalize_keyword(value: str) -> str:
    """Normalize case/diacritics and punctuation without changing semantics."""

    compatibility = unicodedata.normalize("NFKC", value)
    decomposed = unicodedata.normalize("NFKD", compatibility)
    plain = "".join(character for character in decomposed if not unicodedata.combining(character))
    tokens = [character if character.isalnum() else " " for character in plain.casefold()]
    return " ".join("".join(tokens).split())


def _yaml_mapping(path: str | Path) -> Mapping[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


class BlueskyKeyword(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    keyword: str = Field(min_length=1, max_length=80)
    group: Literal["identity", "activity"]
    enabled: Literal[True] = True

    @model_validator(mode="after")
    def validate_keyword(self) -> Self:
        if self.keyword != self.keyword.strip():
            raise ValueError("Bluesky keywords must not have leading or trailing whitespace")
        if any(unicodedata.category(character).startswith("C") for character in self.keyword):
            raise ValueError("Bluesky keywords must not contain control characters")
        if not normalize_keyword(self.keyword):
            raise ValueError("Bluesky keywords must contain a searchable token")
        return self


class BlueskyKeywordDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    default_enabled: Literal[False] = False
    collection: Literal["app.bsky.feed.post"] = "app.bsky.feed.post"
    operations: tuple[Literal["create", "update", "delete"], ...] = BLUESKY_FILTER_OPERATIONS
    keywords: tuple[BlueskyKeyword, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def normalize_keyword_shorthand(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        # A short list of strings is convenient in fixtures, but is normalized
        # into the same immutable named form before validation.
        raw_keywords = data.get("keywords", ())
        if isinstance(raw_keywords, (list, tuple)):
            data["keywords"] = [
                {
                    "name": normalize_keyword(item).replace(" ", "-"),
                    "keyword": item,
                    "group": "activity",
                }
                if isinstance(item, str)
                else item
                for item in raw_keywords
            ]
        return data

    @model_validator(mode="after")
    def validate_registry(self) -> Self:
        if self.default_enabled is not False:
            raise ValueError("Bluesky keyword registry must remain disabled by default")
        if self.collection != BLUESKY_POST_COLLECTION:
            raise ValueError("Bluesky registry collection is not approved")
        if self.operations != BLUESKY_FILTER_OPERATIONS:
            raise ValueError("Bluesky registry operations must remain create/update/delete")
        configured = tuple((item.name, item.keyword, item.group) for item in self.keywords)
        if configured != REQUIRED_BLUESKY_KEYWORDS:
            raise ValueError("Bluesky registry must contain the exact approved keyword list")
        names = [item.name for item in self.keywords]
        if len(names) != len(set(names)):
            raise ValueError("Bluesky registry keyword names must be unique")
        if not any(item.group == "identity" for item in self.keywords):
            raise ValueError("Bluesky registry requires identity keywords")
        if not any(item.group == "activity" for item in self.keywords):
            raise ValueError("Bluesky registry requires activity keywords")
        return self


class BlueskyKeywordRegistry:
    """Immutable matcher for the exact configured post keyword inventory."""

    __slots__ = ("_document", "_normalized")
    _document: BlueskyKeywordDocument
    _normalized: tuple[str, ...]

    def __init__(self, document: BlueskyKeywordDocument) -> None:
        object.__setattr__(self, "_document", document)
        object.__setattr__(
            self,
            "_normalized",
            tuple(normalize_keyword(item.keyword) for item in self.keywords),
        )

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("Bluesky keyword registry is immutable")
        object.__setattr__(self, name, value)

    @property
    def version(self) -> Literal[1]:
        return self._document.version

    @property
    def default_enabled(self) -> Literal[False]:
        return self._document.default_enabled

    @property
    def collection(self) -> Literal["app.bsky.feed.post"]:
        return self._document.collection

    @property
    def operations(self) -> tuple[Literal["create", "update", "delete"], ...]:
        return self._document.operations

    @property
    def keywords(self) -> tuple[BlueskyKeyword, ...]:
        return self._document.keywords

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> BlueskyKeywordRegistry:
        return cls(BlueskyKeywordDocument.model_validate(value))

    @classmethod
    def from_yaml(cls, path: str | Path) -> BlueskyKeywordRegistry:
        return cls.from_mapping(_yaml_mapping(path))

    @property
    def enabled_keywords(self) -> tuple[BlueskyKeyword, ...]:
        return self.keywords

    def matches(self, text: str) -> tuple[str, ...]:
        """Return matching registry names, preserving registry order."""

        normalized_text = normalize_keyword(text)
        if not normalized_text:
            return ()
        padded = f" {normalized_text} "
        matched = tuple(
            item.name
            for item, keyword in zip(self.keywords, self._normalized, strict=True)
            if (
                # Identity terms and the deliberately short TCG acronym may
                # be concatenated by hashtags or CJK text (for example
                # ``#PokemonTCG`` and ``ポケモンカード開封``).  Generic
                # Latin activity words stay token/phrase bounded to avoid
                # matching unrelated words such as ``packing``.
                (item.group == "identity" or item.name == "tcg" or not keyword.isascii())
                and keyword in normalized_text
            )
            or (
                item.group == "activity"
                and item.name != "tcg"
                and keyword.isascii()
                and f" {keyword} " in padded
            )
        )
        matched_groups = {item.group for item in self.keywords if item.name in matched}
        if not {"identity", "activity"} <= matched_groups:
            return ()
        return matched

    def require(self, name: str) -> BlueskyKeyword:
        for item in self.keywords:
            if item.name == name:
                return item
        raise ValueError("Bluesky keyword name is not in the approved registry")


__all__ = [
    "BLUESKY_FILTER_OPERATIONS",
    "BLUESKY_POST_COLLECTION",
    "BlueskyKeyword",
    "BlueskyKeywordDocument",
    "BlueskyKeywordRegistry",
    "REQUIRED_BLUESKY_KEYWORDS",
    "normalize_keyword",
]
