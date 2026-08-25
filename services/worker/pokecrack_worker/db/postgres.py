"""Minimal psycopg query boundary used by queue repositories."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


class PsycopgQueryExecutor:
    """Open a short transaction for each atomic repository operation."""

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    @classmethod
    def from_dsn(cls, dsn: str) -> PsycopgQueryExecutor:
        def connect() -> Any:
            import psycopg

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
