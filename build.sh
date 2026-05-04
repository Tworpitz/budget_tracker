#!/bin/bash
# ============================================================
#  BudgetTracker 构建脚本 (Linux)
#
#  用法:
#    bash build.sh              → 构建便携文件夹 dist/BudgetTracker/
#    bash build.sh appimage     → 构建文件夹 + AppImage
#    bash build.sh deb          → 构建文件夹 + .deb 安装包
#    bash build.sh all          → 构建文件夹 + AppImage + .deb
#
#  输出:
#    dist/BudgetTracker/                → 便携文件夹
#    dist/BudgetTracker-*.AppImage      → AppImage
#    packaging/budgettracker_*.deb      → Debian 安装包
# ============================================================
set -e
cd "$(dirname "$0")"

VERSION=$(tr -d '[:space:]' < VERSION)
APP_NAME="BudgetTracker"

echo "=== 清理旧构建 ==="
rm -rf build dist

echo "=== 检查 conda 环境 ==="
if ! conda run -n budget python --version &>/dev/null; then
    echo "  环境 'budget' 不存在，从 environment.yml 创建..."
    conda env create -f environment.yml -y
fi
if ! conda run -n budget pyinstaller --version &>/dev/null; then
    echo "  安装 pyinstaller..."
    conda run -n budget pip install pyinstaller
fi

echo "=== 生成图标（如需要）==="
if [ ! -f packaging/budgettracker.png ] || [ packaging/budgettracker.svg -nt packaging/budgettracker.png ]; then
    conda run -n budget python packaging/generate_icons.py 2>/dev/null || \
        echo "  警告: 图标生成失败，将使用默认图标"
else
    echo "  图标已存在，跳过生成"
fi

echo "=== PyInstaller 打包 (${APP_NAME} ${VERSION}) ==="
conda run -n budget pyinstaller budget.spec

echo ""
echo "=== 便携文件夹已就绪 ==="
echo "  路径: $(pwd)/dist/${APP_NAME}/"
echo "  启动: ./dist/${APP_NAME}/${APP_NAME}"
du -sh "dist/${APP_NAME}/"

TARGET="${1:-folder}"

# ─── AppImage ────────────────────────────────────────
if [ "$TARGET" = "appimage" ] || [ "$TARGET" = "all" ]; then
    echo ""
    echo "=== 构建 AppImage ==="
    bash packaging/build_appimage.sh
fi

# ─── Debian 包 ───────────────────────────────────────
if [ "$TARGET" = "deb" ] || [ "$TARGET" = "all" ]; then
    echo ""
    echo "=== 构建 .deb 安装包 ==="
    bash packaging/build_deb.sh
fi

echo ""
echo "=== 全部构建完成 ==="
