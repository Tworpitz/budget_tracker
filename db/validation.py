"""界面和数据库写入共用的数据校验。"""

from datetime import date
from decimal import Decimal, InvalidOperation


def _text(value, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}不能为空。")


def _date(value, label: str) -> None:
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须是有效的 YYYY-MM-DD 日期。") from None


def _money(value, label: str, allow_zero: bool = False) -> Decimal:
    try:
        if isinstance(value, bool):
            raise ValueError
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
            raise ValueError
        if amount > Decimal("9999999") or amount != amount.quantize(Decimal("0.01")):
            raise ValueError
    except (ValueError, InvalidOperation):
        qualifier = "非负" if allow_zero else "大于 0 的"
        raise ValueError(f"{label}必须是{qualifier}有限金额，最多两位小数且不超过 9999999。") from None
    return amount


def validate_asset(name, category, purchase_date, lifespan_months,
                   purchase_price, salvage_value=0, notes="") -> None:
    _text(name, "资产名称")
    _text(category, "资产类别")
    _date(purchase_date, "购买日期")
    if isinstance(lifespan_months, bool) or not isinstance(lifespan_months, int) or not 1 <= lifespan_months <= 600:
        raise ValueError("使用月数必须是 1 到 600 的整数。")
    price = _money(purchase_price, "购买价格")
    salvage = _money(salvage_value, "残值", allow_zero=True)
    if salvage > price:
        raise ValueError("残值不能高于购买价格。")


def validate_subscription(service_name, start_date, billing_cycle, amount, notes="") -> None:
    _text(service_name, "服务名称")
    _date(start_date, "开始日期")
    if billing_cycle not in ("monthly", "quarterly", "yearly"):
        raise ValueError("计费周期必须为月付、季付或年付。")
    _money(amount, "订阅金额")


def validate_expense(name, category, expense_date, amount, notes="") -> None:
    _text(name, "开支名称")
    _text(category, "开支类别")
    _date(expense_date, "开支日期")
    _money(amount, "开支金额")
