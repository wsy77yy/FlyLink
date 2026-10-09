@echo off
chcp 65001 >nul
cd /d "%~dp0"
"runtime\python\python.exe" launch.py
if errorlevel 1 pause
