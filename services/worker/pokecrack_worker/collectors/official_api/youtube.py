"""Bounded YouTube Data API discovery; video and page downloads are absent."""

from __future__ import annotations

import html
import json
import os
import re
import signal
import subprocess
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from types import MappingProxyType
from typing import Any, Protocol
from urllib.parse import urlencode

from pydantic import SecretStr

from pokecrack_worker.collectors.official_api.tcgdex import APIResponse
from pokecrack_worker.config.registries import REQUIRED_YOUTUBE_QUERIES, YouTubeQuery
from pokecrack_worker.config.source_policy import CollectorRoute, SourcePolicyRegistry
from pokecrack_worker.models import CollectorType, SourceItemCandidate

YOUTUBE_SEARCH_URL = "https://youtube.googleapis.com/youtube/v3/search"
YOUTUBE_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
YOUTUBE_TIMEOUT_SECONDS = 30.0
_YOUTUBE_CURL_TRANSFER_SECONDS = 27.0
_YOUTUBE_PROCESS_DEADLINE_SECONDS = 29.0
_YOUTUBE_REAP_ATTEMPTS = 4
_YOUTUBE_REAP_SLICE_SECONDS = 0.4
_YOUTUBE_CURL_PATH = "/usr/bin/curl"
_PROCESS_DEADLINE_SUPPORTED = os.name == "posix"
YOUTUBE_COLLECTOR_VERSION = "youtube-global-discovery-v1"
YOUTUBE_APPROVED_QUERY_TEXT: Mapping[str, str] = MappingProxyType(dict(REQUIRED_YOUTUBE_QUERIES))
YOUTUBE_QUERY_ALLOWLIST = tuple(YOUTUBE_APPROVED_QUERY_TEXT)
_EXPECTED_POLICY_CONFIG: dict[str, Any] = {
    "metadata_only": True,
    "media_download": False,
    "max_response_bytes": YOUTUBE_MAX_RESPONSE_BYTES,
    "query_allowlist": list(YOUTUBE_QUERY_ALLOWLIST),
}

_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


class YouTubeError(RuntimeError):
    """Safe typed error whose code/retry disposition can cross the job boundary."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class YouTubeCredentialsUnavailable(YouTubeError):
    def __init__(self) -> None:
        super().__init__("credentials_unavailable", retryable=False)


class YouTubeHTTPError(YouTubeError):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(
            "http_error",
            retryable=status_code in {408, 425, 429} or status_code >= 500,
        )


class YouTubeInvalidResponse(YouTubeError):
    def __init__(self, code: str = "invalid_response") -> None:
        super().__init__(code, retryable=False)


@dataclass(frozen=True, slots=True)
class _SearchItem:
    video_id: str
    title: str | None
    published_at: datetime


@dataclass(frozen=True, slots=True)
class _ReapOutcome:
    reaped: bool
    completed_within_deadline: bool
    control_flow: BaseException | None = None


class YouTubeTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        api_key: SecretStr,
        timeout_seconds: float,
    ) -> APIResponse: ...


class HTTPXYouTubeTransport:
    """Fixed-host curl boundary with byte and synchronous wall-time caps.

    DNS resolution lives inside the child process. A deadline therefore terminates
    both the request and any resolver work before this synchronous method returns.
    """

    def __init__(
        self,
        *,
        max_response_bytes: int = YOUTUBE_MAX_RESPONSE_BYTES,
    ) -> None:
        if not 1 <= max_response_bytes <= YOUTUBE_MAX_RESPONSE_BYTES:
            raise ValueError(
                f"max_response_bytes must be between 1 and {YOUTUBE_MAX_RESPONSE_BYTES}"
            )
        self.max_response_bytes = max_response_bytes

    def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        api_key: SecretStr,
        timeout_seconds: float,
    ) -> APIResponse:
        if url != YOUTUBE_SEARCH_URL:
            raise ValueError("YouTube transport accepts only the fixed search endpoint")
        if timeout_seconds != YOUTUBE_TIMEOUT_SECONDS:
            raise ValueError("YouTube transport requires the fixed 30-second timeout")
        if not _PROCESS_DEADLINE_SUPPORTED:
            raise YouTubeError("absolute_deadline_unavailable", retryable=False)
        secret = api_key.get_secret_value()
        if (
            not secret
            or not secret.isascii()
            or any(character in secret for character in ("\r", "\n", "\0"))
        ):
            raise YouTubeCredentialsUnavailable()

        started_at = monotonic()
        hard_deadline = started_at + YOUTUBE_TIMEOUT_SECONDS
        process_deadline = started_at + _YOUTUBE_PROCESS_DEADLINE_SECONDS
        transfer_deadline = started_at + _YOUTUBE_CURL_TRANSFER_SECONDS
        query_url = f"{url}?{urlencode(params)}"
        command = (
            _YOUTUBE_CURL_PATH,
            "--disable",
            "--silent",
            "--show-error",
            "--request",
            "GET",
            "--proto",
            "=https",
            "--proxy",
            "",
            "--noproxy",
            "*",
            "--max-redirs",
            "0",
            "--connect-timeout",
            "10",
            "--max-time",
            str(int(_YOUTUBE_CURL_TRANSFER_SECONDS)),
            "--max-filesize",
            str(self.max_response_bytes),
            "--header",
            "@-",
            "--header",
            "Accept: application/json",
            "--header",
            "Accept-Encoding: identity",
            "--write-out",
            (
                "%{stderr}POKECRACK_HTTP_CODE:%{http_code}\\n"
                "POKECRACK_CONTENT_ENCODING:%header{content-encoding}\\n"
                "POKECRACK_CONTENT_LENGTH:%header{content-length}\\n"
            ),
            query_url,
        )
        try:
            process = subprocess.Popen(  # noqa: S603 - fixed absolute executable and argv
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                start_new_session=True,
                env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"},
            )
        except OSError:
            raise YouTubeError("transport_unavailable", retryable=False) from None

        try:
            stdout, stderr = process.communicate(
                input=f"X-Goog-Api-Key: {secret}\n".encode("ascii"),
                timeout=_remaining_seconds(transfer_deadline),
            )
        except subprocess.TimeoutExpired:
            _terminate_and_reap(process, deadline=process_deadline)
            raise YouTubeError("request_timeout", retryable=True) from None
        except BaseException as error:
            # start_new_session isolates curl and any resolver descendants. Always
            # tear that group down before an interrupt, shutdown, or unexpected
            # communicate failure can escape this synchronous boundary.
            _terminate_and_reap(process, deadline=process_deadline)
            if isinstance(error, Exception):
                raise YouTubeError("network_error", retryable=True) from None
            raise

        if monotonic() > hard_deadline:
            raise YouTubeError("request_timeout", retryable=True)
        if process.returncode == 28:
            raise YouTubeError("request_timeout", retryable=True)
        if process.returncode == 63:
            raise YouTubeInvalidResponse("response_too_large")
        if process.returncode != 0:
            raise YouTubeError("network_error", retryable=True)
        if len(stdout) > self.max_response_bytes:
            raise YouTubeInvalidResponse("response_too_large")

        response_metadata = _curl_response_metadata(stderr)
        content_encoding = response_metadata["content-encoding"]
        if content_encoding.casefold() not in {"", "identity"}:
            raise YouTubeInvalidResponse("unsupported_content_encoding")
        declared_length = response_metadata["content-length"]
        if declared_length:
            try:
                parsed_length = int(declared_length)
            except ValueError as error:
                raise YouTubeInvalidResponse("invalid_content_length") from error
            if parsed_length < 0:
                raise YouTubeInvalidResponse("invalid_content_length")
            if parsed_length > self.max_response_bytes:
                raise YouTubeInvalidResponse("response_too_large")
        try:
            status_code = int(response_metadata["http-code"])
        except ValueError as error:
            raise YouTubeInvalidResponse() from error
        if not 100 <= status_code <= 599:
            raise YouTubeInvalidResponse()
        if monotonic() > hard_deadline:
            raise YouTubeError("request_timeout", retryable=True)
        return APIResponse(
            status_code,
            {
                "content-encoding": content_encoding,
                "content-length": declared_length,
            },
            stdout,
        )


def _remaining_seconds(deadline: float) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise subprocess.TimeoutExpired(_YOUTUBE_CURL_PATH, 0)
    return remaining


def _terminate_and_reap(process: subprocess.Popen[bytes], *, deadline: float) -> None:
    outcome: _ReapOutcome | None = None
    try:
        outcome = _reap_process_group(process, deadline=deadline)
        if not outcome.reaped or not outcome.completed_within_deadline:
            raise YouTubeError("deadline_cleanup_failed", retryable=False) from None
        if outcome.control_flow is not None:
            raise outcome.control_flow
    except YouTubeError:
        raise
    except BaseException:
        # This outer fence also covers asynchronous control flow delivered at a
        # loop/clock boundary rather than by one of the subprocess calls. Such
        # control flow may escape only after a timely reap was confirmed.
        if outcome is None or not outcome.reaped or not outcome.completed_within_deadline:
            raise YouTubeError("deadline_cleanup_failed", retryable=False) from None
        raise


def _reap_process_group(process: subprocess.Popen[bytes], *, deadline: float) -> _ReapOutcome:
    try:
        return _reap_process_group_guarded(process, deadline=deadline)
    except BaseException as error:
        control_flow = error if not isinstance(error, Exception) else None
        return _ReapOutcome(False, False, control_flow)


def _reap_process_group_guarded(
    process: subprocess.Popen[bytes], *, deadline: float
) -> _ReapOutcome:
    cleanup_control_flow: BaseException | None = None
    reaped = False

    def remember_control_flow(error: BaseException) -> None:
        nonlocal cleanup_control_flow
        if not isinstance(error, Exception) and cleanup_control_flow is None:
            cleanup_control_flow = error

    for _attempt in range(_YOUTUBE_REAP_ATTEMPTS):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except BaseException as error:
            remember_control_flow(error)
        try:
            process.kill()
        except BaseException as error:
            remember_control_flow(error)

        try:
            remaining = deadline - monotonic()
        except BaseException as error:
            remember_control_flow(error)
            continue
        if remaining <= 0:
            return _ReapOutcome(False, False, cleanup_control_flow)
        try:
            process.wait(timeout=min(_YOUTUBE_REAP_SLICE_SECONDS, remaining))
        except BaseException as error:
            remember_control_flow(error)
        else:
            reaped = True
            break

        try:
            if process.poll() is not None:
                reaped = True
                break
        except BaseException as error:
            remember_control_flow(error)

    if not reaped:
        return _ReapOutcome(False, False, cleanup_control_flow)
    try:
        completed_within_deadline = monotonic() <= deadline
    except BaseException as error:
        remember_control_flow(error)
        completed_within_deadline = False
    return _ReapOutcome(reaped, completed_within_deadline, cleanup_control_flow)


def _curl_response_metadata(stderr: bytes) -> dict[str, str]:
    if len(stderr) > 64 * 1024:
        raise YouTubeInvalidResponse("response_headers_too_large")
    try:
        lines = stderr.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as error:
        raise YouTubeInvalidResponse() from error
    prefixes = {
        "POKECRACK_HTTP_CODE:": "http-code",
        "POKECRACK_CONTENT_ENCODING:": "content-encoding",
        "POKECRACK_CONTENT_LENGTH:": "content-length",
    }
    metadata: dict[str, str] = {}
    for line in lines:
        for prefix, key in prefixes.items():
            if line.startswith(prefix):
                if key in metadata:
                    raise YouTubeInvalidResponse("duplicate_response_metadata")
                metadata[key] = line[len(prefix) :].strip()
    if set(metadata) != set(prefixes.values()):
        raise YouTubeInvalidResponse()
    return metadata


def _normalize_text(value: str, *, max_chars: int) -> str | None:
    decoded = unicodedata.normalize("NFKC", html.unescape(value))
    without_controls = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in decoded
    )
    normalized = " ".join(without_controls.split())
    return normalized[:max_chars] or None


def _json_mapping(body: bytes) -> Mapping[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise YouTubeInvalidResponse("duplicate_json_key")
            result[key] = value
        return result

    try:
        payload: Any = json.loads(body, object_pairs_hook=reject_duplicate_keys)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise YouTubeInvalidResponse() from error
    if not isinstance(payload, Mapping):
        raise YouTubeInvalidResponse()
    return payload


def _published_at(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise YouTubeInvalidResponse()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise YouTubeInvalidResponse() from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise YouTubeInvalidResponse()
    return parsed.astimezone(UTC)


def _parse_search_response(body: bytes, *, max_results: int) -> tuple[_SearchItem, ...]:
    payload = _json_mapping(body)
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or len(raw_items) > max_results:
        raise YouTubeInvalidResponse()
    items: list[_SearchItem] = []
    seen_video_ids: set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            raise YouTubeInvalidResponse()
        identity = raw_item.get("id")
        snippet = raw_item.get("snippet")
        if not isinstance(identity, Mapping) or not isinstance(snippet, Mapping):
            raise YouTubeInvalidResponse()
        video_id = identity.get("videoId")
        title = snippet.get("title")
        if (
            identity.get("kind") != "youtube#video"
            or not isinstance(video_id, str)
            or _VIDEO_ID_PATTERN.fullmatch(video_id) is None
            or not isinstance(title, str)
        ):
            raise YouTubeInvalidResponse()
        if video_id in seen_video_ids:
            raise YouTubeInvalidResponse("duplicate_video_id")
        seen_video_ids.add(video_id)
        items.append(
            _SearchItem(
                video_id=video_id,
                title=_normalize_text(title, max_chars=500),
                published_at=_published_at(snippet.get("publishedAt")),
            )
        )
    return tuple(items)


class YouTubeDataClient:
    def __init__(
        self,
        *,
        api_key: str,
        transport: YouTubeTransport,
        policies: SourcePolicyRegistry,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not api_key:
            raise YouTubeCredentialsUnavailable()
        self._api_key = SecretStr(api_key)
        self.transport = transport
        self.policies = policies
        self._clock = clock or (lambda: datetime.now(UTC))

    def discover(self, query: YouTubeQuery) -> tuple[SourceItemCandidate, ...]:
        policy = self.policies.require(YOUTUBE_SEARCH_URL, CollectorRoute.YOUTUBE)
        if (
            policy.version != YOUTUBE_COLLECTOR_VERSION
            or policy.min_delay_seconds != 2
            or policy.max_pages_per_run != 1
            or policy.max_concurrency != 1
            or policy.retention_days != 28
            or not policy.metadata_only
            or policy.statistics_eligible_default
            or policy.config != _EXPECTED_POLICY_CONFIG
            or YOUTUBE_APPROVED_QUERY_TEXT.get(query.name) != query.query
            or query.enabled is not False
            or query.metadata_only is not True
            or query.max_results != 25
            or query.region_code is not None
            or query.published_within_days != 30
            or query.order != "date"
        ):
            raise YouTubeInvalidResponse("source_policy_version_mismatch")
        published_after = self._clock().astimezone(UTC) - timedelta(
            days=query.published_within_days
        )
        # This is an English text-relevance hint, never a region or observed geography.
        search_response = self.transport.get(
            YOUTUBE_SEARCH_URL,
            params={
                "part": "snippet",
                "type": "video",
                "q": query.query,
                "maxResults": str(query.max_results),
                "order": query.order,
                "publishedAfter": published_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "relevanceLanguage": "en",
                "fields": "items(id(kind,videoId),snippet(publishedAt,title))",
            },
            api_key=self._api_key,
            timeout_seconds=YOUTUBE_TIMEOUT_SECONDS,
        )
        if search_response.status_code != 200:
            raise YouTubeHTTPError(search_response.status_code)
        search_items = _parse_search_response(search_response.body, max_results=query.max_results)

        candidates: list[SourceItemCandidate] = []
        for item in search_items:
            try:
                candidate = SourceItemCandidate(
                    platform="youtube",
                    external_id=item.video_id,
                    source_url=f"https://www.youtube.com/watch?v={item.video_id}",
                    title=item.title,
                    text=None,
                    published_at=item.published_at,
                    author_hash=None,
                    media_urls=(),
                    metadata={},
                    collector=CollectorType.OFFICIAL_API,
                    collector_version=YOUTUBE_COLLECTOR_VERSION,
                    source_policy_version=policy.version,
                )
            except (TypeError, ValueError) as error:
                raise YouTubeInvalidResponse() from error
            candidates.append(candidate)
        return tuple(candidates)
