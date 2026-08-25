"""Versionable baseline registry with a deliberately narrow fallback chain."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class BaselineLevel(StrEnum):
    SET_LANGUAGE_PRODUCT_TYPE = "set+language+product_type"
    SET_LANGUAGE = "set+language"
    SET = "set"


@dataclass(frozen=True, slots=True)
class Baseline:
    id: str
    set_id: str
    rate: float
    language: str | None = None
    product_type: str | None = None
    version: str = "1"

    def __post_init__(self) -> None:
        if not self.id or not self.set_id or not self.version:
            raise ValueError("baseline id, set_id, and version are required")
        if not math.isfinite(self.rate) or not 0.0 < self.rate < 1.0:
            raise ValueError("baseline rate must be strictly between zero and one")
        if self.product_type is not None and self.language is None:
            raise ValueError("product-specific baselines require a language")


@dataclass(frozen=True, slots=True)
class BaselineSelection:
    baseline: Baseline
    level: BaselineLevel


class BaselineCatalog:
    def __init__(self, baselines: Iterable[Baseline] = ()) -> None:
        self._by_key: dict[tuple[str, str, str | None, str | None], Baseline] = {}
        self._versions: set[str] = set()
        for baseline in baselines:
            key = (baseline.version, baseline.set_id, baseline.language, baseline.product_type)
            if key in self._by_key:
                raise ValueError(f"duplicate baseline scope: {key!r}")
            self._by_key[key] = baseline
            self._versions.add(baseline.version)

    def resolve(
        self,
        set_id: str,
        *,
        language: str,
        product_type: str,
        version: str | None = None,
    ) -> BaselineSelection:
        selected_version = version
        if selected_version is None:
            if not self._versions:
                raise LookupError(f"no baseline for set {set_id!r}")
            if len(self._versions) != 1:
                raise LookupError(
                    "baseline version is required when the catalog contains multiple versions"
                )
            selected_version = next(iter(self._versions))
        candidates = (
            (
                (selected_version, set_id, language, product_type),
                BaselineLevel.SET_LANGUAGE_PRODUCT_TYPE,
            ),
            ((selected_version, set_id, language, None), BaselineLevel.SET_LANGUAGE),
            ((selected_version, set_id, None, None), BaselineLevel.SET),
        )
        for key, level in candidates:
            baseline = self._by_key.get(key)
            if baseline is not None:
                return BaselineSelection(baseline=baseline, level=level)
        raise LookupError(f"no baseline for set {set_id!r} in version {selected_version!r}")


def select_baseline(
    baselines: Iterable[Baseline],
    set_id: str,
    *,
    language: str,
    product_type: str,
    version: str | None = None,
) -> BaselineSelection:
    return BaselineCatalog(baselines).resolve(
        set_id,
        language=language,
        product_type=product_type,
        version=version,
    )
