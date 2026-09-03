"""Minimal psycopg query boundary used by queue repositories."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


class PsycopgQueryExecutor:
    """Open a short transaction for each atomic repository operation."""

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        *,
        statement_timeout_seconds: float | None = 30,
    ) -> None:
        self._connection_factory = connection_factory
        if statement_timeout_seconds is not None and not 0 < statement_timeout_seconds <= 120:
            raise ValueError("statement_timeout_seconds must be in (0, 120]")
        self._statement_timeout_ms = (
            None if statement_timeout_seconds is None else int(statement_timeout_seconds * 1_000)
        )

    @classmethod
    def from_dsn(
        cls,
        dsn: str,
        *,
        connect_timeout_seconds: int = 10,
        statement_timeout_seconds: float | None = 30,
    ) -> PsycopgQueryExecutor:
        if not 1 <= connect_timeout_seconds <= 120:
            raise ValueError("connect_timeout_seconds must be between 1 and 120")

        def connect() -> Any:
            import psycopg

            return psycopg.connect(dsn, connect_timeout=connect_timeout_seconds)

        return cls(connect, statement_timeout_seconds=statement_timeout_seconds)

    def query(self, sql: str, params: Mapping[str, object]) -> tuple[Mapping[str, Any], ...]:
        from psycopg.rows import dict_row

        with self._connection_factory() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                if self._statement_timeout_ms is not None:
                    cursor.execute(
                        "SELECT pg_catalog.set_config('statement_timeout', %s, true)",
                        (str(self._statement_timeout_ms),),
                    )
                cursor.execute(sql, params)
                rows = tuple(cursor.fetchall()) if cursor.description is not None else ()
            connection.commit()
        return rows

    def execute(self, sql: str, params: Mapping[str, object]) -> int:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                if self._statement_timeout_ms is not None:
                    cursor.execute(
                        "SELECT pg_catalog.set_config('statement_timeout', %s, true)",
                        (str(self._statement_timeout_ms),),
                    )
                cursor.execute(sql, params)
                affected = int(cursor.rowcount)
            connection.commit()
        return affected
