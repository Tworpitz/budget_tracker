#!/bin/bash
# ============================================================
#  BudgetTracker .deb 打包脚本
#  前提: 先运行 bash build.sh 生成 dist/BudgetTracker/
#  输出: packaging/budgettracker_1.0.0_amd64.deb
# ============================================================
set -e
cd "$(dirname "$0")/.."

PROJECT_ROOT="$(pwd)"
DEB_ROOT="$PROJECT_ROOT/packaging/deb"
DIST_DIR="$PROJECT_ROOT/dist/BudgetTracker"
VERSION="1.0.0"
ARCH="amd64"
DEB_NAME="budgettracker_${VERSION}_${ARCH}.deb"

if [ ! -d "$DIST_DIR" ]; then
    echo "错误: 找不到 $DIST_DIR"
    echo "请先运行: bash build.sh"
    exit 1
fi

echo "=== 清理旧打包文件 ==="
rm -rf "$DEB_ROOT/opt/budgettracker"/*
rm -f "$PROJECT_ROOT/packaging/$DEB_NAME"

echo "=== 复制应用程序文件 ==="
cp -r "$DIST_DIR"/* "$DEB_ROOT/opt/budgettracker/"

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
dpkg-deb --build "$DEB_ROOT" "$PROJECT_ROOT/packaging/$DEB_NAME"

echo ""
echo "=== 打包完成 ==="
echo "输出: $PROJECT_ROOT/packaging/$DEB_NAME"
du -sh "$PROJECT_ROOT/packaging/$DEB_NAME"
echo ""
echo "安装: sudo dpkg -i $DEB_NAME"
echo "卸载: sudo dpkg -r budgettracker"
