@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Stop FlyLink
echo Stopping FlyLink...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
echo Done.
ping -n 2 127.0.0.1 >nul
pause
