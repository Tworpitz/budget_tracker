# -*- mode: python ; coding: utf-8 -*-
"""
BudgetTracker — Windows 单文件打包 spec。
用法: pyinstaller budget_win.spec
输出: dist/BudgetTracker.exe
"""

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('db', 'db'),
        ('calc', 'calc'),
        ('ui', 'ui'),
        *collect_data_files('matplotlib', subdir='mpl-data'),
    ],
    hiddenimports=[
        'dateutil.relativedelta',
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_qtagg',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'email',
        'http',
        'xmlrpc',
        'pydoc',
    ],
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='packaging/budgettracker.ico',
)
