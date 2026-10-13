from contextlib import closing
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from db import database as db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path_patch = patch.object(db, "DB_PATH", str(Path(self.temp.name) / "budget.db"))
        legacy_patch = patch.object(db, "legacy_database_paths", return_value=[])
        path_patch.start()
        legacy_patch.start()
        self.addCleanup(path_patch.stop)
        self.addCleanup(legacy_patch.stop)
        db.init_db()

    def test_crud_and_range_query(self):
        a = db.add_asset("设备", "电子设备", "2024-01-01", 1, 310, 10)
        s = db.add_subscription("服务", "2024-01-01", "monthly", 31)
        e = db.add_expense("开支", "其他", "2024-01-07", 12.5)
        db.update_asset(a, "设备2", "其他", "2024-01-01", 2, 310, 10)
        db.update_subscription(s, "服务2", "2024-01-01", "quarterly", 93)
        db.update_expense(e, "开支2", "其他", "2024-01-08", 15)
        self.assertEqual(db.get_asset_by_id(a)["name"], "设备2")
        self.assertEqual(db.get_subscription_by_id(s)["amount"], 93)
        self.assertEqual(len(db.get_expenses_in_range("2024-01-08", "2024-01-08")), 1)
        db.delete_asset(a)
        db.delete_subscription(s)
        db.delete_expense(e)
        self.assertEqual(db.get_all_assets() + db.get_all_subscriptions() + db.get_all_expenses(), [])

    def test_asset_validation_at_write_boundary(self):
        valid = dict(name="设备", category="电子设备", purchase_date="2024-01-01",
                     lifespan_months=12, purchase_price=100, salvage_value=0)
        bad = [dict(salvage_value=101), dict(salvage_value=-1), dict(purchase_price=float("inf")),
               dict(purchase_price=float("nan")), dict(purchase_price=0), dict(purchase_price=1.001),
               dict(lifespan_months=1.5), dict(lifespan_months=True), dict(lifespan_months=0),
               dict(lifespan_months=601), dict(name="  "), dict(category=""), dict(purchase_date="2024-02-30")]
        for change in bad:
            with self.subTest(change=change), self.assertRaises(ValueError):
                db.add_asset(**dict(valid, **change))
        self.assertEqual(db.get_all_assets(), [])

    def test_expense_and_subscription_validation(self):
        for amount in (-1, 0, float("inf"), float("nan"), 1.001, 10000000):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                db.add_expense("开支", "其他", "2024-01-01", amount)
        with self.assertRaises(ValueError):
            db.add_subscription("服务", "2024-01-01", "unknown", 1)
        with self.assertRaises(ValueError):
            db.add_subscription(" ", "2024-01-01", "monthly", 1)
        with self.assertRaises(ValueError):
            db.add_expense("开支", " ", "2024-01-01", 1)

    def test_invalid_update_preserves_record(self):
        a = db.add_asset("设备", "电子设备", "2024-01-01", 12, 100)
        with self.assertRaises(ValueError):
            db.update_asset(a, "设备", "电子设备", "2024-01-01", 12, 100, 101)
        self.assertEqual(db.get_asset_by_id(a)["salvage_value"], 0)

    def test_sql_triggers_reject_invalid_records_and_updates(self):
        with closing(db.get_connection()) as conn:
            for statement in [
                "INSERT INTO assets (name, category, purchase_date, lifespan_months, purchase_price, salvage_value) VALUES ('设备','其他','2024-01-01',12,100,101)",
                "INSERT INTO assets (name, purchase_date, lifespan_months, purchase_price) VALUES ('设备','2024-02-30',12,100)",
                "INSERT INTO subscriptions (service_name,start_date,billing_cycle,amount) VALUES ('服务','2024-01-01','unknown',1)",
                "INSERT INTO one_time_expenses (name,expense_date,amount) VALUES ('开支','2024-01-01',-1)",
                "INSERT INTO one_time_expenses (name,expense_date,amount) VALUES ('开支','nonsense',1)",
            ]:
                with self.subTest(sql=statement), self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(statement)
                conn.rollback()
        a = db.add_asset("设备", "其他", "2024-01-01", 1, 100)
        with self.assertRaises(sqlite3.IntegrityError):
            db._execute("UPDATE assets SET purchase_price=0 WHERE id=?", (a,))
        self.assertEqual(db.get_asset_by_id(a)["purchase_price"], 100)

    def test_existing_tables_receive_constraints_without_losing_data(self):
        a = db.add_asset("设备", "其他", "2024-01-01", 1, 100)
        with db._connection() as conn:
            for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
                conn.execute(f"DROP TRIGGER {name}")
        db.init_db()
        self.assertEqual(db.get_asset_by_id(a)["purchase_price"], 100)
        with self.assertRaises(sqlite3.IntegrityError):
            db._execute("UPDATE assets SET salvage_value=101 WHERE id=?", (a,))

    def test_connection_closed_and_transaction_rolled_back_after_error(self):
        conn = db.get_connection()
        with patch.object(db, "get_connection", return_value=conn), self.assertRaises(sqlite3.IntegrityError):
            with db._connection() as transaction:
                transaction.execute("INSERT INTO one_time_expenses (name,expense_date,amount) VALUES ('开支','2024-01-01',1)")
                transaction.execute("INSERT INTO one_time_expenses (name,expense_date,amount) VALUES ('开支','2024-01-01',-1)")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
        self.assertEqual(db.get_all_expenses(), [])

    def test_active_assets_respect_purchase_and_month_end_lifetime(self):
        a = db.add_asset("设备", "其他", "2024-01-31", 1, 100)
        self.assertEqual(db.get_active_assets_as_of("2024-01-30"), [])
        self.assertEqual(db.get_active_assets_as_of("2024-02-28")[0]["id"], a)
        self.assertEqual(db.get_active_assets_as_of("2024-02-29"), [])
