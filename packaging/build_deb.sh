#!/bin/bash
# ============================================================
#  BudgetTracker .deb 打包脚本
#  前提: 先运行 build.sh 生成 dist/BudgetTracker/
#  输出: packaging/budgettracker_${VERSION}_amd64.deb
# ============================================================
set -e
cd "$(dirname "$0")/.."

VERSION=$(tr -d '[:space:]' < VERSION)
ARCH="amd64"
APP_NAME="BudgetTracker"

PROJECT_ROOT="$(pwd)"
DIST_DIR="${PROJECT_ROOT}/dist/${APP_NAME}"
DEB_SRC="${PROJECT_ROOT}/packaging/deb"
DEB_STAGING="${PROJECT_ROOT}/dist/deb_staging"
DEB_NAME="budgettracker_${VERSION}_${ARCH}.deb"

if [ ! -d "$DIST_DIR" ]; then
    echo "错误: 找不到 ${DIST_DIR}"
    echo "请先运行: bash build.sh"
    exit 1
fi

echo "--- 准备打包临时目录 ---"
rm -rf "$DEB_STAGING"
cp -r "$DEB_SRC" "$DEB_STAGING"

# 写入版本号（不修改源文件）
sed -i "s/^Version:.*/Version: ${VERSION}/" "${DEB_STAGING}/DEBIAN/control"

echo "--- 复制应用程序文件 ---"
mkdir -p "${DEB_STAGING}/opt/budgettracker"
cp -r "${DIST_DIR}"/* "${DEB_STAGING}/opt/budgettracker/"

echo "--- 设置权限 ---"
find "${DEB_STAGING}" -type d -exec chmod 755 {} \;
find "${DEB_STAGING}/opt" -type f -exec chmod 644 {} \;
chmod 755 "${DEB_STAGING}/opt/budgettracker/${APP_NAME}"
chmod 755 "${DEB_STAGING}/usr/local/bin/budgettracker"
chmod 755 "${DEB_STAGING}/DEBIAN/postinst" 2>/dev/null || true
chmod 755 "${DEB_STAGING}/DEBIAN/postrm" 2>/dev/null || true

echo "--- 构建 .deb 包 ---"
dpkg-deb --build "$DEB_STAGING" "${PROJECT_ROOT}/packaging/${DEB_NAME}"

# 清理临时目录
rm -rf "$DEB_STAGING"

echo ""
echo "=== .deb 打包完成 ==="
echo "  输出: packaging/${DEB_NAME}"
du -sh "${PROJECT_ROOT}/packaging/${DEB_NAME}"
echo ""
echo "  安装: sudo dpkg -i packaging/${DEB_NAME}"
echo "  卸载: sudo dpkg -r budgettracker"
