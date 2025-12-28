#!/usr/bin/env python3
"""
The Thing: Web Server Launcher
Starts the browser-based interface for The Thing game
"""

import os
import sys
import subprocess

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import flask
        import flask_socketio
        import flask_cors
        return True
    except ImportError:
        return False

def install_dependencies():
    """Install required packages"""
    print("Installing required dependencies...")
    requirements_file = os.path.join(os.path.dirname(__file__), 'requirements_web.txt')
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', requirements_file])
        print("Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("Error installing dependencies. Please install manually:")
        print(f"  pip install -r {requirements_file}")
        return False

def main():
    """Main launcher function"""
    print("=" * 70)
    print("   THE THING: ANTARCTIC RESEARCH STATION 31")
    print("   Web Server Launcher")
    print("=" * 70)
    print()

    # Check dependencies
    if not check_dependencies():
        print("Required dependencies not found.")
        print("Attempting to install dependencies automatically...")
        if not install_dependencies():
            print("\n" + "=" * 70)
            print("ERROR: Failed to install dependencies")
            print("=" * 70)
            print("Please install dependencies manually:")
            print("  pip install -r requirements_web.txt")
            print("\nPress any key to exit...")
            try:
                input()
            except:
                pass
            sys.exit(1)
        print("\nDependencies installed successfully!")
        print("Restarting server...")
        print()

    # Start the server
    print("Starting web server...")
    print()

    # Import and run the server
    server_path = os.path.join(os.path.dirname(__file__), 'server.py')

    # Execute the server module
    import importlib.util
    spec = importlib.util.spec_from_file_location("server", server_path)
    server_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_module)

if __name__ == "__main__":
    main()
