@echo off
REM Redirect to root build.bat
cd /d "%~dp0\.."
call build.bat %*
