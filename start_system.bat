@echo off
if not DEFINED IS_MINIMIZED set IS_MINIMIZED=1 && start "" /min "%~dpnx0" %* && exit
title Agent-in-the-Loop System Launcher
echo =========================================
echo    Agent-in-the-Loop System Launcher
echo =========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv venv
    echo Then run: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if activation was successful
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment!
    pause
    exit /b 1
)

REM Check if main visualization script exists
if not exist "agent\visualisation\main.py" (
    echo ERROR: Main visualization script not found!
    echo Expected: agent\visualisation\main.py
    pause
    exit /b 1
)

REM Launch the main visualization system
echo.
echo Starting Agent-in-the-Loop Visualization System...
echo.
cd /d "%~dp0"
python agent\visualisation\main.py

REM Check exit code
if errorlevel 1 (
    echo.
    echo ERROR: System encountered an error during execution.
    echo Check the console output above for details.
) else (
    echo.
    echo System closed successfully.
)

echo.
pause