# BudgetTracker WinUI 3 客户端

独立的 C# / WinUI 3 Windows 客户端。原 Python / PySide6 客户端继续保留。

## 功能

| 功能 | WinUI 实现 |
| --- | --- |
| 固定资产 | 新增、编辑、删除、自定义类别、购买日期、寿命、残值、备注；月折旧、累计折旧、净值、预期报废日期和过期提示 |
| 订阅 | 月/季/年付、月均成本、按原始开始日计算下次扣费、7 天内扣费提示、增删改和备注 |
| 日常开支 | 日期、金额、自定义类别、备注、增删改 |
| 报告 | 日期范围、ISO 自然周/自然月、首尾部分周期、汇总卡片、明细表、堆叠柱状图、本月/上月/今年快捷选择 |
| 数据保护 | 写入前校验、SQLite 触发器、事务、删除确认、失败保留表单、旧记录错误提示、备份和首次迁移 |

Windows 10 2004（19041）及以上，当前构建目标 x64。发布目录包含 .NET 和 Windows App SDK 运行时，分发时复制整个 `dist/winui/`，不要只复制 EXE。

## 构建与运行

需要 .NET 8 SDK（仅安装 .NET Runtime 不够），首次还原需要访问 NuGet。无需 Python 运行时来运行 WinUI 客户端。已有 `build/tooling/dotnet/` SDK 时脚本优先使用；也可以传 `-DotNet C:\path\dotnet.exe`。

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_winui.ps1 -Launch
```

可直接打开 `clients/winui/BudgetTracker.Windows/BudgetTracker.Windows.csproj`。界面使用 WinUI 原生控件；表单、列表和图表在 C# 中构建，应用资源定义在 `App.xaml`。

## 数据兼容

默认打开 `%LOCALAPPDATA%\BudgetTracker\budget.db`，与 Python 客户端一致。不修改三张表的字段或 ID，金额继续存储为原表的 REAL；计算和校验使用 C# decimal。启动前对已有账本做 SQLite 在线快照备份到同目录 `backups/before-winui-*.db`，包含已提交 WAL 数据。

当默认账本不存在时，检查 EXE 同目录、可识别的源码目录及旧 `.config/budgettracker/` 路径。只有一个有记录的旧账本时先备份再复制；发现多个有记录的来源时停止，显示来源，不猜测、不覆盖。

两个客户端同时运行时需手动刷新查看另一端的变更；当前不提供自动同步或并发编辑冲突合并。删除有确认，保存失败保留当前输入。旧版异常数据仍可选中编辑，报告会提示校验错误，不显示不可信合计。

统计页的数据库读取和报表计算在后台线程执行，加载时可继续切换页面。切走、重新生成或改变分组会取消旧请求，旧结果不会覆盖最新选择。明细和图表每页最多渲染 60 个周期；上一页/下一页可查看全部周期，汇总卡片始终统计整个所选日期范围。

## 验证

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_winui.ps1 -Verify
```

验证阶段另需原项目 Python 环境（`python-dateutil`）；可通过 `-Python` 指定。测试数据只写入 `build/winui-verification/<随机目录>` 和临时目录，不写真实账本。

- 从当前 Python 计算模块生成 248 组周/月报表、12 组累计折旧/净值、4 组扣费日期期望值，C# 逐项比较。
- 验证增删改、金额和日期校验、SQL 触发器、失败不改数据、事务回滚、WAL 快照、迁移与冲突拒绝。
- Python 创建数据库 → C# 读取和编辑 → Python 再读取并回写，保留原 ID 和表结构。
- 发布 EXE 的 `--smoke-test <结果文件>` 模式使用临时账本，在实际 WinUI 控件上填表，调用与按钮相同的保存处理，检查表单校验、增改删、月/周报表、卡片数据、图表数量、反向日期和清空后刷新，退出并写 JSON。该模式不模拟鼠标、删除确认点击或验证所有屏幕尺寸的外观。
- 自检窗口在屏幕外运行且不抢焦点，逐次等待 XAML 布局和消息循环，检查十次往返统计页、慢读取期间的界面响应、过期请求取消、读取失败恢复及 41 年周报分页；时间日志写入结果文件旁的 `.trace.log`。

若旧版正在运行，可用 `-OutputDirectory dist/winui-updated` 生成独立目录，不必关闭或覆盖正在使用的窗口。省略 `-Launch` 时构建脚本不会打开正常客户端。

代码分层：`BudgetTracker.Core` 为计算/模型，`BudgetTracker.Storage` 为 SQLite/迁移，`BudgetTracker.Windows` 为界面，`BudgetTracker.Tests` 为可执行验证程序。`schema.sql` 与 Python 的数据库规则一致，修改表或触发器时需同步并重新运行互操作测试。
