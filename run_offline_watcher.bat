@echo off
chcp 65001 >nul
cd /d "%~dp0"
cd ..

echo ========================================
echo ATLED OFFLINE WATCHER
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.8+ and add it to PATH
    pause
    exit /b 1
)

REM Run the offline watcher
python -m backup_tool.offline_watcher

pause
