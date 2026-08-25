"""Idempotent aggregate persistence contracts and fixture repository."""

from __future__ import annotations

from threading import RLock

from .models import AggregateRecord, AggregateScope, PublicAggregateSummary


class InMemoryAggregateRepository:
    def __init__(self) -> None:
        self._records: dict[tuple[AggregateScope, str, str], AggregateRecord] = {}
        self._public: dict[tuple[AggregateScope, str, str], PublicAggregateSummary] = {}
        self._lock = RLock()

    def upsert(self, record: AggregateRecord) -> None:
        with self._lock:
            self._records[(record.scope, record.key, record.version)] = record

    def upsert_public(self, summary: PublicAggregateSummary) -> None:
        with self._lock:
            self._public[(summary.scope, summary.id, summary.version)] = summary

    def get(self, scope: AggregateScope, key: str, *, version: str) -> AggregateRecord | None:
        with self._lock:
            return self._records.get((scope, key, version))

    def get_public(
        self, scope: AggregateScope, key: str, *, version: str
    ) -> PublicAggregateSummary | None:
        with self._lock:
            return self._public.get((scope, key, version))

    def list_records(self, *, scope: AggregateScope | None = None) -> tuple[AggregateRecord, ...]:
        with self._lock:
            return tuple(
                record
                for record in self._records.values()
                if scope is None or record.scope is scope
            )

    def list_public(
        self, *, scope: AggregateScope | None = None
    ) -> tuple[PublicAggregateSummary, ...]:
        with self._lock:
            return tuple(
                summary
                for summary in self._public.values()
                if scope is None or summary.scope is scope
            )

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._records)

    @property
    def public_count(self) -> int:
        with self._lock:
            return len(self._public)
