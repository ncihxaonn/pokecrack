import pytest

from pokecrack_worker.deduplication.urls import (
    PlatformIdentity,
    canonicalize_url,
    extract_platform_id,
)


def test_canonicalize_url_removes_tracking_and_normalizes_order() -> None:
    raw = (
        "HTTPS://Example.COM:443/products/card/?utm_source=newsletter&b=2&fbclid=secret&a=1#details"
    )

    assert canonicalize_url(raw) == "https://example.com/products/card?a=1&b=2"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&utm_source=x",
        "https://youtu.be/dQw4w9WgXcQ?t=5",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
    ],
)
def test_extract_platform_id_recognizes_youtube_url_forms(url: str) -> None:
    assert extract_platform_id(url) == PlatformIdentity(
        platform="youtube", external_id="dQw4w9WgXcQ"
    )


@pytest.mark.parametrize(
    ("url", "platform", "external_id"),
    [
        ("https://www.reddit.com/r/pkmntcg/comments/abc123/opening/", "reddit", "abc123"),
        ("https://x.com/example/status/1234567890?s=20", "x", "1234567890"),
        ("https://www.bilibili.com/video/BV1xx411c7mD", "bilibili", "BV1xx411c7mD"),
        ("https://www.xiaohongshu.com/explore/64abc123def456", "xiaohongshu", "64abc123def456"),
    ],
)
def test_extract_platform_id_recognizes_supported_social_metadata_urls(
    url: str, platform: str, external_id: str
) -> None:
    assert extract_platform_id(url) == PlatformIdentity(platform=platform, external_id=external_id)
