"""Bounded fixture-safe adapter for the IANA ``example.com`` page only."""

from __future__ import annotations

from urllib.parse import urlsplit

from pokecrack_worker.collectors.base import CollectorError, HTTPClient
from pokecrack_worker.config.source_policy import SourcePolicy
from pokecrack_worker.deduplication.urls import canonicalize_url
from pokecrack_worker.models import CollectorType, SourceItemCandidate

from ._html import parse_metadata


def _header(headers: object, name: str) -> str:
    if not hasattr(headers, "items"):
        return ""
    expected = name.casefold()
    return next(
        (str(value) for key, value in headers.items() if str(key).casefold() == expected),
        "",
    )


def _require_exact_https_domain(url: str, domain: str) -> str:
    normalized = canonicalize_url(url)
    parsed = urlsplit(normalized)
    if parsed.scheme != "https" or parsed.hostname != domain:
        raise CollectorError(f"adapter accepts only https://{domain} URLs")
    return normalized


class ExamplePublicAdapter:
    """Parse bounded title/text metadata and immediately discard transport HTML."""

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
        if policy.domain != "example.com" or policy.collector is not CollectorType.SCRAPLING_HTTP:
            raise CollectorError("example adapter requires the example.com scrapling_http policy")
        if policy.retain_raw_html is not False:
            raise CollectorError("raw HTML retention is prohibited")
        _require_exact_https_domain(url, "example.com")
        response = self.client.get(url, timeout_seconds=self.timeout_seconds)
        _require_exact_https_domain(response.url, "example.com")
        if response.status_code != 200:
            raise CollectorError(f"public adapter HTTP status {response.status_code}")
        if len(response.body) > self.max_response_bytes:
            raise CollectorError("public response exceeds configured byte cap")
        content_type = _header(response.headers, "content-type").casefold()
        if "text/html" not in content_type:
            raise CollectorError("public adapter expected text/html")
        title, text = parse_metadata(response.body, max_text_chars=self.max_text_chars)
        return (
            SourceItemCandidate(
                platform="web",
                source_url=response.url,
                collector=policy.collector,
                collector_version=str(policy.config.get("collector_version", "example-public-v1")),
                source_policy_version=policy.version,
                title=title,
                text=text,
                metadata={
                    "adapter": "example_public",
                    "content_type": content_type.split(";", maxsplit=1)[0],
                    "metadata_only": True,
                    "synthetic": True,
                },
            ),
        )
