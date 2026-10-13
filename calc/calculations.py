"""折旧和订阅按日分摊；周报与月报使用相同的金额及日期边界。"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from dateutil.relativedelta import relativedelta

from db.validation import validate_asset, validate_expense, validate_subscription


CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def _money(value) -> Decimal:
    return Decimal(str(value))


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate_asset(asset: dict) -> None:
    try:
        validate_asset(**{k: asset[k] for k in
                         ("name", "category", "purchase_date", "lifespan_months", "purchase_price")},
                       salvage_value=asset.get("salvage_value", 0))
    except ValueError as exc:
        raise ValueError(f"资产 {asset['name']}：{exc}") from None


def _validate_subscription(sub: dict) -> None:
    try:
        validate_subscription(**{k: sub[k] for k in ("service_name", "start_date", "billing_cycle", "amount")})
    except ValueError as exc:
        raise ValueError(f"订阅 {sub['service_name']}：{exc}") from None


def _monthly_depreciation(asset: dict) -> Decimal:
    return (_money(asset["purchase_price"]) - _money(asset.get("salvage_value", 0))) / asset["lifespan_months"]


def calc_monthly_depreciation(asset: dict) -> float:
    """直线法的标准月折旧额。"""
    _validate_asset(asset)
    return float(_monthly_depreciation(asset))


def _accumulated_before(asset: dict, boundary: date) -> Decimal:
    """截至 boundary 日开始前的折旧；每个使用月由购买日周年确定。"""
    purchase = date.fromisoformat(asset["purchase_date"])
    lifespan = asset["lifespan_months"]
    if boundary <= purchase:
        return ZERO
    depreciable = _money(asset["purchase_price"]) - _money(asset.get("salvage_value", 0))
    if boundary >= purchase + relativedelta(months=lifespan):
        return depreciable
    months = (boundary.year - purchase.year) * 12 + boundary.month - purchase.month
    if purchase + relativedelta(months=months) > boundary:
        months -= 1
    start = purchase + relativedelta(months=months)
    end = purchase + relativedelta(months=months + 1)
    fraction = Decimal((boundary - start).days) / (end - start).days
    return _cents(_monthly_depreciation(asset) * (months + fraction))


def calc_accumulated_depreciation(asset: dict, as_of: Optional[date] = None) -> float:
    """累计折旧包含 as_of 当日；寿命结束日不再计提。"""
    _validate_asset(asset)
    return float(_accumulated_before(asset, (as_of or date.today()) + timedelta(days=1)))


def calc_current_value(asset: dict, as_of: Optional[date] = None) -> float:
    return float(_money(asset["purchase_price"]) - _money(calc_accumulated_depreciation(asset, as_of)))


def calc_depreciation_for_period(asset: dict, period_start: date, period_end: date) -> float:
    """查询起止日均包含；累计分币差值保证不同分组的合计一致。"""
    _validate_asset(asset)
    _validate_range(period_start, period_end)
    return float(_accumulated_before(asset, period_end + timedelta(days=1))
                 - _accumulated_before(asset, period_start))


def _monthly_subscription_cost(sub: dict) -> Decimal:
    return _money(sub["amount"]) / {"monthly": 1, "quarterly": 3, "yearly": 12}[sub["billing_cycle"]]


def calc_monthly_subscription_cost(sub: dict) -> float:
    _validate_subscription(sub)
    return float(_monthly_subscription_cost(sub))


def calc_next_billing_date(sub: dict, as_of: Optional[date] = None) -> date:
    """从原始开始日期计算周年，避免 31 日经二月后漂移到 28 日。"""
    _validate_subscription(sub)
    start = date.fromisoformat(sub["start_date"])
    today = as_of or date.today()
    interval = {"monthly": 1, "quarterly": 3, "yearly": 12}[sub["billing_cycle"]]
    elapsed = (today.year - start.year) * 12 + today.month - start.month
    cycle = max(elapsed // interval, 0)
    next_date = start + relativedelta(months=cycle * interval)
    while next_date <= today:
        cycle += 1
        next_date = start + relativedelta(months=cycle * interval)
    return next_date


def get_week_range(week_offset: int = 0) -> tuple[date, date]:
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    return monday, monday + timedelta(days=6)


def get_month_range(month_offset: int = 0) -> tuple[date, date]:
    first = date.today().replace(day=1) + relativedelta(months=month_offset)
    return first, first + relativedelta(months=1) - timedelta(days=1)


def _validate_range(start: date, end: date) -> None:
    if start > end:
        raise ValueError("起始日期不能晚于结束日期。")
    if end == date.max:
        raise ValueError("结束日期超出支持范围。")


def _subscription_for_period(sub: dict, start: date, end: date) -> Decimal:
    current = max(start, date.fromisoformat(sub["start_date"]))
    total = ZERO
    monthly = _monthly_subscription_cost(sub)
    while current < end:
        month_start = current.replace(day=1)
        next_month = month_start + relativedelta(months=1)
        stop = min(next_month, end)
        days = (next_month - month_start).days
        total += (_cents(monthly * (stop - month_start).days / days)
                  - _cents(monthly * (current - month_start).days / days))
        current = stop
    return total


def _generate_stats(assets, subscriptions, expenses, start_date, end_date, mode):
    _validate_range(start_date, end_date)
    for asset in assets:
        _validate_asset(asset)
    for sub in subscriptions:
        _validate_subscription(sub)
    expense_days = defaultdict(lambda: ZERO)
    for exp in expenses:
        validate_expense(**{k: exp[k] for k in ("name", "category", "expense_date", "amount")})
        exp_date = date.fromisoformat(exp["expense_date"])
        if start_date <= exp_date <= end_date:
            expense_days[exp_date] += _money(exp["amount"])

    current = start_date
    end = end_date + timedelta(days=1)
    result = []
    while current < end:
        if mode == "week":
            iso_year, week, _ = current.isocalendar()
            key = f"{iso_year}-W{week:02d}"
            stop = min(end, current + timedelta(days=7 - current.weekday()))
        else:
            key = current.strftime("%Y-%m")
            stop = min(end, current.replace(day=1) + relativedelta(months=1))
        dep = sum((_accumulated_before(a, stop) - _accumulated_before(a, current)
                   for a in assets), ZERO)
        sub = sum((_subscription_for_period(s, current, stop) for s in subscriptions), ZERO)
        exp = sum((amount for day, amount in expense_days.items() if current <= day < stop), ZERO)
        result.append({mode: key, "start": current.isoformat(), "end": (stop - timedelta(days=1)).isoformat(),
                       "depreciation": float(dep), "subscriptions": float(sub),
                       "expenses": float(exp), "total": float(dep + sub + exp)})
        current = stop
    return result


def generate_weekly_stats(assets: list[dict], subscriptions: list[dict], expenses: list[dict],
                          start_date: date, end_date: date) -> list[dict]:
    """按 ISO 自然周分组；首尾周仅计查询范围内的天数。"""
    return _generate_stats(assets, subscriptions, expenses, start_date, end_date, "week")


def generate_monthly_stats(assets: list[dict], subscriptions: list[dict], expenses: list[dict],
                           start_date: date, end_date: date) -> list[dict]:
    """按自然月分组；首尾月仅计查询范围内的天数。"""
    return _generate_stats(assets, subscriptions, expenses, start_date, end_date, "month")


def generate_category_breakdown(expenses: list[dict]) -> dict[str, float]:
    breakdown = defaultdict(lambda: ZERO)
    for exp in expenses:
        breakdown[exp["category"]] += _money(exp["amount"])
    return {key: float(value) for key, value in breakdown.items()}
