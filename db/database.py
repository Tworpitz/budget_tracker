"""SQLite CRUD、事务管理和输入校验。数据库存放在用户数据目录。"""

from contextlib import contextmanager
from datetime import date
from pathlib import Path
import sqlite3
from typing import Optional

from dateutil.relativedelta import relativedelta

from db.storage import legacy_database_paths, prepare_database, user_database_path
from db.validation import validate_asset, validate_expense, validate_subscription


def get_db_path() -> str:
    return str(user_database_path())


DB_PATH = get_db_path()


def get_connection() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn
    except BaseException:
        conn.close()
        raise


@contextmanager
def _connection():
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    root = Path(__file__).resolve().parent.parent
    prepare_database(Path(DB_PATH), legacy_database_paths(root))
    with _connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '电子设备',
                purchase_date TEXT NOT NULL,
                lifespan_months INTEGER NOT NULL,
                purchase_price REAL NOT NULL,
                salvage_value REAL NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                billing_cycle TEXT NOT NULL,
                amount REAL NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS one_time_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '其他',
                expense_date TEXT NOT NULL,
                amount REAL NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
        """)
        # 触发器同时保护已有表和新表，无需重建或删除用户记录。
        constraints = {
            "assets": ["length(trim(NEW.name)) > 0", "length(trim(NEW.category)) > 0",
                       "typeof(NEW.lifespan_months) = 'integer' AND NEW.lifespan_months BETWEEN 1 AND 600",
                       _amount_check("purchase_price"), _amount_check("salvage_value", zero=True),
                       "NEW.salvage_value <= NEW.purchase_price", _date_check("purchase_date")],
            "subscriptions": ["length(trim(NEW.service_name)) > 0", _date_check("start_date"),
                              "NEW.billing_cycle IN ('monthly', 'quarterly', 'yearly')", _amount_check("amount")],
            "one_time_expenses": ["length(trim(NEW.name)) > 0", "length(trim(NEW.category)) > 0",
                                  _date_check("expense_date"), _amount_check("amount")],
        }
        for table, checks in constraints.items():
            for operation in ("INSERT", "UPDATE"):
                conn.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS validate_{table}_{operation.lower()}
                    BEFORE {operation} ON {table}
                    WHEN NOT coalesce(({' AND '.join('(' + c + ')' for c in checks)}), 0)
                    BEGIN SELECT RAISE(ABORT, 'Invalid BudgetTracker record'); END
                """)


def _amount_check(field: str, zero: bool = False) -> str:
    op = ">=" if zero else ">"
    return (f"typeof(NEW.{field}) IN ('integer', 'real') AND NEW.{field} {op} 0 "
            f"AND NEW.{field} <= 9999999 AND NEW.{field} = round(NEW.{field}, 2)")


def _date_check(field: str) -> str:
    return f"length(NEW.{field}) = 10 AND date(NEW.{field}, '+0 days') = NEW.{field}"


def _execute(sql: str, values=()) -> int:
    with _connection() as conn:
        return conn.execute(sql, values).lastrowid


def _rows(sql: str, values=()) -> list[dict]:
    with _connection() as conn:
        return [dict(row) for row in conn.execute(sql, values).fetchall()]


def _by_id(table: str, record_id: int) -> Optional[dict]:
    rows = _rows(f"SELECT * FROM {table} WHERE id=?", (record_id,))
    return rows[0] if rows else None


def add_asset(name: str, category: str, purchase_date: str, lifespan_months: int,
              purchase_price: float, salvage_value: float = 0, notes: str = "") -> int:
    validate_asset(name, category, purchase_date, lifespan_months, purchase_price, salvage_value, notes)
    return _execute("""INSERT INTO assets
        (name, category, purchase_date, lifespan_months, purchase_price, salvage_value, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name, category, purchase_date, lifespan_months, purchase_price, salvage_value, notes))


def update_asset(asset_id: int, name: str, category: str, purchase_date: str,
                 lifespan_months: int, purchase_price: float, salvage_value: float = 0, notes: str = "") -> None:
    validate_asset(name, category, purchase_date, lifespan_months, purchase_price, salvage_value, notes)
    _execute("""UPDATE assets SET name=?, category=?, purchase_date=?, lifespan_months=?,
        purchase_price=?, salvage_value=?, notes=? WHERE id=?""",
        (name, category, purchase_date, lifespan_months, purchase_price, salvage_value, notes, asset_id))


def delete_asset(asset_id: int) -> None:
    _execute("DELETE FROM assets WHERE id=?", (asset_id,))


def get_all_assets() -> list[dict]:
    return _rows("SELECT * FROM assets ORDER BY purchase_date DESC")


def get_asset_by_id(asset_id: int) -> Optional[dict]:
    return _by_id("assets", asset_id)


def add_subscription(service_name: str, start_date: str, billing_cycle: str,
                     amount: float, notes: str = "") -> int:
    validate_subscription(service_name, start_date, billing_cycle, amount, notes)
    return _execute("""INSERT INTO subscriptions (service_name, start_date, billing_cycle, amount, notes)
        VALUES (?, ?, ?, ?, ?)""", (service_name, start_date, billing_cycle, amount, notes))


def update_subscription(sub_id: int, service_name: str, start_date: str,
                        billing_cycle: str, amount: float, notes: str = "") -> None:
    validate_subscription(service_name, start_date, billing_cycle, amount, notes)
    _execute("""UPDATE subscriptions SET service_name=?, start_date=?, billing_cycle=?, amount=?, notes=?
        WHERE id=?""", (service_name, start_date, billing_cycle, amount, notes, sub_id))


def delete_subscription(sub_id: int) -> None:
    _execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))


def get_all_subscriptions() -> list[dict]:
    return _rows("SELECT * FROM subscriptions ORDER BY start_date DESC")


def get_subscription_by_id(sub_id: int) -> Optional[dict]:
    return _by_id("subscriptions", sub_id)


def add_expense(name: str, category: str, expense_date: str, amount: float, notes: str = "") -> int:
    validate_expense(name, category, expense_date, amount, notes)
    return _execute("""INSERT INTO one_time_expenses (name, category, expense_date, amount, notes)
        VALUES (?, ?, ?, ?, ?)""", (name, category, expense_date, amount, notes))


def update_expense(exp_id: int, name: str, category: str, expense_date: str,
                   amount: float, notes: str = "") -> None:
    validate_expense(name, category, expense_date, amount, notes)
    _execute("""UPDATE one_time_expenses SET name=?, category=?, expense_date=?, amount=?, notes=?
        WHERE id=?""", (name, category, expense_date, amount, notes, exp_id))


def delete_expense(exp_id: int) -> None:
    _execute("DELETE FROM one_time_expenses WHERE id=?", (exp_id,))


def get_all_expenses() -> list[dict]:
    return _rows("SELECT * FROM one_time_expenses ORDER BY expense_date DESC")


def get_expense_by_id(exp_id: int) -> Optional[dict]:
    return _by_id("one_time_expenses", exp_id)


def get_expenses_in_range(start_date: str, end_date: str) -> list[dict]:
    return _rows("""SELECT * FROM one_time_expenses WHERE expense_date BETWEEN ? AND ?
        ORDER BY expense_date""", (start_date, end_date))


def get_active_assets_as_of(as_of_date: str) -> list[dict]:
    as_of = date.fromisoformat(as_of_date)
    return [a for a in get_all_assets()
            if date.fromisoformat(a["purchase_date"]) <= as_of
            < date.fromisoformat(a["purchase_date"]) + relativedelta(months=a["lifespan_months"])]
