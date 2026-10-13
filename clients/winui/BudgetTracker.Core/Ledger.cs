using System.Globalization;

namespace BudgetTracker.Core;

public enum EntryKind { Asset, Subscription, Expense }

public sealed record Entry
{
    public long Id { get; init; }
    public EntryKind Kind { get; init; }
    public string Name { get; init; } = "";
    public string Category { get; init; } = "其他";
    public string Date { get; init; } = DateOnly.FromDateTime(DateTime.Today).ToString("yyyy-MM-dd");
    public int Months { get; init; } = 36;
    public decimal Amount { get; init; }
    public decimal Salvage { get; init; }
    public string Cycle { get; init; } = "monthly";
    public string Notes { get; init; } = "";
    public DateOnly Day => DateOnly.ParseExact(Date, "yyyy-MM-dd", CultureInfo.InvariantCulture);

    public void Validate()
    {
        if (!Enum.IsDefined(Kind)) throw new ArgumentException("无效的记录类型。");
        if (string.IsNullOrWhiteSpace(Name)) throw new ArgumentException("名称不能为空。");
        if (Kind != EntryKind.Subscription && string.IsNullOrWhiteSpace(Category))
            throw new ArgumentException("类别不能为空。");
        if (!DateOnly.TryParseExact(Date, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out _))
            throw new ArgumentException("请输入有效的 YYYY-MM-DD 日期。");
        Money(Amount, false);
        if (Kind == EntryKind.Asset)
        {
            if (Months is < 1 or > 600) throw new ArgumentException("使用月数必须为 1–600 的整数。");
            Money(Salvage, true);
            if (Salvage > Amount) throw new ArgumentException("残值不能高于购买价格。");
        }
        if (Kind == EntryKind.Subscription && Cycle is not ("monthly" or "quarterly" or "yearly"))
            throw new ArgumentException("请选择月付、季付或年付。");
    }

    private static void Money(decimal amount, bool zero)
    {
        if (amount < 0 || (!zero && amount == 0) || amount > 9999999 || decimal.Round(amount, 2) != amount)
            throw new ArgumentException("金额须大于 0（残值可为 0），最多两位小数且不超过 9999999。");
    }
}

public sealed record ReportRow(string Key, string Start, string End, decimal Depreciation,
    decimal Subscriptions, decimal Expenses)
{
    public decimal Total => Depreciation + Subscriptions + Expenses;
}

public static class Calculations
{
    public static decimal Cents(decimal amount) => decimal.Round(amount, 2, MidpointRounding.AwayFromZero);
    public static decimal MonthlyDepreciation(Entry asset)
    {
        asset.Validate();
        return (asset.Amount - asset.Salvage) / asset.Months;
    }
    private static decimal Before(Entry a, DateOnly boundary)
    {
        var purchase = a.Day;
        if (boundary <= purchase) return 0;
        // Comparing month indices avoids overflowing DateOnly for valid late-year records.
        int months = (boundary.Year - purchase.Year) * 12 + boundary.Month - purchase.Month;
        if (months > a.Months || (months == a.Months && boundary.Day >= Math.Min(purchase.Day, DateTime.DaysInMonth(boundary.Year, boundary.Month))))
            return a.Amount - a.Salvage;
        if (purchase.AddMonths(months) > boundary) months--;
        var start = purchase.AddMonths(months);
        var end = purchase.AddMonths(months + 1);
        return Cents((a.Amount - a.Salvage) / a.Months * (months + (decimal)(boundary.DayNumber - start.DayNumber) / (end.DayNumber - start.DayNumber)));
    }
    public static decimal Accumulated(Entry a, DateOnly today)
    {
        a.Validate();
        return Before(a, today.AddDays(1));
    }
    public static decimal CurrentValue(Entry a, DateOnly today) => a.Amount - Accumulated(a, today);
    public static decimal Depreciation(Entry a, DateOnly start, DateOnly end)
    {
        a.Validate(); Range(start, end);
        return Before(a, end.AddDays(1)) - Before(a, start);
    }
    public static int Interval(Entry s) => s.Cycle switch { "monthly" => 1, "quarterly" => 3, "yearly" => 12, _ => throw new ArgumentException("无效计费周期。") };
    public static decimal MonthlySubscription(Entry s) { s.Validate(); return s.Amount / Interval(s); }
    public static DateOnly NextBilling(Entry s, DateOnly today)
    {
        s.Validate();
        var interval = Interval(s);
        int elapsed = (today.Year - s.Day.Year) * 12 + today.Month - s.Day.Month;
        int cycle = Math.Max(elapsed / interval, 0);
        var next = s.Day.AddMonths(cycle * interval);
        while (next <= today) next = s.Day.AddMonths(++cycle * interval);
        return next;
    }
    private static decimal SubscriptionPeriod(Entry s, DateOnly start, DateOnly end)
    {
        var current = start > s.Day ? start : s.Day;
        decimal total = 0, monthly = s.Amount / Interval(s);
        while (current < end)
        {
            var month = new DateOnly(current.Year, current.Month, 1);
            var next = month.AddMonths(1);
            var stop = next < end ? next : end;
            int days = next.DayNumber - month.DayNumber;
            total += Cents(monthly * (stop.DayNumber - month.DayNumber) / days) - Cents(monthly * (current.DayNumber - month.DayNumber) / days);
            current = stop;
        }
        return total;
    }
    public static void Range(DateOnly start, DateOnly end)
    {
        if (start > end) throw new ArgumentException("起始日期不能晚于结束日期。");
        if (end == DateOnly.MaxValue) throw new ArgumentException("结束日期超出支持范围。");
    }
    public static List<ReportRow> Report(IEnumerable<Entry> source, DateOnly start, DateOnly end, bool weekly, CancellationToken cancellationToken = default)
    {
        Range(start, end);
        var entries = source.ToArray();
        foreach (var entry in entries) { cancellationToken.ThrowIfCancellationRequested(); entry.Validate(); }
        var result = new List<ReportRow>();
        var boundary = end.AddDays(1);
        for (var current = start; current < boundary;)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var date = current.ToDateTime(TimeOnly.MinValue);
            var key = weekly ? $"{ISOWeek.GetYear(date)}-W{ISOWeek.GetWeekOfYear(date):00}" : current.ToString("yyyy-MM");
            int length = weekly ? 7 - ((int)current.DayOfWeek + 6) % 7 : DateTime.DaysInMonth(current.Year, current.Month) - current.Day + 1;
            var stop = current.AddDays(Math.Min(length, boundary.DayNumber - current.DayNumber));
            decimal dep = 0, sub = 0, exp = 0;
            foreach (var entry in entries)
            {
                cancellationToken.ThrowIfCancellationRequested();
                switch (entry.Kind)
                {
                    case EntryKind.Asset: dep += Before(entry, stop) - Before(entry, current); break;
                    case EntryKind.Subscription: sub += SubscriptionPeriod(entry, current, stop); break;
                    case EntryKind.Expense: if (entry.Day >= current && entry.Day < stop) exp += entry.Amount; break;
                }
            }
            result.Add(new(key, current.ToString("yyyy-MM-dd"), stop.AddDays(-1).ToString("yyyy-MM-dd"), dep, sub, exp));
            current = stop;
        }
        return result;
    }
}
