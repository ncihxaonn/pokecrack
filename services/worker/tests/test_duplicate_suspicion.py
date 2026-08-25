from pokecrack_worker.deduplication.fingerprints import suspect_duplicate
from pokecrack_worker.models import SourceItemCandidate


def test_identical_content_across_platforms_is_flagged_for_review_not_auto_merged() -> None:
    youtube = SourceItemCandidate(
        source_url="https://youtube.com/watch?v=abc12345",
        collector="official_api",
        content="Opened six packs and pulled one illustration rare.",
    )
    manual = SourceItemCandidate(
        source_url="https://example.com/openings/fixture-1",
        collector="manual_import",
        content="Opened six packs and pulled one illustration rare.",
    )

    result = suspect_duplicate(youtube, manual)

    assert result.suspected is True
    assert result.auto_merge is False
    assert result.cross_platform is True
    assert result.reasons == ("content_sha256",)
