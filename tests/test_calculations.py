import unittest
from datetime import date, timedelta
from decimal import Decimal
import random

from calc.calculations import (
    calc_accumulated_depreciation, calc_current_value, calc_depreciation_for_period,
    calc_next_billing_date, generate_monthly_stats, generate_weekly_stats,
)


def asset(**changes):
    record = dict(name="设备", category="电子设备", purchase_date="2024-01-01",
                  lifespan_months=1, purchase_price=310, salvage_value=0)
    return dict(record, **changes)


def subscription(**changes):
    record = dict(service_name="服务", start_date="2024-01-01", billing_cycle="monthly", amount=31)
    return dict(record, **changes)


def expense(day, amount):
    return dict(name="开支", category="其他", expense_date=day, amount=amount)


def totals(rows):
    return {field: sum((Decimal(str(row[field])) for row in rows), Decimal(0))
            for field in ("depreciation", "subscriptions", "expenses", "total")}


class ReportTests(unittest.TestCase):
    def both(self, assets, subs, expenses, start, end):
        weekly = generate_weekly_stats(assets, subs, expenses, start, end)
        monthly = generate_monthly_stats(assets, subs, expenses, start, end)
        self.assertEqual(totals(weekly), totals(monthly))
        for rows in (weekly, monthly):
            self.assertEqual(rows[0]["start"], start.isoformat())
            self.assertEqual(rows[-1]["end"], end.isoformat())
            for row in rows:
                self.assertEqual(Decimal(str(row["total"])), sum(
                    (Decimal(str(row[key])) for key in ("depreciation", "subscriptions", "expenses"))))
        return weekly, monthly

    def test_full_month_manual_totals(self):
        weekly, monthly = self.both([asset()], [subscription()],
            [expense("2024-01-07", 12.5), expense("2024-01-31", 5), expense("2024-02-01", 99)],
            date(2024, 1, 1), date(2024, 1, 31))
        self.assertEqual(totals(monthly), dict(depreciation=Decimal(310), subscriptions=Decimal(31),
                                            expenses=Decimal("17.50"), total=Decimal("358.50")))
        self.assertEqual([r["depreciation"] for r in weekly], [70, 70, 70, 70, 30])
        self.assertEqual(weekly[0]["total"], 89.5)

    def test_eight_days_no_duplicate_week(self):
        weekly, monthly = self.both([asset()], [subscription()], [], date(2024, 1, 1), date(2024, 1, 8))
        self.assertEqual([r["depreciation"] for r in weekly], [70, 10])
        self.assertEqual(monthly[0]["total"], 88)

    def test_partial_month_clipped_both_ends(self):
        _, monthly = self.both([asset()], [subscription()],
            [expense("2024-01-09", 99), expense("2024-01-10", 2), expense("2024-01-15", 3),
             expense("2024-01-16", 99)], date(2024, 1, 10), date(2024, 1, 15))
        self.assertEqual(monthly[0]["depreciation"], 60)
        self.assertEqual(monthly[0]["subscriptions"], 6)
        self.assertEqual(monthly[0]["expenses"], 5)

    def test_single_day_included(self):
        _, monthly = self.both([asset()], [subscription()], [expense("2024-01-31", 3)],
                              date(2024, 1, 31), date(2024, 1, 31))
        self.assertEqual(monthly[0]["total"], 14)

    def test_iso_week_year_and_partial_week(self):
        weekly, _ = self.both([], [], [expense("2021-01-01", 1), expense("2021-01-04", 2)],
                              date(2021, 1, 1), date(2021, 1, 6))
        self.assertEqual([r["week"] for r in weekly], ["2020-W53", "2021-W01"])
        self.assertEqual(weekly[0]["end"], "2021-01-03")
        self.assertEqual(weekly[1]["start"], "2021-01-04")

    def test_midweek_start_no_extra_days(self):
        weekly, _ = self.both([asset()], [subscription()], [], date(2024, 1, 3), date(2024, 1, 9))
        self.assertEqual([r["depreciation"] for r in weekly], [50, 20])
        self.assertEqual([r["subscriptions"] for r in weekly], [5, 2])

    def test_leap_day_and_end_of_life_excluded(self):
        a = asset(purchase_date="2024-01-31", purchase_price=290)
        _, monthly = self.both([a], [subscription(start_date="2024-02-01", amount=29)], [],
                              date(2024, 1, 31), date(2024, 2, 29))
        self.assertEqual([r["depreciation"] for r in monthly], [10, 280])
        self.assertEqual(monthly[1]["subscriptions"], 29)
        self.assertEqual(calc_depreciation_for_period(a, date(2024, 2, 29), date(2024, 2, 29)), 0)

    def test_anniversary_month_full_lifetime_and_salvage(self):
        a = asset(purchase_date="2023-01-31", lifespan_months=2, purchase_price=220, salvage_value=20)
        _, monthly = self.both([a], [], [], date(2023, 1, 1), date(2023, 4, 30))
        self.assertEqual(totals(monthly)["depreciation"], 200)
        self.assertEqual(calc_depreciation_for_period(a, date(2023, 1, 31), date(2023, 2, 27)), 100)
        self.assertEqual(calc_current_value(a, date(2023, 3, 31)), 20)

    def test_zero_depreciation_with_equal_salvage(self):
        _, monthly = self.both([asset(salvage_value=310)], [], [], date(2024, 1, 1), date(2024, 2, 2))
        self.assertEqual(totals(monthly)["depreciation"], 0)

    def test_future_records_and_expired_assets(self):
        _, monthly = self.both([asset(purchase_date="2023-01-01"), asset(purchase_date="2025-01-01")],
                              [subscription(start_date="2024-01-31")], [],
                              date(2024, 1, 1), date(2024, 1, 15))
        self.assertEqual(monthly[0]["total"], 0)

    def test_subscription_starts_midmonth(self):
        _, monthly = self.both([], [subscription(start_date="2024-01-16")], [],
                              date(2024, 1, 1), date(2024, 1, 31))
        self.assertEqual(monthly[0]["subscriptions"], 16)

    def test_quarterly_and_yearly_proration(self):
        _, monthly = self.both([], [subscription(billing_cycle="quarterly", amount=93),
                                   subscription(billing_cycle="yearly", amount=372)], [],
                              date(2024, 1, 1), date(2024, 1, 8))
        self.assertEqual(monthly[0]["subscriptions"], 16)

    def test_cents_do_not_accumulate_rounding_errors(self):
        a = asset(purchase_date="2023-12-31", lifespan_months=3, purchase_price=100, salvage_value=0.01)
        _, monthly = self.both([a], [subscription(billing_cycle="yearly", amount=100)], [],
                              date(2023, 12, 31), date(2024, 3, 30))
        self.assertEqual(totals(monthly)["depreciation"], Decimal("99.99"))

    def test_accumulated_matches_report_through_today(self):
        a = asset(purchase_date="2024-01-15", lifespan_months=3, purchase_price=100)
        end = date(2024, 2, 18)
        self.assertEqual(calc_accumulated_depreciation(a, end),
                         calc_depreciation_for_period(a, date(2024, 1, 15), end))
        self.assertEqual(calc_accumulated_depreciation(a, date(2024, 1, 14)), 0)

    def test_empty_periods_have_zero_rows(self):
        weekly, monthly = self.both([], [], [], date(2024, 1, 31), date(2024, 2, 2))
        self.assertEqual(len(weekly), 1)
        self.assertEqual(len(monthly), 2)
        self.assertEqual(totals(monthly)["total"], 0)

    def test_reverse_range_rejected(self):
        for generate in (generate_weekly_stats, generate_monthly_stats):
            with self.assertRaises(ValueError):
                generate([], [], [], date(2024, 2, 1), date(2024, 1, 1))

    def test_billing_dates_do_not_drift_after_february(self):
        self.assertEqual(calc_next_billing_date(subscription(start_date="2023-01-31"), date(2023, 2, 28)),
                         date(2023, 3, 31))
        self.assertEqual(calc_next_billing_date(subscription(start_date="2024-02-29", billing_cycle="yearly"),
                                              date(2027, 3, 1)), date(2028, 2, 29))

    def test_many_ranges_partition_consistently(self):
        rng = random.Random(42)
        assets = [asset(purchase_date="2023-12-31", lifespan_months=15, purchase_price=999.99, salvage_value=50),
                  asset(purchase_date="2024-02-29", lifespan_months=1, purchase_price=0.01)]
        subs = [subscription(start_date="2024-01-17", amount=29.99),
                subscription(start_date="2023-12-25", billing_cycle="yearly", amount=199.99)]
        expenses = [expense("2024-02-29", 12.34), expense("2024-12-31", 90)]
        for i in range(100):
            start = date(2023, 12, 20) + timedelta(days=rng.randrange(370))
            end = start + timedelta(days=rng.randrange(1, 150))
            with self.subTest(start=start, end=end):
                _, monthly = self.both(assets, subs, expenses, start, end)
                self.assertEqual(totals(monthly)["depreciation"], sum(
                    (Decimal(str(calc_depreciation_for_period(a, start, end))) for a in assets)))


if __name__ == "__main__":
    unittest.main()
