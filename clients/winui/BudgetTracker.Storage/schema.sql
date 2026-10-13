-- Compatible with db/database.py; preserve existing tables, IDs and triggers.
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

CREATE TABLE IF NOT EXISTS one_time_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '其他',
                expense_date TEXT NOT NULL,
                amount REAL NOT NULL,
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

CREATE TRIGGER IF NOT EXISTS validate_assets_insert
                    BEFORE INSERT ON assets
                    WHEN NOT coalesce(((length(trim(NEW.name)) > 0) AND (length(trim(NEW.category)) > 0) AND (typeof(NEW.lifespan_months) = 'integer' AND NEW.lifespan_months BETWEEN 1 AND 600) AND (typeof(NEW.purchase_price) IN ('integer', 'real') AND NEW.purchase_price > 0 AND NEW.purchase_price <= 9999999 AND NEW.purchase_price = round(NEW.purchase_price, 2)) AND (typeof(NEW.salvage_value) IN ('integer', 'real') AND NEW.salvage_value >= 0 AND NEW.salvage_value <= 9999999 AND NEW.salvage_value = round(NEW.salvage_value, 2)) AND (NEW.salvage_value <= NEW.purchase_price) AND (length(NEW.purchase_date) = 10 AND date(NEW.purchase_date, '+0 days') = NEW.purchase_date)), 0)
                    BEGIN SELECT RAISE(ABORT, 'Invalid BudgetTracker record'); END;

CREATE TRIGGER IF NOT EXISTS validate_assets_update
                    BEFORE UPDATE ON assets
                    WHEN NOT coalesce(((length(trim(NEW.name)) > 0) AND (length(trim(NEW.category)) > 0) AND (typeof(NEW.lifespan_months) = 'integer' AND NEW.lifespan_months BETWEEN 1 AND 600) AND (typeof(NEW.purchase_price) IN ('integer', 'real') AND NEW.purchase_price > 0 AND NEW.purchase_price <= 9999999 AND NEW.purchase_price = round(NEW.purchase_price, 2)) AND (typeof(NEW.salvage_value) IN ('integer', 'real') AND NEW.salvage_value >= 0 AND NEW.salvage_value <= 9999999 AND NEW.salvage_value = round(NEW.salvage_value, 2)) AND (NEW.salvage_value <= NEW.purchase_price) AND (length(NEW.purchase_date) = 10 AND date(NEW.purchase_date, '+0 days') = NEW.purchase_date)), 0)
                    BEGIN SELECT RAISE(ABORT, 'Invalid BudgetTracker record'); END;

CREATE TRIGGER IF NOT EXISTS validate_one_time_expenses_insert
                    BEFORE INSERT ON one_time_expenses
                    WHEN NOT coalesce(((length(trim(NEW.name)) > 0) AND (length(trim(NEW.category)) > 0) AND (length(NEW.expense_date) = 10 AND date(NEW.expense_date, '+0 days') = NEW.expense_date) AND (typeof(NEW.amount) IN ('integer', 'real') AND NEW.amount > 0 AND NEW.amount <= 9999999 AND NEW.amount = round(NEW.amount, 2))), 0)
                    BEGIN SELECT RAISE(ABORT, 'Invalid BudgetTracker record'); END;

CREATE TRIGGER IF NOT EXISTS validate_one_time_expenses_update
                    BEFORE UPDATE ON one_time_expenses
                    WHEN NOT coalesce(((length(trim(NEW.name)) > 0) AND (length(trim(NEW.category)) > 0) AND (length(NEW.expense_date) = 10 AND date(NEW.expense_date, '+0 days') = NEW.expense_date) AND (typeof(NEW.amount) IN ('integer', 'real') AND NEW.amount > 0 AND NEW.amount <= 9999999 AND NEW.amount = round(NEW.amount, 2))), 0)
                    BEGIN SELECT RAISE(ABORT, 'Invalid BudgetTracker record'); END;

CREATE TRIGGER IF NOT EXISTS validate_subscriptions_insert
                    BEFORE INSERT ON subscriptions
                    WHEN NOT coalesce(((length(trim(NEW.service_name)) > 0) AND (length(NEW.start_date) = 10 AND date(NEW.start_date, '+0 days') = NEW.start_date) AND (NEW.billing_cycle IN ('monthly', 'quarterly', 'yearly')) AND (typeof(NEW.amount) IN ('integer', 'real') AND NEW.amount > 0 AND NEW.amount <= 9999999 AND NEW.amount = round(NEW.amount, 2))), 0)
                    BEGIN SELECT RAISE(ABORT, 'Invalid BudgetTracker record'); END;

CREATE TRIGGER IF NOT EXISTS validate_subscriptions_update
                    BEFORE UPDATE ON subscriptions
                    WHEN NOT coalesce(((length(trim(NEW.service_name)) > 0) AND (length(NEW.start_date) = 10 AND date(NEW.start_date, '+0 days') = NEW.start_date) AND (NEW.billing_cycle IN ('monthly', 'quarterly', 'yearly')) AND (typeof(NEW.amount) IN ('integer', 'real') AND NEW.amount > 0 AND NEW.amount <= 9999999 AND NEW.amount = round(NEW.amount, 2))), 0)
                    BEGIN SELECT RAISE(ABORT, 'Invalid BudgetTracker record'); END;
