@echo off
REM ============================================================
REM  BudgetTracker build script (Windows)
REM
REM  Usage:
REM    build.bat              -> portable .exe
REM    build.bat installer    -> .exe + NSIS installer
REM
REM  Requires: Miniconda / Anaconda
REM  For installer: NSIS (https://nsis.sourceforge.io/)
REM
REM  Output:
REM    dist\BudgetTracker.exe                 -> portable
REM    dist\BudgetTracker-<version>-setup.exe -> installer
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Read version from VERSION file
set VERSION=1.0.0
if exist VERSION (
    for /f "usebackq delims=" %%v in ("VERSION") do set VERSION=%%v
)

REM Locate conda installation
set "CONDA_BAT="
for %%d in (
    "%USERPROFILE%\miniconda3"
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\AppData\Local\miniconda3"
    "%USERPROFILE%\AppData\Local\anaconda3"
    "C:\ProgramData\miniconda3"
    "C:\ProgramData\anaconda3"
) do (
    if exist "%%~d\condabin\conda.bat" (
        set "CONDA_BAT=%%~d\condabin\conda.bat"
        goto :conda_found
    )
)
echo ERROR: conda not found.
echo Please install Miniconda: https://docs.conda.io/en/latest/miniconda.html
pause
goto :eof

:conda_found

REM Check / create conda environment
call "%CONDA_BAT%" run -n budget python --version >nul 2>&1
if errorlevel 1 (
    echo === Creating conda env "budget" from environment.yml ===
    call "%CONDA_BAT%" env create -f environment.yml -y
    if errorlevel 1 (
        echo ERROR: failed to create conda environment.
        pause
        goto :eof
    )
    echo Conda env "budget" created.
)

REM Ensure pyinstaller is installed
call "%CONDA_BAT%" run -n budget pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo === Installing pyinstaller ===
    call "%CONDA_BAT%" run -n budget pip install pyinstaller
)

echo === Clean ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo === Generate icons (if needed) ===
if not exist "packaging\budgettracker.ico" (
    call "%CONDA_BAT%" run -n budget python packaging\generate_icons.py
    if errorlevel 1 (
        echo WARNING: icon generation failed, using default icon.
    )
) else (
    echo Icons already exist, skipping.
)

echo === PyInstaller onefile build (BudgetTracker %VERSION%) ===
call "%CONDA_BAT%" run -n budget pyinstaller budget_win.spec

echo.
echo === Build complete ===
if exist "dist\BudgetTracker.exe" (
    echo Output: %cd%\dist\BudgetTracker.exe
    for %%A in ("dist\BudgetTracker.exe") do echo Size: %%~zA bytes
    echo.
    echo Copy BudgetTracker.exe to any Windows machine and double-click to run.
) else (
    echo Build failed. Check error messages above.
    goto :eof
)

REM --- NSIS installer ---
if /i not "%~1"=="installer" goto :skip_installer
echo.
echo === Build NSIS installer ===

REM Locate makensis
set "MAKENSIS="

REM 1) Try PATH
for /f "delims=" %%f in ('where makensis 2^>nul') do (
    if exist "%%f" set "MAKENSIS=%%f"
)
if not "%MAKENSIS%"=="" goto :makensis_found

REM 2) Try common fixed paths (flat if-exist, no for-loop to avoid paren issues)
if exist "C:\Program Files (x86)\NSIS\makensis.exe"     set "MAKENSIS=C:\Program Files (x86)\NSIS\makensis.exe"
if exist "C:\Program Files\NSIS\makensis.exe"            set "MAKENSIS=C:\Program Files\NSIS\makensis.exe"
if exist "D:\Program Files (x86)\NSIS\makensis.exe"     set "MAKENSIS=D:\Program Files (x86)\NSIS\makensis.exe"
if exist "D:\Program Files\NSIS\makensis.exe"            set "MAKENSIS=D:\Program Files\NSIS\makensis.exe"
if exist "E:\Program Files (x86)\NSIS\makensis.exe"     set "MAKENSIS=E:\Program Files (x86)\NSIS\makensis.exe"
if exist "E:\Program Files\NSIS\makensis.exe"            set "MAKENSIS=E:\Program Files\NSIS\makensis.exe"
if exist "%ProgramFiles%\NSIS\makensis.exe"              set "MAKENSIS=%ProgramFiles%\NSIS\makensis.exe"
if exist "%ProgramFiles(x86)%\NSIS\makensis.exe"        set "MAKENSIS=%ProgramFiles(x86)%\NSIS\makensis.exe"
if exist "%LOCALAPPDATA%\Programs\NSIS\makensis.exe"     set "MAKENSIS=%LOCALAPPDATA%\Programs\NSIS\makensis.exe"
if not "%MAKENSIS%"=="" goto :makensis_found

REM 3) Try registry
for /f "tokens=2*" %%a in (
    'reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\NSIS" /v "InstallLocation" 2^>nul ^| findstr /i "InstallLocation"'
) do (
    if exist "%%b\makensis.exe" set "MAKENSIS=%%b\makensis.exe"
)
if not "%MAKENSIS%"=="" goto :makensis_found

REM 4) Last resort — search C:\NSIS and D:\NSIS
for /f "delims=" %%f in ('dir /s /b "C:\NSIS\makensis.exe" "D:\NSIS\makensis.exe" 2^>nul') do (
    set "MAKENSIS=%%f"
    goto :makensis_found
)

echo ERROR: makensis not found. Install NSIS: https://nsis.sourceforge.io/Download
goto :eof

:makensis_found
echo Using makensis: %MAKENSIS%

if not exist "dist\installer" mkdir "dist\installer"
copy /y "dist\BudgetTracker.exe" "dist\installer\" >nul
if exist "packaging\budgettracker.ico" (
    copy /y "packaging\budgettracker.ico" "dist\installer\" >nul
)

call "%MAKENSIS%" /DVERSION=%VERSION% packaging\installer.nsi
if exist "dist\BudgetTracker-%VERSION%-setup.exe" (
    echo.
    echo === Installer build complete ===
    echo Output: dist\BudgetTracker-%VERSION%-setup.exe
    for %%A in ("dist\BudgetTracker-%VERSION%-setup.exe") do echo Size: %%~zA bytes
) else (
    echo Installer build failed. Check error messages above.
)

:skip_installer

endlocal
if /i not "%~1"=="installer" pause
