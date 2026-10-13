"""数据库快照备份、用户数据路径和旧版数据迁移（仅使用标准库）。"""

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile


TABLES = ("assets", "subscriptions", "one_time_expenses")


def user_database_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "BudgetTracker" / "budget.db"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BudgetTracker" / "budget.db"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "budgettracker" / "budget.db"


def _read_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)


def inspect_database(path: Path) -> dict:
    with closing(_read_connection(path)) as conn:
        if conn.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError(f"数据库完整性检查失败：{path}")
        available = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not set(TABLES).issubset(available):
            raise ValueError(f"不是完整的 BudgetTracker 数据库：{path}")
        return {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in TABLES}


def backup_database(source: Path, destination: Path) -> dict:
    """SQLite 在线备份包含 WAL 中已提交的数据；不覆盖已有目标。"""
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    counts = inspect_database(source)
    handle, temp_name = tempfile.mkstemp(prefix=".budget-backup-", dir=destination.parent)
    os.close(handle)
    temporary = Path(temp_name)
    reserved = False
    try:
        with closing(_read_connection(source)) as src, closing(sqlite3.connect(temporary)) as dst:
            src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")
        # 使用快照中的行数；源数据库可以在在线备份时继续使用。
        counts = inspect_database(temporary)
        with destination.open("xb"):
            reserved = True
        os.replace(temporary, destination)
        reserved = False
        return counts
    finally:
        temporary.unlink(missing_ok=True)
        Path(str(temporary) + "-wal").unlink(missing_ok=True)
        Path(str(temporary) + "-shm").unlink(missing_ok=True)
        if reserved:
            destination.unlink(missing_ok=True)


def backup_project_databases(project_root: Path, backup_root: Path) -> Path | None:
    project_root = Path(project_root).resolve()
    sources = [project_root / "budget.db"]
    if (project_root / "dist").exists():
        sources.extend(sorted((project_root / "dist").rglob("budget.db")))
    sources = [p for p in sources if p.is_file()]
    if not sources:
        return None
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S-%f")
    output = Path(backup_root) / stamp
    records = []
    for source in sources:
        relative = source.relative_to(project_root)
        target = output / relative
        counts = backup_database(source, target)
        records.append({"source": str(source), "backup": str(target), "rows": counts,
                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    (output / "manifest.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def legacy_database_paths(project_root: Path) -> list[Path]:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        local = [exe_dir / "budget.db"]
        # 发布产物从旧 dist/ 移到了 dist/windows/ 或 dist/linux/BudgetTracker/。
        # 在已知的构建目录结构中寻找旧库，移动到其它目录后仍只读取 exe 同目录。
        dist_dir = None
        if exe_dir.name == "dist":
            dist_dir = exe_dir
        elif exe_dir.name == "windows" and exe_dir.parent.name == "dist":
            dist_dir = exe_dir.parent
        elif (exe_dir.name == "BudgetTracker" and exe_dir.parent.name in ("dist", "linux")):
            candidate = exe_dir.parent if exe_dir.parent.name == "dist" else exe_dir.parent.parent
            if candidate.name == "dist":
                dist_dir = candidate
        if dist_dir is not None:
            local.extend([dist_dir / "budget.db", dist_dir / "BudgetTracker" / "budget.db",
                          dist_dir.parent / "budget.db"])
    else:
        local = [project_root / "budget.db", project_root / "dist" / "budget.db",
                 project_root / "dist" / "BudgetTracker" / "budget.db"]
    return local + [Path.home() / ".config" / "budgettracker" / "budget.db"]


def prepare_database(target: Path, legacy_paths: list[Path]) -> Path | None:
    """首次运行复制旧数据并保留原件；有多个不同的数据源时拒绝猜测。"""
    target = Path(target)
    if target.exists():
        return None
    sources = list(dict.fromkeys(p.resolve() for p in legacy_paths
                                if p.is_file() and p.resolve() != target.resolve()))
    populated = [p for p in sources if any(inspect_database(p).values())]
    if len(populated) > 1:
        raise ValueError("发现多个旧数据库，请先选择要迁移的数据库：" + "; ".join(map(str, populated)))
    if not sources:
        target.parent.mkdir(parents=True, exist_ok=True)
        return None
    source = populated[0] if populated else sources[0]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_database(source, target.parent / "backups" / f"before-migration-{stamp}.db")
    backup_database(source, target)
    return source


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="安全备份项目及 dist 中的旧版数据库")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--backup-root", type=Path, default=Path("backups"))
    args = parser.parse_args()
    output = backup_project_databases(args.project_root, args.backup_root)
    print(f"数据库备份：{output.resolve()}" if output else "未发现需要备份的旧数据库。")
