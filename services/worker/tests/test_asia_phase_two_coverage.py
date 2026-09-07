from __future__ import annotations

import json
from pathlib import Path

import pytest

from pokecrack_worker.collectors.base import CollectorError, FetchResponse
from pokecrack_worker.collectors.scrapling.adapters.asia_coverage import (
    EVIDENCE_EXCERPT,
    EVIDENCE_SHA256,
    IDENTITY,
    POLICY_CONFIG,
    TITLE,
    garbage_rips_gem_vol2_adapter,
)
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]


def document() -> str:
    metadata = {
        "@type": "VideoObject",
        "name": TITLE,
        "uploadDate": POLICY_CONFIG["observed_at"],
        "url": IDENTITY.source_url,
        "embedUrl": "https://www.youtube.com/embed/8jKHh-P7P7M",
    }
    return (
        '<script type="application/ld+json">' + json.dumps(metadata) + "</script>"
        "<main><h1>" + TITLE + "</h1><p>One pack. Eeveelutions.</p></main>"
    )


class FixtureClient:
    def __init__(self, body: str) -> None:
        self.body = body
        self.calls: list[str] = []

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls.append(url)
        return FetchResponse(
            status_code=200,
            url=url,
            headers={"content-type": "text/html"},
            body=self.body.encode(),
        )


def test_single_pack_is_product_market_evidence_without_a_rate() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        IDENTITY.fetch_url
    )
    client = FixtureClient(document())
    item = garbage_rips_gem_vol2_adapter(client=client).collect(IDENTITY.fetch_url, policy)[0]
    assert policy.config == POLICY_CONFIG
    assert policy.config["geography_basis"] == "product_market"
    assert policy.config["pack_count"] == 1
    assert "qualifying_hit_pack_count" not in policy.config
    assert item.text == EVIDENCE_EXCERPT
    assert item.content_sha256 == EVIDENCE_SHA256
    assert item.media_urls == ()
    assert client.calls == [IDENTITY.fetch_url]


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("One pack.", "Two packs."),
        ("Chinese Gem Pack Vol 2", "Japanese Gem Pack Vol 2"),
        ("2026-02-13T13:30:09Z", "2026-02-14T13:30:09Z"),
        ("8jKHh-P7P7M", "another-video"),
        ('"@type": "VideoObject"', '"@type": "Article"'),
    ],
)
def test_drift_fails_closed(before: str, after: str) -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
        IDENTITY.fetch_url
    )
    with pytest.raises(CollectorError):
        garbage_rips_gem_vol2_adapter(
            client=FixtureClient(document().replace(before, after))
        ).collect(IDENTITY.fetch_url, policy)
