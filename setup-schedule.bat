@echo off
chcp 65001 >nul
echo ========================================
echo   WeChat Daily Brief Scheduler Setup
echo   Runs daily at 7:00 AM
echo ========================================
echo.

:: Check admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Run PowerShell script
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0setup-schedule.ps1"

echo.
echo Press any key to exit...
pause >nul
