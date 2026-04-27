#!/bin/bash
# ============================================================
#  BudgetTracker 打包脚本
#  用法: bash build.sh            → 构建便携文件夹
#        bash build.sh deb        → 构建便携文件夹 + .deb 安装包
#
#  输出: dist/BudgetTracker/      → ~290MB 便携文件夹
#        packaging/*.deb          → 系统安装包（需 --deb 参数）
# ============================================================
set -e
cd "$(dirname "$0")"

echo "=== 清理旧构建 ==="
rm -rf build dist

echo "=== PyInstaller 打包中（约 2-3 分钟）==="
conda run -n budget pyinstaller budget.spec

echo ""
echo "=== 打包完成 ==="
echo "输出: $(pwd)/dist/BudgetTracker/"
echo "启动: $(pwd)/dist/BudgetTracker/BudgetTracker"
du -sh dist/BudgetTracker/
echo ""
echo "复制整个 dist/BudgetTracker/ 文件夹到其他 Linux 机器即可运行。"

# 如果指定了 deb 参数，继续构建 .deb
if [ "${1:-}" = "deb" ]; then
    echo ""
    echo "=== 继续构建 .deb 安装包 ==="
    bash packaging/build_deb.sh
fi
