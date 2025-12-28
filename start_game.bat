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
echo ====================================================================
echo   STARTING SERVERS...
echo ====================================================================
echo.
echo [1/2] Starting Backend Server (Flask API)...
echo       - Game logic and state management
echo       - WebSocket connections
echo       - Port: 5000
echo.
echo [2/2] Starting Frontend Server (Browser UI)...
echo       - HTML/CSS/JavaScript interface
echo       - Served by Flask at http://localhost:5000
echo.
echo Browser will open automatically in 3 seconds...
echo Press CTRL+C in this window to stop all servers
echo ====================================================================
echo.

REM Start the web server in background first
start "The Thing - Backend Server" python start_web_server.py

REM Wait for server to be ready (using Python health check)
echo Waiting for server to initialize...
python wait_for_server.py http://localhost:5000
if errorlevel 1 (
    echo.
    echo ====================================================================
    echo   ERROR: Server failed to start
    echo ====================================================================
    echo Please check the "The Thing - Backend Server" window for errors
    pause
    exit /b 1
)

REM Open browser
echo.
echo Opening browser interface...
start "" http://localhost:5000

echo.
echo ====================================================================
echo   ALL SERVERS RUNNING
echo ====================================================================
echo Backend Server: http://localhost:5000
echo Frontend UI: Open in your browser
echo.

echo Game is running in the browser!
echo.
echo Press any key to close this launcher (Backend Server will keep running in its own window)...
pause
