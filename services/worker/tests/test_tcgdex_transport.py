from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any

import pytest

from pokecrack_worker.collectors.official_api import tcgdex
from pokecrack_worker.collectors.official_api.tcgdex import (
    TCGDEX_MAX_RESPONSE_BYTES,
    TCGDEX_SETS_URL,
    TCGDEX_TIMEOUT_SECONDS,
    HTTPXTCGdexTransport,
    TCGdexHTTPError,
    TCGdexRequestError,
    TCGdexResponseTooLarge,
)


@dataclass
class StubResponse:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    chunks: tuple[bytes, ...] = ()
    iterated: bool = False
    delay_seconds: float = 0
    raw_chunk_size: int | None = None

    async def aiter_raw(self, *, chunk_size: int) -> AsyncIterator[bytes]:
        self.iterated = True
        self.raw_chunk_size = chunk_size
        for chunk in self.chunks:
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            yield chunk


class StubStream:
    def __init__(self, response: StubResponse) -> None:
        self.response = response

    async def __aenter__(self) -> StubResponse:
        return self.response

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback


class StubAsyncClient:
    def __init__(
        self,
        response: StubResponse,
        calls: list[tuple[str, str, dict[str, Any]]],
        client_options: list[dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        self.response = response
        self.calls = calls
        client_options.append(kwargs)

    async def __aenter__(self) -> StubAsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback

    def stream(self, method: str, url: str, **kwargs: Any) -> StubStream:
        self.calls.append((method, url, kwargs))
        return StubStream(self.response)


def install_stream(
    monkeypatch: pytest.MonkeyPatch,
    response: StubResponse,
) -> tuple[list[tuple[str, str, dict[str, Any]]], list[dict[str, Any]]]:
    calls: list[tuple[str, str, dict[str, Any]]] = []
    client_options: list[dict[str, Any]] = []

    def client(**kwargs: Any) -> StubAsyncClient:
        return StubAsyncClient(response, calls, client_options, **kwargs)

    monkeypatch.setattr(tcgdex.httpx, "AsyncClient", client)
    return calls, client_options


def test_httpx_tcgdex_transport_uses_fixed_get_timeout_and_no_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = StubResponse(200, {"etag": 'W/"fixture"'}, (b"[", b"]"))
    calls, client_options = install_stream(monkeypatch, upstream)

    response = HTTPXTCGdexTransport().get(
        TCGDEX_SETS_URL,
        headers={"If-None-Match": 'W/"old"'},
        timeout_seconds=TCGDEX_TIMEOUT_SECONDS,
    )

    assert response.body == b"[]"
    assert response.status_code == 200
    assert upstream.raw_chunk_size == 64 * 1024
    assert client_options == [{"timeout": 30.0, "follow_redirects": False, "trust_env": False}]
    assert calls == [
        (
            "GET",
            TCGDEX_SETS_URL,
            {
                "headers": {
                    "Accept-Encoding": "identity",
                    "If-None-Match": 'W/"old"',
                },
            },
        )
    ]


def test_httpx_tcgdex_transport_does_not_follow_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = StubResponse(302, {"location": "https://unapproved.example/sets"})
    calls, client_options = install_stream(monkeypatch, upstream)

    with pytest.raises(TCGdexHTTPError) as raised:
        HTTPXTCGdexTransport().get(
            TCGDEX_SETS_URL,
            headers={},
            timeout_seconds=TCGDEX_TIMEOUT_SECONDS,
        )

    assert raised.value.status_code == 302
    assert upstream.iterated is False
    assert client_options[0]["follow_redirects"] is False
    assert calls[0][2]["headers"]["Accept-Encoding"] == "identity"


@pytest.mark.parametrize(
    "response",
    (
        StubResponse(200, {"content-length": "65"}, (b"x" * 65,)),
        StubResponse(200, {}, (b"x" * 32, b"y" * 33)),
    ),
)
def test_httpx_tcgdex_transport_rejects_declared_or_streamed_overflow(
    monkeypatch: pytest.MonkeyPatch,
    response: StubResponse,
) -> None:
    install_stream(monkeypatch, response)

    with pytest.raises(TCGdexResponseTooLarge, match="byte cap"):
        HTTPXTCGdexTransport(max_response_bytes=64).get(
            TCGDEX_SETS_URL,
            headers={},
            timeout_seconds=TCGDEX_TIMEOUT_SECONDS,
        )


def test_httpx_tcgdex_transport_rejects_any_other_url_timeout_or_larger_cap() -> None:
    transport = HTTPXTCGdexTransport()

    with pytest.raises(ValueError, match="fixed English sets endpoint"):
        transport.get(
            "https://api.tcgdex.net/v2/en/cards",
            headers={},
            timeout_seconds=TCGDEX_TIMEOUT_SECONDS,
        )
    with pytest.raises(ValueError, match="30-second"):
        transport.get(TCGDEX_SETS_URL, headers={}, timeout_seconds=31)
    with pytest.raises(ValueError, match=str(TCGDEX_MAX_RESPONSE_BYTES)):
        HTTPXTCGdexTransport(max_response_bytes=TCGDEX_MAX_RESPONSE_BYTES + 1)


def test_httpx_tcgdex_transport_rejects_encoded_responses_before_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = StubResponse(200, {"content-encoding": "gzip"}, (b"compressed",))
    install_stream(monkeypatch, upstream)

    with pytest.raises(tcgdex.TCGdexError, match="encoding is not allowed"):
        HTTPXTCGdexTransport().get(
            TCGDEX_SETS_URL,
            headers={},
            timeout_seconds=TCGDEX_TIMEOUT_SECONDS,
        )

    assert upstream.iterated is False


def test_httpx_tcgdex_transport_enforces_one_absolute_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = StubResponse(200, {}, (b"[", b"]"), delay_seconds=0.02)
    install_stream(monkeypatch, upstream)

    with pytest.raises(TCGdexRequestError, match="absolute deadline"):
        HTTPXTCGdexTransport(total_timeout_seconds=0.01).get(
            TCGDEX_SETS_URL,
            headers={},
            timeout_seconds=TCGDEX_TIMEOUT_SECONDS,
        )
