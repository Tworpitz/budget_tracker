"""
固定资产 Tab — 记录电子设备、生活用品等，计算折旧。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QDateEdit,
    QDoubleSpinBox, QSpinBox, QTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt, QDate, Signal
from datetime import date
from dateutil.relativedelta import relativedelta
from db.validation import validate_asset
from ui.error_handling import run_database_write

from db.database import (
    add_asset, update_asset, delete_asset,
    get_all_assets, get_asset_by_id,
)
from calc.calculations import (
    calc_monthly_depreciation,
    calc_accumulated_depreciation,
    calc_current_value,
)

ASSET_CATEGORIES = ["电子设备", "家电", "家具", "交通工具", "服装", "书籍", "其他"]


class AssetTab(QWidget):
    """固定资产管理页面。"""

    # 数据变更时通知报告页刷新
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

        # ── 表单区域 ──
        form_group = QGroupBox("添加 / 编辑固定资产")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：iPhone 15 Pro")
        form_layout.addRow("名称：", self.name_edit)

        self.category_combo = QComboBox()
        self.category_combo.addItems(ASSET_CATEGORIES)
        self.category_combo.setEditable(True)
        form_layout.addRow("类别：", self.category_combo)

        self.purchase_date_edit = QDateEdit()
        self.purchase_date_edit.setCalendarPopup(True)
        self.purchase_date_edit.setDate(QDate.currentDate())
        self.purchase_date_edit.setDisplayFormat("yyyy-MM-dd")
        form_layout.addRow("购买日期：", self.purchase_date_edit)

        self.lifespan_spin = QSpinBox()
        self.lifespan_spin.setRange(1, 600)
        self.lifespan_spin.setValue(36)
        self.lifespan_spin.setSuffix(" 个月")
        form_layout.addRow("预期使用月数：", self.lifespan_spin)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 9999999)
        self.price_spin.setDecimals(2)
        self.price_spin.setPrefix("¥ ")
        self.price_spin.setValue(0)
        form_layout.addRow("购买价格：", self.price_spin)

        self.salvage_spin = QDoubleSpinBox()
        self.salvage_spin.setRange(0, 9999999)
        self.salvage_spin.setDecimals(2)
        self.salvage_spin.setPrefix("¥ ")
        self.salvage_spin.setValue(0)
        self.salvage_spin.setToolTip(
            "残值是指资产在预期使用年限结束后剩余的估计价值。\n"
            "例如：电脑购买价 8000 元，使用 3 年后预计能卖 1000 元，残值即 1000 元。\n"
            "月折旧额 = (购买价格 − 残值) ÷ 使用月数"
        )
        form_layout.addRow("残值：", self.salvage_spin)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        self.notes_edit.setPlaceholderText("可选备注")
        form_layout.addRow("备注：", self.notes_edit)

        # 按钮行
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

        # ── 表格区域 ──
        table_group = QGroupBox("固定资产列表")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            "ID", "名称", "类别", "购买日期", "预期报废",
            "使用月数", "购买价格", "残值", "月折旧额", "累计折旧", "当前净值", "备注",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)  # 隐藏 ID 列
        # 列宽策略：初始按内容自适应，备注列自动拉伸填满剩余空间
        header = self.table.horizontalHeader()
        for col in range(1, 11):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(11, QHeaderView.ResizeMode.Stretch)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)

        table_layout.addWidget(self.table)

        # 表格操作按钮
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
        """从数据库加载所有固定资产并填充表格。"""
        assets = get_all_assets()
        self.table.setRowCount(len(assets))

        for row, asset in enumerate(assets):
            error = None
            try:
                monthly = calc_monthly_depreciation(asset)
                accumulated = calc_accumulated_depreciation(asset)
                current_val = calc_current_value(asset)
                purchase = date.fromisoformat(asset["purchase_date"])
                scrap_date = purchase + relativedelta(months=asset["lifespan_months"])
            except ValueError as exc:
                error = str(exc)
                monthly = accumulated = current_val = scrap_date = None

            items = [
                str(asset["id"]),                      # 0: ID
                asset["name"],                         # 1: 名称
                asset["category"],                     # 2: 类别
                asset["purchase_date"],                # 3: 购买日期
                scrap_date.strftime("%Y-%m-%d") if scrap_date else "数据有误",
                f"{asset['lifespan_months']} 个月",    # 5: 使用月数
                f"¥ {asset['purchase_price']:,.2f}",   # 6: 购买价格
                f"¥ {asset['salvage_value']:,.2f}",    # 7: 残值
                f"¥ {monthly:,.2f}" if monthly is not None else "数据有误",
                f"¥ {accumulated:,.2f}" if accumulated is not None else "数据有误",
                f"¥ {current_val:,.2f}" if current_val is not None else "数据有误",
                asset.get("notes", ""),                # 11: 备注
            ]

            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                # 已报废的资产 → 当前净值灰显
                if col == 10 and current_val is not None:
                    if current_val <= asset.get("salvage_value", 0):
                        item.setForeground(Qt.GlobalColor.gray)
                # 预期报废日期：已过期的标红
                if col == 4 and scrap_date is not None and scrap_date < date.today():
                    item.setForeground(Qt.GlobalColor.red)
                if error:
                    item.setToolTip(error)
                    item.setForeground(Qt.GlobalColor.red)
                self.table.setItem(row, col, item)

        self.table.resizeColumnsToContents()

    # ── 表单操作 ─────────────────────────────────

    def _clear_form(self) -> None:
        """清空表单，重置为添加模式。"""
        self._editing_id = None
        self.name_edit.clear()
        self.category_combo.setCurrentIndex(0)
        self.purchase_date_edit.setDate(QDate.currentDate())
        self.lifespan_spin.setValue(36)
        self.price_spin.setValue(0)
        self.salvage_spin.setValue(0)
        self.notes_edit.clear()
        self.add_btn.setText("添加")

    def _get_form_data(self) -> dict:
        """收集表单数据。"""
        return {
            "name": self.name_edit.text().strip(),
            "category": self.category_combo.currentText().strip(),
            "purchase_date": self.purchase_date_edit.date().toString("yyyy-MM-dd"),
            "lifespan_months": self.lifespan_spin.value(),
            "purchase_price": self.price_spin.value(),
            "salvage_value": self.salvage_spin.value(),
            "notes": self.notes_edit.toPlainText().strip(),
        }

    def _validate_form(self, data: dict) -> bool:
        try:
            validate_asset(**data)
        except ValueError as exc:
            QMessageBox.warning(self, "输入有误", str(exc))
            return False
        return True

    def _on_add(self) -> None:
        """添加新资产。"""
        data = self._get_form_data()
        if not self._validate_form(data):
            return

        if not run_database_write(self, add_asset, **data):
            return
        self._clear_form()
        self._load_table()
        self.data_changed.emit()

    def _on_update(self) -> None:
        """更新当前编辑的资产。"""
        if self._editing_id is None:
            QMessageBox.information(self, "提示", "请先双击表格行或点击「编辑选中行」选择要编辑的记录。")
            return

        data = self._get_form_data()
        if not self._validate_form(data):
            return

        if not run_database_write(self, update_asset, self._editing_id, **data):
            return
        self._clear_form()
        self._load_table()
        self.data_changed.emit()

    # ── 表格交互 ─────────────────────────────────

    def _get_selected_id(self) -> int | None:
        """获取当前选中行的资产 ID。"""
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        id_item = self.table.item(row, 0)
        return int(id_item.text()) if id_item else None

    def _populate_form_from_row(self, row: int) -> None:
        """将表格行数据填入表单。"""
        asset_id = int(self.table.item(row, 0).text())
        asset = get_asset_by_id(asset_id)
        if not asset:
            return

        self._editing_id = asset_id
        self.name_edit.setText(asset["name"])
        idx = self.category_combo.findText(asset["category"])
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setEditText(asset["category"])
        self.purchase_date_edit.setDate(
            QDate.fromString(asset["purchase_date"], "yyyy-MM-dd")
        )
        self.lifespan_spin.setValue(asset["lifespan_months"])
        self.price_spin.setValue(asset["purchase_price"])
        self.salvage_spin.setValue(asset.get("salvage_value", 0))
        self.notes_edit.setPlainText(asset.get("notes", ""))
        self.add_btn.setText("添加（当前为编辑模式）")

    def _on_row_double_clicked(self, item: QTableWidgetItem) -> None:
        """双击表格行 → 填充表单进入编辑模式。"""
        self._populate_form_from_row(item.row())

    def _on_edit_selected(self) -> None:
        """编辑选中行按钮。"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先在表格中选中一行。")
            return
        self._populate_form_from_row(selected[0].row())

    def _on_delete_selected(self) -> None:
        """删除选中行。"""
        asset_id = self._get_selected_id()
        if asset_id is None:
            QMessageBox.information(self, "提示", "请先在表格中选中一行。")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除该固定资产记录吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if not run_database_write(self, delete_asset, asset_id):
                return
            self._clear_form()
            self._load_table()
            self.data_changed.emit()
