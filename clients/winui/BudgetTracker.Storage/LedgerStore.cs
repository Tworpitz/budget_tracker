using BudgetTracker.Core;
using Microsoft.Data.Sqlite;
using System.Globalization;

namespace BudgetTracker.Storage;

public sealed class LedgerStore(string path)
{
    public string Path { get; } = System.IO.Path.GetFullPath(path);
    public static string DefaultPath => System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BudgetTracker", "budget.db");
    public static string Table(EntryKind kind) => kind switch
    {
        EntryKind.Asset => "assets", EntryKind.Subscription => "subscriptions", EntryKind.Expense => "one_time_expenses", _ => throw new ArgumentException("无效记录类型")
    };
    public SqliteConnection Open()
    {
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(Path)!);
        var conn = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = Path, Pooling = false, DefaultTimeout = 10 }.ToString());
        try { conn.Open(); using var cmd = conn.CreateCommand(); cmd.CommandText = "PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;"; cmd.ExecuteNonQuery(); return conn; }
        catch { conn.Dispose(); throw; }
    }
    public void Initialize()
    {
        using var conn = Open();
        using var tx = conn.BeginTransaction();
        using var stream = typeof(LedgerStore).Assembly.GetManifestResourceStream("BudgetTracker.Storage.schema.sql")!;
        using var reader = new StreamReader(stream);
        using var cmd = conn.CreateCommand(); cmd.Transaction = tx; cmd.CommandText = reader.ReadToEnd(); cmd.ExecuteNonQuery(); tx.Commit();
    }
    public List<Entry> Read(EntryKind kind)
    {
        using var conn = Open(); using var cmd = conn.CreateCommand();
        string day = kind switch { EntryKind.Asset => "purchase_date", EntryKind.Subscription => "start_date", _ => "expense_date" };
        cmd.CommandText = $"SELECT * FROM {Table(kind)} ORDER BY {day} DESC, id DESC";
        using var r = cmd.ExecuteReader(); var rows = new List<Entry>();
        string Text(string key) => r.GetString(r.GetOrdinal(key));
        decimal Money(string key) => Convert.ToDecimal(r.GetDouble(r.GetOrdinal(key)), CultureInfo.InvariantCulture);
        while (r.Read()) rows.Add(new Entry
        {
            Id = r.GetInt64(r.GetOrdinal("id")), Kind = kind,
            Name = Text(kind == EntryKind.Subscription ? "service_name" : "name"), Date = Text(day),
            Category = kind == EntryKind.Subscription ? "" : Text("category"), Notes = Text("notes"),
            Amount = Money(kind == EntryKind.Asset ? "purchase_price" : "amount"),
            Salvage = kind == EntryKind.Asset ? Money("salvage_value") : 0,
            Months = kind == EntryKind.Asset ? r.GetInt32(r.GetOrdinal("lifespan_months")) : 36,
            Cycle = kind == EntryKind.Subscription ? Text("billing_cycle") : "monthly"
        });
        return rows;
    }
    public List<Entry> ReadAll() => Enum.GetValues<EntryKind>().SelectMany(Read).ToList();
    public long Save(Entry entry)
    {
        entry.Validate();
        using var conn = Open(); using var tx = conn.BeginTransaction(); using var cmd = conn.CreateCommand(); cmd.Transaction = tx;
        var fields = new Dictionary<string, object>();
        fields[entry.Kind == EntryKind.Subscription ? "service_name" : "name"] = entry.Name;
        fields[entry.Kind switch { EntryKind.Asset => "purchase_date", EntryKind.Subscription => "start_date", _ => "expense_date" }] = entry.Date;
        fields[entry.Kind == EntryKind.Asset ? "purchase_price" : "amount"] = (double)entry.Amount;
        fields["notes"] = entry.Notes;
        if (entry.Kind != EntryKind.Subscription) fields["category"] = entry.Category;
        if (entry.Kind == EntryKind.Asset) { fields["lifespan_months"] = entry.Months; fields["salvage_value"] = (double)entry.Salvage; }
        if (entry.Kind == EntryKind.Subscription) fields["billing_cycle"] = entry.Cycle;
        foreach (var (key, value) in fields) cmd.Parameters.AddWithValue("$" + key, value);
        if (entry.Id == 0)
            cmd.CommandText = $"INSERT INTO {Table(entry.Kind)} ({string.Join(',', fields.Keys)}) VALUES ({string.Join(',', fields.Keys.Select(k => "$" + k))}); SELECT last_insert_rowid();";
        else
        {
            cmd.CommandText = $"UPDATE {Table(entry.Kind)} SET {string.Join(',', fields.Keys.Select(k => k + "=$" + k))} WHERE id=$id;";
            cmd.Parameters.AddWithValue("$id", entry.Id);
        }
        long id;
        if (entry.Id == 0) id = (long)cmd.ExecuteScalar()!;
        else { if (cmd.ExecuteNonQuery() != 1) throw new InvalidOperationException("记录已被其他窗口删除，请刷新。"); id = entry.Id; }
        tx.Commit(); return id;
    }
    public void Delete(EntryKind kind, long id)
    {
        using var conn = Open(); using var cmd = conn.CreateCommand();
        cmd.CommandText = $"DELETE FROM {Table(kind)} WHERE id=$id"; cmd.Parameters.AddWithValue("$id", id);
        if (cmd.ExecuteNonQuery() != 1) throw new InvalidOperationException("记录已不存在，请刷新。");
    }
    public static long Inspect(string source)
    {
        using var conn = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = source, Mode = SqliteOpenMode.ReadOnly, Pooling = false }.ToString()); conn.Open();
        using var cmd = conn.CreateCommand(); cmd.CommandText = "PRAGMA quick_check";
        if (!Equals(cmd.ExecuteScalar(), "ok")) throw new InvalidDataException("数据库完整性检查失败：" + source);
        long count = 0;
        foreach (var kind in Enum.GetValues<EntryKind>()) { cmd.CommandText = $"SELECT count(*) FROM {Table(kind)}"; count += (long)cmd.ExecuteScalar()!; }
        return count;
    }
    public static void Backup(string source, string destination)
    {
        Inspect(source);
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(destination))!);
        string temporary = destination + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            using (var src = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = source, Mode = SqliteOpenMode.ReadOnly, Pooling = false }.ToString()))
            using (var dst = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = temporary, Pooling = false }.ToString()))
            {
                src.Open(); dst.Open(); src.BackupDatabase(dst);
                using var cmd = dst.CreateCommand(); cmd.CommandText = "PRAGMA journal_mode=DELETE"; cmd.ExecuteNonQuery();
            }
            Inspect(temporary); File.Move(temporary, destination, false);
        }
        finally { File.Delete(temporary); File.Delete(temporary + "-wal"); File.Delete(temporary + "-shm"); }
    }
    public static string? Prepare(string target, IEnumerable<string> legacy)
    {
        if (File.Exists(target)) return null;
        var sources = legacy.Select(System.IO.Path.GetFullPath).Distinct(StringComparer.OrdinalIgnoreCase).Where(p => File.Exists(p) && !string.Equals(p, System.IO.Path.GetFullPath(target), StringComparison.OrdinalIgnoreCase)).ToList();
        var populated = sources.Where(p => Inspect(p) > 0).ToList();
        if (populated.Count > 1) throw new InvalidDataException("发现多个旧账本，未自动选择。请先确定要迁移的数据库：\n" + string.Join("\n", populated));
        if (sources.Count == 0) return null;
        string source = populated.FirstOrDefault() ?? sources[0];
        Backup(source, System.IO.Path.Combine(System.IO.Path.GetDirectoryName(target)!, "backups", $"before-winui-migration-{DateTime.Now:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}.db"));
        Backup(source, target); return source;
    }
    public static IEnumerable<string> LegacyPaths()
    {
        yield return System.IO.Path.Combine(AppContext.BaseDirectory, "budget.db");
        yield return System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".config", "budgettracker", "budget.db");
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir != null; dir = dir.Parent)
        {
            if (!File.Exists(System.IO.Path.Combine(dir.FullName, "main.py")) || !Directory.Exists(System.IO.Path.Combine(dir.FullName, "db"))) continue;
            foreach (var relative in new[] { "budget.db", "dist/budget.db", "dist/BudgetTracker/budget.db", "dist/windows/budget.db" })
                yield return System.IO.Path.Combine(dir.FullName, relative);
            break;
        }
    }
}
