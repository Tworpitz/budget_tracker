"""
一次性开支 Tab — 记录吃饭、送礼等非固定支出。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLineEdit, QComboBox, QDateEdit,
    QDoubleSpinBox, QTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt, QDate, Signal

from db.database import (
    add_expense, update_expense, delete_expense,
    get_all_expenses, get_expense_by_id,
)

EXPENSE_CATEGORIES = ["餐饮", "礼物", "旅行", "医疗", "教育", "娱乐", "交通", "日用", "服饰", "住房", "其他"]


class ExpenseTab(QWidget):
    """一次性开支管理页面。"""

    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_id: int | None = None
        self._setup_ui()
        self._load_table()

    # ── UI 构建 ─────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── 表单 ──
        form_group = QGroupBox("记录一次性开支")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：朋友聚餐、生日礼物")
        form_layout.addRow("名称：", self.name_edit)

        self.category_combo = QComboBox()
        self.category_combo.addItems(EXPENSE_CATEGORIES)
        self.category_combo.setEditable(True)
        form_layout.addRow("类别：", self.category_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow("日期：", self.date_edit)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 9999999)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix("¥ ")
        self.amount_spin.setValue(0)
        form_layout.addRow("金额：", self.amount_spin)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        self.notes_edit.setPlaceholderText("可选备注")
        form_layout.addRow("备注：", self.notes_edit)

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

        # ── 表格 ──
        table_group = QGroupBox("开支列表")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "名称", "类别", "日期", "金额", "备注",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)
        # 列宽策略：内容自适应 + 备注列拉伸
        header = self.table.horizontalHeader()
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
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
        expenses = get_all_expenses()
        self.table.setRowCount(len(expenses))

        for row, exp in enumerate(expenses):
            items = [
                str(exp["id"]),
                exp["name"],
                exp["category"],
                exp["expense_date"],
                f"¥ {exp['amount']:,.2f}",
                exp.get("notes", ""),
            ]
            for col, text in enumerate(items):
                self.table.setItem(row, col, QTableWidgetItem(text))

        self.table.resizeColumnsToContents()

    # ── 表单操作 ─────────────────────────────────

    def _clear_form(self) -> None:
        self._editing_id = None
        self.name_edit.clear()
        self.category_combo.setCurrentIndex(0)
        self.date_edit.setDate(QDate.currentDate())
        self.amount_spin.setValue(0)
        self.notes_edit.clear()
        self.add_btn.setText("添加")

    def _get_form_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "category": self.category_combo.currentText().strip(),
            "expense_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "amount": self.amount_spin.value(),
            "notes": self.notes_edit.toPlainText().strip(),
        }

    def _validate_form(self, data: dict) -> bool:
        if not data["name"]:
            QMessageBox.warning(self, "提示", "请输入开支名称。")
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
        add_expense(**data)
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
        update_expense(self._editing_id, **data)
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
        exp_id = int(self.table.item(row, 0).text())
        exp = get_expense_by_id(exp_id)
        if not exp:
            return
        self._editing_id = exp_id
        self.name_edit.setText(exp["name"])
        idx = self.category_combo.findText(exp["category"])
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setEditText(exp["category"])
        self.date_edit.setDate(
            QDate.fromString(exp["expense_date"], "yyyy-MM-dd")
        )
        self.amount_spin.setValue(exp["amount"])
        self.notes_edit.setPlainText(exp.get("notes", ""))
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
        exp_id = self._get_selected_id()
        if exp_id is None:
            QMessageBox.information(self, "提示", "请先在表格中选中一行。")
            return
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除该开支记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_expense(exp_id)
            self._clear_form()
            self._load_table()
            self.data_changed.emit()
