"""Synthetic dynamic adapter used to verify policy/browser boundaries without I/O."""

from __future__ import annotations

from urllib.parse import urlsplit

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.source_policy import SourcePolicy
from pokecrack_worker.deduplication.urls import canonicalize_url
from pokecrack_worker.models import CollectorType, SourceItemCandidate

from ._html import parse_metadata
from .example_public import _header


def _require_dynamic_fixture_url(url: str) -> None:
    normalized = canonicalize_url(url)
    parsed = urlsplit(normalized)
    if parsed.scheme != "https" or parsed.hostname != "dynamic.example":
        raise CollectorError("dynamic fixture accepts only https://dynamic.example URLs")


class DynamicFixtureAdapter:
    """Exercise a dynamic response path only when the exact policy allows it."""

    def __init__(
        self,
        *,
        client: HTTPClient,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 1_000_000,
        max_text_chars: int = 20_000,
    ) -> None:
        if not 0 < timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be in (0, 120]")
        if not 1 <= max_response_bytes <= 10_000_000:
            raise ValueError("max_response_bytes must be between 1 and 10000000")
        if not 1 <= max_text_chars <= 20_000:
            raise ValueError("max_text_chars must be between 1 and 20000")
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_text_chars = max_text_chars

    def collect(self, url: str, policy: SourcePolicy) -> tuple[SourceItemCandidate, ...]:
        if not policy.dynamic_allowed:
            raise CollectorError("dynamic_allowed policy is required")
        if (
            policy.domain != "dynamic.example"
            or policy.collector is not CollectorType.SCRAPLING_DYNAMIC
        ):
            raise CollectorError("dynamic fixture requires its exact scrapling_dynamic policy")
        if policy.retain_raw_html is not False:
            raise CollectorError("raw HTML retention is prohibited")
        _require_dynamic_fixture_url(url)
        response = self.client.get(url, timeout_seconds=self.timeout_seconds)
        _require_dynamic_fixture_url(response.url)
        if response.status_code != 200:
            raise CollectorError(f"dynamic adapter HTTP status {response.status_code}")
        if len(response.body) > self.max_response_bytes:
            raise CollectorError("dynamic response exceeds configured byte cap")
        content_type = _header(response.headers, "content-type").casefold()
        if "text/html" not in content_type:
            raise CollectorError("dynamic adapter expected text/html")
        title, text = parse_metadata(response.body, max_text_chars=self.max_text_chars)
        return (
            SourceItemCandidate(
                platform="web",
                source_url=response.url,
                collector=policy.collector,
                collector_version=str(policy.config.get("collector_version", "dynamic-fixture-v1")),
                source_policy_version=policy.version,
                title=title,
                text=text,
                metadata={
                    "adapter": "dynamic_fixture",
                    "content_type": content_type.split(";", maxsplit=1)[0],
                    "metadata_only": True,
                    "rendered": True,
                    "synthetic": True,
                },
            ),
        )
