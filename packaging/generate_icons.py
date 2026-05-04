"""
从 SVG 生成 PNG (256px) 和 ICO 图标。
需要: PySide6 (已在 environment.yml 中)
用法: python packaging/generate_icons.py
"""

import struct
import os
import sys

try:
    from PySide6.QtGui import QPainter, QImage, QGuiApplication
    from PySide6.QtCore import Qt
    from PySide6.QtSvg import QSvgRenderer
except ImportError as e:
    print(f"错误: 缺少依赖 — {e}")
    print("请确保已在 conda 环境中: conda activate budget")
    sys.exit(1)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SVG_PATH = os.path.join(SCRIPT_DIR, "budgettracker.svg")
PNG_PATH = os.path.join(SCRIPT_DIR, "budgettracker.png")
ICO_PATH = os.path.join(SCRIPT_DIR, "budgettracker.ico")


def svg_to_png(svg_path: str, png_path: str, size: int = 256) -> None:
    """Render SVG to PNG using Qt."""
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        raise RuntimeError(f"无法加载 SVG: {svg_path}")

    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    if not image.save(png_path, "PNG"):
        raise RuntimeError(f"PNG 保存失败: {png_path}")
    print(f"  PNG: {png_path} ({size}x{size})")


def png_to_ico(png_path: str, ico_path: str) -> None:
    """Create a minimal .ico file embedding a PNG (supported since Windows Vista)."""
    with open(png_path, "rb") as f:
        png_data = f.read()

    data_size = len(png_data)
    offset = 6 + 16  # ICO header (6) + 1 directory entry (16)

    # ICO header
    header = struct.pack("<HHH", 0, 1, 1)  # reserved, type=ICO, count=1
    # Directory entry: 0 = 256px for width/height
    entry = struct.pack(
        "<BBBBHHII",
        0, 0,       # width, height (0 = 256px)
        0,          # no palette
        0,          # reserved
        1,          # color planes
        32,         # bits per pixel
        data_size,
        offset,
    )

    with open(ico_path, "wb") as f:
        f.write(header)
        f.write(entry)
        f.write(png_data)

    print(f"  ICO: {ico_path}")


def main():
    if not os.path.exists(SVG_PATH):
        print(f"错误: 找不到 SVG 图标: {SVG_PATH}")
        sys.exit(1)

    # Qt needs a QGuiApplication for font/text rendering
    app = QGuiApplication(sys.argv)

    print("=== 生成图标 ===")
    svg_to_png(SVG_PATH, PNG_PATH, size=256)
    png_to_ico(PNG_PATH, ICO_PATH)
    print("=== 图标生成完成 ===")


if __name__ == "__main__":
    main()
