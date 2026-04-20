@echo off
REM =============================================================
REM  run_jarvis.bat - JARVIS V2 Launcher
REM  Double-click this file to start Jarvis.
REM =============================================================

title JARVIS V2

echo.
echo ============================================================
echo                    JARVIS V2 - STARTING
echo ============================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if venv exists
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Please run setup.py first to create .venv
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Set UTF-8 encoding (important for Hindi/emoji)
set PYTHONIOENCODING=utf-8
chcp 65001 > nul

REM Launch
echo [INFO] Launching Jarvis...
echo.
python Main.py

REM On exit
echo.
echo ============================================================
echo                    JARVIS V2 - STOPPED
echo ============================================================
echo.
pause