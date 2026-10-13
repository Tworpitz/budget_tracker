# -*- mode: python ; coding: utf-8 -*-
"""Windows 单文件配置；入口为 packaging/build_windows.bat。"""

from PyInstaller.utils.hooks import collect_data_files
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent

datas = [(str(PROJECT_ROOT / name), name) for name in ('db', 'calc', 'ui')]
datas += collect_data_files('matplotlib')


a = Analysis(
    [str(PROJECT_ROOT / 'main.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=['dateutil.relativedelta', 'matplotlib.backends.backend_qt5agg', 'matplotlib.backends.backend_qtagg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BudgetTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
