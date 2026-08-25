"""Centralized ANSI removal and credential redaction for every captured byte."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

REDACTED = "[REDACTED]"
_ANSI = re.compile(r"(?:\x1B[@-_][0-?]*[ -/]*[@-~])|(?:\x9B[0-?]*[ -/]*[@-~])")
_HEADER = re.compile(r"(?im)\b(authorization|proxy-authorization|cookie|set-cookie)\s*:\s*[^\r\n]*")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_ASSIGNMENT = re.compile(
    r"(?i)\b(access_token|refresh_token|id_token|session(?:[_-]?(?:id|data))?|sid|auth|api[_-]?key|password|secret|token)"
    r"(\s*[=:]\s*)([^&\s,;]+)"
)
_JSON_SECRET = re.compile(
    r"(?i)([\"'](?:authorization|cookie|set-cookie|access_token|refresh_token|id_token|session(?:[_-]?(?:id|data))?|sid|auth|token|secret|password|api[_-]?key)[\"']\s*:\s*)[\"'][^\"']*[\"']"
)
_SENSITIVE_KEY_FRAGMENT = re.compile(
    r"authorization|cookie|credential|password|secret|token|api_?key"
    r"|(?:^|_)(?:auth|sid|session(?:_?id)?)(?:_|$)",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_URL_TRAILING_PUNCTUATION = ".,;:!?)]}"


def strip_ansi(value: str) -> str:
    return _ANSI.sub("", value)


def _sanitize_url_match(match: re.Match[str]) -> str:
    raw = match.group(0)
    trailing = ""
    while raw and raw[-1] in _URL_TRAILING_PUNCTUATION:
        trailing = raw[-1] + trailing
        raw = raw[:-1]
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        return f"{REDACTED}{trailing}"
    if not parsed.hostname:
        return f"{REDACTED}{trailing}"
    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    default_port = 80 if parsed.scheme.casefold() == "http" else 443
    netloc = hostname if port in (None, default_port) else f"{hostname}:{port}"
    safe = urlunsplit((parsed.scheme.casefold(), netloc, parsed.path or "/", "", ""))
    return f"{safe}{trailing}"


def redact_text(value: str) -> str:
    cleaned = strip_ansi(value)
    cleaned = _URL.sub(_sanitize_url_match, cleaned)
    cleaned = _HEADER.sub(lambda match: f"{match.group(1)}: {REDACTED}", cleaned)
    cleaned = _BEARER.sub(f"Bearer {REDACTED}", cleaned)
    cleaned = _ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
        cleaned,
    )
    cleaned = _JSON_SECRET.sub(lambda match: f'{match.group(1)}"{REDACTED}"', cleaned)
    return cleaned


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, nested in value.items():
            text_key = str(key)
            snake_key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text_key)
            normalized = re.sub(r"[^a-z0-9]+", "_", snake_key.lower()).strip("_")
            if _SENSITIVE_KEY_FRAGMENT.search(normalized):
                result[text_key] = REDACTED
            else:
                result[text_key] = redact(nested)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value
