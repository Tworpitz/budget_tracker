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
    仅计算资产在使用期内的月份。
    """
    purchase = datetime.strptime(asset["purchase_date"], "%Y-%m-%d").date()
    lifespan = asset["lifespan_months"]
    end_of_life = purchase + relativedelta(months=lifespan)
    monthly = calc_monthly_depreciation(asset)

    # 确定资产在 period 内的有效区间
    effective_start = max(purchase, period_start)
    effective_end = min(end_of_life, period_end)

    if effective_start >= effective_end:
        return 0.0

    # 计算有效月数
    delta = relativedelta(effective_end, effective_start)
    months = delta.years * 12 + delta.months

    # 处理首尾月份的部分折旧（简化：不足一月按比例）
    # 首月部分
    if effective_start > purchase and effective_start.day > 1:
        days_in_month = (
            effective_start.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
        ).day
        first_month_fraction = 1.0 - (effective_start.day - 1) / days_in_month
        months = months - 1 + first_month_fraction
    elif effective_start == purchase and purchase.day > 1:
        days_in_month = (purchase.replace(day=1) + relativedelta(months=1) - timedelta(days=1)).day
        first_month_fraction = 1.0 - (purchase.day - 1) / days_in_month
        months = months - 1 + first_month_fraction

    # 末月部分
    if effective_end < end_of_life and effective_end.day < (
        effective_end.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
    ).day:
        days_in_last_month = (
            effective_end.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
        ).day
        last_month_fraction = effective_end.day / days_in_last_month
        months = months - 1 + last_month_fraction

    return round(monthly * max(months, 0), 2)


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


def generate_weekly_stats(assets: list[dict], subscriptions: list[dict],
                          expenses: list[dict], start_date: date,
                          end_date: date) -> list[dict]:
    """生成按周汇总的统计数据。"""
    # 将 expenses 按周分组
    weekly_data: dict[str, dict] = defaultdict(
        lambda: {"depreciation": 0.0, "subscriptions": 0.0, "expenses": 0.0}
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
        total = d["depreciation"] + d["subscriptions"] + d["expenses"]
        result.append({
            "week": week_key,
            "start": d.get("_start", ""),
            "end": d.get("_end", ""),
            "depreciation": round(d["depreciation"], 2),
            "subscriptions": round(d["subscriptions"], 2),
            "expenses": round(d["expenses"], 2),
            "total": round(total, 2),
        })

    return result


def generate_monthly_stats(assets: list[dict], subscriptions: list[dict],
                           expenses: list[dict], start_date: date,
                           end_date: date) -> list[dict]:
    """生成按月汇总的统计数据。"""
    monthly_data: dict[str, dict] = defaultdict(
        lambda: {"depreciation": 0.0, "subscriptions": 0.0, "expenses": 0.0}
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
        total = d["depreciation"] + d["subscriptions"] + d["expenses"]
        result.append({
            "month": month_key,
            "depreciation": round(d["depreciation"], 2),
            "subscriptions": round(d["subscriptions"], 2),
            "expenses": round(d["expenses"], 2),
            "total": round(total, 2),
        })

    return result


def generate_category_breakdown(expenses: list[dict]) -> dict[str, float]:
    """按类别汇总一次性开支。"""
    breakdown: dict[str, float] = defaultdict(float)
    for exp in expenses:
        breakdown[exp["category"]] += exp["amount"]
    return dict(breakdown)
