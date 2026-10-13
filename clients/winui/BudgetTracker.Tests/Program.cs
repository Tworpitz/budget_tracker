using BudgetTracker.Core;
using BudgetTracker.Storage;
using Microsoft.Data.Sqlite;
using System.Text.Json;

int checks = 0;
void Assert(bool condition, string label) { if (!condition) throw new Exception(label); checks++; }
void Reject(Action action, string label)
{
    bool rejected = false;
    try { action(); } catch (ArgumentException) { rejected = true; } catch (SqliteException) { rejected = true; } catch (IOException) { rejected = true; } catch (InvalidDataException) { rejected = true; }
    Assert(rejected, label);
}
var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
string fixtures = Path.GetFullPath(args[0]);
using var data = JsonDocument.Parse(File.ReadAllText(Path.Combine(fixtures, "parity.json")));
Entry ParseEntry(JsonElement json) => json.Deserialize<Entry>(options)!;
DateOnly Day(JsonElement json, string field) => DateOnly.Parse(json.GetProperty(field).GetString()!);
var entries = data.RootElement.GetProperty("entries").EnumerateArray().Select(ParseEntry).ToArray();
foreach (var test in data.RootElement.GetProperty("cases").EnumerateArray())
{
    var actual = Calculations.Report(entries, Day(test, "start"), Day(test, "end"), test.GetProperty("weekly").GetBoolean());
    var expected = test.GetProperty("rows").Deserialize<List<ReportRow>>(options)!;
    Assert(actual.SequenceEqual(expected), "Python parity: " + test.GetProperty("start") + " weekly=" + test.GetProperty("weekly"));
}
foreach (var test in data.RootElement.GetProperty("snapshots").EnumerateArray())
{
    var entry = ParseEntry(test.GetProperty("entry")); var day = Day(test, "today");
    Assert(Calculations.Accumulated(entry, day) == test.GetProperty("accumulated").GetDecimal(), "accumulated parity");
    Assert(Calculations.CurrentValue(entry, day) == test.GetProperty("current").GetDecimal(), "current value parity");
}
foreach (var test in data.RootElement.GetProperty("billing").EnumerateArray())
    Assert(Calculations.NextBilling(ParseEntry(test.GetProperty("entry")), Day(test, "today")) == Day(test, "next"), "billing anniversary parity");
Assert(Calculations.Report([], new(2024,1,31), new(2024,2,2), false).Count == 2, "empty monthly rows");
using (var canceled = new CancellationTokenSource())
{
    canceled.Cancel(); bool stopped = false;
    try { Calculations.Report(entries, new(2000,1,1), new(2040,12,31), true, canceled.Token); }
    catch (OperationCanceledException) { stopped = true; }
    Assert(stopped, "canceled report stops calculation");
}
Reject(() => Calculations.Report([], new(2024,2,1), new(2024,1,1), false), "reverse range");

string temporary = Path.Combine(Path.GetTempPath(), "BudgetTracker-tests-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(temporary);
try
{
    var store = new LedgerStore(Path.Combine(temporary, "test.db")); store.Initialize();
    foreach (var kind in Enum.GetValues<EntryKind>())
    {
        var record = new Entry { Kind = kind, Name = "测试", Category = "中文", Date = "2024-02-29", Amount = 310, Months = 12, Notes = "备注" };
        long id = store.Save(record); Assert(store.Read(kind).Single().Id == id, "insert/read " + kind);
        store.Save(record with { Id = id, Name = "编辑", Amount = 123.45m });
        Assert(store.Read(kind).Single().Name == "编辑", "update " + kind);
        foreach (var invalid in new[] { record with { Id = id, Name = " " }, record with { Id = id, Amount = 0 }, record with { Id = id, Amount = -1 }, record with { Id = id, Amount = 1.001m }, record with { Id = id, Amount = 10000000 }, record with { Id = id, Date = "2024-02-30" } })
            Reject(() => store.Save(invalid), "invalid write " + kind);
        Assert(store.Read(kind).Single().Amount == 123.45m, "failed update preserves row");
        store.Delete(kind, id); Assert(store.Read(kind).Count == 0, "delete " + kind);
    }
    var asset = new Entry { Kind = EntryKind.Asset, Name = "资产", Amount = 100, Date = "2024-01-31" };
    foreach (var invalid in new[] { asset with { Months = 0 }, asset with { Months = 601 }, asset with { Salvage = -1 }, asset with { Salvage = 101 }, asset with { Category = " " } }) Reject(() => store.Save(invalid), "asset validation");
    Reject(() => store.Save(asset with { Kind = EntryKind.Subscription, Cycle = "invalid" }), "subscription cycle");
    store.Save(asset);
    using (var conn = store.Open())
    {
        using var command = conn.CreateCommand();
        command.CommandText = "UPDATE assets SET salvage_value=101"; Reject(() => command.ExecuteNonQuery(), "SQL trigger");
        using var tx = conn.BeginTransaction(); command.Transaction = tx;
        command.CommandText = "UPDATE assets SET name='uncommitted'"; command.ExecuteNonQuery(); tx.Rollback();
    }
    Assert(store.Read(EntryKind.Asset).Single().Name == "资产", "rollback");
    store.Initialize(); Assert(store.ReadAll().Count == 1, "idempotent schema preserves data");
    string backup = Path.Combine(temporary, "backup.db");
    using (var openWriter = store.Open())
    {
        using var cmd = openWriter.CreateCommand(); cmd.CommandText = "UPDATE assets SET notes='WAL committed'"; cmd.ExecuteNonQuery();
        LedgerStore.Backup(store.Path, backup);
    }
    Assert(new LedgerStore(backup).ReadAll().Single().Notes == "WAL committed", "backup includes committed WAL");
    Reject(() => LedgerStore.Backup(store.Path, backup), "never overwrite backup");
    string migrated = Path.Combine(temporary, "migrated", "budget.db");
    LedgerStore.Prepare(migrated, [store.Path]); Assert(LedgerStore.Inspect(migrated) == 1 && File.Exists(store.Path), "migration preserves source");
    Assert(LedgerStore.Prepare(migrated, [backup]) == null, "never overwrite destination");
    Reject(() => LedgerStore.Prepare(Path.Combine(temporary, "ambiguous.db"), [store.Path, backup]), "ambiguous migration refused");
    string corrupt = Path.Combine(temporary, "corrupt.db"); File.WriteAllText(corrupt, "not sqlite");
    Reject(() => LedgerStore.Backup(corrupt, Path.Combine(temporary, "bad-backup.db")), "corrupt database rejected");

    var interop = new LedgerStore(Path.Combine(fixtures, "interop.db")); interop.Initialize();
    var old = interop.ReadAll(); Assert(old.Count == 3, "read Python database");
    interop.Save(old.Single(e => e.Kind == EntryKind.Asset) with { Name = "C# 编辑资产" });
    interop.Save(old.Single(e => e.Kind == EntryKind.Subscription) with { Cycle = "quarterly", Amount = 93 });
    interop.Save(old.Single(e => e.Kind == EntryKind.Expense) with { Notes = "C# 中文备注", Amount = 15.25m });
    Assert(interop.ReadAll().Select(e => (e.Kind,e.Id)).SequenceEqual(old.Select(e => (e.Kind,e.Id))), "preserve Python IDs");
}
finally { Directory.Delete(temporary, true); }
Console.WriteLine($"PASS: {checks} parity, validation, CRUD, SQL, backup, migration and interoperability checks");
