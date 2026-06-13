@echo off
REM ATLED_BK Shutdown Script - Send OFFLINE notification
cd /d "%~dp0"
ATLED_BK.exe --offline-on-shutdown
