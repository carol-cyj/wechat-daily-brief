@echo off
chcp 65001
cls
echo ========================================
echo    WeWe-RSS Docker Hub
echo ========================================
echo.

echo [1/4] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop first.
    pause
    exit /b 1
)
echo        Docker OK

echo.
echo [2/4] Creating data folder...
if not exist "%USERPROFILE%\wewe-data" mkdir "%USERPROFILE%\wewe-data"
echo        Done

echo.
echo [3/4] Pulling image (may take a few minutes)...
docker pull cooderl/wewe-rss-sqlite:latest
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to pull image!
    echo.
    echo Possible reasons:
    echo   1. No internet connection
    echo   2. Docker Hub blocked (common in China)
    echo.
    echo Solutions:
    echo   A. Set Docker mirror: Docker Desktop - Settings - Docker Engine
    echo      Add: { "registry-mirrors": ["https://docker.1ms.run"] }
    echo      Then restart Docker Desktop and try again
    echo.
    echo   B. Use VPN
    echo.
    pause
    exit /b 1
)

echo.
echo [4/4] Starting container...
docker rm -f wewe-rss >nul 2>&1
docker run -d --name wewe-rss -p 4000:4000 -e DATABASE_TYPE=sqlite -e AUTH_CODE=yourpassword -v "%USERPROFILE%\wewe-data:/app/data" cooderl/wewe-rss-sqlite:latest

if errorlevel 1 (
    echo [ERROR] Failed to start!
    pause
    exit /b 1
)

echo.
echo ========================================
echo    SUCCESS!
echo ========================================
echo.
echo    URL:    http://localhost:4000
echo    Code:   yourpassword
echo.
echo    Wait 10-20 seconds before visiting.
echo.

choice /c yn /n /m "Open browser now? (Y/N) "
if %errorlevel% == 1 start http://localhost:4000

pause
