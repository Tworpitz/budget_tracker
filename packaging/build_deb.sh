#!/bin/bash
# ============================================================
#  BudgetTracker .deb 打包脚本
#  前提: 先运行 bash packaging/build_linux.sh 生成 dist/linux/BudgetTracker/
#  输出: dist/linux/budgettracker_1.0.0_amd64.deb
# ============================================================
set -e
cd "$(dirname "$0")/.."

PROJECT_ROOT="$(pwd)"
DEB_ROOT="$PROJECT_ROOT/packaging/deb"
DIST_DIR="$PROJECT_ROOT/dist/linux/BudgetTracker"
VERSION="1.0.0"
ARCH="amd64"
DEB_NAME="budgettracker_${VERSION}_${ARCH}.deb"
OUTPUT_FILE="$PROJECT_ROOT/dist/linux/$DEB_NAME"

if [ ! -d "$DIST_DIR" ]; then
    echo "错误: 找不到 $DIST_DIR"
    echo "请先运行: bash packaging/build_linux.sh"
    exit 1
fi

echo "=== 清理旧打包文件 ==="
mkdir -p "$DEB_ROOT/opt/budgettracker"
rm -rf "$DEB_ROOT/opt/budgettracker"/*
rm -f "$OUTPUT_FILE"

echo "=== 复制应用程序文件 ==="
cp -r "$DIST_DIR"/* "$DEB_ROOT/opt/budgettracker/"
# 用户数据库不得进入安装包。
find "$DEB_ROOT/opt/budgettracker" -type f -name 'budget.db*' -delete

echo "=== 创建启动脚本 ==="
cat > "$DEB_ROOT/usr/local/bin/budgettracker" << 'LAUNCHER'
#!/bin/bash
cd /opt/budgettracker
exec /opt/budgettracker/BudgetTracker "$@"
LAUNCHER
chmod 755 "$DEB_ROOT/usr/local/bin/budgettracker"

echo "=== 设置权限 ==="
find "$DEB_ROOT" -type d -exec chmod 755 {} \;
find "$DEB_ROOT/opt" -type f -exec chmod 644 {} \;
chmod 755 "$DEB_ROOT/opt/budgettracker/BudgetTracker"
chmod 755 "$DEB_ROOT/usr/local/bin/budgettracker"

echo "=== 构建 .deb 包 ==="
dpkg-deb --build "$DEB_ROOT" "$OUTPUT_FILE"

echo ""
echo "=== 打包完成 ==="
echo "输出: $OUTPUT_FILE"
du -sh "$OUTPUT_FILE"
echo ""
echo "安装: sudo dpkg -i \"$OUTPUT_FILE\""
echo "卸载: sudo dpkg -r budgettracker"
