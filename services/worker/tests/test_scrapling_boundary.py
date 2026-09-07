from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from pokecrack_worker.collectors.scrapling.backend import (
    ScraplingBackend,
    ScraplingBindings,
    ScraplingResolutionError,
    ScraplingResponseError,
    ScraplingUnavailableError,
)


def test_resolver_os_failure_is_distinct_from_a_rejected_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pokecrack_worker.collectors.scrapling import backend

    def fail_resolution(*args: object, **kwargs: object) -> object:
        raise OSError("private resolver details")

    monkeypatch.setattr(backend, "getaddrinfo", fail_resolution)
    with pytest.raises(ScraplingResolutionError, match="^hostname resolution failed$"):
        backend._resolve_hostname("example.com")


def test_loaded_static_fetchers_enforce_dns_pinning_capability() -> None:
    class ImportedFetcher:
        pass

    class ImportedAsyncFetcher:
        pass

    class ImportedDynamicFetcher:
        pass

    class Module:
        Fetcher = ImportedFetcher
        AsyncFetcher = ImportedAsyncFetcher
        DynamicFetcher = ImportedDynamicFetcher

    bindings = ScraplingBindings.load(import_module=lambda _name: Module)

    assert bindings.Fetcher is not ImportedFetcher
    assert bindings.AsyncFetcher is not ImportedAsyncFetcher
    assert bindings.Fetcher.supports_pinned_address is True
    assert bindings.AsyncFetcher.supports_pinned_address is True
    assert bindings.DynamicFetcher is not ImportedDynamicFetcher
    assert bindings.DynamicFetcher.supports_fail_closed_setup is True


def test_loaded_dynamic_fetcher_requires_browser_proxy_bypass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pokecrack_worker.collectors.scrapling.backend as backend_module

    class Module:
        Fetcher = object()
        AsyncFetcher = object()
        DynamicFetcher = object()

    bindings = ScraplingBindings.load(import_module=lambda _name: Module)

    def unexpected_import(_name: str) -> object:
        raise AssertionError("browser imported before proxy policy validation")

    monkeypatch.setattr(backend_module, "import_module", unexpected_import)

    with pytest.raises(ValueError, match="proxy"):
        bindings.DynamicFetcher.fetch(
            "https://dynamic.example/opening",
            timeout=4,
            retries=1,
            page_setup=lambda _page: None,
            google_search=False,
            additional_args={"service_workers": "block"},
            extra_flags=["--host-resolver-rules=MAP dynamic.example 93.184.216.34"],
        )


def test_loaded_dynamic_fetcher_rejects_conflicting_proxy_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pokecrack_worker.collectors.scrapling.backend as backend_module

    class Module:
        Fetcher = object()
        AsyncFetcher = object()
        DynamicFetcher = object()

    bindings = ScraplingBindings.load(import_module=lambda _name: Module)

    def unexpected_import(_name: str) -> object:
        raise AssertionError("browser imported before proxy policy validation")

    monkeypatch.setattr(backend_module, "import_module", unexpected_import)

    with pytest.raises(ValueError, match="proxy"):
        bindings.DynamicFetcher.fetch(
            "https://dynamic.example/opening",
            timeout=4,
            retries=1,
            page_setup=lambda _page: None,
            google_search=False,
            additional_args={"service_workers": "block"},
            extra_flags=[
                "--no-proxy-server",
                "--proxy-server=http://127.0.0.1:8080",
                "--host-resolver-rules=MAP dynamic.example 93.184.216.34",
            ],
        )


def test_loaded_dynamic_fetcher_aborts_before_navigation_when_guard_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pokecrack_worker.collectors.scrapling.backend as backend_module

    goto_called = False

    class Page:
        url = "about:blank"

        def route(self, _pattern: str, _handler: object) -> None:
            raise RuntimeError("route registration failed")

        def goto(self, _url: str, **_kwargs: object) -> object:
            nonlocal goto_called
            goto_called = True
            return object()

    page = Page()

    class UnsafeDynamicFetcher:
        @staticmethod
        def fetch(url: str, **kwargs: object) -> FixturePage:
            try:
                kwargs["page_setup"](page)
            except RuntimeError:
                pass
            page.goto(url)
            return FixturePage(url, b"unsafe")

    class Fetchers:
        Fetcher = object()
        AsyncFetcher = object()
        DynamicFetcher = UnsafeDynamicFetcher

    class Context:
        def new_page(self) -> Page:
            return page

        def close(self) -> None:
            return None

    class Browser:
        def new_context(self, **_kwargs: object) -> Context:
            return Context()

        def close(self) -> None:
            return None

    class Chromium:
        def launch(self, **_kwargs: object) -> Browser:
            return Browser()

    class Playwright:
        chromium = Chromium()

    class SyncPlaywright:
        def __enter__(self) -> Playwright:
            return Playwright()

        def __exit__(self, *_args: object) -> None:
            return None

    bindings = ScraplingBindings.load(import_module=lambda _name: Fetchers)
    monkeypatch.setattr(
        backend_module,
        "import_module",
        lambda name: (
            type("PlaywrightModule", (), {"sync_playwright": SyncPlaywright})
            if name == "playwright.sync_api"
            else Fetchers
        ),
    )

    with pytest.raises(RuntimeError, match="route registration failed"):
        bindings.DynamicFetcher.fetch(
            "https://dynamic.example/opening",
            timeout=4,
            retries=1,
            page_setup=lambda target: target.route("**/*", object()),
            google_search=False,
            additional_args={"service_workers": "block"},
            extra_flags=[
                "--no-proxy-server",
                "--host-resolver-rules=MAP dynamic.example 93.184.216.34",
            ],
        )
    assert goto_called is False


def test_loaded_static_fetcher_pins_curl_to_the_validated_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pokecrack_worker.collectors.scrapling.backend as backend_module

    captured: dict[str, object] = {}
    resolve_option = object()

    class CurlOpt:
        RESOLVE = resolve_option

    class Session:
        def __init__(self, **kwargs: object) -> None:
            captured["session"] = kwargs

        def __enter__(self) -> Session:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, url: str, **kwargs: object) -> object:
            captured["request"] = (url, kwargs)
            return object()

    class ResponseFactory:
        @staticmethod
        def from_http_request(_response: object, _selector_config: object) -> FixturePage:
            return FixturePage("https://allowed.example/item", b"safe")

    class Fetchers:
        Fetcher = object()
        AsyncFetcher = object()
        DynamicFetcher = object()

    def importer(name: str) -> object:
        modules = {
            "scrapling.fetchers": Fetchers,
            "curl_cffi": type("CurlModule", (), {"CurlOpt": CurlOpt}),
            "curl_cffi.requests": type("RequestsModule", (), {"Session": Session}),
            "scrapling.engines.toolbelt.convertor": type(
                "ConverterModule", (), {"ResponseFactory": ResponseFactory}
            ),
        }
        return modules[name]

    monkeypatch.setattr(backend_module, "import_module", importer)
    backend = ScraplingBackend(
        bindings=ScraplingBindings.load(),
        hostname_resolver=lambda _hostname: ("93.184.216.34",),
    )

    result = backend.fetch_http("https://allowed.example/item", timeout_seconds=5)

    assert result.body == b"safe"
    assert captured["session"] == {
        "curl_options": {resolve_option: ["allowed.example:443:93.184.216.34"]},
        "trust_env": False,
    }
    request_url, request_options = captured["request"]
    assert request_url == "https://allowed.example/item"
    callback = request_options.pop("content_callback")
    assert callable(callback)
    assert request_options == {
        "timeout": 5,
        "allow_redirects": False,
        "max_redirects": 0,
        "impersonate": "chrome",
        "headers": {
            "User-Agent": "PokecrackMetadataCollector/0.1",
            "Accept-Encoding": "identity",
        },
    }


def test_loaded_sync_static_fetcher_aborts_before_exceeding_the_response_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pokecrack_worker.collectors.scrapling.backend as backend_module

    class CurlOpt:
        RESOLVE = object()

    class CurlModule:
        pass

    CurlModule.CurlOpt = CurlOpt

    class Response:
        content = b""

    class Session:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def __enter__(self) -> Session:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def get(self, url: str, **kwargs: object) -> Response:
            del url
            callback = kwargs.get("content_callback")
            if callback is not None:
                assert callable(callback)
                assert callback(b"12345") == 5
                assert callback(b"67890") == 0
                raise RuntimeError("curl write aborted")
            return Response()

    class RequestsModule:
        pass

    RequestsModule.Session = Session
    RequestsModule.AsyncSession = object

    class ResponseFactory:
        @staticmethod
        def from_http_request(response: object, parser_arguments: dict[str, object]) -> FixturePage:
            del response, parser_arguments
            raise AssertionError("oversized response must abort before parsing")

    class ConvertorModule:
        pass

    ConvertorModule.ResponseFactory = ResponseFactory

    class RawFetcher:
        pass

    class RawAsyncFetcher:
        pass

    class RawDynamicFetcher:
        pass

    class FetchersModule:
        pass

    FetchersModule.Fetcher = RawFetcher
    FetchersModule.AsyncFetcher = RawAsyncFetcher
    FetchersModule.DynamicFetcher = RawDynamicFetcher

    modules = {
        "scrapling.fetchers": FetchersModule,
        "curl_cffi": CurlModule,
        "curl_cffi.requests": RequestsModule,
        "scrapling.engines.toolbelt.convertor": ConvertorModule,
    }
    monkeypatch.setattr(backend_module, "import_module", lambda name: modules[name])
    backend = ScraplingBackend(
        bindings=ScraplingBindings.load(),
        hostname_resolver=lambda _hostname: ("93.184.216.34",),
        max_response_bytes=8,
    )

    with pytest.raises(ScraplingResponseError, match="byte cap"):
        backend.fetch_http("https://allowed.example/item")


def test_loaded_async_fetcher_pins_curl_to_the_validated_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pokecrack_worker.collectors.scrapling.backend as backend_module

    captured: dict[str, object] = {}
    resolve_option = object()

    class CurlOpt:
        RESOLVE = resolve_option

    class AsyncSession:
        def __init__(self, **kwargs: object) -> None:
            captured["session"] = kwargs

        async def __aenter__(self) -> AsyncSession:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, url: str, **kwargs: object) -> object:
            captured["request"] = (url, kwargs)
            return object()

    class ResponseFactory:
        @staticmethod
        def from_http_request(_response: object, _selector_config: object) -> FixturePage:
            return FixturePage("https://allowed.example/item", b"safe-async")

    class Fetchers:
        Fetcher = object()
        AsyncFetcher = object()
        DynamicFetcher = object()

    def importer(name: str) -> object:
        modules = {
            "scrapling.fetchers": Fetchers,
            "curl_cffi": type("CurlModule", (), {"CurlOpt": CurlOpt}),
            "curl_cffi.requests": type("RequestsModule", (), {"AsyncSession": AsyncSession}),
            "scrapling.engines.toolbelt.convertor": type(
                "ConverterModule", (), {"ResponseFactory": ResponseFactory}
            ),
        }
        return modules[name]

    monkeypatch.setattr(backend_module, "import_module", importer)
    backend = ScraplingBackend(
        bindings=ScraplingBindings.load(),
        hostname_resolver=lambda _hostname: ("93.184.216.34",),
    )

    result = asyncio.run(backend.fetch_async("https://allowed.example/item", timeout_seconds=7))

    assert result.body == b"safe-async"
    assert captured["session"] == {
        "curl_options": {resolve_option: ["allowed.example:443:93.184.216.34"]},
        "trust_env": False,
    }
    request_url, request_options = captured["request"]
    assert request_url == "https://allowed.example/item"
    callback = request_options.pop("content_callback")
    assert callable(callback)
    assert request_options == {
        "timeout": 7,
        "allow_redirects": False,
        "max_redirects": 0,
        "impersonate": "chrome",
        "headers": {
            "User-Agent": "PokecrackMetadataCollector/0.1",
            "Accept-Encoding": "identity",
        },
    }


def test_loaded_async_static_fetcher_aborts_before_exceeding_the_response_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pokecrack_worker.collectors.scrapling.backend as backend_module

    class CurlOpt:
        RESOLVE = object()

    class Response:
        content = b""

    class AsyncSession:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        async def __aenter__(self) -> AsyncSession:
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def get(self, url: str, **kwargs: object) -> Response:
            del url
            callback = kwargs.get("content_callback")
            if callback is not None:
                assert callable(callback)
                assert callback(b"12345") == 5
                assert callback(b"67890") == 0
                raise RuntimeError("curl write aborted")
            return Response()

    class ResponseFactory:
        @staticmethod
        def from_http_request(response: object, parser_arguments: dict[str, object]) -> FixturePage:
            del response, parser_arguments
            raise AssertionError("oversized response must abort before parsing")

    class Fetchers:
        Fetcher = object()
        AsyncFetcher = object()
        DynamicFetcher = object()

    modules = {
        "scrapling.fetchers": Fetchers,
        "curl_cffi": type("CurlModule", (), {"CurlOpt": CurlOpt}),
        "curl_cffi.requests": type("RequestsModule", (), {"AsyncSession": AsyncSession}),
        "scrapling.engines.toolbelt.convertor": type(
            "ConverterModule", (), {"ResponseFactory": ResponseFactory}
        ),
    }
    monkeypatch.setattr(backend_module, "import_module", lambda name: modules[name])
    backend = ScraplingBackend(
        bindings=ScraplingBindings.load(),
        hostname_resolver=lambda _hostname: ("93.184.216.34",),
        max_response_bytes=8,
    )

    with pytest.raises(ScraplingResponseError, match="byte cap"):
        asyncio.run(backend.fetch_async("https://allowed.example/item"))


def test_scrapling_optional_dependency_fails_with_actionable_unavailable_error() -> None:
    def missing(name: str) -> object:
        raise ModuleNotFoundError(name)

    with pytest.raises(ScraplingUnavailableError, match="optional.*scrapling"):
        ScraplingBindings.load(import_module=missing)


@dataclass
class FixturePage:
    url: str
    body: bytes
    status: int = 200
    headers: dict[str, str] | None = None


def test_scrapling_backend_exposes_http_async_and_dynamic_fetcher_paths() -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    class Fetcher:
        supports_pinned_address = True

        @staticmethod
        def get(url: str, **kwargs: object) -> FixturePage:
            calls.append(("http", url, kwargs))
            return FixturePage(url, b"<p>http</p>", headers={"content-type": "text/html"})

    class AsyncFetcher:
        supports_pinned_address = True

        @staticmethod
        async def get(url: str, **kwargs: object) -> FixturePage:
            calls.append(("async", url, kwargs))
            return FixturePage(url, b"<p>async</p>", headers={"content-type": "text/html"})

    class DynamicFetcher:
        supports_fail_closed_setup = True

        @staticmethod
        def fetch(url: str, **kwargs: object) -> FixturePage:
            calls.append(("dynamic", url, kwargs))
            return FixturePage(url, b"<p>dynamic</p>", headers={"content-type": "text/html"})

    backend = ScraplingBackend(
        bindings=ScraplingBindings(Fetcher, AsyncFetcher, DynamicFetcher),
        max_response_bytes=1_000,
        hostname_resolver=lambda _hostname: ("93.184.216.34",),
    )

    http = backend.fetch_http("https://example.com/")
    async_result = asyncio.run(backend.fetch_async("https://example.com/"))
    dynamic = backend.fetch_dynamic("https://dynamic.example/")

    assert http.body == b"<p>http</p>"
    assert async_result.body == b"<p>async</p>"
    assert dynamic.body == b"<p>dynamic</p>"
    assert calls[0] == (
        "http",
        "https://example.com/",
        {
            "timeout": 30.0,
            "follow_redirects": False,
            "max_redirects": 0,
            "pinned_address": "93.184.216.34",
            "max_response_bytes": 1_000,
        },
    )
    assert calls[1] == (
        "async",
        "https://example.com/",
        {
            "timeout": 30.0,
            "follow_redirects": False,
            "max_redirects": 0,
            "pinned_address": "93.184.216.34",
            "max_response_bytes": 1_000,
        },
    )
    kind, dynamic_url, dynamic_kwargs = calls[2]
    assert kind == "dynamic"
    assert dynamic_url == "https://dynamic.example/"
    assert dynamic_kwargs["timeout"] == 30.0
    assert dynamic_kwargs["google_search"] is False
    assert dynamic_kwargs["retries"] == 1
    assert dynamic_kwargs["additional_args"] == {"service_workers": "block"}
    assert dynamic_kwargs["extra_flags"] == [
        "--no-proxy-server",
        "--host-resolver-rules=MAP dynamic.example 93.184.216.34",
    ]
    assert callable(dynamic_kwargs["page_setup"])


def test_static_fetch_rejects_private_dns_resolution_before_network_dispatch() -> None:
    calls: list[str] = []

    class Fetcher:
        @staticmethod
        def get(url: str, **_kwargs: object) -> FixturePage:
            calls.append(url)
            return FixturePage(url, b"private")

    backend = ScraplingBackend(
        bindings=ScraplingBindings(Fetcher, object(), object()),
        hostname_resolver=lambda _hostname: ("127.0.0.1",),
    )

    with pytest.raises(ScraplingResponseError, match="public address"):
        backend.fetch_http("https://allowed.example/resource")
    assert calls == []


def test_async_static_fetch_rejects_private_dns_before_network_dispatch() -> None:
    calls: list[str] = []

    class AsyncFetcher:
        @staticmethod
        async def get(url: str, **_kwargs: object) -> FixturePage:
            calls.append(url)
            return FixturePage(url, b"private")

    backend = ScraplingBackend(
        bindings=ScraplingBindings(object(), AsyncFetcher, object()),
        hostname_resolver=lambda _hostname: ("169.254.169.254",),
    )

    with pytest.raises(ScraplingResponseError, match="public address"):
        asyncio.run(backend.fetch_async("https://allowed.example/resource"))
    assert calls == []


def test_dynamic_fetch_blocks_cross_domain_and_private_browser_requests_before_navigation() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class DynamicFetcher:
        supports_fail_closed_setup = True

        @staticmethod
        def fetch(url: str, **kwargs: object) -> FixturePage:
            calls.append((url, kwargs))
            return FixturePage(url, b"<p>dynamic</p>", headers={"content-type": "text/html"})

    backend = ScraplingBackend(
        bindings=ScraplingBindings(object(), object(), DynamicFetcher),
        hostname_resolver=lambda _hostname: ("93.184.216.34",),
    )
    backend.fetch_dynamic("https://dynamic.example/opening", timeout_seconds=4)

    kwargs = calls[0][1]
    page_setup = kwargs.get("page_setup")
    assert callable(page_setup)

    captured: dict[str, object] = {}

    class Page:
        def route(self, pattern: str, handler: object) -> None:
            captured["pattern"] = pattern
            captured["handler"] = handler

        def route_web_socket(self, pattern: str, handler: object) -> None:
            captured["websocket_pattern"] = pattern
            captured["websocket_handler"] = handler

    page_setup(Page())
    assert captured["pattern"] == "**/*"
    assert captured["websocket_pattern"] == "**/*"
    websocket_handler = captured["websocket_handler"]

    class WebSocketRoute:
        def __init__(self) -> None:
            self.closed = False

        def close(self, *, code: int, reason: str) -> None:
            assert code == 1008
            assert reason == "dynamic browser WebSockets are disabled"
            self.closed = True

    websocket_route = WebSocketRoute()
    websocket_handler(websocket_route)
    assert websocket_route.closed is True

    handler = captured["handler"]

    class Request:
        def __init__(self, url: str) -> None:
            self.url = url

    class Route:
        def __init__(self) -> None:
            self.action: str | None = None

        def continue_(self) -> None:
            self.action = "continue"

        def abort(self, _reason: str = "blockedbyclient") -> None:
            self.action = "abort"

    for candidate, expected in (
        ("https://dynamic.example/app.js", "continue"),
        ("https://other.example/redirect", "abort"),
        ("https://dynamic.example:8443/internal", "abort"),
        ("http://127.0.0.1/admin", "abort"),
        ("http://169.254.169.254/latest/meta-data", "abort"),
        ("https://[::1]/", "abort"),
    ):
        route = Route()
        handler(route, Request(candidate))
        assert route.action == expected


def test_dynamic_fetch_rejects_private_dns_resolution_before_browser_launch() -> None:
    calls: list[str] = []

    class DynamicFetcher:
        @staticmethod
        def fetch(url: str, **_kwargs: object) -> FixturePage:
            calls.append(url)
            return FixturePage(url, b"private")

    backend = ScraplingBackend(
        bindings=ScraplingBindings(object(), object(), DynamicFetcher),
        hostname_resolver=lambda _hostname: ("127.0.0.1",),
    )

    with pytest.raises(ScraplingResponseError, match="public address"):
        backend.fetch_dynamic("https://dynamic.example/opening")
    assert calls == []


def test_dynamic_fetch_rejects_hostname_rule_injection_before_browser_launch() -> None:
    calls: list[str] = []

    class DynamicFetcher:
        @staticmethod
        def fetch(url: str, **_kwargs: object) -> FixturePage:
            calls.append(url)
            return FixturePage(url, b"unsafe")

    resolved: list[str] = []

    def resolver(hostname: str) -> tuple[str, ...]:
        resolved.append(hostname)
        return ("93.184.216.34",)

    backend = ScraplingBackend(
        bindings=ScraplingBindings(object(), object(), DynamicFetcher),
        hostname_resolver=resolver,
    )

    with pytest.raises(ValueError, match="public HTTPS URL"):
        backend.fetch_dynamic("https://example.com,EXCLUDE%20localhost/opening")
    assert calls == []
    assert resolved == []
