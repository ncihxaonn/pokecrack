"""Explicit, source-specific Scrapling adapter registries."""

from __future__ import annotations

from pokecrack_worker.collectors.base import (
    DynamicAdapterRegistry,
    HTTPAdapterRegistry,
    HTTPClient,
)

from .adapters.dynamic_fixture import DynamicFixtureAdapter
from .adapters.example_public import ExamplePublicAdapter
from .adapters.public_studies import (
    comicbook_perfect_order_adapter,
    wargamer_chaos_rising_adapter,
)


def build_fixture_registries(
    *, http_client: HTTPClient, dynamic_client: HTTPClient
) -> tuple[HTTPAdapterRegistry, DynamicAdapterRegistry]:
    """Build only the two bounded synthetic adapters; there is no catch-all."""

    static_registry = HTTPAdapterRegistry()
    static_registry.register("example_public", ExamplePublicAdapter(client=http_client))
    dynamic_registry = DynamicAdapterRegistry()
    dynamic_registry.register("dynamic_fixture", DynamicFixtureAdapter(client=dynamic_client))
    return static_registry, dynamic_registry


def build_live_static_registry(*, http_client: HTTPClient) -> HTTPAdapterRegistry:
    """Build only explicitly reviewed live static adapters; there is no catch-all."""

    static_registry = HTTPAdapterRegistry()
    static_registry.register(
        "comicbook_perfect_order_study",
        comicbook_perfect_order_adapter(client=http_client),
    )
    static_registry.register(
        "wargamer_chaos_rising_study",
        wargamer_chaos_rising_adapter(client=http_client),
    )
    return static_registry


__all__ = [
    "DynamicAdapterRegistry",
    "HTTPAdapterRegistry",
    "build_fixture_registries",
    "build_live_static_registry",
]
