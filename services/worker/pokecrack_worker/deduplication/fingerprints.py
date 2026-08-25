"""Content, optional image fingerprints, and conservative duplicate suspicion."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol, runtime_checkable


def content_sha256(content: str | bytes) -> str:
    """Hash the exact UTF-8 content bytes with SHA-256."""

    value = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(value).hexdigest()


class MediaFingerprintUnavailable(RuntimeError):
    """No video/audio implementation is enabled in the base worker."""


@runtime_checkable
class VideoFingerprintProvider(Protocol):
    """Future bounded video-fingerprint adapter; full video retention is prohibited."""

    def fingerprint_video(self, media: bytes) -> str: ...


@runtime_checkable
class AudioFingerprintProvider(Protocol):
    """Future bounded audio-fingerprint adapter interface."""

    def fingerprint_audio(self, media: bytes) -> str: ...


@dataclass(frozen=True, slots=True)
class DuplicateCluster:
    """Auditable placeholder; clustered/suspected members never enter statistics."""

    cluster_id: str
    member_ids: tuple[str, ...]
    suspected: bool = True
    statistics_eligible: bool = False
    auto_merge: bool = False

    def __post_init__(self) -> None:
        if not self.cluster_id.strip() or len(self.member_ids) < 2:
            raise ValueError("duplicate cluster requires an id and at least two members")
        if any(not member.strip() for member in self.member_ids):
            raise ValueError("duplicate cluster member ids must be non-empty")
        if self.statistics_eligible or self.auto_merge:
            raise ValueError("duplicate cluster placeholders must remain review-only")


class ImagePHashUnavailable(RuntimeError):
    """Raised when the optional Pillow/imagehash implementation is unavailable."""


@runtime_checkable
class ImagePHashProvider(Protocol):
    """Interface used by collectors without making image dependencies mandatory."""

    def phash(self, image: bytes) -> str: ...


class OptionalImagePHashProvider:
    """Perceptual hash adapter loaded only when explicitly used."""

    def phash(self, image: bytes) -> str:
        try:
            import imagehash  # type: ignore[import-not-found]
            from PIL import Image  # type: ignore[import-not-found]
        except ImportError as error:
            raise ImagePHashUnavailable(
                "image pHash requires the optional 'images' dependencies"
            ) from error
        if not image:
            raise ValueError("image bytes must not be empty")
        try:
            with Image.open(BytesIO(image)) as decoded:
                return str(imagehash.phash(decoded.convert("RGB")))
        except (OSError, ValueError) as error:
            raise ValueError("image bytes could not be decoded") from error


def phash_hamming_distance(left: str, right: str) -> int:
    """Return bit distance for equal-width hexadecimal perceptual hashes."""

    if not left or len(left) != len(right):
        raise ValueError("pHash values must be non-empty and have equal width")
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError as error:
        raise ValueError("pHash values must be hexadecimal") from error


class FingerprintedCandidate(Protocol):
    canonical_url: str | None
    platform: str | None
    platform_id: str | None
    content_sha256: str | None
    collector: object


@dataclass(frozen=True, slots=True)
class DuplicateSuspicion:
    """Evidence for review; suspicion never silently merges observations."""

    suspected: bool
    reasons: tuple[str, ...]
    cross_platform: bool
    auto_merge: bool = False
    image_phash_distance: int | None = None
    statistics_eligible: bool = False


def _channel(candidate: FingerprintedCandidate) -> str:
    if candidate.platform:
        return candidate.platform
    value = getattr(candidate.collector, "value", candidate.collector)
    return str(value)


def suspect_duplicate(
    left: FingerprintedCandidate,
    right: FingerprintedCandidate,
    *,
    left_image_phash: str | None = None,
    right_image_phash: str | None = None,
    max_phash_distance: int = 6,
) -> DuplicateSuspicion:
    """Combine stable duplicate signals while preserving a human/audit review step."""

    if max_phash_distance < 0:
        raise ValueError("max_phash_distance must be non-negative")
    reasons: list[str] = []
    if left.canonical_url and left.canonical_url == right.canonical_url:
        reasons.append("canonical_url")
    if (
        left.platform
        and left.platform == right.platform
        and left.platform_id
        and left.platform_id == right.platform_id
    ):
        reasons.append("platform_id")
    if (
        left.content_sha256
        and left.content_sha256 == right.content_sha256
        and "canonical_url" not in reasons
    ):
        reasons.append("content_sha256")

    distance: int | None = None
    if left_image_phash is not None and right_image_phash is not None:
        distance = phash_hamming_distance(left_image_phash, right_image_phash)
        if distance <= max_phash_distance:
            reasons.append("image_phash")

    cross_platform = _channel(left) != _channel(right)
    stable_identity = "canonical_url" in reasons or "platform_id" in reasons
    return DuplicateSuspicion(
        suspected=bool(reasons),
        reasons=tuple(reasons),
        cross_platform=cross_platform,
        auto_merge=stable_identity and not cross_platform,
        image_phash_distance=distance,
    )
