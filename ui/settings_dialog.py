"""
设置对话框。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QSpinBox,
    QDoubleSpinBox, QPushButton, QDialogButtonBox, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt

from config import load_settings, save_settings, DEFAULT_SETTINGS


CURRENCIES = ["¥", "$", "€", "£", "₩", "自定义..."]
THEMES = {"light": "浅色", "dark": "深色"}


class SettingsDialog(QDialog):
    """软件设置对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(480)
        self._settings = load_settings()
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # ── 通用 ──
        group_general = QGroupBox("通用")
        form = QFormLayout(group_general)
        form.setSpacing(8)

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(CURRENCIES)
        self.currency_combo.setEditable(True)
        self.currency_combo.currentTextChanged.connect(self._on_currency_changed)
        form.addRow("货币符号：", self.currency_combo)

        self.budget_spin = QDoubleSpinBox()
        self.budget_spin.setRange(0, 99999999)
        self.budget_spin.setDecimals(2)
        self.budget_spin.setPrefix("¥ ")
        self.budget_spin.setToolTip("设置每月支出预算上限，0 表示不限制")
        form.addRow("月度预算：", self.budget_spin)

        self.theme_combo = QComboBox()
        for key, label in THEMES.items():
            self.theme_combo.addItem(label, key)
        form.addRow("主题：", self.theme_combo)

        layout.addWidget(group_general)

        # ── 默认值 ──
        group_defaults = QGroupBox("新建记录默认值")
        form2 = QFormLayout(group_defaults)
        form2.setSpacing(8)

        self.lifespan_spin = QSpinBox()
        self.lifespan_spin.setRange(1, 600)
        self.lifespan_spin.setSuffix(" 个月")
        form2.addRow("默认使用月数：", self.lifespan_spin)

        layout.addWidget(group_defaults)

        # ── 数据库 ──
        group_db = QGroupBox("数据库")
        db_layout = QHBoxLayout(group_db)

        self.db_path_edit = QLineEdit()
        self.db_path_edit.setPlaceholderText("留空使用默认路径")
        self.db_path_edit.setReadOnly(True)
        db_layout.addWidget(self.db_path_edit)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._browse_db_path)
        db_layout.addWidget(self.browse_btn)

        layout.addWidget(group_db)

        # ── 按钮 ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._restore_defaults)
        layout.addWidget(buttons)

    def _load(self) -> None:
        idx = self.currency_combo.findText(self._settings.get("currency", "¥"))
        if idx >= 0:
            self.currency_combo.setCurrentIndex(idx)
        else:
            self.currency_combo.setEditText(self._settings.get("currency", "¥"))

        theme = self._settings.get("theme", "light")
        idx = self.theme_combo.findData(theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

        self.lifespan_spin.setValue(self._settings.get("default_lifespan_months", 36))
        self.budget_spin.setValue(self._settings.get("monthly_budget", 0))
        self.db_path_edit.setText(self._settings.get("db_path", ""))

    def _on_save(self) -> None:
        self._settings["currency"] = self.currency_combo.currentText().strip()
        self._settings["theme"] = self.theme_combo.currentData()
        self._settings["default_lifespan_months"] = self.lifespan_spin.value()
        self._settings["monthly_budget"] = self.budget_spin.value()
        self._settings["db_path"] = self.db_path_edit.text().strip()

        save_settings(self._settings)

        # 提示需要重启才能应用部分设置
        QMessageBox.information(
            self, "设置已保存",
            "设置已保存。\n\n"
            "主题和数据库路径将在下次启动时生效。\n"
            "货币符号和默认月数立即生效。"
        )
        self.accept()

    def _restore_defaults(self) -> None:
        reply = QMessageBox.question(
            self, "恢复默认",
            "确定要恢复所有设置为默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            save_settings(dict(DEFAULT_SETTINGS))
            self._settings = dict(DEFAULT_SETTINGS)
            self._load()

    def _browse_db_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "选择数据库位置",
            self.db_path_edit.text() or "",
            "SQLite 数据库 (*.db);;所有文件 (*)"
        )
        if path:
            self.db_path_edit.setText(path)

    def _on_currency_changed(self, text: str) -> None:
        if text == "自定义...":
            self.currency_combo.setEditable(True)
            self.currency_combo.setEditText("")
            self.currency_combo.setFocus()
