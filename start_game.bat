@echo off
REM The Thing: Antarctic Research Station 31
REM Game Launcher for Windows

echo ========================================
echo   THE THING - Starting Game...
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher from https://www.python.org/
    echo.
    pause
    exit /b 1
)

REM Display Python version
echo Using Python version:
python --version
echo.

REM Install/check dependencies (pyreadline3 for Windows command history)
echo Checking dependencies...
pip install pyreadline3 --quiet 2>nul
if errorlevel 1 (
    echo Warning: Could not install pyreadline3. Command history may not work.
)
echo.

REM Start the game
echo Starting The Thing...
echo.
python main.py

REM Pause to see any error messages
if errorlevel 1 (
    echo.
    echo ========================================
    echo   Game exited with an error
    echo ========================================
    pause
)
