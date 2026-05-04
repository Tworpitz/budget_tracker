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

图标会在首次构建时自动生成（也可手动运行：`python packaging/generate_icons.py`）。

**Linux：**
```bash
bash build.sh              # 便携文件夹 dist/BudgetTracker/
bash build.sh appimage     # AppImage (需 appimagetool)
bash build.sh deb          # .deb 安装包
bash build.sh all          # 以上全部
```

**Windows：**
```bat
build.bat                  # 便携单文件 dist\BudgetTracker.exe
build.bat installer        # NSIS 安装包 (需 NSIS)
```

## 🏗 项目结构

```
budget_tracker/
├── main.py                  # 入口：高 DPI 适配，启动主窗口
├── environment.yml          # conda 环境（Python 3.11 + PySide6 + matplotlib）
├── build.sh                 # Linux 构建入口
├── build.bat                # Windows 构建入口
│
├── db/
│   ├── __init__.py
│   └── database.py          # SQLite 数据库层：建表、CRUD、连接管理
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
│   └── reports_tab.py       # 统计报告 Tab：汇总卡片 + 表格 + 堆叠柱状图
│
├── packaging/
│   ├── build_appimage.sh    # AppImage 构建
│   ├── build_deb.sh         # .deb 构建
│   ├── installer.nsi        # NSIS 安装包脚本
│   ├── generate_icons.py    # 图标生成脚本 (SVG → PNG/ICO)
│   ├── budgettracker.svg    # 应用图标 (SVG)
│   ├── budgettracker.png    # 应用图标 (256px PNG, 生成)
│   ├── budgettracker.ico    # 应用图标 (Windows ICO, 生成)
│   ├── budgettracker.desktop # .desktop 入口文件
│   └── deb/DEBIAN/          # Debian 打包文件（control, postinst, postrm）
│
├── build/                   # PyInstaller 临时构建文件（gitignored）
├── dist/                    # PyInstaller 输出（gitignored）
│   ├── BudgetTracker.exe    # Windows 可执行文件
│   └── budget.db            # 用户数据库
│
├── budget.spec              # PyInstaller spec（Linux 文件夹模式）
├── budget_win.spec          # PyInstaller spec（Windows 单文件模式）
├── VERSION                  # 版本号单一来源
├── .gitignore
└── README.md
```

## 🗄 数据存储

- **数据库**：SQLite (budget.db)
- **3 张表**：
  - `assets` — 固定资产（名称、类别、购买日期、使用月数、价格、残值）
  - `subscriptions` — 订阅服务（服务名、开始日期、计费周期、金额）
  - `one_time_expenses` — 一次性开支（名称、类别、日期、金额）
- **路径自动检测**：
  - 开发模式 → 项目根目录
  - PyInstaller 文件夹模式 → exe 同级目录
  - 系统安装（/opt 等只读路径）→ `~/.config/budgettracker/`

## 🧮 计算逻辑

### 折旧（直线法）
```
月折旧额 = (购买价格 − 残值) ÷ 使用月数
当前净值 = max(购买价格 − 累计折旧, 残值)
```

### 订阅月均成本
```
月付 = 金额
季付 = 金额 ÷ 3
年付 = 金额 ÷ 12
```

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
- 图表中文显示自动检测系统中文字体（Noto CJK / WenKai / YaHei 等）

---

*随手记，清楚花。Made with ❤️ by tworpitz.*
