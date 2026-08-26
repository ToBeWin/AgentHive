"""Unit tests for quarterly budget period window calculation."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from app.llm.budget import _period_window
from app.models.llm import LLMBudget


def _budget(period: str, *, custom_start=None, custom_end=None) -> LLMBudget:
    return LLMBudget(
        tenant_id=uuid4(),
        scope_type="tenant",
        scope_id=None,
        period=period,
        amount_usd=Decimal("100"),
        hard_limit=True,
        is_active=True,
        custom_period_start=custom_start,
        custom_period_end=custom_end,
    )


class QuarterlyWindowTests(unittest.TestCase):
    """Quarterly budgets should align to calendar quarters (Q1=Jan-Mar, ...)."""

    def _assert_quarter(self, month: int, expected_start_month: int) -> None:
        # Patch utc_now to a fixed month in 2026.
        fixed = datetime(2026, month, 15, 10, 30, tzinfo=timezone.utc)
        with patch("app.llm.budget.utc_now", return_value=fixed):
            start, end = _period_window(_budget("quarterly"))
        self.assertEqual(
            start,
            datetime(2026, expected_start_month, 1, tzinfo=timezone.utc),
        )
        # End is the first day of the next quarter.
        expected_end_month = expected_start_month + 3
        if expected_end_month > 12:
            expected_end = datetime(2027, expected_end_month - 12, 1, tzinfo=timezone.utc)
        else:
            expected_end = datetime(2026, expected_end_month, 1, tzinfo=timezone.utc)
        self.assertEqual(end, expected_end)

    def test_q1_january(self) -> None:
        self._assert_quarter(1, 1)

    def test_q1_february(self) -> None:
        self._assert_quarter(2, 1)

    def test_q1_march(self) -> None:
        self._assert_quarter(3, 1)

    def test_q2_april(self) -> None:
        self._assert_quarter(4, 4)

    def test_q2_may(self) -> None:
        self._assert_quarter(5, 4)

    def test_q2_june(self) -> None:
        self._assert_quarter(6, 4)

    def test_q3_july(self) -> None:
        self._assert_quarter(7, 7)

    def test_q3_august(self) -> None:
        self._assert_quarter(8, 7)

    def test_q3_september(self) -> None:
        self._assert_quarter(9, 7)

    def test_q4_october(self) -> None:
        self._assert_quarter(10, 10)

    def test_q4_november(self) -> None:
        self._assert_quarter(11, 10)

    def test_q4_december_rolls_into_next_year(self) -> None:
        fixed = datetime(2026, 12, 15, 10, 30, tzinfo=timezone.utc)
        with patch("app.llm.budget.utc_now", return_value=fixed):
            start, end = _period_window(_budget("quarterly"))
        self.assertEqual(start, datetime(2026, 10, 1, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2027, 1, 1, tzinfo=timezone.utc))

    def test_daily_and_monthly_unchanged(self) -> None:
        """Existing periods must keep their behaviour."""
        fixed = datetime(2026, 5, 15, 10, 30, tzinfo=timezone.utc)
        with patch("app.llm.budget.utc_now", return_value=fixed):
            daily_start, daily_end = _period_window(_budget("daily"))
            monthly_start, monthly_end = _period_window(_budget("monthly"))
        # Daily: 2026-05-15 to 2026-05-16
        self.assertEqual(daily_start, datetime(2026, 5, 15, tzinfo=timezone.utc))
        self.assertEqual(daily_end, datetime(2026, 5, 16, tzinfo=timezone.utc))
        # Monthly: 2026-05-01 to 2026-06-01
        self.assertEqual(monthly_start, datetime(2026, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(monthly_end, datetime(2026, 6, 1, tzinfo=timezone.utc))

    def test_custom_period_takes_precedence(self) -> None:
        custom_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        custom_end = datetime(2026, 3, 31, tzinfo=timezone.utc)
        budget = _budget(
            "custom",
            custom_start=custom_start,
            custom_end=custom_end,
        )
        start, end = _period_window(budget)
        self.assertEqual(start, custom_start)
        self.assertEqual(end, custom_end)


if __name__ == "__main__":
    unittest.main()
