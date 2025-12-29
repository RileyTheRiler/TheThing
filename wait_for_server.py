#!/usr/bin/env python3
"""
Wait for the Flask server to be ready before opening the browser
"""
import sys
import time
import urllib.request
import urllib.error

def check_server(url, max_attempts=30, delay=0.5):
    """
    Check if the server is responding

    Args:
        url: The URL to check
        max_attempts: Maximum number of attempts (default: 30)
        delay: Delay between attempts in seconds (default: 0.5)

    Returns:
        True if server is ready, False otherwise
    """
    print(f"Waiting for server at {url}...")

    for attempt in range(1, max_attempts + 1):
        try:
            # Try to connect to the server
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    print(f"✓ Server is ready! (attempt {attempt}/{max_attempts})")
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionRefusedError, OSError):
            # Server not ready yet
            if attempt % 5 == 0:  # Print progress every 5 attempts
                print(f"  Still waiting... (attempt {attempt}/{max_attempts})")
            time.sleep(delay)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(delay)

    print(f"✗ Server did not respond after {max_attempts} attempts")
    return False

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"

    # Wait up to 15 seconds (30 attempts * 0.5 seconds)
    if check_server(url):
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Failure
