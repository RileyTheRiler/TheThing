@echo off
REM The Thing: Antarctic Research Station 31
REM Browser UI Launcher for Windows

echo ====================================================================
echo    THE THING: ANTARCTIC RESEARCH STATION 31
echo    Browser Interface Launcher
echo ====================================================================
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

echo Starting web server...
echo.
echo Your browser will open automatically to: http://localhost:5000
echo.
echo Press CTRL+C in this window to stop the server
echo ====================================================================
echo.

REM Wait 3 seconds then open browser
start "" /B timeout /t 3 /nobreak >nul && start http://localhost:5000

REM Start the web server
python start_web_server.py

REM Pause if error occurs
if errorlevel 1 (
    echo.
    echo ====================================================================
    echo   Server exited with an error
    echo ====================================================================
    pause
)
