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

# ── 配置中文字体（优先使用已知可靠的字体） ──
import matplotlib.font_manager as fm
import platform

_CJK_CANDIDATES = {
    "Windows": ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi", "FangSong"],
    "Darwin": ["PingFang SC", "Heiti SC", "STHeiti", "Songti SC"],
}.get(platform.system(), ["WenQuanYi Micro Hei", "Noto Sans CJK SC", "Noto Sans SC"])

# 同时扫描系统中实际存在的 CJK 字体作为备选
_available = {f.name for f in fm.fontManager.ttflist}
_cjk_found = [f for f in _CJK_CANDIDATES if f in _available]

if _cjk_found:
    matplotlib.rcParams["font.sans-serif"] = _cjk_found + matplotlib.rcParams.get("font.sans-serif", [])
    matplotlib.rcParams["font.family"] = "sans-serif"
else:
    # 回退：从系统字体中查找任何 CJK 字体
    _fallback = [f.name for f in fm.fontManager.ttflist
                 if any(k in f.name for k in ("YaHei", "SimHei", "SimSun", "KaiTi",
                                               "PingFang", "Heiti", "Songti",
                                               "Noto Sans CJK", "WenQuanYi"))]
    if _fallback:
        matplotlib.rcParams["font.sans-serif"] = _fallback + matplotlib.rcParams.get("font.sans-serif", [])
        matplotlib.rcParams["font.family"] = "sans-serif"

matplotlib.rcParams["axes.unicode_minus"] = False

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as mticker

from config import format_currency, get_setting
from db.database import (
    get_all_assets, get_all_subscriptions, get_expenses_in_range,
    get_all_recurring,
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

        # ── 汇总卡片（两行） ──
        summary_layout = QVBoxLayout()
        summary_layout.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(12)
        self.card_depreciation = self._make_summary_card("折旧费用", format_currency(0))
        self.card_subscriptions = self._make_summary_card("订阅费用", format_currency(0))
        self.card_expenses = self._make_summary_card("一次性开支", format_currency(0))
        self.card_recurring_expense = self._make_summary_card("周期性支出", format_currency(0))
        self.card_total = self._make_summary_card("合计支出", format_currency(0), highlight=True)
        row1.addWidget(self.card_depreciation)
        row1.addWidget(self.card_subscriptions)
        row1.addWidget(self.card_expenses)
        row1.addWidget(self.card_recurring_expense)
        row1.addWidget(self.card_total)
        row1.addStretch()

        row2 = QHBoxLayout()
        row2.setSpacing(12)
        self.card_recurring_income = self._make_summary_card("周期性收入", format_currency(0))
        self.card_budget = self._make_summary_card("月度预算", format_currency(0))
        row2.addWidget(self.card_recurring_income)
        row2.addWidget(self.card_budget)
        row2.addStretch()

        summary_layout.addLayout(row1)
        summary_layout.addLayout(row2)
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

    _CARD_COLORS = {
        "light": {
            "normal_bg": "#f5f5f5",
            "normal_border": "none",
            "normal_title": "#666",
            "normal_value": "#333",
            "highlight_bg": "#e8f5e9",
            "highlight_border": "2px solid #4CAF50",
            "highlight_value": "#2e7d32",
            "danger_bg": "#fce4ec",
            "danger_border": "2px solid #f44336",
            "danger_value": "#c62828",
            "warning_bg": "#fff3e0",
            "warning_border": "none",
        },
        "dark": {
            "normal_bg": "#2a2a2a",
            "normal_border": "1px solid #444",
            "normal_title": "#aaa",
            "normal_value": "#e0e0e0",
            "highlight_bg": "#1b3a1b",
            "highlight_border": "2px solid #4CAF50",
            "highlight_value": "#81c784",
            "danger_bg": "#3e1a1a",
            "danger_border": "2px solid #f44336",
            "danger_value": "#ef9a9a",
            "warning_bg": "#3a2e1a",
            "warning_border": "1px solid #444",
        },
    }

    _CHART_COLORS = {
        "light": {"bg": "#ffffff", "axes_bg": "#fafafa", "text": "#333333", "grid": "#e0e0e0"},
        "dark": {"bg": "#2d2d2d", "axes_bg": "#252525", "text": "#cccccc", "grid": "#444444"},
    }

    def _is_dark(self) -> bool:
        return get_setting("theme", "light") == "dark"

    def _make_summary_card(self, title: str, value: str, highlight: bool = False) -> QFrame:
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        card_layout = QVBoxLayout(card)
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setObjectName("card_title")
        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName("card_value")
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        card._highlight = highlight
        card._card_title = title_label
        card._card_value = value_label
        return card

    def _apply_card_style(self, card: QFrame, highlight: bool = False, danger: bool = False) -> None:
        theme = self._CARD_COLORS["dark" if self._is_dark() else "light"]
        if danger:
            bg, border, vcolor = theme["danger_bg"], theme["danger_border"], theme["danger_value"]
        elif highlight:
            bg, border, vcolor = theme["highlight_bg"], theme["highlight_border"], theme["highlight_value"]
        else:
            bg, border, vcolor = theme["normal_bg"], theme["normal_border"], theme["normal_value"]
        border_css = f"border: {border};" if border != "none" else ""
        card.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border-radius: 8px; padding: 12px; {border_css} }}"
        )
        card._card_title.setStyleSheet(f"font-size: 12px; color: {theme['normal_title']};")
        card._card_value.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {vcolor};")

    @staticmethod
    def _update_summary_card(card: QFrame, value: str) -> None:
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
        recurrings = get_all_recurring()

        view = self.view_combo.currentText()

        if view == "按月统计":
            stats = generate_monthly_stats(assets, subscriptions, expenses, recurrings, start, end)
            self._display_stats_table(stats, "month")
            self._draw_bar_chart(stats, "month")
        else:
            stats = generate_weekly_stats(assets, subscriptions, expenses, recurrings, start, end)
            self._display_stats_table(stats, "week")
            self._draw_bar_chart(stats, "week")

        # 汇总
        total_dep = sum(s["depreciation"] for s in stats)
        total_sub = sum(s["subscriptions"] for s in stats)
        total_exp = sum(s["expenses"] for s in stats)
        total_rec_exp = sum(s["recurring_expense"] for s in stats)
        total_rec_inc = sum(s["recurring_income"] for s in stats)
        total_all = total_dep + total_sub + total_exp + total_rec_exp

        self._update_summary_card(self.card_depreciation, format_currency(total_dep))
        self._update_summary_card(self.card_subscriptions, format_currency(total_sub))
        self._update_summary_card(self.card_expenses, format_currency(total_exp))
        self._update_summary_card(self.card_recurring_expense, format_currency(total_rec_exp))
        self._update_summary_card(self.card_recurring_income, format_currency(total_rec_inc))
        self._update_summary_card(self.card_total, format_currency(total_all))

        # 更新卡片样式（响应主题）
        self._apply_card_style(self.card_depreciation)
        self._apply_card_style(self.card_subscriptions)
        self._apply_card_style(self.card_expenses)
        self._apply_card_style(self.card_recurring_expense)
        self._apply_card_style(self.card_recurring_income)
        self._apply_card_style(self.card_total, highlight=True)
        self._apply_card_style(self.card_budget)

        # 预算对比
        budget = get_setting("monthly_budget", 0)
        if budget > 0:
            remaining = budget - total_all
            self._update_summary_card(self.card_budget,
                                      f"{format_currency(total_all)} / {format_currency(budget)}")
            if remaining < 0:
                self._apply_card_style(self.card_total, danger=True)
                self._apply_card_style(self.card_budget, danger=True)
        else:
            self._update_summary_card(self.card_budget, "未设置")

    # ── 统计表格 ─────────────────────────────────

    def _display_stats_table(self, stats: list[dict], mode: str) -> None:
        """填充统计明细表格。"""
        if mode == "month":
            headers = ["月份", "折旧费用", "订阅费用", "一次性开支", "周期性支出", "周期性收入", "合计"]
            keys = ["month", "depreciation", "subscriptions", "expenses", "recurring_expense", "recurring_income", "total"]
        else:
            headers = ["周", "起止日期", "折旧费用", "订阅费用", "一次性开支", "周期性支出", "周期性收入", "合计"]
            keys = ["week", "range", "depreciation", "subscriptions", "expenses", "recurring_expense", "recurring_income", "total"]

        self.stats_table.setColumnCount(len(headers))
        self.stats_table.setHorizontalHeaderLabels(headers)
        self.stats_table.setRowCount(len(stats))

        for row, s in enumerate(stats):
            for col, key in enumerate(keys):
                if key == "range":
                    text = f"{s.get('start', '')} ~ {s.get('end', '')}"
                elif key in ("depreciation", "subscriptions", "expenses", "recurring_expense", "recurring_income", "total"):
                    text = format_currency(s[key])
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
        is_dark = self._is_dark()
        colors = self._CHART_COLORS["dark" if is_dark else "light"]
        text_color = colors["text"]

        ax = self.figure.add_subplot(111)
        self.figure.patch.set_facecolor(colors["bg"])
        ax.set_facecolor(colors["axes_bg"])
        for spine in ax.spines.values():
            spine.set_color(colors["grid"])
        ax.tick_params(colors=text_color)
        ax.yaxis.label.set_color(text_color)
        ax.title.set_color(text_color)

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
        rec_exp_vals = [s["recurring_expense"] for s in stats]

        x = range(len(labels))
        width = 0.6

        ax.bar(x, dep_vals, width, label="折旧", color="#2196F3")
        ax.bar(x, sub_vals, width, bottom=dep_vals, label="订阅", color="#FF9800")
        bottom2 = [d + s for d, s in zip(dep_vals, sub_vals)]
        ax.bar(x, exp_vals, width, bottom=bottom2, label="一次性开支", color="#4CAF50")
        bottom3 = [d + s + e for d, s, e in zip(dep_vals, sub_vals, exp_vals)]
        ax.bar(x, rec_exp_vals, width, bottom=bottom3, label="周期性支出", color="#9C27B0")

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("金额 (¥)", color=text_color)
        ax.set_title("支出构成趋势" if mode == "month" else "每周支出构成", color=text_color)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"¥{v:,.0f}"))
        ax.grid(axis="y", color=colors["grid"], linestyle="--", alpha=0.5)
        ax.legend(loc="upper right", fontsize=9,
                  facecolor=colors["bg"], edgecolor=colors["grid"],
                  labelcolor=text_color)

        self.figure.tight_layout()
        self.canvas.draw()
