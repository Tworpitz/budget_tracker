# BudgetTracker - 固定资产与生活支出统计

一个基于 PySide6 + SQLite 的桌面记账工具，帮你管清三件事：**固定资产折旧、订阅服务、一次性开支**。

![techstack](https://img.shields.io/badge/Python-3.11-blue) ![PySide6](https://img.shields.io/badge/GUI-PySide6-green) ![matplotlib](https://img.shields.io/badge/Chart-matplotlib-orange) ![build](https://img.shields.io/badge/Packaging-PyInstaller-ff69b4)

## ✨ 功能

### 📦 固定资产管理
- 记录电子设备、家电、家具等资产
- 直线法自动计算 **月折旧额 / 累计折旧 / 当前净值**
- 支持残值设置
- 已报废资产灰显，超期标红

### 🔄 订阅服务管理
- 管理月付 / 季付 / 年付订阅（Netflix、iCloud+ 等）
- 自动折算 **月均成本**
- 自动计算 **下次扣费日期**（快到的标红提醒）

### 💳 一次性开支
- 记录吃饭、送礼、旅行等非固定支出
- 支持分类：餐饮、礼物、旅行、医疗、教育、娱乐、交通、日用、服饰、住房等

### 📊 统计报告
- 按月 / 按周汇总查看
- 汇总卡片：折旧、订阅、开支、合计
- **堆叠柱状图**可视化支出构成
- 快捷切换：本月 / 上月 / 今年

## 🚀 快速开始

### 开发环境

```bash
# 1. conda 创建环境
conda env create -f environment.yml
conda activate budget

# 2. 直接运行
python main.py
```

### 打包构建

**Linux 便携版：**
```bash
bash packaging/build_linux.sh
# 输出：dist/linux/BudgetTracker/
```

**Linux .deb 安装包：**
```bash
bash packaging/build_linux.sh deb
# 输出：dist/linux/*.deb
```

**Windows：**
```bat
packaging\build_windows.bat
REM 输出：dist\windows\BudgetTracker.exe
```

## 🏗 项目结构

```
budget_tracker/
├── main.py                  # 入口：高 DPI 适配，启动主窗口
├── environment.yml          # conda 环境（Python 3.11 + PySide6 + matplotlib）
│
├── db/
│   ├── __init__.py
│   ├── database.py          # SQLite 数据库层：建表、CRUD、连接管理
│   ├── storage.py           # 数据库备份、路径及迁移
│   └── validation.py        # 界面与数据库共用的输入校验
│
├── calc/
│   ├── __init__.py
│   └── calculations.py      # 业务逻辑：折旧计算、订阅折算、统计汇总
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py       # 主窗口：Tab 切换、信号联动、样式表
│   ├── asset_tab.py         # 固定资产 Tab：表单 + 表格（含折旧计算）
│   ├── subscription_tab.py  # 订阅服务 Tab：表单 + 表格（含下次扣费）
│   ├── expense_tab.py       # 一次性开支 Tab：表单 + 表格
│   ├── reports_tab.py       # 统计报告 Tab：汇总卡片 + 表格 + 堆叠柱状图
│   └── error_handling.py    # 数据库操作失败时的界面提示
│
├── packaging/
│   ├── build_linux.sh       # Linux 打包入口
│   ├── build_windows.bat    # Windows 打包脚本
│   ├── build_deb.sh         # .deb 打包脚本
│   ├── linux.spec           # Linux PyInstaller 配置
│   ├── windows.spec         # Windows PyInstaller 配置
│   └── deb/                 # Debian 打包文件（control, .desktop, icon）
│
├── build/                   # PyInstaller 临时构建文件（gitignored）
├── dist/                    # PyInstaller 输出（gitignored）
│   ├── windows/             # Windows 可执行文件
│   └── linux/               # Linux 便携文件夹及 .deb 安装包
├── backups/                 # 旧数据库的时间戳备份（gitignored）
├── tests/                   # 计算、数据库、迁移与界面回归测试
│
├── .gitignore
├── .gitattributes           # Linux 脚本使用 LF，Windows 脚本使用 CRLF
└── README.md
```

## 🗄 数据存储

- **数据库**：SQLite (budget.db)
- **3 张表**：
  - `assets` — 固定资产（名称、类别、购买日期、使用月数、价格、残值）
  - `subscriptions` — 订阅服务（服务名、开始日期、计费周期、金额）
  - `one_time_expenses` — 一次性开支（名称、类别、日期、金额）
- **用户数据独立存储**（源码运行和打包版使用同一路径）：
  - Windows → `%LOCALAPPDATA%\BudgetTracker\budget.db`
  - Linux → `$XDG_DATA_HOME/budgettracker/budget.db`，默认 `~/.local/share/budgettracker/budget.db`
  - macOS → `~/Library/Application Support/BudgetTracker/budget.db`
- 首次运行会检查旧数据库（项目根目录、旧 `dist/` 或 exe 同目录，以及旧 `~/.config/budgettracker/`），先备份再复制到新位置，保留原文件。已有新数据库时不会覆盖它；发现多个有记录的旧数据库时停止自动迁移并显示来源，避免误选。
- 打包脚本先用 SQLite 在线备份旧数据库到 `backups/<时间戳>/`，包含 WAL 中已提交的数据，并检查完整性。构建不再清空整个 `dist/`。备份记录和数据库均不提交到 Git。
- 手动备份旧数据库：`python -m db.storage --project-root . --backup-root backups`。

## 🧮 计算逻辑

### 折旧（直线法）
```
月折旧额 = (购买价格 − 残值) ÷ 使用月数
当前净值 = max(购买价格 − 累计折旧, 残值)
```

按购买日起的周年日期划分使用月（例如 1 月 31 日到 2 月最后一天），每个使用月的折旧按实际天数分摊。购买日计提，预期使用寿命结束日停止计提；全寿命累计折旧恰好等于购买价格减残值。累计折旧包含查询当日。

### 订阅月均成本
```
月付 = 金额
季付 = 金额 ÷ 3
年付 = 金额 ÷ 12
```

报表展示分摊成本，订阅开始日之后按每个自然月的实际天数分摊月均成本，并非实际扣款流水。查询起止日期均包含，周报按 ISO 自然周（周一至周日）分组，月报按自然月分组，首尾只计查询范围内的天数。采用 Decimal 和累计金额的分币差值，同一日期范围的周报与月报各项合计一致；年付金额不能整除 12 时，各月成本舍入到分。

资产、订阅和开支的界面与数据库写入共用校验：名称/类别非空、有效日期、正金额（最多两位小数，最大 9999999）、有效计费周期、使用月数 1–600，且残值不超过购买价。数据库触发器同时保护旧表和新表，不重建或删除旧记录。

## 🔧 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.11 |
| GUI | PySide6 (Qt for Python) |
| 数据库 | SQLite (WAL 模式) |
| 图表 | matplotlib |
| 日期计算 | python-dateutil |
| 打包 | PyInstaller |
| 可选主题 | qt-material |
| 包管理 | conda / pip |

## 📝 开发说明

- 所有 UI 代码位于 `ui/` 目录，各 Tab 通过 `data_changed` Signal 联动统计报告
- 数据库连接采用 WAL 模式 + 每操作关闭，适合桌面单用户场景
- PyInstaller 构建时需 `--hidden-import` 显式导入 `dateutil.relativedelta` 和 matplotlib backend
- 所有打包脚本与配置位于 `packaging/`，构建产物统一放在 `dist/<平台>/`；脚本按自身位置定位项目根目录，可以从其他工作目录用绝对路径调用。
- 图表中文显示自动检测系统中文字体（Noto CJK / WenKai / YaHei 等）
- 回归测试：`python -m unittest discover -s tests -v`。计算与数据库测试使用临时数据库，不写入用户数据库。

---

*随手记，清楚花。Made with ❤️ by tworpitz.*
