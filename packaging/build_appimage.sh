#!/bin/bash
# ============================================================
#  BudgetTracker AppImage 构建脚本
#  前提: 先运行 build.sh 生成 dist/BudgetTracker/
#  输出: dist/BudgetTracker-${VERSION}-x86_64.AppImage
#
#  需要: appimagetool (https://github.com/AppImage/appimagetool)
#  下载到 /usr/local/bin/appimagetool 或同目录下
# ============================================================
set -e
cd "$(dirname "$0")/.."

VERSION=$(tr -d '[:space:]' < VERSION)
APP_NAME="BudgetTracker"
DIST_DIR="dist/${APP_NAME}"
APPDIR="dist/AppDir"
APPIMAGE_NAME="${APP_NAME}-${VERSION}-x86_64.AppImage"

if [ ! -d "$DIST_DIR" ]; then
    echo "错误: 找不到 ${DIST_DIR}"
    echo "请先运行: bash build.sh"
    exit 1
fi

echo "--- 准备 AppDir ---"
rm -rf "$APPDIR"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/metainfo"

# 复制应用文件
cp -r "${DIST_DIR}"/* "${APPDIR}/usr/bin/"

# 创建启动脚本 (AppRun)
cat > "${APPDIR}/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="${HERE}/usr/bin:${PATH}"
exec "${HERE}/usr/bin/BudgetTracker" "$@"
APPRUN
chmod +x "${APPDIR}/AppRun"

# .desktop 文件 — 修正 Exec 为 AppImage 内路径
sed 's|^Exec=.*|Exec=BudgetTracker|' packaging/budgettracker.desktop \
    > "${APPDIR}/usr/share/applications/budgettracker.desktop"
cp "${APPDIR}/usr/share/applications/budgettracker.desktop" "${APPDIR}/${APP_NAME}.desktop"

# 图标
if [ -f packaging/budgettracker.png ]; then
    cp packaging/budgettracker.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/"
    cp packaging/budgettracker.png "${APPDIR}/${APP_NAME}.png"
elif [ -f packaging/budgettracker.svg ]; then
    cp packaging/budgettracker.svg "${APPDIR}/usr/share/icons/hicolor/scalable/apps/"
    cp packaging/budgettracker.svg "${APPDIR}/${APP_NAME}.svg"
fi

# AppStream 元数据
cat > "${APPDIR}/usr/share/metainfo/${APP_NAME}.appdata.xml" << APPDATA
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>com.budgetapp.budgettracker</id>
  <name>BudgetTracker</name>
  <summary>固定资产与生活支出统计</summary>
  <metadata_license>MIT</metadata_license>
  <project_license>MIT</project_license>
  <description>
    <p>记录固定资产折旧、订阅服务管理和一次性开支的个人财务统计工具。</p>
  </description>
  <categories>
    <category>Office</category>
    <category>Finance</category>
  </categories>
  <launchable type="desktop-id">budgettracker.desktop</launchable>
</component>
APPDATA

echo "--- 调用 appimagetool ---"
# 查找 appimagetool
if command -v appimagetool &>/dev/null; then
    APPIMAGETOOL="appimagetool"
elif [ -f /usr/local/bin/appimagetool ]; then
    APPIMAGETOOL="/usr/local/bin/appimagetool"
elif [ -f ./appimagetool ]; then
    APPIMAGETOOL="./appimagetool"
else
    echo "错误: 找不到 appimagetool。"
    echo "下载: wget https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    echo "安装: chmod +x appimagetool-x86_64.AppImage && sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool"
    exit 1
fi

ARCH=x86_64 $APPIMAGETOOL "$APPDIR" "dist/${APPIMAGE_NAME}"

# 清理 AppDir（保留 AppImage）
rm -rf "$APPDIR"

echo ""
echo "=== AppImage 构建完成 ==="
echo "  输出: dist/${APPIMAGE_NAME}"
ls -lh "dist/${APPIMAGE_NAME}"
echo ""
echo "  使用: chmod +x dist/${APPIMAGE_NAME} && ./dist/${APPIMAGE_NAME}"
