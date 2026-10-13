@echo off
REM BudgetTracker Windows build. Output: dist\windows\BudgetTracker.exe
setlocal
cd /d "%~dp0\.."

call conda run -n budget-win python --version >nul 2>&1
if errorlevel 1 (
    call conda create -n budget-win python=3.11 -y
    if errorlevel 1 exit /b 1
)
call conda activate budget-win
if errorlevel 1 exit /b 1

echo === Installing dependencies ===
python -m pip install pyside6 matplotlib python-dateutil pyinstaller
if errorlevel 1 goto failed

echo === Backing up legacy databases ===
python -m db.storage --project-root . --backup-root backups
if errorlevel 1 goto failed

echo === Building Windows executable ===
python -m PyInstaller --noconfirm --distpath dist\windows --workpath build\windows packaging\windows.spec
if errorlevel 1 goto failed

echo Output: %cd%\dist\windows\BudgetTracker.exe
echo User data is stored separately in LOCALAPPDATA\BudgetTracker.
call conda deactivate
endlocal
exit /b 0

:failed
echo Build failed. Existing databases and backups are preserved.
call conda deactivate
endlocal
exit /b 1
