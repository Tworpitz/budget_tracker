"""
周期性收支 Tab — 管理工资、房租等固定周期收支。
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
    add_recurring, update_recurring, delete_recurring,
    get_all_recurring, get_recurring_by_id,
)

CYCLES = ["monthly", "quarterly", "yearly"]
CYCLE_LABELS = {"monthly": "月付", "quarterly": "季付", "yearly": "年付"}
TYPE_LABELS = {"income": "收入", "expense": "支出"}
RECUR_CATEGORIES = ["工资", "房租", "水电", "保险", "贷款", "投资", "其他"]


class RecurringTab(QWidget):
    """周期性收支管理页面。"""

    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_id: int | None = None
        self._all_rows: list[dict] = []
        self._setup_ui()
        self._load_table()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 表单
        form_group = QGroupBox("添加 / 编辑周期性收支")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：工资、房租")
        form_layout.addRow("名称：", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItem("支出", "expense")
        self.type_combo.addItem("收入", "income")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form_layout.addRow("类型：", self.type_combo)

        self.category_combo = QComboBox()
        self.category_combo.addItems(RECUR_CATEGORIES)
        self.category_combo.setEditable(True)
        form_layout.addRow("类别：", self.category_combo)

        self.cycle_combo = QComboBox()
        for c in CYCLES:
            self.cycle_combo.addItem(CYCLE_LABELS[c], c)
        form_layout.addRow("周期：", self.cycle_combo)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow("开始日期：", self.start_date_edit)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 9999999)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix(get_setting("currency", "¥") + " ")
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

        # 表格
        table_group = QGroupBox("周期性收支列表")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "名称", "类型", "类别", "周期", "金额", "开始日期", "备注",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)
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

    def _load_table(self) -> None:
        self._all_rows = get_all_recurring()
        self._apply_filter()

    def _apply_filter(self) -> None:
        keyword = self.search_edit.text().strip().lower() if hasattr(self, 'search_edit') else ""
        rows = [r for r in self._all_rows
                if not keyword or keyword in r["name"].lower() or keyword in r["category"].lower()]

        self.table.setRowCount(len(rows))
        for row, rec in enumerate(rows):
            items = [
                str(rec["id"]),
                rec["name"],
                TYPE_LABELS.get(rec["type"], rec["type"]),
                rec["category"],
                CYCLE_LABELS.get(rec["cycle"], rec["cycle"]),
                format_currency(rec["amount"]),
                rec["start_date"],
                rec.get("notes", ""),
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                if col == 2:
                    if rec["type"] == "income":
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    else:
                        item.setForeground(Qt.GlobalColor.darkRed)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()

    def _clear_search(self) -> None:
        self.search_edit.clear()
        self._apply_filter()

    def _clear_form(self) -> None:
        self._editing_id = None
        self.name_edit.clear()
        self.type_combo.setCurrentIndex(0)
        self.category_combo.setCurrentIndex(0)
        self.cycle_combo.setCurrentIndex(0)
        self.start_date_edit.setDate(QDate.currentDate())
        self.amount_spin.setValue(0)
        self.notes_edit.clear()
        self.add_btn.setText("添加")

    def _get_form_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "rtype": self.type_combo.currentData(),
            "category": self.category_combo.currentText().strip(),
            "cycle": self.cycle_combo.currentData(),
            "amount": self.amount_spin.value(),
            "start_date": self.start_date_edit.date().toString("yyyy-MM-dd"),
            "notes": self.notes_edit.toPlainText().strip(),
        }

    def _validate_form(self, data: dict) -> bool:
        if not data["name"]:
            QMessageBox.warning(self, "提示", "请输入名称。")
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
        add_recurring(**data)
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
        update_recurring(self._editing_id, **data)
        self._clear_form()
        self._load_table()
        self.data_changed.emit()

    def _on_type_changed(self) -> None:
        if self.type_combo.currentData() == "income":
            self.amount_spin.setPrefix(get_setting("currency", "¥") + " +")
        else:
            self.amount_spin.setPrefix(get_setting("currency", "¥") + " ")

    def _get_selected_id(self) -> int | None:
        selected = self.table.selectedItems()
        if not selected:
            return None
        return int(self.table.item(selected[0].row(), 0).text())

    def _populate_form_from_row(self, row: int) -> None:
        rec_id = int(self.table.item(row, 0).text())
        rec = get_recurring_by_id(rec_id)
        if not rec:
            return
        self._editing_id = rec_id
        self.name_edit.setText(rec["name"])
        idx = self.type_combo.findData(rec["type"])
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        idx = self.category_combo.findText(rec["category"])
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setEditText(rec["category"])
        idx = self.cycle_combo.findData(rec["cycle"])
        if idx >= 0:
            self.cycle_combo.setCurrentIndex(idx)
        self.start_date_edit.setDate(QDate.fromString(rec["start_date"], "yyyy-MM-dd"))
        self.amount_spin.setValue(rec["amount"])
        self.notes_edit.setPlainText(rec.get("notes", ""))
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
        rec_id = self._get_selected_id()
        if rec_id is None:
            QMessageBox.information(self, "提示", "请先在表格中选中一行。")
            return
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除该记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_recurring(rec_id)
            self._clear_form()
            self._load_table()
            self.data_changed.emit()
