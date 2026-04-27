@echo off
REM ============================================================
REM  BudgetTracker Windows 打包脚本
REM  前提: 已安装 Miniconda / Anaconda
REM  输出: packaging\BudgetTracker.exe（单文件 ~150MB）
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

echo === 清理旧构建 ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo === 创建 Windows conda 环境 ===
call conda create -n budget-win python=3.11 -y 2>nul
call conda activate budget-win

echo === 安装依赖 ===
pip install pyside6 matplotlib python-dateutil pyinstaller

echo === PyInstaller 单文件打包（约 3-5 分钟）===
pyinstaller --onefile --windowed --name BudgetTracker --add-data "db;db" --add-data "calc;calc" --add-data "ui;ui" --hidden-import dateutil.relativedelta --hidden-import matplotlib.backends.backend_qt5agg --hidden-import matplotlib.backends.backend_qtagg --collect-data matplotlib --exclude-module tkinter main.py

echo.
echo === 打包完成 ===
if exist "dist\BudgetTracker.exe" (
    echo 输出: %cd%\dist\BudgetTracker.exe
    for %%A in ("dist\BudgetTracker.exe") do echo 大小: %%~zA bytes
    echo.
    echo 将 BudgetTracker.exe 复制到任意 Windows 机器双击即可运行。
) else (
    echo 打包失败，请检查错误信息。
)

call conda deactivate
endlocal
pause
