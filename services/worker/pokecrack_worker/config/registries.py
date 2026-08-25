"""Validated YouTube query and rarity taxonomy registries."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

REQUIRED_YOUTUBE_QUERIES: tuple[tuple[str, str], ...] = (
    ("pokemon-tcg-opening-australia", "Pokemon TCG opening Australia"),
    ("pokemon-booster-box-opening-melbourne", "Pokemon booster box opening Melbourne"),
    ("pokemon-etb-opening-australia", "Pokemon ETB opening Australia"),
    ("pokemon-booster-bundle-opening-sydney", "Pokemon booster bundle opening Sydney"),
    ("pokemon-card-opening-batch-code", "Pokemon card opening batch code"),
)


def _yaml_mapping(path: str | Path) -> Mapping[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


class YouTubeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=500)
    enabled: bool = False
    metadata_only: Literal[True] = True
    max_results: int = Field(default=25, ge=1, le=50)
    region_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    published_within_days: int = Field(default=30, ge=1, le=3650)
    order: Literal["date", "relevance"] = "date"


class YouTubeQueryDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    default_enabled: Literal[False] = False
    queries: tuple[YouTubeQuery, ...] = ()

    @model_validator(mode="after")
    def unique_names(self) -> Self:
        names = [query.name for query in self.queries]
        if len(names) != len(set(names)):
            raise ValueError("YouTube query names must be unique")
        configured = tuple((query.name, query.query) for query in self.queries)
        if configured != REQUIRED_YOUTUBE_QUERIES:
            raise ValueError("YouTube registry must contain the exact five approved queries")
        return self


class YouTubeQueryRegistry:
    def __init__(self, document: YouTubeQueryDocument) -> None:
        self.default_enabled = document.default_enabled
        self.queries = document.queries

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> YouTubeQueryRegistry:
        return cls(YouTubeQueryDocument.model_validate(value))

    @classmethod
    def from_yaml(cls, path: str | Path) -> YouTubeQueryRegistry:
        return cls.from_mapping(_yaml_mapping(path))

    @property
    def enabled_queries(self) -> tuple[YouTubeQuery, ...]:
        return tuple(query for query in self.queries if query.enabled)


class RarityClass(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=128)
    aliases: tuple[str, ...] = ()
    statistics_eligible: bool = True


class RarityTaxonomyDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    baseline_priority: tuple[tuple[Literal["set_id", "language", "product_type"], ...], ...]
    chase_categories: tuple[str, ...] = ()
    rarities: tuple[RarityClass, ...]

    @model_validator(mode="after")
    def validate_taxonomy(self) -> Self:
        keys = [rarity.key for rarity in self.rarities]
        if len(keys) != len(set(keys)):
            raise ValueError("rarity keys must be unique")
        if "unknown" not in keys:
            raise ValueError("rarity taxonomy requires an unknown fallback")
        expected = (
            ("set_id", "language", "product_type"),
            ("set_id", "language"),
            ("set_id",),
        )
        if self.baseline_priority != expected:
            raise ValueError("baseline priority must use the documented fallback hierarchy")
        unknown_chase = sorted(set(self.chase_categories) - set(keys))
        if unknown_chase:
            raise ValueError("unknown chase categories: " + ", ".join(unknown_chase))
        return self


def normalize_rarity(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain.casefold()).split())


class RarityTaxonomy:
    def __init__(self, document: RarityTaxonomyDocument) -> None:
        self.baseline_priority = document.baseline_priority
        self.baseline_scope = document.baseline_priority[0]
        self.chase_categories = document.chase_categories
        self.rarities = document.rarities
        self._unknown = next(rarity for rarity in self.rarities if rarity.key == "unknown")
        aliases: dict[str, RarityClass] = {}
        for rarity in self.rarities:
            for value in (rarity.key, rarity.label, *rarity.aliases):
                normalized = normalize_rarity(value)
                prior = aliases.get(normalized)
                if prior is not None and prior.key != rarity.key:
                    raise ValueError(f"duplicate rarity alias: {value}")
                aliases[normalized] = rarity
        self._aliases = aliases

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RarityTaxonomy:
        return cls(RarityTaxonomyDocument.model_validate(value))

    @classmethod
    def from_yaml(cls, path: str | Path) -> RarityTaxonomy:
        return cls.from_mapping(_yaml_mapping(path))

    def resolve(self, label: str | None) -> RarityClass:
        if label is None:
            return self._unknown
        return self._aliases.get(normalize_rarity(label), self._unknown)
