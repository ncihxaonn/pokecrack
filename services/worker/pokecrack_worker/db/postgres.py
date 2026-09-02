"""Minimal psycopg query boundary used by queue repositories."""

from __future__ import annotations

import socket
import time
from collections.abc import Callable, Mapping
from typing import Any

CONNECTION_MAX_ATTEMPTS = 3
# libpq bounds each acquisition to 10 seconds.  A single operation can spend
# at most three such attempts plus two short delays; the Nostr healthcheck
# allows for its two independent database operations.
CONNECTION_ATTEMPT_TIMEOUT_SECONDS = 10
CONNECTION_RETRY_DELAY_SECONDS = 0.25
_TRANSIENT_CONNECTION_MARKERS = (
    "connection timed out",
    "operation timed out",
    "timeout expired",
    "connection refused",
    "connection reset by peer",
    "server closed the connection unexpectedly",
    "connection terminated unexpectedly",
    "could not translate host name",
    "temporary failure in name resolution",
    "name or service not known",
    "nodename nor servname provided",
    "network is unreachable",
    "no route to host",
    "cannot assign requested address",
)


def _is_transient_connection_error(error: BaseException) -> bool:
    """Recognize only explicit transport failures at connection acquisition."""

    sqlstate = getattr(error, "sqlstate", None)
    if isinstance(sqlstate, str) and sqlstate.startswith("08"):
        return True
    if isinstance(error, (ConnectionError, TimeoutError, socket.gaierror)):
        return True
    message = str(error).casefold()
    return any(marker in message for marker in _TRANSIENT_CONNECTION_MARKERS)


def _connect_with_retry(connection_factory: Callable[[], Any]) -> Any:
    """Retry only opening a connection; never wraps statements or commits."""

    for attempt in range(CONNECTION_MAX_ATTEMPTS):
        try:
            return connection_factory()
        except Exception as error:
            if (
                not _is_transient_connection_error(error)
                or attempt + 1 >= CONNECTION_MAX_ATTEMPTS
            ):
                raise
            time.sleep(CONNECTION_RETRY_DELAY_SECONDS)
    raise AssertionError("connection retry loop exhausted unexpectedly")


class PsycopgQueryExecutor:
    """Open a short transaction for each atomic repository operation."""

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    @classmethod
    def from_dsn(
        cls,
        dsn: str,
        *,
        retry_connection: bool = False,
    ) -> PsycopgQueryExecutor:
        def connect() -> Any:
            import psycopg

            if retry_connection:
                return _connect_with_retry(
                    lambda: psycopg.connect(
                        dsn,
                        connect_timeout=CONNECTION_ATTEMPT_TIMEOUT_SECONDS,
                    )
                )
            return psycopg.connect(dsn)

        return cls(connect)

    def query(self, sql: str, params: Mapping[str, object]) -> tuple[Mapping[str, Any], ...]:
        from psycopg.rows import dict_row

        with self._connection_factory() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(sql, params)
                rows = tuple(cursor.fetchall()) if cursor.description is not None else ()
            connection.commit()
        return rows

    def execute(self, sql: str, params: Mapping[str, object]) -> int:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                affected = int(cursor.rowcount)
            connection.commit()
        return affected
