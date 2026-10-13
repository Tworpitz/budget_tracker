"""写入失败时保留表单，并显示可读的错误。"""

import sqlite3

from PySide6.QtWidgets import QMessageBox


def run_database_write(parent, operation, *args, **kwargs) -> bool:
    try:
        operation(*args, **kwargs)
        return True
    except (sqlite3.Error, OSError, ValueError) as exc:
        QMessageBox.critical(parent, "保存失败", f"数据未保存，请检查数据库后重试。\n{exc}")
        return False
