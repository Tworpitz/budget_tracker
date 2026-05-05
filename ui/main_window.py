"""
主窗口 — 包含所有 Tab 的主界面。
"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMessageBox, QMenuBar,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction

from config import load_settings, get_setting
from db.database import init_db, get_db_path
from ui.asset_tab import AssetTab
from ui.subscription_tab import SubscriptionTab
from ui.expense_tab import ExpenseTab
from ui.reports_tab import ReportsTab
from ui.recurring_tab import RecurringTab
from ui.settings_dialog import SettingsDialog


def _light_stylesheet() -> str:
    return """
        QMainWindow { background-color: #fafafa; }
        QTabWidget::pane { border: 1px solid #ddd; background-color: #fff; }
        QTabBar::tab { padding: 10px 24px; font-size: 14px; border: 1px solid #ddd;
            border-bottom: none; background-color: #eee; margin-right: 2px;
            border-top-left-radius: 6px; border-top-right-radius: 6px; }
        QTabBar::tab:selected { background-color: #fff; font-weight: bold;
            border-bottom: 2px solid #4CAF50; }
        QGroupBox { font-size: 14px; font-weight: bold; border: 1px solid #ddd;
            border-radius: 6px; margin-top: 12px; padding-top: 16px; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; }
        QTableWidget { gridline-color: #e0e0e0; font-size: 13px; }
        QTableWidget::item:selected { background-color: #bbdefb; color: #000; }
        QHeaderView::section { background-color: #f5f5f5; padding: 6px;
            border: 1px solid #ddd; font-weight: bold; }
        QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {
            padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
        QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
        QDoubleSpinBox:focus, QSpinBox:focus { border-color: #4CAF50; }
        QPushButton { padding: 6px 16px; border: 1px solid #ccc;
            border-radius: 4px; font-size: 13px; background-color: #fff; }
        QPushButton:hover { background-color: #e8e8e8; }
        QStatusBar { font-size: 12px; color: #666; }
        QMenuBar { font-size: 13px; }
        QMenuBar::item:selected { background-color: #ddd; }
    """


def _dark_stylesheet() -> str:
    return """
        QMainWindow { background-color: #1e1e1e; color: #ddd; }
        QTabWidget::pane { border: 1px solid #444; background-color: #2d2d2d; }
        QTabBar::tab { padding: 10px 24px; font-size: 14px; border: 1px solid #444;
            border-bottom: none; background-color: #333; margin-right: 2px;
            border-top-left-radius: 6px; border-top-right-radius: 6px; color: #aaa; }
        QTabBar::tab:selected { background-color: #2d2d2d; font-weight: bold;
            border-bottom: 2px solid #4CAF50; color: #eee; }
        QGroupBox { font-size: 14px; font-weight: bold; border: 1px solid #444;
            border-radius: 6px; margin-top: 12px; padding-top: 16px; color: #ddd; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; color: #ddd; }
        QTableWidget { gridline-color: #444; font-size: 13px; background-color: #252525;
            color: #ddd; alternate-background-color: #2a2a2a; }
        QTableWidget::item:selected { background-color: #1565c0; color: #fff; }
        QHeaderView::section { background-color: #333; padding: 6px;
            border: 1px solid #444; font-weight: bold; color: #ddd; }
        QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit {
            padding: 6px 8px; border: 1px solid #555; border-radius: 4px; font-size: 13px;
            background-color: #333; color: #ddd; }
        QTextEdit { padding: 4px 6px; }
        QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
        QDoubleSpinBox:focus, QSpinBox:focus, QTextEdit:focus { border-color: #4CAF50; }
        QPushButton { padding: 6px 16px; border: 1px solid #555;
            border-radius: 4px; font-size: 13px; background-color: #3a3a3a; color: #ddd; }
        QPushButton:hover { background-color: #4a4a4a; }
        QFrame { background-color: #2d2d2d; color: #ddd; }
        QStatusBar { font-size: 12px; color: #999; background-color: #1e1e1e; }
        QMenuBar { font-size: 13px; background-color: #252525; color: #ddd; }
        QMenuBar::item:selected { background-color: #444; }
        QMenu { background-color: #2d2d2d; color: #ddd; border: 1px solid #444; }
        QMenu::item:selected { background-color: #444; }
        QDialog { background-color: #2d2d2d; color: #ddd; }
        QCalendarWidget { background-color: #333; color: #ddd; }
        QCalendarWidget QToolButton { color: #ddd; background-color: #3a3a3a; border: 1px solid #555; }
        QCalendarWidget QAbstractItemView { background-color: #333; color: #ddd; selection-background-color: #1565c0; }
        QComboBox QAbstractItemView { background-color: #333; color: #ddd; selection-background-color: #1565c0; }
        QComboBox:editable { background-color: #333; }
        QDateEdit::drop-down, QComboBox::drop-down,
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
        QSpinBox::up-button, QSpinBox::down-button {
            background-color: #3a3a3a; border: 1px solid #555; }
    """


class MainWindow(QMainWindow):
    """应用程序主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("固定资产与生活支出统计")
        self.resize(1280, 820)

        # 加载设置
        load_settings()

        # 初始化数据库
        init_db()

        self._setup_menu_bar()
        self._setup_ui()
        self._apply_theme()

    def _setup_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        # ── 文件 ──
        file_menu = menu_bar.addMenu("文件(&F)")

        export_action = QAction("导出 CSV...", self)
        export_action.triggered.connect(self._export_csv)
        file_menu.addAction(export_action)

        import_action = QAction("导入 CSV...", self)
        import_action.triggered.connect(self._import_csv)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ── 工具 ──
        tools_menu = menu_bar.addMenu("工具(&T)")

        settings_action = QAction("设置...", self)
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)

        backup_action = QAction("备份数据库...", self)
        backup_action.triggered.connect(self._backup_database)
        tools_menu.addAction(backup_action)

        restore_action = QAction("恢复数据库...", self)
        restore_action.triggered.connect(self._restore_database)
        tools_menu.addAction(restore_action)

        # ── 帮助 ──
        help_menu = menu_bar.addMenu("帮助(&H)")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_ui(self) -> None:
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.asset_tab = AssetTab()
        self.subscription_tab = SubscriptionTab()
        self.expense_tab = ExpenseTab()
        self.reports_tab = ReportsTab()
        self.recurring_tab = RecurringTab()

        self.tab_widget.addTab(self.asset_tab, "📦 固定资产")
        self.tab_widget.addTab(self.subscription_tab, "🔄 订阅服务")
        self.tab_widget.addTab(self.expense_tab, "💳 一次性开支")
        self.tab_widget.addTab(self.recurring_tab, "🔁 周期性收支")
        self.tab_widget.addTab(self.reports_tab, "📊 统计报告")

        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        self.asset_tab.data_changed.connect(lambda: self._mark_reports_stale())
        self.subscription_tab.data_changed.connect(lambda: self._mark_reports_stale())
        self.expense_tab.data_changed.connect(lambda: self._mark_reports_stale())
        self.recurring_tab.data_changed.connect(lambda: self._mark_reports_stale())

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"数据库: {get_db_path()}")

        self._reports_stale = False

    def _apply_theme(self) -> None:
        theme = get_setting("theme", "light")
        if theme == "dark":
            self.setStyleSheet(_dark_stylesheet())
        else:
            self.setStyleSheet(_light_stylesheet())

    def _on_tab_changed(self, index: int) -> None:
        if index == 4 and self._reports_stale:
            self.reports_tab.refresh()
            self._reports_stale = False

    def _mark_reports_stale(self) -> None:
        self._reports_stale = True
        self.status_bar.showMessage("数据已更新，切换到「统计报告」查看最新统计", 5000)

    # ── 菜单动作 ────────────────────────────────

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec():
            # 立即应用不需要重启的设置
            from config import get_setting
            from db.database import DB_PATH
            self.status_bar.showMessage(f"数据库: {DB_PATH}")
            self._mark_reports_stale()

    def _export_csv(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 CSV", "", "CSV 文件 (*.csv);;所有文件 (*)"
        )
        if path:
            from db.database import export_to_csv
            export_to_csv(path)
            QMessageBox.information(self, "导出完成", f"数据已导出到:\n{path}")

    def _import_csv(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 CSV", "", "CSV 文件 (*.csv);;所有文件 (*)"
        )
        if path:
            from db.database import import_from_csv
            count = import_from_csv(path)
            if count >= 0:
                QMessageBox.information(self, "导入完成", f"成功导入 {count} 条记录。")
                self.asset_tab._load_table()
                self.subscription_tab._load_table()
                self.expense_tab._load_table()
                self.recurring_tab._load_table()
                self._mark_reports_stale()

    def _backup_database(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        import shutil
        path, _ = QFileDialog.getSaveFileName(
            self, "备份数据库", "budget_backup.db", "SQLite 数据库 (*.db);;所有文件 (*)"
        )
        if path:
            shutil.copy2(get_db_path(), path)
            QMessageBox.information(self, "备份完成", f"数据库已备份到:\n{path}")

    def _restore_database(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        import shutil
        path, _ = QFileDialog.getOpenFileName(
            self, "恢复数据库", "", "SQLite 数据库 (*.db);;所有文件 (*)"
        )
        if not path:
            return
        reply = QMessageBox.warning(
            self, "确认恢复",
            "恢复数据库将覆盖当前所有数据！\n确定要恢复吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            shutil.copy2(path, get_db_path())
            self.asset_tab._load_table()
            self.subscription_tab._load_table()
            self.expense_tab._load_table()
            self.recurring_tab._load_table()
            self._mark_reports_stale()
            QMessageBox.information(self, "恢复完成", "数据库已恢复。")

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "关于 BudgetTracker",
            "BudgetTracker — 固定资产与生活支出统计\n\n"
            "版本: 1.0.0\n\n"
            "功能：\n"
            "- 固定资产折旧管理\n"
            "- 订阅服务管理\n"
            "- 一次性开支记录\n"
            "- 统计报告与图表\n\n"
            "Made with PySide6 + SQLite"
        )
