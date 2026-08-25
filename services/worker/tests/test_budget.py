from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pokecrack_worker.extraction.budget import (
    BudgetGate,
    BudgetLedger,
    BudgetLimits,
    BudgetStatus,
    ExecutionStatus,
    JobState,
    PendingAIJob,
)
from pokecrack_worker.extraction.providers import AIRunMetadata, TokenUsage

UTC = UTC


def ai_run(run_id: str, at: datetime, cost: str) -> AIRunMetadata:
    return AIRunMetadata(
        run_id=run_id,
        operation="extract",
        provider="fixture",
        model="fixture",
        schema_name="extractor_output",
        started_at=at,
        completed_at=at,
        attempts=1,
        usage=TokenUsage(0, 0),
        cost_aud=Decimal(cost),
    )


class BudgetLedgerTests(unittest.TestCase):
    def test_record_run_is_idempotent_and_tracks_utc_day_and_month(self) -> None:
        ledger = BudgetLedger(BudgetLimits(Decimal("5"), Decimal("20")))
        yesterday = datetime(2026, 8, 24, 23, 59, tzinfo=UTC)
        today = datetime(2026, 8, 25, 0, 1, tzinfo=UTC)

        self.assertTrue(ledger.record_run(ai_run("one", yesterday, "3.25")))
        self.assertTrue(ledger.record_run(ai_run("two", today, "2.50")))
        self.assertFalse(ledger.record_run(ai_run("two", today, "99")))

        snapshot = ledger.snapshot(today)
        self.assertEqual(snapshot.daily_spend_aud, Decimal("2.50"))
        self.assertEqual(snapshot.monthly_spend_aud, Decimal("5.75"))
        self.assertEqual(snapshot.daily_remaining_aud, Decimal("2.50"))
        self.assertEqual(snapshot.monthly_remaining_aud, Decimal("14.25"))

    def test_committed_reservations_remain_charged_to_their_start_period(self) -> None:
        cases = (
            (
                datetime(2026, 8, 24, 23, 59, 59, tzinfo=UTC),
                datetime(2026, 8, 25, 0, 0, tzinfo=UTC),
                Decimal("2"),
            ),
            (
                datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC),
                datetime(2026, 9, 1, 0, 0, tzinfo=UTC),
                Decimal("1"),
            ),
        )
        for started_at, next_period, expected_monthly in cases:
            with self.subTest(started_at=started_at):
                ledger = BudgetLedger(BudgetLimits(Decimal("1"), Decimal("10")))
                previous = ledger.reserve(Decimal("1"), at=started_at)
                ledger.reserve(Decimal("1"), at=next_period)
                completed = replace(
                    ai_run("previous", started_at, "1"),
                    completed_at=next_period,
                )

                ledger.commit(previous, completed)
                snapshot = ledger.snapshot(next_period + timedelta(seconds=1))

                self.assertEqual(snapshot.daily_spend_aud, Decimal("1"))
                self.assertEqual(snapshot.monthly_spend_aud, expected_monthly)

    def test_check_pauses_at_daily_or_monthly_cap_but_allows_exact_boundary(self) -> None:
        ledger = BudgetLedger(BudgetLimits(Decimal("5"), Decimal("10")))
        yesterday = datetime(2026, 8, 24, 12, tzinfo=UTC)
        today = datetime(2026, 8, 25, 12, tzinfo=UTC)
        tomorrow = datetime(2026, 8, 26, 12, tzinfo=UTC)
        ledger.record_run(ai_run("previous", yesterday, "4"))
        ledger.record_run(ai_run("current", today, "4"))

        exact = ledger.check(Decimal("1"), at=today)
        daily_pause = ledger.check(Decimal("1.01"), at=today)
        monthly_pause = ledger.check(Decimal("2.01"), at=tomorrow)

        self.assertEqual(exact.status, BudgetStatus.AVAILABLE)
        self.assertTrue(exact.allowed)
        self.assertEqual(daily_pause.status, BudgetStatus.BUDGET_PAUSED)
        self.assertEqual(daily_pause.reason, "daily_limit")
        self.assertFalse(daily_pause.allowed)
        self.assertEqual(monthly_pause.status, BudgetStatus.BUDGET_PAUSED)
        self.assertEqual(monthly_pause.reason, "monthly_limit")


class BudgetGateTests(unittest.TestCase):
    def test_budget_pause_does_not_run_work_or_change_pending_job(self) -> None:
        now = datetime(2026, 8, 25, 12, tzinfo=UTC)
        ledger = BudgetLedger(BudgetLimits(Decimal("1"), Decimal("10")))
        ledger.record_run(ai_run("spent", now, "1"))
        gate = BudgetGate(ledger)
        job = PendingAIJob("job-7")
        called = False

        def work() -> object:
            nonlocal called
            called = True
            return object()

        result = gate.execute(job, Decimal("0.01"), work, at=now)

        self.assertEqual(result.status, ExecutionStatus.BUDGET_PAUSED)
        self.assertEqual(result.status.value, "budget_paused")
        self.assertIs(result.job, job)
        self.assertEqual(result.job.state, JobState.PENDING)
        self.assertIsNone(result.value)
        self.assertFalse(called)


if __name__ == "__main__":
    unittest.main()
