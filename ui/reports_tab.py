"""
报告 Tab — 周/月支出统计 + 图表可视化。
"""

from datetime import date, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QDateEdit, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView,
    QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, QDate

import matplotlib
matplotlib.use("Qt5Agg")

# ── 配置中文字体 ──
import matplotlib.font_manager as fm
_cjk_fonts = [f.name for f in fm.fontManager.ttflist
              if any(k in f.name for k in ("CJK", "WenKai", "YaHei", "Hei", "Ming", "Song", "UKai", "UMing"))]
if _cjk_fonts:
    # 优先选择 SC（简体中文）或包含 "CJK" 的字体
    _preferred = [f for f in _cjk_fonts if "SC" in f or "CJK" in f]
    _chosen = (_preferred or _cjk_fonts)[0]
    matplotlib.rcParams["font.family"] = _chosen
    # 设置负号正常显示
    matplotlib.rcParams["axes.unicode_minus"] = False

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as mticker

from db.database import (
    get_all_assets, get_all_subscriptions, get_expenses_in_range,
)
from calc.calculations import (
    generate_weekly_stats,
    generate_monthly_stats,
    generate_category_breakdown,
)


class ReportsTab(QWidget):
    """统计报告页面。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    # ── UI 构建 ─────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── 顶部：日期范围选择 ──
        control_group = QGroupBox("统计设置")
        control_layout = QHBoxLayout(control_group)
        control_layout.setSpacing(12)

        control_layout.addWidget(QLabel("起始日期："))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        # 默认本月 1 号
        today = date.today()
        self.start_date_edit.setDate(QDate(today.year, today.month, 1))
        control_layout.addWidget(self.start_date_edit)

        control_layout.addWidget(QLabel("结束日期："))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setDate(QDate.currentDate())
        control_layout.addWidget(self.end_date_edit)

        control_layout.addWidget(QLabel("视图："))
        self.view_combo = QComboBox()
        self.view_combo.addItems(["按月统计", "按周统计"])
        control_layout.addWidget(self.view_combo)

        # 快捷按钮
        self.btn_this_month = QPushButton("本月")
        self.btn_this_month.clicked.connect(self._set_this_month)
        control_layout.addWidget(self.btn_this_month)

        self.btn_last_month = QPushButton("上月")
        self.btn_last_month.clicked.connect(self._set_last_month)
        control_layout.addWidget(self.btn_last_month)

        self.btn_this_year = QPushButton("今年")
        self.btn_this_year.clicked.connect(self._set_this_year)
        control_layout.addWidget(self.btn_this_year)

        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 6px 16px; }")
        self.btn_refresh.clicked.connect(self.refresh)
        control_layout.addWidget(self.btn_refresh)

        control_layout.addStretch()
        layout.addWidget(control_group)

        # ── 汇总卡片 ──
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(12)

        self.card_depreciation = self._make_summary_card("折旧费用", "¥ 0.00")
        self.card_subscriptions = self._make_summary_card("订阅费用", "¥ 0.00")
        self.card_expenses = self._make_summary_card("一次性开支", "¥ 0.00")
        self.card_total = self._make_summary_card("合计支出", "¥ 0.00", highlight=True)

        summary_layout.addWidget(self.card_depreciation)
        summary_layout.addWidget(self.card_subscriptions)
        summary_layout.addWidget(self.card_expenses)
        summary_layout.addWidget(self.card_total)
        layout.addLayout(summary_layout)

        # ── 表格 + 图表（左右分栏） ──
        split_layout = QHBoxLayout()
        split_layout.setSpacing(12)

        # 左侧：统计表格
        table_group = QGroupBox("明细")
        table_vlayout = QVBoxLayout(table_group)
        self.stats_table = QTableWidget()
        self.stats_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.stats_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        table_vlayout.addWidget(self.stats_table)
        split_layout.addWidget(table_group, stretch=1)

        # 右侧：图表
        chart_group = QGroupBox("趋势图")
        chart_vlayout = QVBoxLayout(chart_group)
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart_vlayout.addWidget(self.canvas)
        split_layout.addWidget(chart_group, stretch=1)

        layout.addLayout(split_layout, stretch=1)

    # ── 汇总卡片 ─────────────────────────────────

    def _make_summary_card(self, title: str, value: str, highlight: bool = False) -> QFrame:
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        card.setStyleSheet(
            "QFrame { background-color: #f5f5f5; border-radius: 8px; padding: 12px; }"
            if not highlight else
            "QFrame { background-color: #e8f5e9; border-radius: 8px; padding: 12px; border: 2px solid #4CAF50; }"
        )
        card_layout = QVBoxLayout(card)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 12px; color: #666;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label = QLabel(value)
        value_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #333;" if not highlight
            else "font-size: 20px; font-weight: bold; color: #2e7d32;"
        )
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName("value_label")
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        return card

    @staticmethod
    def _update_summary_card(card: QFrame, value: str) -> None:
        """更新汇总卡片数值（第二个 QLabel 始终是数值标签）。"""
        labels = card.findChildren(QLabel)
        if len(labels) >= 2:
            labels[1].setText(value)

    # ── 日期快捷设置 ────────────────────────────

    def _set_this_month(self) -> None:
        today = date.today()
        self.start_date_edit.setDate(QDate(today.year, today.month, 1))
        self.end_date_edit.setDate(QDate.currentDate())
        self.view_combo.setCurrentText("按周统计")
        self.refresh()

    def _set_last_month(self) -> None:
        today = date.today()
        first = today.replace(day=1)
        last_month = first - timedelta(days=1)
        self.start_date_edit.setDate(QDate(last_month.year, last_month.month, 1))
        self.end_date_edit.setDate(QDate(last_month.year, last_month.month, last_month.day))
        self.view_combo.setCurrentText("按周统计")
        self.refresh()

    def _set_this_year(self) -> None:
        today = date.today()
        self.start_date_edit.setDate(QDate(today.year, 1, 1))
        self.end_date_edit.setDate(QDate.currentDate())
        self.view_combo.setCurrentText("按月统计")
        self.refresh()

    # ── 数据刷新 ─────────────────────────────────

    def refresh(self) -> None:
        """刷新所有统计数据和图表。"""
        start = self.start_date_edit.date().toPython()
        end = self.end_date_edit.date().toPython()

        if start > end:
            start, end = end, start

        start_str = start.isoformat()
        end_str = end.isoformat()

        # 获取数据
        assets = get_all_assets()
        subscriptions = get_all_subscriptions()
        expenses = get_expenses_in_range(start_str, end_str)

        view = self.view_combo.currentText()

        if view == "按月统计":
            stats = generate_monthly_stats(assets, subscriptions, expenses, start, end)
            self._display_stats_table(stats, "month")
            self._draw_bar_chart(stats, "month")
        else:
            stats = generate_weekly_stats(assets, subscriptions, expenses, start, end)
            self._display_stats_table(stats, "week")
            self._draw_bar_chart(stats, "week")

        # 汇总
        total_dep = sum(s["depreciation"] for s in stats)
        total_sub = sum(s["subscriptions"] for s in stats)
        total_exp = sum(s["expenses"] for s in stats)
        total_all = total_dep + total_sub + total_exp

        self._update_summary_card(self.card_depreciation, f"¥ {total_dep:,.2f}")
        self._update_summary_card(self.card_subscriptions, f"¥ {total_sub:,.2f}")
        self._update_summary_card(self.card_expenses, f"¥ {total_exp:,.2f}")
        self._update_summary_card(self.card_total, f"¥ {total_all:,.2f}")

    # ── 统计表格 ─────────────────────────────────

    def _display_stats_table(self, stats: list[dict], mode: str) -> None:
        """填充统计明细表格。"""
        if mode == "month":
            headers = ["月份", "折旧费用", "订阅费用", "一次性开支", "合计"]
            keys = ["month", "depreciation", "subscriptions", "expenses", "total"]
        else:
            headers = ["周", "起止日期", "折旧费用", "订阅费用", "一次性开支", "合计"]
            keys = ["week", "range", "depreciation", "subscriptions", "expenses", "total"]

        self.stats_table.setColumnCount(len(headers))
        self.stats_table.setHorizontalHeaderLabels(headers)
        self.stats_table.setRowCount(len(stats))

        for row, s in enumerate(stats):
            for col, key in enumerate(keys):
                if key == "range":
                    text = f"{s.get('start', '')} ~ {s.get('end', '')}"
                elif key in ("depreciation", "subscriptions", "expenses", "total"):
                    text = f"¥ {s[key]:,.2f}"
                else:
                    text = str(s.get(key, ""))
                item = QTableWidgetItem(text)
                if key == "total":
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.stats_table.setItem(row, col, item)

        self.stats_table.resizeColumnsToContents()

    # ── 图表 ─────────────────────────────────────

    def _draw_bar_chart(self, stats: list[dict], mode: str) -> None:
        """绘制堆叠柱状图。"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if not stats:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14, color="#999")
            self.canvas.draw()
            return

        # 限制显示数量，避免标签重叠
        max_display = 14
        if len(stats) > max_display:
            stats = stats[-max_display:]

        labels = [s.get("month", s.get("week", "")) for s in stats]
        dep_vals = [s["depreciation"] for s in stats]
        sub_vals = [s["subscriptions"] for s in stats]
        exp_vals = [s["expenses"] for s in stats]

        x = range(len(labels))
        width = 0.6

        bar1 = ax.bar(x, dep_vals, width, label="折旧", color="#2196F3")
        bar2 = ax.bar(x, sub_vals, width, bottom=dep_vals, label="订阅", color="#FF9800")
        bottom2 = [d + s for d, s in zip(dep_vals, sub_vals)]
        bar3 = ax.bar(x, exp_vals, width, bottom=bottom2, label="一次性开支", color="#4CAF50")

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("金额 (¥)")
        ax.set_title("支出构成趋势" if mode == "month" else "每周支出构成")
        ax.legend(loc="upper right", fontsize=9)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"¥{v:,.0f}"))

        self.figure.tight_layout()
        self.canvas.draw()
