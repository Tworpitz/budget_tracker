using BudgetTracker.Core;
using BudgetTracker.Storage;
using Microsoft.UI;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Rectangle = Microsoft.UI.Xaml.Shapes.Rectangle;
using Microsoft.UI.Windowing;
using System.Globalization;
using System.Text.Json;

namespace BudgetTracker.Windows;

public sealed class MainWindow : Window
{
    private readonly LedgerStore store;
    private readonly Grid root = new();
    private readonly NavigationView navigation = new() { IsSettingsVisible = false, PaneDisplayMode = NavigationViewPaneDisplayMode.Left, OpenPaneLength = 220, IsBackButtonVisible = NavigationViewBackButtonVisible.Collapsed };
    private readonly InfoBar notice = new() { IsClosable = true };
    private readonly ContentControl body = new();
    private readonly TextBlock status = new() { FontSize = 12, Opacity = .65, TextWrapping = TextWrapping.Wrap };
    private readonly Dictionary<EntryKind, EntryEditor> editors = new();
    private readonly ReportView reports;

    public MainWindow(LedgerStore store)
    {
        this.store = store;
        Title = "BudgetTracker · WinUI 3";
        SystemBackdrop = new MicaBackdrop();
        AppWindow.Resize(new global::Windows.Graphics.SizeInt32(1360, 900));
        var area = DisplayArea.GetFromWindowId(AppWindow.Id, DisplayAreaFallback.Primary).WorkArea;
        AppWindow.Move(new global::Windows.Graphics.PointInt32(area.X + Math.Max(0, (area.Width - 1360) / 2), area.Y + Math.Max(0, (area.Height - 900) / 2)));
        root.Background = (Brush)Application.Current.Resources["ApplicationPageBackgroundThemeBrush"];
        root.Children.Add(navigation); Content = root;
        navigation.PaneHeader = new TextBlock { Text = "BUDGET TRACKER", FontSize = 14, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Margin = new Thickness(16, 20, 0, 20) };
        foreach (var (name, symbol) in new[] { ("固定资产", Symbol.AllApps), ("订阅服务", Symbol.RepeatAll), ("日常开支", Symbol.Shop), ("统计报告", Symbol.View) })
            navigation.MenuItems.Add(new NavigationViewItem { Content = name, Icon = new SymbolIcon(symbol) });
        var layout = new Grid { Padding = new Thickness(28, 12, 28, 16), RowSpacing = 12 };
        layout.RowDefinitions.Add(new() { Height = GridLength.Auto }); layout.RowDefinitions.Add(new()); layout.RowDefinitions.Add(new() { Height = GridLength.Auto });
        layout.Children.Add(notice); Grid.SetRow(body, 1); layout.Children.Add(body); Grid.SetRow(status, 2); layout.Children.Add(status);
        navigation.Content = layout;
        foreach (var kind in Enum.GetValues<EntryKind>()) editors[kind] = new EntryEditor(store, kind, ShowError, Changed);
        reports = new ReportView(store, ShowError);
        navigation.SelectionChanged += (_, _) => RefreshPage();
        navigation.SelectedItem = navigation.MenuItems[0];
        status.Text = "账本：" + store.Path;
    }
    private void ShowError(Exception error) { notice.Title = "操作未完成"; notice.Message = error.Message; notice.Severity = InfoBarSeverity.Error; notice.IsOpen = true; }
    private void Changed() { notice.Title = "已保存"; notice.Message = "账本已更新，统计报告会在打开时刷新。"; notice.Severity = InfoBarSeverity.Success; notice.IsOpen = true; }
    private void RefreshPage()
    {
        int index = navigation.MenuItems.IndexOf(navigation.SelectedItem);
        if (index < 0) return;
        notice.IsOpen = false;
        if (index == 3) { body.Content = reports; reports.Refresh(); }
        else { reports.CancelRefresh(); var editor = editors[(EntryKind)index]; body.Content = editor; editor.Refresh(); }
    }
    internal static TextBlock Text(string value, double size = 14) => new() { Text = value, FontSize = size, TextWrapping = TextWrapping.Wrap, VerticalAlignment = VerticalAlignment.Center };
    internal static Button Button(string label, Action action)
    {
        var button = new Button { Content = label }; button.Click += (_, _) => action(); return button;
    }
    internal static Border Card(UIElement child) => new() { Child = child, Style = (Style)Application.Current.Resources["BudgetCardStyle"] };
    internal static Grid Cells(IEnumerable<string> values, double[] widths, bool header = false)
    {
        var grid = new Grid { ColumnSpacing = 16, Padding = new Thickness(12, 9, 12, 9) };
        int i = 0;
        foreach (var value in values)
        {
            grid.ColumnDefinitions.Add(new() { Width = new GridLength(widths[i]) });
            var text = Text(value, header ? 12 : 14); if (header) { text.Opacity = .65; text.FontWeight = Microsoft.UI.Text.FontWeights.SemiBold; }
            Grid.SetColumn(text, i++); grid.Children.Add(text);
        }
        return grid;
    }
    public void StartSmokeTest(string output)
    {
        root.Loaded += async (_, _) =>
        {
            var checks = new List<string>();
            void Trace(string stage) => File.AppendAllText(output + ".trace.log", $"{DateTimeOffset.Now:O} {stage}\n");
            async Task Pump(string stage)
            {
                Trace(stage + " begin");
                await Task.Delay(100);
                root.UpdateLayout();
                await Task.Delay(100);
                Trace(stage + " complete");
            }
            try
            {
                await Task.Delay(250);
                // Earlier smoke tests closed before XAML processed report layout.
                navigation.SelectedItem = navigation.MenuItems[3];
                await reports.RefreshAsync();
                await Pump("empty report navigation");
                foreach (var kind in Enum.GetValues<EntryKind>())
                {
                    navigation.SelectedItem = navigation.MenuItems[(int)kind];
                    var editor = editors[kind];
                    editor.SetForm(new Entry { Kind = kind, Name = "界面验证", Date = "2024-01-01", Amount = kind == EntryKind.Asset ? 310 : 31, Months = 1 });
                    if (!editor.SaveForm()) throw new Exception("新增失败：" + kind);
                    var saved = store.Read(kind).Single();
                    editor.SetForm(saved with { Name = "已编辑", Amount = -1 });
                    if (editor.SaveForm() || store.Read(kind).Single().Name != "界面验证") throw new Exception("校验/失败保留失败");
                    editor.SetForm(saved with { Name = "已编辑", Notes = "中文备注" });
                    if (!editor.SaveForm() || store.Read(kind).Single().Notes != "中文备注") throw new Exception("编辑失败");
                    checks.Add(kind + ": add, validation, edit, notes, list refresh");
                }
                navigation.SelectedItem = navigation.MenuItems[3];
                reports.SetRange(new(2024, 1, 1), new(2024, 1, 31)); reports.SetWeekly(false); await reports.RefreshAsync();
                if (reports.Rows.Count != 1 || reports.Rows.Sum(r => r.Total) != 372 || reports.ChartColumns != 1) throw new Exception("月报/图表/合计失败");
                await Pump("monthly report layout");
                reports.SetWeekly(true); await reports.RefreshAsync();
                if (reports.Rows.Count != 5 || reports.Rows.Sum(r => r.Total) != 372 || reports.ChartColumns != 5) throw new Exception("周报失败");
                await Pump("weekly report layout");
                for (int i = 0; i < 10; i++)
                {
                    navigation.SelectedItem = navigation.MenuItems[i % 3];
                    await Pump("leave report " + i);
                    navigation.SelectedItem = navigation.MenuItems[3];
                    await reports.RefreshAsync();
                    await Pump("return to report " + i);
                }
                checks.Add("empty/populated report layout and ten round-trip navigations with a live dispatcher");
                checks.Add("weekly/monthly cards, table and stacked chart: 372.00");

                // Deterministic regression: a delayed database read must not block
                // dispatcher/layout or a newer navigation/filter request.
                var originalReader = reports.ReadEntries;
                using (var releaseRead = new ManualResetEventSlim())
                {
                    var readStarted = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
                    reports.ReadEntries = () =>
                    {
                        readStarted.TrySetResult(true);
                        if (!releaseRead.Wait(TimeSpan.FromSeconds(8))) throw new TimeoutException("测试读取未释放");
                        return originalReader();
                    };
                    var delayed = reports.RefreshAsync();
                    try
                    {
                        await readStarted.Task.WaitAsync(TimeSpan.FromSeconds(3));
                        await Pump("dispatcher remains responsive while database read waits");
                        navigation.SelectedItem = navigation.MenuItems[0];
                        await Pump("navigate away while database read waits");
                        reports.ReadEntries = originalReader;
                        reports.SetRange(new(2024, 2, 1), new(2024, 2, 29));
                        reports.SetWeekly(false);
                        navigation.SelectedItem = navigation.MenuItems[3];
                        var newest = reports.RefreshAsync();
                        releaseRead.Set();
                        await Task.WhenAll(delayed, newest);
                        if (reports.Rows.Count != 1 || reports.Rows[0].Total != 31) throw new Exception("过期请求覆盖了最新日期的报告");
                    }
                    finally { releaseRead.Set(); reports.ReadEntries = originalReader; }
                }
                checks.Add("slow read leaves dispatcher/navigation responsive; canceled/stale results cannot overwrite latest report");
                reports.ReadEntries = () => throw new IOException("模拟数据库读取失败");
                await reports.RefreshAsync();
                if (reports.Rows.Count != 0) throw new Exception("读取失败保留了过期数据");
                reports.ReadEntries = originalReader;
                reports.SetRange(new(2000, 1, 1), new(2040, 12, 31)); reports.SetWeekly(true);
                await reports.RefreshAsync();
                if (reports.Rows.Count <= 60 || reports.ChartColumns != 60) throw new Exception("大范围报告没有限制一次渲染数量");
                reports.RenderPage((reports.Rows.Count - 1) / 60);
                if (reports.ChartColumns != (reports.Rows.Count - 1) % 60 + 1) throw new Exception("最后一页周期丢失");
                await Pump("long-range report layout after read failure recovery");
                checks.Add("read failure recovery; 41-year weekly report renders at most 60 periods per page, including last page");
                reports.SetRange(new(2024, 2, 1), new(2024, 1, 1)); await reports.RefreshAsync();
                if (reports.Rows.Count != 0) throw new Exception("反向日期未清空报表");
                checks.Add("invalid date range clears stale reports");
                foreach (var kind in Enum.GetValues<EntryKind>()) { editors[kind].DeleteConfirmed(store.Read(kind).Single()); if (store.Read(kind).Count != 0) throw new Exception("删除失败"); }
                checks.Add("delete all three record kinds");
                reports.SetRange(new(2024, 1, 1), new(2024, 1, 31)); await reports.RefreshAsync();
                if (reports.Rows.Sum(r => r.Total) != 0) throw new Exception("空账本失败");
                checks.Add("empty ledger and report refresh after delete");
                File.WriteAllText(output, JsonSerializer.Serialize(new { success = true, checks }, new JsonSerializerOptions { WriteIndented = true }));
            }
            catch (Exception ex) { File.WriteAllText(output, JsonSerializer.Serialize(new { success = false, error = ex.ToString(), checks })); }
            finally { Directory.Delete(Path.GetDirectoryName(store.Path)!, true); Close(); }
        };
    }
}

internal sealed class EntryEditor : Grid
{
    private readonly LedgerStore store;
    private readonly EntryKind kind;
    private readonly Action<Exception> error;
    private readonly Action changed;
    private readonly TextBox name = new() { Header = "名称" }, date = new() { Header = "日期 · YYYY-MM-DD" }, amount = new() { Header = "金额（元）" }, months = new() { Header = "使用月数" }, salvage = new() { Header = "残值（元）" }, notes = new() { Header = "备注", AcceptsReturn = true, MinHeight = 70, TextWrapping = TextWrapping.Wrap };
    private readonly ComboBox category = new() { Header = "类别", IsEditable = true, HorizontalAlignment = HorizontalAlignment.Stretch }, cycle = new() { Header = "计费周期", HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly ListView list = new() { SelectionMode = ListViewSelectionMode.Single, MinHeight = 180 };
    private readonly TextBlock count = MainWindow.Text("");
    private readonly TextBlock mode = MainWindow.Text("新增记录", 20);
    private long editing;
    private readonly double[] widths;
    public EntryEditor(LedgerStore store, EntryKind kind, Action<Exception> error, Action changed)
    {
        this.store = store; this.kind = kind; this.error = error; this.changed = changed;
        ColumnSpacing = 20; ColumnDefinitions.Add(new()); ColumnDefinitions.Add(new() { Width = new GridLength(290) });
        var left = new Grid { RowSpacing = 12 }; left.RowDefinitions.Add(new() { Height = GridLength.Auto }); left.RowDefinitions.Add(new() { Height = GridLength.Auto }); left.RowDefinitions.Add(new());
        string title = kind switch { EntryKind.Asset => "固定资产", EntryKind.Subscription => "订阅服务", _ => "日常开支" };
        left.Children.Add(MainWindow.Text(title, 28));
        var toolbar = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 10 };
        toolbar.Children.Add(MainWindow.Button("刷新", Refresh)); toolbar.Children.Add(MainWindow.Button("编辑选中", EditSelected));
        toolbar.Children.Add(MainWindow.Button("删除选中", () => _ = ConfirmDelete())); toolbar.Children.Add(count); Grid.SetRow(toolbar, 1); left.Children.Add(toolbar);
        string[] headers = kind switch
        {
            EntryKind.Asset => ["名称 / 类别", "购买日期", "预期报废", "月数", "购买价", "残值", "月折旧", "累计折旧", "当前净值", "备注"],
            EntryKind.Subscription => ["服务名称", "开始日期", "周期", "金额", "月均成本", "下次扣费", "备注"],
            _ => ["名称", "类别", "日期", "金额", "备注"]
        };
        widths = kind switch { EntryKind.Asset => [140, 94, 94, 42, 85, 70, 85, 85, 85, 160], EntryKind.Subscription => [150, 100, 60, 90, 90, 110, 160], _ => [150, 90, 100, 100, 200] };
        var table = new Grid(); table.RowDefinitions.Add(new() { Height = GridLength.Auto }); table.RowDefinitions.Add(new());
        table.Children.Add(MainWindow.Cells(headers, widths, true)); Grid.SetRow(list, 1); table.Children.Add(list);
        var scroll = new ScrollViewer { Content = table, HorizontalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollMode = ScrollMode.Enabled, VerticalScrollBarVisibility = ScrollBarVisibility.Disabled, VerticalScrollMode = ScrollMode.Disabled };
        Grid.SetRow(scroll, 2); left.Children.Add(scroll); Children.Add(left);
        list.DoubleTapped += (_, _) => EditSelected();
        var form = new StackPanel { Spacing = 12 }; form.Children.Add(mode); form.Children.Add(name);
        foreach (var label in kind == EntryKind.Asset ? new[] { "电子设备", "家电", "家具", "交通工具", "服装", "书籍", "其他" } : new[] { "餐饮", "礼物", "旅行", "医疗", "教育", "娱乐", "交通", "日用", "服饰", "住房", "其他" }) category.Items.Add(label);
        if (kind != EntryKind.Subscription) form.Children.Add(category);
        form.Children.Add(date);
        if (kind == EntryKind.Asset) form.Children.Add(months);
        if (kind == EntryKind.Subscription) { foreach (var label in new[] { "月付", "季付", "年付" }) cycle.Items.Add(label); form.Children.Add(cycle); }
        form.Children.Add(amount); if (kind == EntryKind.Asset) form.Children.Add(salvage); form.Children.Add(notes);
        var save = MainWindow.Button("保存", () => SaveForm()); save.Style = (Style)Application.Current.Resources["BudgetSaveButtonStyle"]; save.HorizontalAlignment = HorizontalAlignment.Stretch;
        form.Children.Add(save); form.Children.Add(MainWindow.Button("清空 / 新增", Clear));
        var formScroll = new ScrollViewer { Content = MainWindow.Card(form), VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        Grid.SetColumn(formScroll, 1); Children.Add(formScroll); Clear();
    }
    private static string Money(decimal value) => value.ToString("N2", CultureInfo.CurrentCulture);
    public void Refresh()
    {
        try
        {
            var rows = store.Read(kind); list.Items.Clear(); count.Text = $"{rows.Count} 条记录";
            foreach (var entry in rows)
            {
                string[] values; string? failure = null; var today = DateOnly.FromDateTime(DateTime.Today);
                try
                {
                    entry.Validate();
                    values = kind switch
                    {
                        EntryKind.Asset => [entry.Name + "\n" + entry.Category, entry.Date, entry.Day.AddMonths(entry.Months).ToString("yyyy-MM-dd"), entry.Months.ToString(), Money(entry.Amount), Money(entry.Salvage), Money(Calculations.MonthlyDepreciation(entry)), Money(Calculations.Accumulated(entry, today)), Money(Calculations.CurrentValue(entry, today)), entry.Notes],
                        EntryKind.Subscription => [entry.Name, entry.Date, new[] { "月付", "季付", "年付" }[entry.Cycle == "monthly" ? 0 : entry.Cycle == "quarterly" ? 1 : 2], Money(entry.Amount), Money(Calculations.MonthlySubscription(entry)), Calculations.NextBilling(entry, today).ToString("yyyy-MM-dd"), entry.Notes],
                        _ => [entry.Name, entry.Category, entry.Date, Money(entry.Amount), entry.Notes]
                    };
                }
                catch (Exception ex) { failure = ex.Message; values = Enumerable.Repeat("数据有误", widths.Length).ToArray(); values[0] = entry.Name; values[^1] = entry.Notes; }
                var cells = MainWindow.Cells(values, widths);
                if (failure != null) { foreach (TextBlock text in cells.Children) text.Foreground = new SolidColorBrush(Colors.Firebrick); ToolTipService.SetToolTip(cells, failure); }
                else if (kind == EntryKind.Asset)
                {
                    if (entry.Day.AddMonths(entry.Months) < today) ((TextBlock)cells.Children[2]).Foreground = new SolidColorBrush(Colors.Firebrick);
                    if (Calculations.CurrentValue(entry, today) <= entry.Salvage) cells.Children[8].Opacity = .5;
                }
                else if (kind == EntryKind.Subscription && Calculations.NextBilling(entry, today) <= today.AddDays(7)) ((TextBlock)cells.Children[5]).Foreground = new SolidColorBrush(Colors.DarkOrange);
                list.Items.Add(new ListViewItem { Content = cells, Tag = entry, HorizontalContentAlignment = HorizontalAlignment.Stretch, Padding = new Thickness(0) });
            }
        }
        catch (Exception ex) { error(ex); }
    }
    public void SetForm(Entry entry)
    {
        editing = entry.Id; mode.Text = editing == 0 ? "新增记录" : "编辑记录";
        name.Text = entry.Name;
        category.SelectedItem = category.Items.Contains(entry.Category) ? entry.Category : null;
        category.Text = entry.Category;
        date.Text = entry.Date; amount.Text = entry.Amount.ToString(CultureInfo.InvariantCulture);
        months.Text = entry.Months.ToString(); salvage.Text = entry.Salvage.ToString(CultureInfo.InvariantCulture); notes.Text = entry.Notes;
        cycle.SelectedIndex = entry.Cycle switch { "monthly" => 0, "quarterly" => 1, "yearly" => 2, _ => -1 };
    }
    private void Clear() { list.SelectedItem = null; SetForm(new Entry { Kind = kind, Category = kind == EntryKind.Asset ? "电子设备" : "其他" }); }
    private void EditSelected()
    {
        if (list.SelectedItem is ListViewItem { Tag: Entry entry }) SetForm(entry);
        else error(new ArgumentException("请先选择要编辑的记录。"));
    }
    public bool SaveForm()
    {
        try
        {
            var entry = new Entry { Id = editing, Kind = kind, Name = name.Text.Trim(), Category = category.Text.Trim(), Date = date.Text.Trim(),
                Amount = decimal.Parse(amount.Text, NumberStyles.AllowDecimalPoint | NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture),
                Months = kind == EntryKind.Asset ? int.Parse(months.Text) : 36,
                Salvage = kind == EntryKind.Asset ? decimal.Parse(salvage.Text, NumberStyles.AllowDecimalPoint | NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture) : 0,
                Cycle = cycle.SelectedIndex switch { 0 => "monthly", 1 => "quarterly", 2 => "yearly", _ => "" }, Notes = notes.Text };
            store.Save(entry); Refresh(); Clear(); changed(); return true;
        }
        catch (Exception ex) { error(ex is FormatException or OverflowException ? new ArgumentException("请输入有效金额和整数月数；金额的小数点使用 .。") : ex); return false; }
    }
    private async Task ConfirmDelete()
    {
        if (list.SelectedItem is not ListViewItem { Tag: Entry entry }) { error(new ArgumentException("请先选择要删除的记录。")); return; }
        var dialog = new ContentDialog { XamlRoot = XamlRoot, Title = "删除记录？", Content = $"将删除「{entry.Name}」。此操作无法撤销。", PrimaryButtonText = "删除", CloseButtonText = "取消", DefaultButton = ContentDialogButton.Close };
        try { if (await dialog.ShowAsync() == ContentDialogResult.Primary) DeleteConfirmed(entry); } catch (Exception ex) { error(ex); }
    }
    public void DeleteConfirmed(Entry entry) { store.Delete(kind, entry.Id); Refresh(); Clear(); changed(); }
}

internal sealed class ReportView : UserControl
{
    private readonly Action<Exception> error;
    internal Func<List<Entry>> ReadEntries { get; set; }
    private readonly SemaphoreSlim readGate = new(1, 1);
    private CancellationTokenSource? refreshCancellation;
    private long requestVersion;
    private int page;
    private const int PageSize = 60;
    private readonly CalendarDatePicker start = new() { Header = "开始日期" }, end = new() { Header = "结束日期" };
    private readonly ComboBox mode = new() { Header = "分组", Width = 120 };
    private readonly StackPanel cards = new() { Orientation = Orientation.Horizontal, Spacing = 12 }, table = new() { Spacing = 2 }, chart = new() { Orientation = Orientation.Horizontal, Spacing = 12 };
    private readonly TextBlock range = MainWindow.Text("");
    private readonly TextBlock pageLabel = MainWindow.Text("");
    private readonly ProgressRing busy = new() { Width = 20, Height = 20, IsActive = false, Visibility = Visibility.Collapsed };
    private readonly Button previous, next;
    public List<ReportRow> Rows { get; private set; } = [];
    public int ChartColumns => chart.Children.Count;
    public ReportView(LedgerStore store, Action<Exception> error)
    {
        ReadEntries = store.ReadAll; this.error = error;
        var content = new StackPanel { Spacing = 20 };
        Content = new ScrollViewer { Content = content, HorizontalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollMode = ScrollMode.Enabled };
        content.Children.Add(MainWindow.Text("统计报告", 28));
        content.Children.Add(MainWindow.Text("资产折旧 + 订阅分摊 + 日常开支。展示分摊成本，不等同于实际扣款流水。"));
        var filters = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 10, VerticalAlignment = VerticalAlignment.Bottom };
        mode.Items.Add("按月统计"); mode.Items.Add("按周统计"); mode.SelectedIndex = 0;
        filters.Children.Add(start); filters.Children.Add(end); filters.Children.Add(mode);
        foreach (var (label, offset) in new[] { ("本月", 0), ("上月", -1), ("今年", 12) }) filters.Children.Add(MainWindow.Button(label, () => Shortcut(offset)));
        filters.Children.Add(MainWindow.Button("生成报告", Refresh)); filters.Children.Add(busy);
        content.Children.Add(filters); content.Children.Add(range); content.Children.Add(cards);
        var paging = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 10 };
        previous = MainWindow.Button("上一页", () => { page--; RenderPage(); });
        next = MainWindow.Button("下一页", () => { page++; RenderPage(); });
        previous.IsEnabled = next.IsEnabled = false;
        paging.Children.Add(previous); paging.Children.Add(next); paging.Children.Add(pageLabel); content.Children.Add(paging);
        var graph = new StackPanel { Spacing = 12 }; graph.Children.Add(MainWindow.Text("支出构成", 20));
        graph.Children.Add(MainWindow.Text("蓝：资产折旧    紫：订阅成本    橙：日常开支"));
        graph.Children.Add(new ScrollViewer { Content = chart, HorizontalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollMode = ScrollMode.Enabled, VerticalScrollMode = ScrollMode.Disabled, VerticalScrollBarVisibility = ScrollBarVisibility.Disabled });
        content.Children.Add(MainWindow.Card(graph)); content.Children.Add(table);
        Shortcut(0, false); mode.SelectionChanged += (_, _) => Refresh();
    }
    public void SetWeekly(bool weekly) => mode.SelectedIndex = weekly ? 1 : 0;
    public void SetRange(DateOnly a, DateOnly b) { start.Date = new DateTimeOffset(a.ToDateTime(TimeOnly.MinValue)); end.Date = new DateTimeOffset(b.ToDateTime(TimeOnly.MinValue)); }
    private void Shortcut(int offset, bool refresh = true)
    {
        var today = DateOnly.FromDateTime(DateTime.Today);
        var first = offset == 12 ? new DateOnly(today.Year, 1, 1) : new DateOnly(today.Year, today.Month, 1).AddMonths(offset);
        SetRange(first, offset == 12 ? new DateOnly(today.Year, 12, 31) : first.AddMonths(1).AddDays(-1));
        if (refresh) Refresh();
    }
    public void Refresh() => _ = RefreshAsync();
    public void CancelRefresh()
    {
        requestVersion++;
        refreshCancellation?.Cancel();
        busy.IsActive = false; busy.Visibility = Visibility.Collapsed;
    }
    public async Task RefreshAsync()
    {
        refreshCancellation?.Cancel();
        using var cancellation = new CancellationTokenSource();
        refreshCancellation = cancellation;
        long version = ++requestVersion;
        var token = cancellation.Token;
        Rows = []; cards.Children.Clear(); table.Children.Clear(); chart.Children.Clear(); range.Text = "";
        pageLabel.Text = ""; previous.IsEnabled = next.IsEnabled = false;
        busy.IsActive = true; busy.Visibility = Visibility.Visible;
        try
        {
            if (start.Date == null || end.Date == null) throw new ArgumentException("请选择开始和结束日期。");
            var a = DateOnly.FromDateTime(start.Date.Value.Date);
            var b = DateOnly.FromDateTime(end.Date.Value.Date);
            Calculations.Range(a, b);
            bool weekly = mode.SelectedIndex == 1;
            var readEntries = ReadEntries;
            range.Text = "正在读取账本并生成报告…可以继续切换页面。";
            List<ReportRow> loaded;
            await readGate.WaitAsync(token);
            try
            {
                // SQLite can wait for another writer; neither that wait nor the
                // calculation should ever run on the XAML dispatcher thread.
                loaded = await Task.Run(() =>
                {
                    var entries = readEntries();
                    token.ThrowIfCancellationRequested();
                    return Calculations.Report(entries, a, b, weekly, token);
                }, token);
            }
            finally { readGate.Release(); }
            if (token.IsCancellationRequested || version != requestVersion) return;
            Rows = loaded;
            range.Text = $"{a:yyyy-MM-dd} — {b:yyyy-MM-dd} · 共 {Rows.Count} 个周期";
            foreach (var (label, value) in new[] { ("资产折旧", Rows.Sum(r => r.Depreciation)), ("订阅成本", Rows.Sum(r => r.Subscriptions)), ("日常开支", Rows.Sum(r => r.Expenses)), ("合计", Rows.Sum(r => r.Total)) })
            {
                var panel = new StackPanel { Spacing = 8, MinWidth = 145 }; panel.Children.Add(MainWindow.Text(label, 12)); panel.Children.Add(MainWindow.Text($"¥ {value:N2}", 24)); cards.Children.Add(MainWindow.Card(panel));
            }
            page = 0; RenderPage();
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            if (version == requestVersion) { Rows = []; range.Text = "数据有误，请检查记录和日期范围。"; error(ex); }
        }
        finally
        {
            if (ReferenceEquals(refreshCancellation, cancellation)) refreshCancellation = null;
            if (version == requestVersion) { busy.IsActive = false; busy.Visibility = Visibility.Collapsed; }
        }
    }
    internal void RenderPage(int index) { page = index; RenderPage(); }
    private void RenderPage()
    {
            table.Children.Clear(); chart.Children.Clear();
            page = Math.Clamp(page, 0, Math.Max(0, (Rows.Count - 1) / PageSize));
            previous.IsEnabled = page > 0;
            next.IsEnabled = (page + 1) * PageSize < Rows.Count;
            pageLabel.Text = Rows.Count == 0 ? "" : $"显示第 {page * PageSize + 1}–{Math.Min((page + 1) * PageSize, Rows.Count)} 个周期，共 {Rows.Count} 个；上方合计包含全部周期。";
            if (Rows.Count == 0) return;
            double[] widths = [100, 200, 110, 110, 110, 110];
            table.Children.Add(MainWindow.Cells(["周期", "日期范围", "折旧", "订阅", "开支", "合计"], widths, true));
            decimal maximum = Math.Max(1, Rows.Max(r => r.Total));
            foreach (var row in Rows.Skip(page * PageSize).Take(PageSize))
            {
                table.Children.Add(MainWindow.Cells([row.Key, row.Start + " — " + row.End, row.Depreciation.ToString("N2"), row.Subscriptions.ToString("N2"), row.Expenses.ToString("N2"), row.Total.ToString("N2")], widths));
                var column = new StackPanel { Width = 86, Spacing = 6 };
                var plot = new Grid { Height = 210 }; var bars = new StackPanel { VerticalAlignment = VerticalAlignment.Bottom };
                foreach (var (amount, color) in new[] { (row.Expenses, Colors.DarkOrange), (row.Subscriptions, Colors.MediumPurple), (row.Depreciation, Colors.SteelBlue) }) bars.Children.Add(new Rectangle { Height = (double)(amount / maximum * 185), Fill = new SolidColorBrush(color), Margin = new Thickness(16, 0, 16, 0) });
                plot.Children.Add(bars); ToolTipService.SetToolTip(plot, $"{row.Key}\n折旧 {row.Depreciation:N2}\n订阅 {row.Subscriptions:N2}\n开支 {row.Expenses:N2}");
                column.Children.Add(MainWindow.Text($"¥ {row.Total:N2}", 12)); column.Children.Add(plot); column.Children.Add(MainWindow.Text(row.Key, 12)); chart.Children.Add(column);
            }
    }
}
