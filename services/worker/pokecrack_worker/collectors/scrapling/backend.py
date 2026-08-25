"""Lazy, bounded Scrapling transport bindings.

Importing this module never imports the optional :mod:`scrapling` package. The
package is resolved only when :meth:`ScraplingBindings.load` is explicitly called.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from ipaddress import IPv4Address, ip_address
from socket import SOCK_STREAM, getaddrinfo
from typing import Any
from urllib.parse import urlsplit

from pokecrack_worker.collectors.base import FetchResponse


class ScraplingUnavailableError(RuntimeError):
    """The optional Scrapling dependency or a required safe fetcher is absent."""


class ScraplingResponseError(RuntimeError):
    """A Scrapling response violated the bounded transport contract."""


def _curl_resolve_rule(url: str, pinned_address: str) -> str:
    parsed = urlsplit(url)
    if not parsed.hostname:
        raise ValueError("static URL must contain a hostname")
    return f"{parsed.hostname}:{parsed.port or 443}:{pinned_address}"


class _PinnedStaticFetcher:
    supports_pinned_address = True

    @staticmethod
    def get(
        url: str,
        *,
        timeout: float,
        follow_redirects: bool,
        max_redirects: int,
        pinned_address: str,
        max_response_bytes: int,
    ) -> Any:
        if follow_redirects is not False or max_redirects != 0:
            raise ValueError("pinned static fetcher requires redirects to be disabled")
        curl_module = import_module("curl_cffi")
        requests_module = import_module("curl_cffi.requests")
        converter_module = import_module("scrapling.engines.toolbelt.convertor")
        resolve_rule = _curl_resolve_rule(url, pinned_address)
        chunks = bytearray()
        exceeded = False

        def write_chunk(chunk: bytes) -> int:
            nonlocal exceeded
            if exceeded or len(chunks) + len(chunk) > max_response_bytes:
                exceeded = True
                return 0
            chunks.extend(chunk)
            return len(chunk)

        try:
            with requests_module.Session(
                curl_options={curl_module.CurlOpt.RESOLVE: [resolve_rule]},
                trust_env=False,
            ) as session:
                response = session.get(
                    url,
                    timeout=timeout,
                    allow_redirects=False,
                    max_redirects=0,
                    impersonate="chrome",
                    content_callback=write_chunk,
                )
        except Exception as error:
            if exceeded:
                raise ScraplingResponseError(
                    "Scrapling response exceeded configured byte cap"
                ) from error
            raise
        if exceeded:
            raise ScraplingResponseError("Scrapling response exceeded configured byte cap")
        if chunks:
            response.content = bytes(chunks)
        return converter_module.ResponseFactory.from_http_request(response, {})


class _PinnedAsyncStaticFetcher:
    supports_pinned_address = True

    @staticmethod
    async def get(
        url: str,
        *,
        timeout: float,
        follow_redirects: bool,
        max_redirects: int,
        pinned_address: str,
        max_response_bytes: int,
    ) -> Any:
        if follow_redirects is not False or max_redirects != 0:
            raise ValueError("pinned async static fetcher requires redirects to be disabled")
        curl_module = import_module("curl_cffi")
        requests_module = import_module("curl_cffi.requests")
        converter_module = import_module("scrapling.engines.toolbelt.convertor")
        resolve_rule = _curl_resolve_rule(url, pinned_address)
        chunks = bytearray()
        exceeded = False

        def write_chunk(chunk: bytes) -> int:
            nonlocal exceeded
            if exceeded or len(chunks) + len(chunk) > max_response_bytes:
                exceeded = True
                return 0
            chunks.extend(chunk)
            return len(chunk)

        try:
            async with requests_module.AsyncSession(
                curl_options={curl_module.CurlOpt.RESOLVE: [resolve_rule]},
                trust_env=False,
            ) as session:
                response = await session.get(
                    url,
                    timeout=timeout,
                    allow_redirects=False,
                    max_redirects=0,
                    impersonate="chrome",
                    content_callback=write_chunk,
                )
        except Exception as error:
            if exceeded:
                raise ScraplingResponseError(
                    "Scrapling response exceeded configured byte cap"
                ) from error
            raise
        if exceeded:
            raise ScraplingResponseError("Scrapling response exceeded configured byte cap")
        if chunks:
            response.content = bytes(chunks)
        return converter_module.ResponseFactory.from_http_request(response, {})


@dataclass(frozen=True, slots=True)
class _DynamicFetchResult:
    url: str
    body: bytes
    status: int
    headers: Mapping[str, str]


class _PinnedDynamicFetcher:
    """Single-attempt Playwright fetcher with fail-closed guard setup."""

    supports_fail_closed_setup = True

    @staticmethod
    def fetch(
        url: str,
        *,
        timeout: float,
        retries: int,
        page_setup: Callable[[Any], None],
        google_search: bool,
        additional_args: Mapping[str, Any],
        extra_flags: list[str],
    ) -> _DynamicFetchResult:
        if retries != 1:
            raise ValueError("dynamic fetcher requires exactly one attempt")
        if google_search is not False:
            raise ValueError("dynamic fetcher forbids implicit referrer traffic")
        if not callable(page_setup):
            raise TypeError("dynamic fetcher requires a page setup callback")
        context_options = dict(additional_args)
        if context_options.get("service_workers") != "block":
            raise ValueError("dynamic fetcher requires service workers to be blocked")
        if timeout <= 0 or timeout > 120:
            raise ValueError("dynamic timeout must be in (0, 120] seconds")
        proxy_flags = ("--proxy-server", "--proxy-pac-url", "--proxy-auto-detect")
        if "--no-proxy-server" not in extra_flags or any(
            flag.startswith(proxy_flags) for flag in extra_flags
        ):
            raise ValueError("dynamic fetcher requires browser proxy bypass")

        playwright_module = import_module("playwright.sync_api")
        with playwright_module.sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=list(extra_flags))
            context = None
            try:
                context = browser.new_context(**context_options)
                page = context.new_page()
                # Call directly rather than through Scrapling 0.4.x, which logs and
                # swallows page_setup failures before continuing to navigation.
                page_setup(page)
                navigation = page.goto(
                    url,
                    timeout=max(1, int(timeout * 1_000)),
                    wait_until="load",
                )
                if navigation is None:
                    raise ScraplingResponseError("dynamic navigation returned no response")
                content = page.content()
                if not isinstance(content, str):
                    raise ScraplingResponseError("dynamic page content must be text")
                status = getattr(navigation, "status", None)
                if not isinstance(status, int) or isinstance(status, bool):
                    raise ScraplingResponseError("dynamic response status must be an integer")
                header_reader = getattr(navigation, "all_headers", None)
                headers = header_reader() if callable(header_reader) else {}
                if not isinstance(headers, Mapping):
                    raise ScraplingResponseError("dynamic response headers must be a mapping")
                final_url = getattr(page, "url", url)
                if not isinstance(final_url, str) or not final_url:
                    raise ScraplingResponseError("dynamic response URL must be non-empty")
                return _DynamicFetchResult(
                    url=final_url,
                    body=content.encode("utf-8"),
                    status=status,
                    headers={str(key): str(value) for key, value in headers.items()},
                )
            finally:
                if context is not None:
                    context.close()
                browser.close()


@dataclass(frozen=True, slots=True)
class ScraplingBindings:
    """The three explicitly supported Scrapling fetcher classes.

    ``DynamicFetcher`` must be a normal browser fetcher. No stealth, proxy, or
    CAPTCHA-oriented fallback is discovered or selected by this adapter.
    """

    Fetcher: Any
    AsyncFetcher: Any
    DynamicFetcher: Any

    @classmethod
    def load(
        cls,
        *,
        import_module: Callable[[str], Any] = import_module,
    ) -> ScraplingBindings:
        try:
            module = import_module("scrapling.fetchers")
            fetcher = module.Fetcher
            async_fetcher = module.AsyncFetcher
            dynamic_fetcher = module.DynamicFetcher
        except (ModuleNotFoundError, ImportError, AttributeError) as error:
            raise ScraplingUnavailableError(
                "the optional 'scrapling' dependency with Fetcher, AsyncFetcher, "
                "and DynamicFetcher is required for live Scrapling collection"
            ) from error
        del fetcher, async_fetcher, dynamic_fetcher
        return cls(_PinnedStaticFetcher, _PinnedAsyncStaticFetcher, _PinnedDynamicFetcher)


def _valid_dns_hostname(hostname: str) -> bool:
    if not hostname or len(hostname) > 253:
        return False
    labels = hostname.split(".")
    return all(
        1 <= len(label) <= 63
        and label[0] in "abcdefghijklmnopqrstuvwxyz0123456789"
        and label[-1] in "abcdefghijklmnopqrstuvwxyz0123456789"
        and all(character in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in label)
        for label in labels
    )


def _browser_request_allowed(candidate: str, allowed_hostname: str, allowed_port: int) -> bool:
    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
        port = parsed.port or 443
    except (TypeError, ValueError):
        return False
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or port != allowed_port
    ):
        return False
    normalized = hostname.rstrip(".").casefold()
    if normalized != allowed_hostname:
        return False
    if normalized == "localhost" or normalized.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        address = ip_address(normalized)
    except ValueError:
        return _valid_dns_hostname(normalized)
    return address.is_global


def _dynamic_page_setup(requested_url: str) -> Callable[[Any], None]:
    try:
        requested = urlsplit(requested_url)
        hostname = requested.hostname
        allowed_port = requested.port or 443
    except ValueError as error:
        raise ValueError("dynamic URL has an invalid port") from error
    if not hostname:
        raise ValueError("dynamic URL must contain a hostname")
    allowed_hostname = hostname.rstrip(".").casefold()
    if not _browser_request_allowed(requested_url, allowed_hostname, allowed_port):
        raise ValueError("dynamic URL must be a public HTTPS URL")

    def setup(page: Any) -> None:
        def route_request(route: Any, request: Any) -> None:
            candidate = getattr(request, "url", "")
            if isinstance(candidate, str) and _browser_request_allowed(
                candidate, allowed_hostname, allowed_port
            ):
                route.continue_()
            else:
                route.abort("blockedbyclient")

        def block_websocket(route: Any) -> None:
            route.close(code=1008, reason="dynamic browser WebSockets are disabled")

        page.route("**/*", route_request)
        page.route_web_socket("**/*", block_websocket)

    return setup


def _resolve_hostname(hostname: str) -> tuple[str, ...]:
    try:
        results = getaddrinfo(hostname, None, type=SOCK_STREAM)
    except OSError as error:
        raise ScraplingResponseError("dynamic hostname resolution failed") from error
    return tuple(sorted({str(result[4][0]) for result in results}))


class ScraplingBackend:
    """Convert Scrapling responses to the worker's small bounded DTO."""

    def __init__(
        self,
        *,
        bindings: ScraplingBindings | None = None,
        max_response_bytes: int = 1_000_000,
        hostname_resolver: Callable[[str], tuple[str, ...]] = _resolve_hostname,
    ) -> None:
        if not 1 <= max_response_bytes <= 10_000_000:
            raise ValueError("max_response_bytes must be between 1 and 10000000")
        self._bindings = bindings
        self.max_response_bytes = max_response_bytes
        self._hostname_resolver = hostname_resolver

    @property
    def bindings(self) -> ScraplingBindings:
        if self._bindings is None:
            self._bindings = ScraplingBindings.load()
        return self._bindings

    def _response(self, page: Any, requested_url: str) -> FetchResponse:
        body_value = getattr(page, "body", None)
        if body_value is None:
            body_value = getattr(page, "content", None)
        if isinstance(body_value, str):
            body = body_value.encode("utf-8")
        elif isinstance(body_value, (bytes, bytearray, memoryview)):
            body = bytes(body_value)
        else:
            raise ScraplingResponseError("Scrapling response body must be bytes or text")
        if len(body) > self.max_response_bytes:
            raise ScraplingResponseError("Scrapling response exceeds configured byte cap")

        status_value = getattr(page, "status", None)
        if status_value is None:
            status_value = getattr(page, "status_code", None)
        if not isinstance(status_value, int) or isinstance(status_value, bool):
            raise ScraplingResponseError("Scrapling response status must be an integer")

        url_value = getattr(page, "url", requested_url)
        if not isinstance(url_value, str) or not url_value:
            raise ScraplingResponseError("Scrapling response URL must be a non-empty string")
        headers_value = getattr(page, "headers", {}) or {}
        if not isinstance(headers_value, Mapping):
            raise ScraplingResponseError("Scrapling response headers must be a mapping")
        headers = {str(key): str(value) for key, value in headers_value.items()}
        return FetchResponse(status_code=status_value, url=url_value, headers=headers, body=body)

    def _pinned_dynamic_address(self, hostname: str) -> str:
        addresses = self._hostname_resolver(hostname)
        parsed_addresses = []
        for value in addresses:
            try:
                address = ip_address(value)
            except ValueError as error:
                raise ScraplingResponseError(
                    "dynamic hostname returned an invalid address"
                ) from error
            if not address.is_global:
                raise ScraplingResponseError(
                    "dynamic hostname must resolve only to public addresses"
                )
            parsed_addresses.append(address)
        if not parsed_addresses:
            raise ScraplingResponseError("dynamic hostname did not resolve to a public address")
        selected = next(
            (address for address in parsed_addresses if isinstance(address, IPv4Address)),
            parsed_addresses[0],
        )
        return str(selected) if isinstance(selected, IPv4Address) else f"[{selected}]"

    def _validate_public_resolution(self, url: str) -> str:
        try:
            requested = urlsplit(url)
            hostname = requested.hostname
            allowed_port = requested.port or 443
        except ValueError as error:
            raise ValueError("static URL has an invalid port") from error
        normalized_hostname = (hostname or "").rstrip(".").casefold()
        if not hostname or not _browser_request_allowed(url, normalized_hostname, allowed_port):
            raise ValueError("static URL must be a public HTTPS URL")
        return self._pinned_dynamic_address(hostname)

    def fetch_http(self, url: str, *, timeout_seconds: float = 30.0) -> FetchResponse:
        if timeout_seconds <= 0 or timeout_seconds > 120:
            raise ValueError("timeout_seconds must be in (0, 120]")
        pinned_address = self._validate_public_resolution(url)
        fetcher = self.bindings.Fetcher
        if getattr(fetcher, "supports_pinned_address", False) is not True:
            raise ScraplingUnavailableError("static fetcher cannot pin validated DNS addresses")
        page = fetcher.get(
            url,
            timeout=timeout_seconds,
            follow_redirects=False,
            max_redirects=0,
            pinned_address=pinned_address,
            max_response_bytes=self.max_response_bytes,
        )
        return self._response(page, url)

    async def fetch_async(self, url: str, *, timeout_seconds: float = 30.0) -> FetchResponse:
        if timeout_seconds <= 0 or timeout_seconds > 120:
            raise ValueError("timeout_seconds must be in (0, 120]")
        pinned_address = self._validate_public_resolution(url)
        fetcher = self.bindings.AsyncFetcher
        if getattr(fetcher, "supports_pinned_address", False) is not True:
            raise ScraplingUnavailableError(
                "async static fetcher cannot pin validated DNS addresses"
            )
        page_or_awaitable: Awaitable[Any] | Any = fetcher.get(
            url,
            timeout=timeout_seconds,
            follow_redirects=False,
            max_redirects=0,
            pinned_address=pinned_address,
            max_response_bytes=self.max_response_bytes,
        )
        page = (
            await page_or_awaitable if inspect.isawaitable(page_or_awaitable) else page_or_awaitable
        )
        return self._response(page, url)

    def fetch_dynamic(self, url: str, *, timeout_seconds: float = 30.0) -> FetchResponse:
        if timeout_seconds <= 0 or timeout_seconds > 120:
            raise ValueError("timeout_seconds must be in (0, 120]")
        requested = urlsplit(url)
        if not requested.hostname:
            raise ValueError("dynamic URL must contain a hostname")
        page_setup = _dynamic_page_setup(url)
        pinned_address = self._pinned_dynamic_address(requested.hostname)
        fetcher = self.bindings.DynamicFetcher
        if getattr(fetcher, "supports_fail_closed_setup", False) is not True:
            raise ScraplingUnavailableError(
                "dynamic fetcher cannot fail closed when browser guards are unavailable"
            )
        page = fetcher.fetch(
            url,
            timeout=timeout_seconds,
            retries=1,
            page_setup=page_setup,
            google_search=False,
            additional_args={"service_workers": "block"},
            extra_flags=[
                "--no-proxy-server",
                f"--host-resolver-rules=MAP {requested.hostname} {pinned_address}",
            ],
        )
        return self._response(page, url)
