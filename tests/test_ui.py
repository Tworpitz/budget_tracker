"""在临时数据库上验证表单拦截和报表展示，不打开可见窗口。"""

import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QLabel
    from ui.main_window import MainWindow
    from db import database as db
    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "需要 PySide6 和 matplotlib")
class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db_patch = patch.object(db, "DB_PATH", str(Path(self.temp.name) / "budget.db"))
        legacy_patch = patch.object(db, "legacy_database_paths", return_value=[])
        db_patch.start()
        legacy_patch.start()
        self.addCleanup(db_patch.stop)
        self.addCleanup(legacy_patch.stop)
        self.window = MainWindow()
        self.addCleanup(self.window.close)

    def test_weekly_and_monthly_cards_and_tables_match_manual_totals(self):
        db.add_asset("设备", "其他", "2024-01-01", 1, 310)
        db.add_subscription("服务", "2024-01-01", "monthly", 31)
        db.add_expense("开支", "其他", "2024-01-07", 12.5)
        report = self.window.reports_tab
        report.start_date_edit.setDate(QDate(2024, 1, 1))
        report.end_date_edit.setDate(QDate(2024, 1, 31))
        for mode, count in (("按月统计", 1), ("按周统计", 5)):
            report.view_combo.setCurrentText(mode)
            report.refresh()
            with self.subTest(mode=mode):
                self.assertEqual(report.stats_table.rowCount(), count)
                self.assertEqual(report.card_total.findChild(QLabel, "value_label").text(), "¥ 353.50")
                self.assertEqual(report.card_depreciation.findChild(QLabel, "value_label").text(), "¥ 310.00")

    def test_form_rejects_high_salvage_and_failed_save_preserves_fields(self):
        tab = self.window.asset_tab
        tab.name_edit.setText("设备")
        tab.price_spin.setValue(100)
        tab.salvage_spin.setValue(101)
        with patch("ui.asset_tab.QMessageBox.warning") as warning:
            tab._on_add()
            warning.assert_called_once()
        self.assertEqual(db.get_all_assets(), [])
        tab.salvage_spin.setValue(0)
        with patch("ui.asset_tab.add_asset", side_effect=sqlite3.OperationalError("database is locked")), \
                patch("ui.error_handling.QMessageBox.critical") as critical:
            tab._on_add()
            critical.assert_called_once()
        self.assertEqual(tab.name_edit.text(), "设备")
        self.assertEqual(tab.price_spin.value(), 100)
        self.assertEqual(db.get_all_assets(), [])

    def test_legacy_invalid_asset_can_be_edited_without_misleading_report(self):
        a = db.add_asset("旧记录", "其他", "2024-01-01", 1, 100)
        with db._connection() as conn:
            conn.execute("DROP TRIGGER validate_assets_update")
            conn.execute("UPDATE assets SET salvage_value=101 WHERE id=?", (a,))
        self.window.asset_tab._load_table()
        self.assertEqual(self.window.asset_tab.table.item(0, 8).text(), "数据有误")
        self.window.asset_tab._populate_form_from_row(0)
        self.assertEqual(self.window.asset_tab.name_edit.text(), "旧记录")
        with patch("ui.reports_tab.QMessageBox.warning") as warning:
            self.window.reports_tab.refresh()
            warning.assert_called_once()
        self.assertEqual(self.window.reports_tab.card_total.findChild(QLabel, "value_label").text(), "数据有误")
