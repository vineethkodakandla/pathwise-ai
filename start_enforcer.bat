@echo off
:: PathWise AI — Start with REAL Windows QoS Enforcement
:: This script must be Run as Administrator
:: Right-click → Run as administrator

echo ============================================
echo  PathWise AI — Windows QoS Enforcement Mode
echo ============================================
echo.

:: Check admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo Right-click start_enforcer.bat and select "Run as administrator"
    pause
    exit /b 1
)

echo [OK] Running as Administrator
echo.

:: Kill any existing server on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTEN"') do (
    echo Killing existing server PID %%a...
    taskkill /PID %%a /F >nul 2>&1
)

:: Set environment
set ENFORCER_MODE=powershell
set WAN_INTERFACE=eth0
set TOTAL_LINK_MBPS=100
set DATA_SOURCE=sim

echo [OK] ENFORCER_MODE = powershell (REAL enforcement)
echo [OK] YouTube will ACTUALLY drop to 144p when throttled
echo.

:: Change to project directory
cd /d "%~dp0"

:: Start server
echo Starting PathWise AI server on http://localhost:8000 ...
echo.
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000

pause
