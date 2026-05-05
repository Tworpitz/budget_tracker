"""
计算模块：折旧计算、月度订阅成本、统计汇总。
"""

from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional
from collections import defaultdict


# ──────────────────────────────────────────────
#  折旧计算（直线法）
# ──────────────────────────────────────────────

def calc_monthly_depreciation(asset: dict) -> float:
    """计算固定资产的月折旧额（直线法）。"""
    price = asset["purchase_price"]
    salvage = asset.get("salvage_value", 0)
    months = asset["lifespan_months"]
    if months <= 0:
        return 0.0
    return (price - salvage) / months


def calc_accumulated_depreciation(asset: dict, as_of: Optional[date] = None) -> float:
    """计算截至某日的累计折旧额。"""
    if as_of is None:
        as_of = date.today()

    purchase = datetime.strptime(asset["purchase_date"], "%Y-%m-%d").date()
    if purchase > as_of:
        return 0.0

    monthly = calc_monthly_depreciation(asset)
    # 计算已使用的完整月数
    delta = relativedelta(as_of, purchase)
    months_used = delta.years * 12 + delta.months
    lifespan = asset["lifespan_months"]

    if months_used >= lifespan:
        # 已超过使用年限，累计折旧 = 原值 - 残值
        return asset["purchase_price"] - asset.get("salvage_value", 0)

    return monthly * months_used


def calc_current_value(asset: dict, as_of: Optional[date] = None) -> float:
    """计算固定资产当前净值。"""
    accumulated = calc_accumulated_depreciation(asset, as_of)
    return max(asset["purchase_price"] - accumulated,
               asset.get("salvage_value", 0))


def calc_depreciation_for_period(asset: dict, period_start: date,
                                 period_end: date) -> float:
    """
    计算某项资产在指定时间段内的折旧费用。
    按天精确计算，逐月累加各月的占用天数比例。
    """
    purchase = datetime.strptime(asset["purchase_date"], "%Y-%m-%d").date()
    lifespan = asset["lifespan_months"]
    end_of_life = purchase + relativedelta(months=lifespan)
    monthly = calc_monthly_depreciation(asset)

    effective_start = max(purchase, period_start)
    effective_end = min(end_of_life, period_end)

    if effective_start >= effective_end:
        return 0.0

    total_months = 0.0
    cursor = effective_start

    while cursor < effective_end:
        # 当月第一天和最后一天
        month_first = cursor.replace(day=1)
        month_last = month_first + relativedelta(months=1) - timedelta(days=1)
        days_in_month = month_last.day

        # 当前段结束日（不超过 effective_end）
        segment_end = min(month_last, effective_end)
        # 当前段起始日
        segment_start = cursor
        days_active = (segment_end - segment_start).days + 1

        total_months += days_active / days_in_month
        cursor = segment_end + timedelta(days=1)

    return round(monthly * total_months, 2)


# ──────────────────────────────────────────────
#  订阅月成本
# ──────────────────────────────────────────────

def calc_monthly_subscription_cost(sub: dict) -> float:
    """将订阅费用折算为每月成本。"""
    cycle = sub["billing_cycle"]
    amount = sub["amount"]
    if cycle == "monthly":
        return amount
    elif cycle == "quarterly":
        return amount / 3
    elif cycle == "yearly":
        return amount / 12
    return amount


def calc_next_billing_date(sub: dict) -> date:
    """计算下一次扣费日期。"""
    start = datetime.strptime(sub["start_date"], "%Y-%m-%d").date()
    today = date.today()
    cycle = sub["billing_cycle"]

    if sub["billing_cycle"] == "monthly":
        delta = relativedelta(months=1)
    elif sub["billing_cycle"] == "quarterly":
        delta = relativedelta(months=3)
    elif sub["billing_cycle"] == "yearly":
        delta = relativedelta(years=1)
    else:
        delta = relativedelta(months=1)

    next_date = start
    while next_date <= today:
        next_date += delta
    return next_date


# ──────────────────────────────────────────────
#  统计汇总
# ──────────────────────────────────────────────

def get_week_range(week_offset: int = 0) -> tuple[date, date]:
    """获取某周的起止日期（周一到周日）。week_offset=0 为本周，-1 为上周。"""
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_month_range(month_offset: int = 0) -> tuple[date, date]:
    """获取某月的起止日期。month_offset=0 为本月，-1 为上月。"""
    today = date.today()
    first_day = today.replace(day=1) + relativedelta(months=month_offset)
    last_day = first_day + relativedelta(months=1) - timedelta(days=1)
    return first_day, last_day


def _calc_monthly_recurring_cost(rec: dict) -> float:
    """将周期性收支折算为每月金额。"""
    cycle = rec["cycle"]
    amount = rec["amount"]
    if cycle == "monthly":
        return amount
    elif cycle == "quarterly":
        return amount / 3
    elif cycle == "yearly":
        return amount / 12
    return amount


def generate_weekly_stats(assets: list[dict], subscriptions: list[dict],
                          expenses: list[dict], recurrings: list[dict],
                          start_date: date, end_date: date) -> list[dict]:
    """生成按周汇总的统计数据。"""
    weekly_data: dict[str, dict] = defaultdict(
        lambda: {"depreciation": 0.0, "subscriptions": 0.0, "expenses": 0.0,
                 "recurring_income": 0.0, "recurring_expense": 0.0}
    )

    # 计算每周折旧
    for asset in assets:
        depreciation = calc_depreciation_for_period(asset, start_date, end_date)
        # 简化：将折旧均分到每周
        total_weeks = max(((end_date - start_date).days // 7), 1)
        weekly_dep = depreciation / total_weeks

        current = start_date
        week_num = 1
        while current <= end_date:
            week_end = min(current + timedelta(days=6), end_date)
            week_key = f"{current.year}-W{current.isocalendar()[1]:02d}"
            weekly_data[week_key]["depreciation"] += round(weekly_dep, 2)
            weekly_data[week_key]["_start"] = current.isoformat()
            weekly_data[week_key]["_end"] = week_end.isoformat()
            current += timedelta(days=7)
            week_num += 1

    # 订阅费用按周分摊
    for sub in subscriptions:
        monthly_cost = calc_monthly_subscription_cost(sub)
        weekly_cost = monthly_cost / 4.345  # 平均每月周数

        current = max(
            datetime.strptime(sub["start_date"], "%Y-%m-%d").date(),
            start_date
        )
        while current <= end_date:
            week_key = f"{current.year}-W{current.isocalendar()[1]:02d}"
            weekly_data[week_key]["subscriptions"] += round(weekly_cost, 2)
            if "_start" not in weekly_data[week_key]:
                week_start = current - timedelta(days=current.weekday())
                weekly_data[week_key]["_start"] = week_start.isoformat()
                weekly_data[week_key]["_end"] = (
                    week_start + timedelta(days=6)
                ).isoformat()
            current += timedelta(days=7)

    # 周期性收支按周分摊
    for rec in recurrings:
        monthly_cost = _calc_monthly_recurring_cost(rec)
        weekly_cost = monthly_cost / 4.345
        rec_start = datetime.strptime(rec["start_date"], "%Y-%m-%d").date()
        field = "recurring_income" if rec["type"] == "income" else "recurring_expense"

        current = max(rec_start, start_date)
        while current <= end_date:
            week_key = f"{current.year}-W{current.isocalendar()[1]:02d}"
            weekly_data[week_key][field] += round(weekly_cost, 2)
            if "_start" not in weekly_data[week_key]:
                week_start = current - timedelta(days=current.weekday())
                weekly_data[week_key]["_start"] = week_start.isoformat()
                weekly_data[week_key]["_end"] = (
                    week_start + timedelta(days=6)
                ).isoformat()
            current += timedelta(days=7)

    # 一次性开支直接归入对应周
    for exp in expenses:
        exp_date = datetime.strptime(exp["expense_date"], "%Y-%m-%d").date()
        if start_date <= exp_date <= end_date:
            week_key = f"{exp_date.year}-W{exp_date.isocalendar()[1]:02d}"
            weekly_data[week_key]["expenses"] += exp["amount"]
            if "_start" not in weekly_data[week_key]:
                week_start = exp_date - timedelta(days=exp_date.weekday())
                weekly_data[week_key]["_start"] = week_start.isoformat()
                weekly_data[week_key]["_end"] = (
                    week_start + timedelta(days=6)
                ).isoformat()

    # 整理输出
    result = []
    for week_key in sorted(weekly_data.keys()):
        d = weekly_data[week_key]
        total = d["depreciation"] + d["subscriptions"] + d["expenses"] + d["recurring_expense"]
        result.append({
            "week": week_key,
            "start": d.get("_start", ""),
            "end": d.get("_end", ""),
            "depreciation": round(d["depreciation"], 2),
            "subscriptions": round(d["subscriptions"], 2),
            "expenses": round(d["expenses"], 2),
            "recurring_expense": round(d["recurring_expense"], 2),
            "recurring_income": round(d["recurring_income"], 2),
            "total": round(total, 2),
        })

    return result


def generate_monthly_stats(assets: list[dict], subscriptions: list[dict],
                           expenses: list[dict], recurrings: list[dict],
                           start_date: date, end_date: date) -> list[dict]:
    """生成按月汇总的统计数据。"""
    monthly_data: dict[str, dict] = defaultdict(
        lambda: {"depreciation": 0.0, "subscriptions": 0.0, "expenses": 0.0,
                 "recurring_income": 0.0, "recurring_expense": 0.0}
    )

    # 计算每月折旧
    for asset in assets:
        purchase = datetime.strptime(asset["purchase_date"], "%Y-%m-%d").date()
        lifespan = asset["lifespan_months"]
        end_of_life = purchase + relativedelta(months=lifespan)
        monthly_dep = calc_monthly_depreciation(asset)

        current = max(purchase.replace(day=1), start_date.replace(day=1))
        end = min(end_of_life, end_date)

        while current <= end:
            month_key = current.strftime("%Y-%m")
            # 判断当月资产是否完全在用
            month_start = current
            month_end = current + relativedelta(months=1) - timedelta(days=1)

            effective_start = max(purchase, month_start)
            effective_end = min(end_of_life, month_end)

            if effective_start < effective_end:
                if effective_start == month_start and effective_end == month_end:
                    monthly_data[month_key]["depreciation"] += round(monthly_dep, 2)
                else:
                    # 部分月份
                    days_active = (effective_end - effective_start).days + 1
                    days_in_month = (month_end - month_start).days + 1
                    monthly_data[month_key]["depreciation"] += round(
                        monthly_dep * days_active / days_in_month, 2
                    )

            current += relativedelta(months=1)

    # 订阅月成本
    for sub in subscriptions:
        monthly_cost = calc_monthly_subscription_cost(sub)
        sub_start = datetime.strptime(sub["start_date"], "%Y-%m-%d").date()

        current = max(sub_start.replace(day=1), start_date.replace(day=1))
        while current <= end_date:
            month_key = current.strftime("%Y-%m")
            monthly_data[month_key]["subscriptions"] += round(monthly_cost, 2)
            current += relativedelta(months=1)

    # 周期性收支
    for rec in recurrings:
        monthly_cost = _calc_monthly_recurring_cost(rec)
        rec_start = datetime.strptime(rec["start_date"], "%Y-%m-%d").date()
        field = "recurring_income" if rec["type"] == "income" else "recurring_expense"

        current = max(rec_start.replace(day=1), start_date.replace(day=1))
        while current <= end_date:
            month_key = current.strftime("%Y-%m")
            monthly_data[month_key][field] += round(monthly_cost, 2)
            current += relativedelta(months=1)

    # 一次性开支
    for exp in expenses:
        exp_date = datetime.strptime(exp["expense_date"], "%Y-%m-%d").date()
        if start_date <= exp_date <= end_date:
            month_key = exp_date.strftime("%Y-%m")
            monthly_data[month_key]["expenses"] += exp["amount"]

    # 整理输出
    result = []
    for month_key in sorted(monthly_data.keys()):
        d = monthly_data[month_key]
        total = d["depreciation"] + d["subscriptions"] + d["expenses"] + d["recurring_expense"]
        result.append({
            "month": month_key,
            "depreciation": round(d["depreciation"], 2),
            "subscriptions": round(d["subscriptions"], 2),
            "expenses": round(d["expenses"], 2),
            "recurring_expense": round(d["recurring_expense"], 2),
            "recurring_income": round(d["recurring_income"], 2),
            "total": round(total, 2),
        })

    return result


def generate_category_breakdown(expenses: list[dict]) -> dict[str, float]:
    """按类别汇总一次性开支。"""
    breakdown: dict[str, float] = defaultdict(float)
    for exp in expenses:
        breakdown[exp["category"]] += exp["amount"]
    return dict(breakdown)
