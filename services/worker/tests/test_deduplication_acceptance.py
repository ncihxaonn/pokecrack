from __future__ import annotations

from pokecrack_worker.deduplication import (
    AudioFingerprintProvider,
    DuplicateCluster,
    VideoFingerprintProvider,
    suspect_duplicate,
)
from pokecrack_worker.models import SourceItemCandidate


def test_media_fingerprint_interfaces_and_duplicate_cluster_are_fail_closed_placeholders() -> None:
    assert hasattr(VideoFingerprintProvider, "fingerprint_video")
    assert hasattr(AudioFingerprintProvider, "fingerprint_audio")

    cluster = DuplicateCluster(cluster_id="synthetic-cluster", member_ids=("one", "two"))
    assert cluster.suspected is True
    assert cluster.statistics_eligible is False
    assert cluster.auto_merge is False


def test_every_suspected_duplicate_is_statistics_ineligible() -> None:
    left = SourceItemCandidate(
        source_url="https://example.com/opening/one",
        collector="manual_import",
        text="same synthetic content",
    )
    right = SourceItemCandidate(
        source_url="https://example.com/opening/two",
        collector="manual_import",
        text="same synthetic content",
    )

    suspicion = suspect_duplicate(left, right)

    assert suspicion.suspected is True
    assert suspicion.statistics_eligible is False
