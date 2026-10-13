#!/usr/bin/env python3
"""
固定资产与生活支出统计 — 主入口。

功能：
  1. 记录固定资产（电子设备、生活用品等），自动计算月折旧额和当前净值
  2. 管理按月/季/年订阅服务，自动折算月均成本和下次扣费日期
  3. 记录一次性开支（吃饭、送礼等），按类别归类
  4. 按周/月生成支出统计报表和堆叠柱状图

用法：
  python main.py
"""

import sys
import sqlite3
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


def main():
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("BudgetTracker")
    app.setOrganizationName("BudgetApp")

    try:
        window = MainWindow()
    except (sqlite3.Error, OSError, ValueError) as exc:
        QMessageBox.critical(None, "无法启动", f"数据库初始化或数据校验失败。\n{exc}")
        sys.exit(1)
    window.show_on_screen()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
