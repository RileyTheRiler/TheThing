#!/bin/bash
# The Thing - Web Server Launcher (Linux/Mac)
# Starts the browser-based interface

echo "===================================================================="
echo "   THE THING: ANTARCTIC RESEARCH STATION 31"
echo "   Web Server Launcher"
echo "===================================================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Start the web server
echo "Starting web server..."
echo ""
echo "Navigate to: http://localhost:5000"
echo ""
echo "Press CTRL+C to stop the server"
echo "===================================================================="
echo ""

python3 start_web_server.py
