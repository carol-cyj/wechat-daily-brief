@echo off
chcp 65001 >nul
echo ========================================
echo   Daily Brief - Quick Start
echo ========================================
echo.

cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Python not found. Please install Python first.
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
pip install -r requirements.txt --break-system-packages --quiet 2>nul

echo [2/3] Generating today's brief...
python main.py --text-only
echo.

echo [3/3] Starting web server...
echo.
echo ========================================
echo   Server is running!
echo ========================================
echo.
echo   Open on PC:   http://localhost:8080
echo.
echo   Phone access:
echo   1. Connect phone to same WiFi
echo   2. Open the LAN URL shown below
echo.
echo   Press Ctrl+C to stop the server
echo ========================================
echo.

python server.py --port 8080
pause
