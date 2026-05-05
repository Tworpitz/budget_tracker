"""
订阅服务 Tab — 管理按月/季/年付费的订阅服务。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QDateEdit,
    QDoubleSpinBox, QTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt, QDate, Signal

from config import format_currency, get_setting
from db.database import (
    add_subscription, update_subscription, delete_subscription,
    get_all_subscriptions, get_subscription_by_id,
)
from calc.calculations import (
    calc_monthly_subscription_cost,
    calc_next_billing_date,
)

BILLING_CYCLES = ["monthly", "quarterly", "yearly"]
BILLING_CYCLE_LABELS = {"monthly": "月付", "quarterly": "季付", "yearly": "年付"}


class SubscriptionTab(QWidget):
    """订阅服务管理页面。"""

    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_id: int | None = None
        self._all_rows: list[dict] = []
        self._setup_ui()
        self._load_table()

    # ── UI 构建 ─────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── 表单 ──
        form_group = QGroupBox("添加 / 编辑订阅服务")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：Netflix、iCloud+")
        form_layout.addRow("服务名称：", self.name_edit)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow("开始日期：", self.start_date_edit)

        self.cycle_combo = QComboBox()
        for cycle in BILLING_CYCLES:
            self.cycle_combo.addItem(BILLING_CYCLE_LABELS[cycle], cycle)
        form_layout.addRow("计费周期：", self.cycle_combo)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 9999999)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix(get_setting("currency", "¥") + " ")
        self.amount_spin.setValue(0)
        form_layout.addRow("金额：", self.amount_spin)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        self.notes_edit.setPlaceholderText("可选备注")
        form_layout.addRow("备注：", self.notes_edit)

        # 按钮
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("添加")
        self.add_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 6px 20px; }")
        self.add_btn.clicked.connect(self._on_add)

        self.update_btn = QPushButton("更新选中")
        self.update_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; padding: 6px 20px; }")
        self.update_btn.clicked.connect(self._on_update)

        self.clear_btn = QPushButton("清空表单")
        self.clear_btn.clicked.connect(self._clear_form)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.update_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        form_layout.addRow("", btn_layout)

        layout.addWidget(form_group)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索："))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入关键词筛选...")
        self.search_edit.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self.search_edit)
        self.search_clear_btn = QPushButton("清除")
        self.search_clear_btn.clicked.connect(self._clear_search)
        search_layout.addWidget(self.search_clear_btn)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # ── 表格 ──
        table_group = QGroupBox("订阅服务列表")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "服务名称", "开始日期", "计费周期",
            "金额", "月均成本", "下次扣费", "备注",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)
        # 列宽策略：内容自适应 + 备注列拉伸
        header = self.table.horizontalHeader()
        for col in range(1, 7):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)

        table_layout.addWidget(self.table)

        tbl_btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("编辑选中行")
        self.edit_btn.clicked.connect(self._on_edit_selected)
        self.delete_btn = QPushButton("删除选中行")
        self.delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 6px 20px; }")
        self.delete_btn.clicked.connect(self._on_delete_selected)
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.clicked.connect(self._load_table)

        tbl_btn_layout.addWidget(self.edit_btn)
        tbl_btn_layout.addWidget(self.delete_btn)
        tbl_btn_layout.addWidget(self.refresh_btn)
        tbl_btn_layout.addStretch()
        table_layout.addLayout(tbl_btn_layout)

        layout.addWidget(table_group)

    # ── 表格加载 ─────────────────────────────────

    def _load_table(self) -> None:
        """加载所有订阅服务。"""
        self._all_rows = get_all_subscriptions()
        self._apply_filter()

    def _apply_filter(self) -> None:
        keyword = self.search_edit.text().strip().lower() if hasattr(self, 'search_edit') else ""
        subs = [s for s in self._all_rows
                if not keyword or keyword in s["service_name"].lower()]

        self.table.setRowCount(len(subs))
        for row, sub in enumerate(subs):
            monthly_cost = calc_monthly_subscription_cost(sub)
            next_billing = calc_next_billing_date(sub)

            items = [
                str(sub["id"]),
                sub["service_name"],
                sub["start_date"],
                BILLING_CYCLE_LABELS.get(sub["billing_cycle"], sub["billing_cycle"]),
                format_currency(sub["amount"]),
                format_currency(monthly_cost),
                next_billing.strftime("%Y-%m-%d"),
                sub.get("notes", ""),
            ]

            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                if col == 6:  # 下次扣费日期
                    from datetime import date as dt_date
                    if next_billing <= dt_date.today():
                        item.setForeground(Qt.GlobalColor.red)
                self.table.setItem(row, col, item)

        self.table.resizeColumnsToContents()

    def _clear_search(self) -> None:
        self.search_edit.clear()
        self._apply_filter()

    # ── 表单操作 ─────────────────────────────────

    def _clear_form(self) -> None:
        self._editing_id = None
        self.name_edit.clear()
        self.start_date_edit.setDate(QDate.currentDate())
        self.cycle_combo.setCurrentIndex(0)
        self.amount_spin.setValue(0)
        self.notes_edit.clear()
        self.add_btn.setText("添加")

    def _get_form_data(self) -> dict:
        return {
            "service_name": self.name_edit.text().strip(),
            "start_date": self.start_date_edit.date().toString("yyyy-MM-dd"),
            "billing_cycle": self.cycle_combo.currentData(),
            "amount": self.amount_spin.value(),
            "notes": self.notes_edit.toPlainText().strip(),
        }

    def _validate_form(self, data: dict) -> bool:
        if not data["service_name"]:
            QMessageBox.warning(self, "提示", "请输入服务名称。")
            self.name_edit.setFocus()
            return False
        if data["amount"] <= 0:
            QMessageBox.warning(self, "提示", "金额必须大于 0。")
            self.amount_spin.setFocus()
            return False
        return True

    def _on_add(self) -> None:
        data = self._get_form_data()
        if not self._validate_form(data):
            return
        add_subscription(**data)
        self._clear_form()
        self._load_table()
        self.data_changed.emit()

    def _on_update(self) -> None:
        if self._editing_id is None:
            QMessageBox.information(self, "提示", "请先双击表格行或点击「编辑选中行」。")
            return
        data = self._get_form_data()
        if not self._validate_form(data):
            return
        update_subscription(self._editing_id, **data)
        self._clear_form()
        self._load_table()
        self.data_changed.emit()

    # ── 表格交互 ─────────────────────────────────

    def _get_selected_id(self) -> int | None:
        selected = self.table.selectedItems()
        if not selected:
            return None
        return int(self.table.item(selected[0].row(), 0).text())

    def _populate_form_from_row(self, row: int) -> None:
        sub_id = int(self.table.item(row, 0).text())
        sub = get_subscription_by_id(sub_id)
        if not sub:
            return
        self._editing_id = sub_id
        self.name_edit.setText(sub["service_name"])
        self.start_date_edit.setDate(
            QDate.fromString(sub["start_date"], "yyyy-MM-dd")
        )
        idx = self.cycle_combo.findData(sub["billing_cycle"])
        if idx >= 0:
            self.cycle_combo.setCurrentIndex(idx)
        self.amount_spin.setValue(sub["amount"])
        self.notes_edit.setPlainText(sub.get("notes", ""))
        self.add_btn.setText("添加（当前为编辑模式）")

    def _on_row_double_clicked(self, item: QTableWidgetItem) -> None:
        self._populate_form_from_row(item.row())

    def _on_edit_selected(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先在表格中选中一行。")
            return
        self._populate_form_from_row(selected[0].row())

    def _on_delete_selected(self) -> None:
        sub_id = self._get_selected_id()
        if sub_id is None:
            QMessageBox.information(self, "提示", "请先在表格中选中一行。")
            return
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除该订阅记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_subscription(sub_id)
            self._clear_form()
            self._load_table()
            self.data_changed.emit()
