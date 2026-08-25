"""Deduplication helpers and interfaces."""

from .fingerprints import (
    AudioFingerprintProvider,
    DuplicateCluster,
    DuplicateSuspicion,
    ImagePHashProvider,
    ImagePHashUnavailable,
    MediaFingerprintUnavailable,
    OptionalImagePHashProvider,
    VideoFingerprintProvider,
    content_sha256,
    suspect_duplicate,
)
from .urls import PlatformIdentity, canonicalize_url, extract_platform_id

__all__ = [
    "AudioFingerprintProvider",
    "DuplicateCluster",
    "DuplicateSuspicion",
    "ImagePHashProvider",
    "ImagePHashUnavailable",
    "MediaFingerprintUnavailable",
    "OptionalImagePHashProvider",
    "PlatformIdentity",
    "VideoFingerprintProvider",
    "canonicalize_url",
    "content_sha256",
    "extract_platform_id",
    "suspect_duplicate",
]
