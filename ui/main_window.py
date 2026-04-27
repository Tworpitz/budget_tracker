"""
主窗口 — 包含所有 Tab 的主界面。
"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction

from db.database import init_db
from ui.asset_tab import AssetTab
from ui.subscription_tab import SubscriptionTab
from ui.expense_tab import ExpenseTab
from ui.reports_tab import ReportsTab


class MainWindow(QMainWindow):
    """应用程序主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("固定资产与生活支出统计")
        self.resize(1280, 820)

        # 初始化数据库
        init_db()

        self._setup_ui()
        self._apply_stylesheet()

    # ── UI 构建 ─────────────────────────────────

    def _setup_ui(self) -> None:
        # 标签页
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # 创建各个 Tab
        self.asset_tab = AssetTab()
        self.subscription_tab = SubscriptionTab()
        self.expense_tab = ExpenseTab()
        self.reports_tab = ReportsTab()

        self.tab_widget.addTab(self.asset_tab, "📦 固定资产")
        self.tab_widget.addTab(self.subscription_tab, "🔄 订阅服务")
        self.tab_widget.addTab(self.expense_tab, "💳 一次性开支")
        self.tab_widget.addTab(self.reports_tab, "📊 统计报告")

        # Tab 切换时自动刷新报告
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # 各数据 Tab 变更时刷新报告
        self.asset_tab.data_changed.connect(lambda: self._mark_reports_stale())
        self.subscription_tab.data_changed.connect(lambda: self._mark_reports_stale())
        self.expense_tab.data_changed.connect(lambda: self._mark_reports_stale())

        # 状态栏
        from db.database import get_db_path
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"数据库: {get_db_path()}")

        self._reports_stale = False

    def _on_tab_changed(self, index: int) -> None:
        """切换到报告 Tab 时自动刷新。"""
        if index == 3 and self._reports_stale:
            self.reports_tab.refresh()
            self._reports_stale = False

    def _mark_reports_stale(self) -> None:
        """标记报告需要刷新。"""
        self._reports_stale = True
        self.status_bar.showMessage("数据已更新，切换到「统计报告」查看最新统计", 5000)

    # ── 样式 ────────────────────────────────────

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet("""
            QMainWindow {
                background-color: #fafafa;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                background-color: #fff;
            }
            QTabBar::tab {
                padding: 10px 24px;
                font-size: 14px;
                border: 1px solid #ddd;
                border-bottom: none;
                background-color: #eee;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #fff;
                font-weight: bold;
                border-bottom: 2px solid #4CAF50;
            }
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
            QTableWidget {
                gridline-color: #e0e0e0;
                font-size: 13px;
            }
            QTableWidget::item:selected {
                background-color: #bbdefb;
                color: #000;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 6px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {
                padding: 6px 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
            QDoubleSpinBox:focus, QSpinBox:focus {
                border-color: #4CAF50;
            }
            QPushButton {
                padding: 6px 16px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 13px;
                background-color: #fff;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QStatusBar {
                font-size: 12px;
                color: #666;
            }
        """)
