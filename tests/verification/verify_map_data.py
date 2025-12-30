
import requests
import sys
import time

def verify_map_data():
    print("Verifying map data from server...")
    base_url = "http://127.0.0.1:5000"
    
    try:
        # Start new game
        print(f"Starting new game at {base_url}/api/new_game...")
        session_id = "verify_test_session"
        response = requests.post(f"{base_url}/api/new_game", json={
            "difficulty": "NORMAL",
            "session_id": session_id
        })
        response.raise_for_status()
        new_game_data = response.json()
        print(f"New game started. Session ID: {new_game_data.get('session_id')}")

        # Check for ascii_map in new_game response first (it returns game_state)
        # But let's follow the standard polling flow
        
        # Fetch game state
        print(f"Fetching game state for session {session_id}...")
        response = requests.get(f"{base_url}/api/game_state/{session_id}")
        response.raise_for_status()
        data = response.json()
        
        # Check for ascii_map
        if "ascii_map" not in data:
            print("FAIL: 'ascii_map' field missing from game state.")
            return False
            
        ascii_map = data["ascii_map"]
        if not ascii_map or len(ascii_map) == 0:
            print("FAIL: 'ascii_map' is empty.")
            return False
            
        print("SUCCESS: 'ascii_map' found in game state.")
        print("Sample data:")
        lines = ascii_map.split('\n')
        # Print a few non-empty lines
        count = 0
        for line in lines:
            if line.strip():
                print(f"  {line}")
                count += 1
            if count >= 5:
                break
            
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"FAIL: HTTP Error: {e}")
        if e.response is not None:
             print("Response Text:")
             print(e.response.text)
        return False
    except Exception as e:
        print(f"FAIL: Error fetching data: {e}")
        return False

if __name__ == "__main__":
    success = verify_map_data()
    sys.exit(0 if success else 1)
