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
    - PyInstaller 文件夹模式：可执行文件同级目录 budget.db
    - 系统安装（/opt 等只读路径）：~/.config/budgettracker/budget.db
    """
    if _is_packaged():
        # PyInstaller 打包模式
        exe_dir = os.path.dirname(sys.executable) if hasattr(sys, "executable") else os.path.dirname(sys.argv[0])

        # 如果可执行文件所在目录不可写（如 /opt/），使用用户配置目录
        if not os.access(exe_dir, os.W_OK) or exe_dir.startswith("/opt/"):
            xdg_config = os.path.join(os.path.expanduser("~"), ".config", "budgettracker")
            os.makedirs(xdg_config, exist_ok=True)
            return os.path.join(xdg_config, "budget.db")

        return os.path.join(exe_dir, "budget.db")

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
    """初始化数据库：创建所有表。"""
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
    """)

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
                     amount: float, notes: str = "") -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO subscriptions (service_name, start_date, billing_cycle, amount, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (service_name, start_date, billing_cycle, amount, notes))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_subscription(sub_id: int, service_name: str, start_date: str,
                        billing_cycle: str, amount: float, notes: str = "") -> None:
    conn = get_connection()
    conn.execute("""
        UPDATE subscriptions
        SET service_name=?, start_date=?, billing_cycle=?, amount=?, notes=?
        WHERE id=?
    """, (service_name, start_date, billing_cycle, amount, notes, sub_id))
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
        SELECT id, service_name, start_date, billing_cycle, amount, notes
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
