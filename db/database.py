"""
数据库层：SQLite 连接管理、建表、所有 CRUD 操作。
"""

import sqlite3
import os
import sys
from datetime import datetime, date
from typing import Optional


def _is_packaged() -> bool:
    """判断是否在 PyInstaller 打包环境中运行。"""
    return getattr(sys, "frozen", False)


def get_db_path() -> str:
    """
    返回数据库文件路径，根据运行环境自动选择：

    - 开发模式（源码运行）：项目根目录 budget.db
    - PyInstaller 打包模式：用户数据目录（始终可写）
    """
    if _is_packaged():
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
            data_dir = os.path.join(appdata, "BudgetTracker")
            os.makedirs(data_dir, exist_ok=True)
            return os.path.join(data_dir, "budget.db")
        elif sys.platform == "darwin":
            app_support = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "BudgetTracker")
            os.makedirs(app_support, exist_ok=True)
            return os.path.join(app_support, "budget.db")
        else:
            # Linux: XDG config directory
            xdg_config = os.path.join(os.path.expanduser("~"), ".config", "budgettracker")
            os.makedirs(xdg_config, exist_ok=True)
            return os.path.join(xdg_config, "budget.db")

    # 开发模式：项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "budget.db")


# 全局数据库路径
DB_PATH = get_db_path()


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（启用 WAL 模式和外键）。"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """初始化数据库：创建所有表并执行迁移。"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS assets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            category        TEXT    NOT NULL DEFAULT '电子设备',
            purchase_date   TEXT    NOT NULL,  -- YYYY-MM-DD
            lifespan_months INTEGER NOT NULL,
            purchase_price  REAL    NOT NULL,
            salvage_value   REAL    NOT NULL DEFAULT 0,
            notes           TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name    TEXT    NOT NULL,
            start_date      TEXT    NOT NULL,  -- YYYY-MM-DD
            end_date        TEXT    NOT NULL DEFAULT '',  -- YYYY-MM-DD, empty if ongoing
            billing_cycle   TEXT    NOT NULL,  -- monthly / quarterly / yearly
            amount          REAL    NOT NULL,
            notes           TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS one_time_expenses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            category        TEXT    NOT NULL DEFAULT '其他',
            expense_date    TEXT    NOT NULL,  -- YYYY-MM-DD
            amount          REAL    NOT NULL,
            notes           TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS recurring_transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            type            TEXT    NOT NULL DEFAULT 'expense',  -- income / expense
            category        TEXT    NOT NULL DEFAULT '其他',
            cycle           TEXT    NOT NULL DEFAULT 'monthly',  -- monthly / quarterly / yearly
            amount          REAL    NOT NULL,
            start_date      TEXT    NOT NULL,  -- YYYY-MM-DD
            notes           TEXT    NOT NULL DEFAULT '',
            created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
    """)

    # 迁移：为旧数据库添加 end_date 列
    cols = conn.execute("PRAGMA table_info(subscriptions)").fetchall()
    col_names = [c[1] for c in cols]
    if "end_date" not in col_names:
        conn.execute("ALTER TABLE subscriptions ADD COLUMN end_date TEXT NOT NULL DEFAULT ''")

    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
#  固定资产 CRUD
# ──────────────────────────────────────────────

def add_asset(name: str, category: str, purchase_date: str,
              lifespan_months: int, purchase_price: float,
              salvage_value: float = 0, notes: str = "") -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO assets (name, category, purchase_date, lifespan_months,
                            purchase_price, salvage_value, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, category, purchase_date, lifespan_months,
          purchase_price, salvage_value, notes))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_asset(asset_id: int, name: str, category: str, purchase_date: str,
                 lifespan_months: int, purchase_price: float,
                 salvage_value: float = 0, notes: str = "") -> None:
    conn = get_connection()
    conn.execute("""
        UPDATE assets
        SET name=?, category=?, purchase_date=?, lifespan_months=?,
            purchase_price=?, salvage_value=?, notes=?
        WHERE id=?
    """, (name, category, purchase_date, lifespan_months,
          purchase_price, salvage_value, notes, asset_id))
    conn.commit()
    conn.close()


def delete_asset(asset_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM assets WHERE id=?", (asset_id,))
    conn.commit()
    conn.close()


def get_all_assets() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, category, purchase_date, lifespan_months,
               purchase_price, salvage_value, notes
        FROM assets
        ORDER BY purchase_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_asset_by_id(asset_id: int) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM assets WHERE id=?", (asset_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ──────────────────────────────────────────────
#  订阅服务 CRUD
# ──────────────────────────────────────────────

def add_subscription(service_name: str, start_date: str, billing_cycle: str,
                     amount: float, notes: str = "", end_date: str = "") -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO subscriptions (service_name, start_date, end_date, billing_cycle, amount, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (service_name, start_date, end_date, billing_cycle, amount, notes))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_subscription(sub_id: int, service_name: str, start_date: str,
                        billing_cycle: str, amount: float, notes: str = "",
                        end_date: str = "") -> None:
    conn = get_connection()
    conn.execute("""
        UPDATE subscriptions
        SET service_name=?, start_date=?, end_date=?, billing_cycle=?, amount=?, notes=?
        WHERE id=?
    """, (service_name, start_date, end_date, billing_cycle, amount, notes, sub_id))
    conn.commit()
    conn.close()


def delete_subscription(sub_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))
    conn.commit()
    conn.close()


def get_all_subscriptions() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, service_name, start_date, end_date, billing_cycle, amount, notes
        FROM subscriptions
        ORDER BY start_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_subscription_by_id(sub_id: int) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE id=?", (sub_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ──────────────────────────────────────────────
#  一次性开支 CRUD
# ──────────────────────────────────────────────

def add_expense(name: str, category: str, expense_date: str,
                amount: float, notes: str = "") -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO one_time_expenses (name, category, expense_date, amount, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (name, category, expense_date, amount, notes))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_expense(exp_id: int, name: str, category: str, expense_date: str,
                   amount: float, notes: str = "") -> None:
    conn = get_connection()
    conn.execute("""
        UPDATE one_time_expenses
        SET name=?, category=?, expense_date=?, amount=?, notes=?
        WHERE id=?
    """, (name, category, expense_date, amount, notes, exp_id))
    conn.commit()
    conn.close()


def delete_expense(exp_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM one_time_expenses WHERE id=?", (exp_id,))
    conn.commit()
    conn.close()


def get_all_expenses() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, category, expense_date, amount, notes
        FROM one_time_expenses
        ORDER BY expense_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_expense_by_id(exp_id: int) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM one_time_expenses WHERE id=?", (exp_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ──────────────────────────────────────────────
#  周期性收支 CRUD
# ──────────────────────────────────────────────

def add_recurring(name: str, rtype: str, category: str, cycle: str,
                  amount: float, start_date: str, notes: str = "") -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO recurring_transactions (name, type, category, cycle, amount, start_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, rtype, category, cycle, amount, start_date, notes))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_recurring(rec_id: int, name: str, rtype: str, category: str,
                     cycle: str, amount: float, start_date: str, notes: str = "") -> None:
    conn = get_connection()
    conn.execute("""
        UPDATE recurring_transactions
        SET name=?, type=?, category=?, cycle=?, amount=?, start_date=?, notes=?
        WHERE id=?
    """, (name, rtype, category, cycle, amount, start_date, notes, rec_id))
    conn.commit()
    conn.close()


def delete_recurring(rec_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM recurring_transactions WHERE id=?", (rec_id,))
    conn.commit()
    conn.close()


def get_all_recurring() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, type, category, cycle, amount, start_date, notes
        FROM recurring_transactions
        ORDER BY start_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recurring_by_id(rec_id: int) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM recurring_transactions WHERE id=?", (rec_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ──────────────────────────────────────────────
#  统计查询
# ──────────────────────────────────────────────

def get_expenses_in_range(start_date: str, end_date: str) -> list[dict]:
    """返回某个时间段内的一次性开支。"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, category, expense_date, amount, notes
        FROM one_time_expenses
        WHERE expense_date BETWEEN ? AND ?
        ORDER BY expense_date
    """, (start_date, end_date)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_assets_as_of(as_of_date: str) -> list[dict]:
    """返回在 as_of_date 仍在使用期内的固定资产。"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, category, purchase_date, lifespan_months,
               purchase_price, salvage_value, notes
        FROM assets
        WHERE date(purchase_date, '+' || lifespan_months || ' months') >= ?
        ORDER BY purchase_date
    """, (as_of_date,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────
#  数据导出 / 导入
# ──────────────────────────────────────────────

def export_to_csv(filepath: str) -> None:
    """导出所有数据到一个 CSV 文件。"""
    import csv

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        # 固定资产
        writer.writerow(["_type", "id", "name", "category", "purchase_date",
                         "lifespan_months", "purchase_price", "salvage_value",
                         "start_date", "billing_cycle", "amount",
                         "expense_date", "transaction_type", "notes", "end_date"])
        for a in get_all_assets():
            writer.writerow(["asset", a["id"], a["name"], a["category"],
                            a["purchase_date"], a["lifespan_months"],
                            a["purchase_price"], a.get("salvage_value", 0),
                            "", "", "", "", "", a.get("notes", "")])

        for s in get_all_subscriptions():
            writer.writerow(["subscription", s["id"], s["service_name"], "",
                            s["start_date"], "", "", "",
                            s["start_date"], s["billing_cycle"], s["amount"],
                            "", "", s.get("notes", ""), s.get("end_date", "")])

        for e in get_all_expenses():
            writer.writerow(["expense", e["id"], e["name"], e["category"],
                            e["expense_date"], "", "", "", "", "",
                            e["amount"], e["expense_date"], "", e.get("notes", "")])

        for r in get_all_recurring():
            writer.writerow(["recurring", r["id"], r["name"], r["category"],
                            "", "", "", "",
                            r["start_date"], r["cycle"], r["amount"],
                            "", r["type"], r.get("notes", "")])


def import_from_csv(filepath: str) -> int:
    """从 CSV 文件导入数据，返回导入的记录数。"""
    import csv

    count = 0
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rtype = row.get("_type", "")
            name = row.get("name", "").strip()
            notes = row.get("notes", "").strip()
            if not name:
                continue

            if rtype == "asset":
                add_asset(
                    name=name,
                    category=row.get("category", "其他").strip() or "其他",
                    purchase_date=row.get("purchase_date", "").strip(),
                    lifespan_months=int(row.get("lifespan_months", 36) or 36),
                    purchase_price=float(row.get("purchase_price", 0) or 0),
                    salvage_value=float(row.get("salvage_value", 0) or 0),
                    notes=notes,
                )
                count += 1
            elif rtype == "subscription":
                add_subscription(
                    service_name=name,
                    start_date=row.get("start_date", "").strip(),
                    billing_cycle=row.get("billing_cycle", "monthly").strip() or "monthly",
                    amount=float(row.get("amount", 0) or 0),
                    notes=notes,
                    end_date=row.get("end_date", "").strip(),
                )
                count += 1
            elif rtype == "expense":
                add_expense(
                    name=name,
                    category=row.get("category", "其他").strip() or "其他",
                    expense_date=row.get("expense_date", "").strip(),
                    amount=float(row.get("amount", 0) or 0),
                    notes=notes,
                )
                count += 1
            elif rtype == "recurring":
                add_recurring(
                    name=name,
                    rtype=row.get("transaction_type", "expense").strip() or "expense",
                    category=row.get("category", "其他").strip() or "其他",
                    cycle=row.get("billing_cycle", "monthly").strip() or "monthly",
                    amount=float(row.get("amount", 0) or 0),
                    start_date=row.get("start_date", "").strip(),
                    notes=notes,
                )
                count += 1
    return count
