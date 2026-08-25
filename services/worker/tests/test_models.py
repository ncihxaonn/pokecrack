import hashlib

import pytest
from pydantic import ValidationError

from pokecrack_worker.models import SourceItemCandidate


def test_source_candidate_derives_canonical_identity_and_content_hash() -> None:
    candidate = SourceItemCandidate(
        source_url=("https://www.youtube.com/watch?v=dQw4w9WgXcQ&utm_campaign=launch"),
        collector="official_api",
        title="Booster box opening",
        content="three packs, one rare",
    )

    assert candidate.canonical_url == ("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert candidate.platform == "youtube"
    assert candidate.platform_id == "dQw4w9WgXcQ"
    assert candidate.content_sha256 == hashlib.sha256(b"three packs, one rare").hexdigest()


def test_source_candidate_rejects_unbounded_excerpt() -> None:
    with pytest.raises(ValidationError, match="string_too_long"):
        SourceItemCandidate(
            source_url="https://retailer.example/opening/1",
            collector="manual_import",
            excerpt="x" * 4_001,
        )


def test_source_candidate_serializes_exact_bounded_public_collector_contract() -> None:
    candidate = SourceItemCandidate(
        platform="youtube",
        external_id="dQw4w9WgXcQ",
        source_url="https://youtube.com/watch?v=dQw4w9WgXcQ&utm_source=test",
        title="Fixture opening",
        text="six packs",
        published_at="2026-08-25T00:00:00Z",
        author_hash="a" * 64,
        media_urls=("https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",),
        metadata={"fixture": True},
        collector="official_api",
        collector_version="youtube-data-v3",
        source_policy_version="1",
    )

    assert set(candidate.model_dump()) == {
        "platform",
        "external_id",
        "source_url",
        "title",
        "text",
        "published_at",
        "author_hash",
        "media_urls",
        "metadata",
        "collector",
        "collector_version",
        "source_policy_version",
    }
    assert candidate.normalized_url == "https://youtube.com/watch?v=dQw4w9WgXcQ"
    assert candidate.content_hash == hashlib.sha256(b"six packs").hexdigest()


def test_source_candidate_rejects_text_above_twenty_thousand_characters() -> None:
    with pytest.raises(ValidationError, match="string_too_long"):
        SourceItemCandidate(
            platform="web",
            source_url="https://example.com/opening/1",
            text="x" * 20_001,
            collector="scrapling_http",
            collector_version="fixture-v1",
            source_policy_version="1",
        )


def test_source_candidate_rejects_legacy_collector_aliases() -> None:
    for alias in ("youtube", "catalog", "static", "dynamic", "opencli", "manual"):
        with pytest.raises(ValidationError):
            SourceItemCandidate(
                source_url="https://example.com/opening/1",
                collector=alias,
            )
