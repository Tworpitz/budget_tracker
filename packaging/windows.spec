# -*- mode: python ; coding: utf-8 -*-
"""Windows 单文件配置；入口为 packaging/build_windows.bat。"""

from PyInstaller.utils.hooks import collect_data_files
from pathlib import Path
import os
import pefile

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

# Recent Qt wheels use Windows' ICU API. PATH may also contain an unrelated
# icuuc.dll (e.g. Poppler/Conda) with version-suffixed exports. Bundling that
# library shadows the system DLL and makes QtWidgets fail to load. Only omit
# it when the system library satisfies every ICU import of the bundled Qt.
qt_core = next(Path(source) for dest, source, _ in a.binaries
               if Path(dest).name.lower() == 'qt6core.dll')
with pefile.PE(str(qt_core)) as qt_pe:
    icu_imports = {entry.name for library in qt_pe.DIRECTORY_ENTRY_IMPORT
                   if library.dll.lower() == b'icuuc.dll'
                   for entry in library.imports if entry.name}
system_icu = Path(os.environ['SystemRoot']) / 'System32' / 'icuuc.dll'
if icu_imports and system_icu.is_file():
    with pefile.PE(str(system_icu)) as system_pe:
        system_exports = {entry.name for entry in system_pe.DIRECTORY_ENTRY_EXPORT.symbols}
    if icu_imports <= system_exports:
        a.binaries = [(dest, source, kind) for dest, source, kind in a.binaries
                      if Path(dest).name.lower() != 'icuuc.dll']

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
