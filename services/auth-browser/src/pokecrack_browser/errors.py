"""Stable service error categories and JSON payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUIRED_ERROR_CATEGORIES = (
    "auth_required",
    "extension_disconnected",
    "daemon_unavailable",
    "adapter_failed",
    "timeout",
    "invalid_json",
    "rate_limited",
    "source_unavailable",
)

EXIT_CODES = {
    "invalid_request": 2,
    "auth_required": 20,
    "extension_disconnected": 21,
    "daemon_unavailable": 22,
    "adapter_failed": 23,
    "timeout": 24,
    "invalid_json": 25,
    "rate_limited": 26,
    "source_unavailable": 27,
    "profile_busy": 28,
    "not_running": 29,
    "internal_error": 70,
}


@dataclass(slots=True)
class ServiceError(Exception):
    category: str
    message: str
    details: dict[str, Any] | None = None

    @property
    def exit_code(self) -> int:
        return EXIT_CODES.get(self.category, EXIT_CODES["internal_error"])

    def as_payload(self) -> dict[str, Any]:
        error: dict[str, Any] = {"category": self.category, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"ok": False, "error": error}
