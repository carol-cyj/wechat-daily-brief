@echo off
chcp 65001 >nul
echo ========================================
echo   Daily Brief - Scheduler + Server
echo   Auto-generates at 7:00 AM daily
echo   Serves briefs via web
echo ========================================
echo.

cd /d "%~dp0"

:: Check admin for scheduler setup
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges for scheduler setup...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Setup scheduled task
echo Setting up daily 7:00 AM task...
powershell -ExecutionPolicy Bypass -File "%~dp0setup-schedule.ps1"
echo.

:: Start web server in background
echo Starting web server on port 8080...
start /b python server.py --port 8080

echo.
echo ========================================
echo   Setup complete!
echo ========================================
echo.
echo   Scheduled task: Daily at 7:00 AM
echo   Web server: http://localhost:8080
echo.
echo   Keep this window open for the server.
echo   Close to stop the server.
echo.
echo   Phone: connect to same WiFi,
echo   then open the LAN URL shown above.
echo ========================================
echo.

:: Keep window open
python -c "import time; [time.sleep(1) for _ in iter(int, 1)]"
