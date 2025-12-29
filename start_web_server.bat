@echo off
REM The Thing - Web Server Launcher (Windows)
REM Starts the browser-based interface

echo ====================================================================
echo    THE THING: ANTARCTIC RESEARCH STATION 31
echo    Web Server Launcher
echo ====================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from python.org
    pause
    exit /b 1
)

REM Start the web server
echo Starting web server...
echo.
echo Navigate to: http://localhost:5000
echo.
echo Press CTRL+C to stop the server
echo ====================================================================
echo.

python start_web_server.py

pause
