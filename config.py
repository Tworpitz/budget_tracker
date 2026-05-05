"""
应用配置 — 读取 / 写入 settings.json。
"""

import json
import os
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "currency": "¥",
    "theme": "light",
    "default_lifespan_months": 36,
    "monthly_budget": 0.0,
}

_settings_cache: dict[str, Any] | None = None


def _get_config_dir() -> str:
    """返回配置文件目录，与数据库路径检测逻辑一致。"""
    xdg_config = os.path.join(os.path.expanduser("~"), ".config", "budgettracker")
    os.makedirs(xdg_config, exist_ok=True)
    return xdg_config


def _get_config_path() -> str:
    return os.path.join(_get_config_dir(), "settings.json")


def load_settings() -> dict[str, Any]:
    """加载设置，缺失项用默认值补齐。"""
    global _settings_cache
    path = _get_config_path()
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        settings.update(stored)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    _settings_cache = settings
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    """保存设置到文件。"""
    global _settings_cache
    _settings_cache = dict(settings)
    path = _get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get_setting(key: str, default: Any = None) -> Any:
    """读取单个设置项。"""
    global _settings_cache
    if _settings_cache is None:
        load_settings()
    return _settings_cache.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))


def format_currency(amount: float) -> str:
    """按用户设置的货币符号格式化金额。"""
    sym = get_setting("currency", "¥")
    return f"{sym} {amount:,.2f}"
