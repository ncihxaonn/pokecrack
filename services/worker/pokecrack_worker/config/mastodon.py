"""Frozen, reviewable Mastodon instance and hashtag registry.

The worker intentionally has one instance and one fixed set of hashtag values.
Jobs carry only an ASCII instance key and tag key; URLs, domains, and raw
hashtag values are resolved here and cannot be supplied by an operator or an
upstream response.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Self
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

MASTODON_INSTANCE_KEY = "mastodon_social"
MASTODON_DOMAIN = "mastodon.social"
MASTODON_ORIGIN = "https://mastodon.social"
MASTODON_BASE_URL = "https://mastodon.social/"
MASTODON_INSTANCE_URL = "https://mastodon.social/api/v2/instance"
MASTODON_RULES_URL = "https://mastodon.social/api/v1/instance/rules"
MASTODON_TERMS_URL = "https://mastodon.social/api/v1/instance/terms_of_service"
MASTODON_HASHTAG_BASE_URL = "https://mastodon.social/api/v1/timelines/tag/"
MASTODON_OFFICIAL_DOCS_URL = "https://docs.joinmastodon.org/methods/timelines/"
MASTODON_POLICY_STATE = "reviewed_public_api_2026-08-31"
MASTODON_TERMS_EFFECTIVE_DATE = "2026-08-31"

# ``tag_key`` values are deliberately ASCII and stable for queue payloads and
# schedule names.  The second member is the exact canonical hashtag sent in
# the fixed endpoint path and compared with returned tag names.
MASTODON_TAG_ROWS: tuple[tuple[str, str], ...] = (
    ("pokemontcg", "pokemontcg"),
    ("pokemoncards", "pokemoncards"),
    ("pokeca_ja", "ポケカ"),
    ("pokemon_card_ja", "ポケモンカード"),
    ("pokemon_card_ko", "포켓몬카드"),
    ("pokemon_card_zh_hans", "宝可梦卡牌"),
    ("pokemon_card_zh_hant", "寶可夢卡牌"),
)
MASTODON_APPROVED_TAGS: tuple[str, ...] = tuple(value for _key, value in MASTODON_TAG_ROWS)
MASTODON_TAG_KEYS: tuple[str, ...] = tuple(key for key, _value in MASTODON_TAG_ROWS)
MASTODON_APPROVED_TAG_MAP: Mapping[str, str] = MappingProxyType(dict(MASTODON_TAG_ROWS))


def normalize_mastodon_tag(value: str) -> str:
    """Normalize a returned tag only for allowlist matching."""

    return unicodedata.normalize("NFKC", value).casefold()


class MastodonTag(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    value: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_value(self) -> Self:
        if self.value != self.value.strip():
            raise ValueError("Mastodon tags must not have leading or trailing whitespace")
        if any(unicodedata.category(character).startswith("C") for character in self.value):
            raise ValueError("Mastodon tags must not contain control characters")
        return self


class MastodonInstance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: Literal["mastodon_social"] = "mastodon_social"
    domain: Literal["mastodon.social"] = "mastodon.social"
    base_url: Literal["https://mastodon.social/"] = "https://mastodon.social/"
    instance_url: Literal["https://mastodon.social/api/v2/instance"] = (
        "https://mastodon.social/api/v2/instance"
    )
    rules_url: Literal["https://mastodon.social/api/v1/instance/rules"] = (
        "https://mastodon.social/api/v1/instance/rules"
    )
    terms_url: Literal["https://mastodon.social/api/v1/instance/terms_of_service"] = (
        "https://mastodon.social/api/v1/instance/terms_of_service"
    )
    hashtag_base_url: Literal["https://mastodon.social/api/v1/timelines/tag/"] = (
        "https://mastodon.social/api/v1/timelines/tag/"
    )
    official_docs_url: Literal["https://docs.joinmastodon.org/methods/timelines/"] = (
        "https://docs.joinmastodon.org/methods/timelines/"
    )

    @model_validator(mode="after")
    def validate_origins(self) -> Self:
        for field_name in (
            "base_url",
            "instance_url",
            "rules_url",
            "terms_url",
            "hashtag_base_url",
            "official_docs_url",
        ):
            parsed = urlsplit(getattr(self, field_name))
            if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
                raise ValueError(
                    "Mastodon registry URLs must be HTTPS without credentials/fragments"
                )
        return self


class MastodonDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    default_enabled: Literal[False] = False
    protocol: Literal["rest"] = "rest"
    instances: tuple[MastodonInstance, ...]
    tags: tuple[MastodonTag, ...]

    @model_validator(mode="after")
    def validate_exact_inventory(self) -> Self:
        if (
            len(self.instances) != 1
            or self.instances[0].model_dump() != MastodonInstance().model_dump()
        ):
            raise ValueError("Mastodon registry must contain the exact reviewed instance")
        rows = tuple((item.key, item.value) for item in self.tags)
        if rows != MASTODON_TAG_ROWS:
            raise ValueError("Mastodon registry must contain the exact approved tag inventory")
        if len({item.key for item in self.tags}) != len(self.tags):
            raise ValueError("Mastodon tag keys must be unique")
        if len({normalize_mastodon_tag(item.value) for item in self.tags}) != len(self.tags):
            raise ValueError("Mastodon tag values must be unique after normalization")
        return self


class MastodonRegistry:
    """Immutable resolver for the one reviewed instance and seven tags."""

    __slots__ = ("_document", "_instances", "_tags", "_normalized_tags")
    _document: MastodonDocument
    _instances: Mapping[str, MastodonInstance]
    _tags: Mapping[str, MastodonTag]
    _normalized_tags: Mapping[str, MastodonTag]

    def __init__(self, document: MastodonDocument) -> None:
        object.__setattr__(self, "_document", document)
        object.__setattr__(
            self,
            "_instances",
            MappingProxyType({item.key: item for item in document.instances}),
        )
        object.__setattr__(
            self,
            "_tags",
            MappingProxyType({item.key: item for item in document.tags}),
        )
        object.__setattr__(
            self,
            "_normalized_tags",
            MappingProxyType({normalize_mastodon_tag(item.value): item for item in document.tags}),
        )

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("Mastodon registry is immutable")
        object.__setattr__(self, name, value)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MastodonRegistry:
        return cls(MastodonDocument.model_validate(value))

    @classmethod
    def reviewed(cls) -> MastodonRegistry:
        """Return the compiled reviewed inventory for parser-only callers."""

        return cls(
            MastodonDocument(
                instances=(MastodonInstance(),),
                tags=tuple(MastodonTag(key=key, value=value) for key, value in MASTODON_TAG_ROWS),
            )
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> MastodonRegistry:
        with Path(path).open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
        if not isinstance(value, Mapping):
            raise ValueError("Mastodon registry YAML must contain a mapping")
        return cls.from_mapping(value)

    @property
    def version(self) -> Literal[1]:
        return self._document.version

    @property
    def default_enabled(self) -> Literal[False]:
        return self._document.default_enabled

    @property
    def protocol(self) -> Literal["rest"]:
        return self._document.protocol

    @property
    def instances(self) -> tuple[MastodonInstance, ...]:
        return self._document.instances

    @property
    def tags(self) -> tuple[MastodonTag, ...]:
        return self._document.tags

    @property
    def approved_tags(self) -> Mapping[str, str]:
        return MASTODON_APPROVED_TAG_MAP

    def require_instance(self, instance_key: str) -> MastodonInstance:
        if not isinstance(instance_key, str):
            raise ValueError("Mastodon instance key is not approved")
        try:
            return self._instances[instance_key]
        except KeyError:
            raise ValueError("Mastodon instance key is not approved") from None

    # Keep the short resolver name consistent with the other registries.
    require = require_instance

    def require_tag(self, tag_key: str) -> MastodonTag:
        if not isinstance(tag_key, str):
            raise ValueError("Mastodon tag key is not approved")
        try:
            return self._tags[tag_key]
        except KeyError:
            raise ValueError("Mastodon tag key is not approved") from None

    def matched_tag_keys(self, raw_tags: object) -> tuple[str, ...]:
        """Return only approved ASCII keys for returned Mastodon tag names."""

        if not isinstance(raw_tags, list):
            return ()
        matches: set[str] = set()
        for raw_tag in raw_tags:
            if not isinstance(raw_tag, Mapping):
                continue
            value = raw_tag.get("name")
            if not isinstance(value, str) or not value or len(value) > 128:
                continue
            tag = self._normalized_tags.get(normalize_mastodon_tag(value))
            if tag is not None:
                matches.add(tag.key)
        return tuple(item.key for item in self.tags if item.key in matches)


# Explicit aliases make the boundary discoverable to callers without creating
# a second mutable registry implementation.
MastodonInstanceRegistry = MastodonRegistry
MastodonConfig = MastodonDocument

__all__ = [
    "MASTODON_APPROVED_TAG_MAP",
    "MASTODON_APPROVED_TAGS",
    "MASTODON_BASE_URL",
    "MASTODON_DOMAIN",
    "MASTODON_HASHTAG_BASE_URL",
    "MASTODON_INSTANCE_KEY",
    "MASTODON_INSTANCE_URL",
    "MASTODON_OFFICIAL_DOCS_URL",
    "MASTODON_ORIGIN",
    "MASTODON_POLICY_STATE",
    "MASTODON_RULES_URL",
    "MASTODON_TAG_KEYS",
    "MASTODON_TAG_ROWS",
    "MASTODON_TERMS_EFFECTIVE_DATE",
    "MASTODON_TERMS_URL",
    "MastodonConfig",
    "MastodonDocument",
    "MastodonInstance",
    "MastodonInstanceRegistry",
    "MastodonRegistry",
    "MastodonTag",
    "normalize_mastodon_tag",
]
