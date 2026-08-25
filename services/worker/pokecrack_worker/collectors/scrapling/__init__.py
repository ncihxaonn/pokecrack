"""Policy-gated Scrapling transports and explicit source adapters.

The optional third-party package is lazy: importing this package is safe in the
base CI environment without the ``scrapling`` extra installed.
"""

from .backend import (
    ScraplingBackend,
    ScraplingBindings,
    ScraplingResponseError,
    ScraplingUnavailableError,
)

__all__ = [
    "ScraplingBackend",
    "ScraplingBindings",
    "ScraplingResponseError",
    "ScraplingUnavailableError",
]
