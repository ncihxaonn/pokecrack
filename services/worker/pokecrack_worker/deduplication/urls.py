"""Stable URL identities used by collection and deduplication."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

_TRACKING_KEYS = frozenset(
    {
        "dclid",
        "fbclid",
        "gclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "ref_src",
        "s_cid",
        "spm",
    }
)
_TRACKING_PREFIXES = ("utm_",)
_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_PLATFORM_ID = re.compile(r"^[A-Za-z0-9_-]{3,128}$")


@dataclass(frozen=True, slots=True)
class PlatformIdentity:
    """Stable identity supplied by a publishing platform."""

    platform: str
    external_id: str


def _is_tracking_key(key: str, host: str | None = None) -> bool:
    lowered = key.casefold()
    if lowered in _TRACKING_KEYS or lowered.startswith(_TRACKING_PREFIXES):
        return True
    normalized_host = (host or "").removeprefix("www.")
    if normalized_host in {"youtube.com", "youtu.be", "m.youtube.com"}:
        return lowered in {"feature", "si", "pp"}
    if normalized_host in {"x.com", "twitter.com", "mobile.twitter.com"}:
        return lowered in {"s", "t"}
    return False


def canonicalize_url(url: str) -> str:
    """Return an HTTP(S) URL stripped of non-identity tracking data."""

    value = url.strip()
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("only http and https URLs can be canonicalized")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not accepted")
    if parsed.hostname is None:
        raise ValueError("URL must contain a hostname")

    host = parsed.hostname.lower().rstrip(".").encode("idna").decode("ascii")
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL contains an invalid port") from exc
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"

    path = quote(parsed.path or "", safe="/%:@!$&'()*+,;=-._~")
    if path != "/":
        path = path.rstrip("/")

    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_key(key, host)
    ]
    query_items.sort(key=lambda item: (item[0], item[1]))
    query = urlencode(query_items, doseq=True)
    return urlunsplit((scheme, host, path, query, ""))


def extract_platform_id(url: str) -> PlatformIdentity | None:
    """Extract a platform-owned identifier when the URL form is recognized."""

    parsed = urlsplit(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = [part for part in parsed.path.split("/") if part]

    external_id: str | None = None
    platform: str | None = None
    if host == "youtu.be":
        external_id = parts[0] if parts else None
        platform = "youtube"
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path.rstrip("/") == "/watch":
            external_id = dict(parse_qsl(parsed.query)).get("v")
        elif len(parts) >= 2 and parts[0] in {"embed", "live", "shorts"}:
            external_id = parts[1]
        platform = "youtube"
    if platform == "youtube":
        if external_id and _YOUTUBE_ID.fullmatch(external_id):
            return PlatformIdentity(platform=platform, external_id=external_id)
        return None

    if host == "redd.it" and parts:
        platform, external_id = "reddit", parts[0]
    elif host in {"reddit.com", "old.reddit.com", "new.reddit.com"}:
        if "comments" in parts:
            index = parts.index("comments")
            if index + 1 < len(parts):
                platform, external_id = "reddit", parts[index + 1]
    elif host in {"x.com", "twitter.com", "mobile.twitter.com"}:
        if "status" in parts:
            index = parts.index("status")
            if index + 1 < len(parts):
                candidate = parts[index + 1]
                if candidate.isdigit():
                    platform, external_id = "x", candidate
    elif host in {"bilibili.com", "m.bilibili.com"}:
        if len(parts) >= 2 and parts[0] == "video":
            platform, external_id = "bilibili", parts[1]
    elif host in {"xiaohongshu.com", "xhslink.com"}:
        if len(parts) >= 2 and parts[0] in {"explore", "discovery"}:
            platform, external_id = "xiaohongshu", parts[-1]

    if platform and external_id and _PLATFORM_ID.fullmatch(external_id):
        return PlatformIdentity(platform=platform, external_id=external_id)
    return None
