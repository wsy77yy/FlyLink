@echo off
chcp 65001 >nul
cd /d "%~dp0"
title FlyLink Local
echo Starting FlyLink Local (no internet required)...
echo.
if not exist "%~dp0launcher.py" (
  echo [ERROR] launcher.py missing
  pause
  exit /b 1
)
if exist "%~dp0backend\.venv\Scripts\python.exe" (
  "%~dp0backend\.venv\Scripts\python.exe" "%~dp0launcher.py"
) else if exist "%~dp0runtime\python\python.exe" (
  "%~dp0runtime\python\python.exe" "%~dp0launcher.py"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
  )
  python "%~dp0launcher.py"
)
if errorlevel 1 (
  echo Start failed. See FlyLink-start-log.txt
  pause
)
