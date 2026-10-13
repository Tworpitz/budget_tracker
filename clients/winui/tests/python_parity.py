"""Generate expectations from the existing Python implementation; verify C# writes.

Usage: python clients/winui/tests/python_parity.py build/winui-tests [--verify]
Only explicitly supplied test directories are written; never touches the user ledger.
"""
import json
from pathlib import Path
import random
import sys
from datetime import date, timedelta
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from calc import calculations as calc
from db import database as db


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if "--verify" in sys.argv:
        with patch.object(db, "DB_PATH", str(output / "interop.db")), patch.object(db, "legacy_database_paths", return_value=[]):
            db.init_db()
            assets, subs, expenses = db.get_all_assets(), db.get_all_subscriptions(), db.get_all_expenses()
            assert assets[0]["name"] == "C# 编辑资产" and assets[0]["salvage_value"] == 10
            assert subs[0]["billing_cycle"] == "quarterly" and subs[0]["amount"] == 93
            assert expenses[0]["notes"] == "C# 中文备注" and expenses[0]["amount"] == 15.25
            for exp in expenses:
                db.update_expense(exp["id"], exp["name"], exp["category"], exp["expense_date"], exp["amount"], "Python 回写")
        print("PASS: Python reads C# changes, triggers and IDs; Python writes back to the same schema")
        return

    assets = [dict(name="月末资产", category="电子设备", purchase_date="2023-12-31", lifespan_months=15, purchase_price=999.99, salvage_value=50),
              dict(name="闰日资产", category="其他", purchase_date="2024-02-29", lifespan_months=1, purchase_price=.01, salvage_value=0),
              dict(name="零折旧", category="其他", purchase_date="2024-01-01", lifespan_months=12, purchase_price=100, salvage_value=100)]
    subs = [dict(service_name="月付", start_date="2024-01-17", billing_cycle="monthly", amount=29.99),
            dict(service_name="年付", start_date="2023-12-25", billing_cycle="yearly", amount=199.99),
            dict(service_name="季付", start_date="2024-02-29", billing_cycle="quarterly", amount=93)]
    expenses = [dict(name="餐饮", category="餐饮", expense_date="2024-02-29", amount=12.34),
                dict(name="交通", category="交通", expense_date="2024-12-31", amount=90)]

    def convert(row, kind):
        return dict(kind=kind, name=row.get("name", row.get("service_name")), category=row.get("category", ""),
                    date=row.get("purchase_date", row.get("start_date", row.get("expense_date"))),
                    months=row.get("lifespan_months", 36), amount=row.get("purchase_price", row.get("amount")),
                    salvage=row.get("salvage_value", 0), cycle=row.get("billing_cycle", "monthly"))

    entries = [convert(a, 0) for a in assets] + [convert(s, 1) for s in subs] + [convert(e, 2) for e in expenses]
    rng = random.Random(42)
    ranges = [(date(2023, 12, 20) + timedelta(days=rng.randrange(740)), rng.randrange(0, 150)) for _ in range(120)]
    ranges += [(date(2024, 2, 29), 0), (date(2024, 1, 1), 30), (date(2020, 12, 28), 10), (date(2023, 12, 31), 500)]
    cases = []
    for start, length in ranges:
        end = start + timedelta(days=length)
        for weekly in (True, False):
            rows = (calc.generate_weekly_stats if weekly else calc.generate_monthly_stats)(assets, subs, expenses, start, end)
            rows = [dict(key=r.get("week", r.get("month")), **{k:v for k,v in r.items() if k not in ("week", "month")}) for r in rows]
            cases.append(dict(start=start.isoformat(), end=end.isoformat(), weekly=weekly, rows=rows))
    snapshots = [dict(entry=convert(a, 0), today=day.isoformat(), accumulated=calc.calc_accumulated_depreciation(a, day), current=calc.calc_current_value(a, day))
                 for a in assets for day in [date(2023,12,30), date(2024,2,29), date(2024,3,31), date(2025,12,1)]]
    billing = []
    for start, cycle, today in [("2023-01-31", "monthly", date(2023,2,28)), ("2024-02-29", "yearly", date(2027,3,1)), ("2024-02-29", "quarterly", date(2024,5,29)), ("2028-01-01", "monthly", date(2024,1,1))]:
        sub = dict(service_name="计费", start_date=start, billing_cycle=cycle, amount=12)
        billing.append(dict(entry=convert(sub,1), today=today.isoformat(), next=calc.calc_next_billing_date(sub,today).isoformat()))
    (output / "parity.json").write_text(json.dumps(dict(entries=entries, cases=cases, snapshots=snapshots, billing=billing), ensure_ascii=False), encoding="utf-8")
    path = output / "interop.db"
    if path.exists():
        raise SystemExit("Test database already exists; choose a fresh output directory.")
    with patch.object(db, "DB_PATH", str(path)), patch.object(db, "legacy_database_paths", return_value=[]):
        db.init_db()
        db.add_asset("Python 资产", "电子设备", "2024-01-01", 12, 310, 10)
        db.add_subscription("Python 订阅", "2024-01-01", "monthly", 31)
        db.add_expense("Python 开支", "餐饮", "2024-01-07", 12.5)
    print(f"Generated {len(cases)} Python report expectations, {len(snapshots)} depreciation snapshots, {len(billing)} billing dates and SQLite interop fixture")


if __name__ == "__main__":
    main()
