@echo off
rem ============================================
rem  YOUchat launcher (double-click to start)
rem  Auto-elevates to admin, then runs start.py
rem ============================================

rem switch to script directory
cd /d "%~dp0"

rem check if running as admin
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Requesting administrator privileges...
    echo Please click "Yes" in the popup.
    powershell -Command "Start-Process '%~f0' -Verb runAs"
    exit /b
)

echo ============================================
echo   YOUchat Launcher
echo ============================================
echo.

rem UTF-8 output for Python
set PYTHONIOENCODING=utf-8

rem run the launcher script (already admin, skip admin check)
python start.py --no-admin-check

echo.
echo ============================================
echo   Script finished. Press any key to close.
echo ============================================
pause >nul
