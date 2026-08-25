"""Static HTTP transport backed by lazy Scrapling bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pokecrack_worker.collectors.base import FetchResponse

from .backend import ScraplingBackend


class HTTPBackend(Protocol):
    def fetch_http(self, url: str, *, timeout_seconds: float) -> FetchResponse: ...


@dataclass(slots=True)
class ScraplingHTTPClient:
    """The only static Scrapling transport path; it has no fallback/escalation."""

    backend: HTTPBackend
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not 0 < self.timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be in (0, 120]")

    @classmethod
    def live(cls, *, timeout_seconds: float = 30.0) -> ScraplingHTTPClient:
        return cls(backend=ScraplingBackend(), timeout_seconds=timeout_seconds)

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        if not 0 < timeout <= 120:
            raise ValueError("timeout_seconds must be in (0, 120]")
        return self.backend.fetch_http(url, timeout_seconds=timeout)
