using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using BudgetTracker.Storage;

namespace BudgetTracker.Windows;

public partial class App : Application
{
    private Window? window;
    public App() { InitializeComponent(); }
    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        var arguments = Environment.GetCommandLineArgs();
        int smokeIndex = Array.IndexOf(arguments, "--smoke-test");
        string? output = smokeIndex >= 0 && smokeIndex + 1 < arguments.Length ? arguments[smokeIndex + 1] : null;
        try
        {
            string path = output == null ? LedgerStore.DefaultPath : Path.Combine(Path.GetTempPath(), "BudgetTracker-WinUI-" + Guid.NewGuid().ToString("N"), "budget.db");
            if (output == null)
            {
                LedgerStore.Prepare(path, LedgerStore.LegacyPaths());
                // Snapshot the shared database before this client ever changes its schema.
                if (File.Exists(path)) LedgerStore.Backup(path, Path.Combine(Path.GetDirectoryName(path)!, "backups", $"before-winui-{DateTime.Now:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}.db"));
            }
            var store = new LedgerStore(path); store.Initialize();
            var main = new MainWindow(store); window = main;
            if (output != null)
            {
                main.StartSmokeTest(output);
                // Exercise the real XAML dispatcher/layout without stealing focus.
                main.AppWindow.Move(new global::Windows.Graphics.PointInt32(-32000, -32000));
                main.AppWindow.Show(false);
            }
            else main.Activate();
        }
        catch (Exception ex)
        {
            if (output != null) { File.WriteAllText(output, ex.ToString()); Exit(); return; }
            window = new Window { Title = "BudgetTracker · 无法打开账本", Content = new TextBox { Text = "初始化失败，未进入编辑界面。\n\n" + ex.Message, IsReadOnly = true, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(32) } };
            window.Activate();
        }
    }
}
