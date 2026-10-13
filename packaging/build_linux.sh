#!/bin/bash
# ============================================================
#  BudgetTracker Linux 打包脚本
#  用法: bash packaging/build_linux.sh     → 构建便携文件夹
#        bash packaging/build_linux.sh deb → 构建便携文件夹 + .deb 安装包
#
#  输出: dist/linux/BudgetTracker/ → 便携文件夹
#        dist/linux/*.deb          → 系统安装包（需 deb 参数）
# ============================================================
set -e
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

case "${1:-}" in
    ""|deb) ;;
    -h|--help)
        echo "用法: bash packaging/build_linux.sh [deb]"
        exit 0
        ;;
    *)
        echo "错误: 未知参数 $1。用法: bash packaging/build_linux.sh [deb]" >&2
        exit 2
        ;;
esac

echo "=== 备份旧版数据库 ==="
conda run -n budget python -m db.storage --project-root . --backup-root backups

echo "=== PyInstaller 打包中（约 2-3 分钟）==="
conda run -n budget pyinstaller --noconfirm --distpath dist/linux --workpath build/linux packaging/linux.spec

echo ""
echo "=== 打包完成 ==="
echo "输出: $(pwd)/dist/linux/BudgetTracker/"
echo "启动: $(pwd)/dist/linux/BudgetTracker/BudgetTracker"
du -sh dist/linux/BudgetTracker/
echo ""
echo "复制整个 dist/linux/BudgetTracker/ 文件夹到其他 Linux 机器即可运行。"

# 如果指定了 deb 参数，继续构建 .deb
if [ "${1:-}" = "deb" ]; then
    echo ""
    echo "=== 继续构建 .deb 安装包 ==="
    bash packaging/build_deb.sh
fi
