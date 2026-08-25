"""Explicit dynamic-browser transport with no static or stealth fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pokecrack_worker.collectors.base import FetchResponse

from .backend import ScraplingBackend


class DynamicBackend(Protocol):
    def fetch_dynamic(self, url: str, *, timeout_seconds: float) -> FetchResponse: ...


@dataclass(slots=True)
class ScraplingDynamicClient:
    """Invoke only Scrapling's approved dynamic fetcher.

    Policy authorization happens in ``CollectionService`` and again in every
    source-specific dynamic adapter. There is deliberately no automatic proxy,
    stealth, authenticated, or CAPTCHA fallback.
    """

    backend: DynamicBackend
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not 0 < self.timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be in (0, 120]")

    @classmethod
    def live(cls, *, timeout_seconds: float = 30.0) -> ScraplingDynamicClient:
        return cls(backend=ScraplingBackend(), timeout_seconds=timeout_seconds)

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        if not 0 < timeout <= 120:
            raise ValueError("timeout_seconds must be in (0, 120]")
        return self.backend.fetch_dynamic(url, timeout_seconds=timeout)
