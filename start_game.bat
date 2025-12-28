@echo off
REM The Thing: Antarctic Research Station 31
REM Game Launcher for Windows - Browser UI Edition

echo ====================================================================
echo    THE THING: ANTARCTIC RESEARCH STATION 31
echo    Starting Browser Interface...
echo ====================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://www.python.org/
    echo.
    pause
    exit /b 1
)

REM Display Python version
echo Using Python version:
python --version
echo.

REM Install/check web dependencies
echo Checking web dependencies...
pip install -r requirements_web.txt --quiet 2>nul
if errorlevel 1 (
    echo Warning: Some dependencies may not have installed correctly.
)
echo.

REM Start the web server and open browser
echo Starting web server on http://localhost:5000
echo Opening browser...
echo.
echo Press CTRL+C in this window to stop the server
echo ====================================================================
echo.

REM Open browser after a brief delay to let server start
start "" http://localhost:5000

REM Start the web server
python start_web_server.py

REM Pause if server exits with error
if errorlevel 1 (
    echo.
    echo ====================================================================
    echo   Server exited with an error
    echo ====================================================================
    pause
)
