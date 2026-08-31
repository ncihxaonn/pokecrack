"""Bounded, duplicate-key-safe JSONL loader for authorized opening bundles."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import AuthorizedOpeningSubmission

MAX_BUNDLE_ROWS = 100
MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_LINE_BYTES = 16 * 1024


@dataclass(frozen=True, slots=True)
class AuthorizedOpeningBundleError(ValueError):
    code: str
    line: int | None = None

    def __str__(self) -> str:
        location = f" at line {self.line}" if self.line is not None else ""
        return f"authorized opening bundle {self.code}{location}"


class _DuplicateKey(ValueError):
    pass


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def load_authorized_opening_bundle(
    path: str | Path,
    *,
    max_rows: int = MAX_BUNDLE_ROWS,
    max_bytes: int = MAX_BUNDLE_BYTES,
    max_line_bytes: int = MAX_LINE_BYTES,
) -> tuple[AuthorizedOpeningSubmission, ...]:
    if max_rows < 1 or max_bytes < 1 or max_line_bytes < 1:
        raise ValueError("bundle limits must be positive")
    submissions: list[AuthorizedOpeningSubmission] = []
    seen_submission_keys: set[str] = set()
    seen_provenance: set[str] = set()
    total_bytes = 0
    try:
        stream = Path(path).open("rb")
    except OSError as error:
        raise AuthorizedOpeningBundleError("input_unavailable") from error
    with stream:
        for line_number, raw_line in enumerate(stream, start=1):
            total_bytes += len(raw_line)
            if total_bytes > max_bytes:
                raise AuthorizedOpeningBundleError("file_too_large", line_number)
            if len(raw_line) > max_line_bytes:
                raise AuthorizedOpeningBundleError("line_too_large", line_number)
            if not raw_line.strip():
                continue
            if len(submissions) >= max_rows:
                raise AuthorizedOpeningBundleError("too_many_rows", line_number)
            try:
                text = raw_line.decode("utf-8", errors="strict")
                value = json.loads(
                    text,
                    object_pairs_hook=_strict_object,
                    parse_constant=_reject_constant,
                )
            except UnicodeDecodeError as error:
                raise AuthorizedOpeningBundleError("invalid_utf8", line_number) from error
            except _DuplicateKey as error:
                raise AuthorizedOpeningBundleError("duplicate_json_key", line_number) from error
            except (json.JSONDecodeError, ValueError, TypeError) as error:
                raise AuthorizedOpeningBundleError("invalid_json", line_number) from error
            if not isinstance(value, dict):
                raise AuthorizedOpeningBundleError("row_must_be_object", line_number)
            try:
                submission = AuthorizedOpeningSubmission.model_validate(value)
            except ValidationError as error:
                raise AuthorizedOpeningBundleError("invalid_row", line_number) from error
            if submission.submission_key in seen_submission_keys:
                raise AuthorizedOpeningBundleError("duplicate_submission_key", line_number)
            if submission.provenance_dedupe_sha256 in seen_provenance:
                raise AuthorizedOpeningBundleError("duplicate_provenance", line_number)
            seen_submission_keys.add(submission.submission_key)
            seen_provenance.add(submission.provenance_dedupe_sha256)
            submissions.append(submission)
    if not submissions:
        raise AuthorizedOpeningBundleError("empty_bundle")
    return tuple(submissions)
