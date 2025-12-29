import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from engine import GameState

def test_location_hints():
    print("Initializing Game...")
    game = GameState()
    
    # Find Clark (Dog Handler)
    clark = next((m for m in game.crew if m.name == "Clark"), None)
    if not clark:
        print("ERROR: Clark not found.")
        return

    print(f"\nTesting {clark.name} Location Hints...")
    print(f"Invariants: {clark.invariants}")
    
    # Set time to work hours (10:00) - use internal attribute
    game.time_system._hour = 10
    
    # Test 1: Clark in Kennel (expected location) - should NOT trigger
    kennel_pos = (5, 5)  # Approximate kennel position
    clark.location = kennel_pos
    clark.is_infected = True  # Make infected to test slip
    
    print(f"\n--- Test 1: Clark in Kennel (Expected) ---")
    print(f"Location: {game.station_map.get_room_name(*clark.location)}")
    print(f"Hour: {game.time_system.hour}")
    hints = clark.check_location_hints(game)
    print(f"Hints: {hints}")
    if not hints:
        print("PASS: No location hint when in expected room.")
    else:
        print("FAIL: Location hint triggered in expected room.")
    
    # Test 2: Clark in Rec Room (unexpected) - should trigger
    rec_room_pos = (7, 7)
    clark.location = rec_room_pos
    
    print(f"\n--- Test 2: Clark in Rec Room (Unexpected) ---")
    print(f"Location: {game.station_map.get_room_name(*clark.location)}")
    print(f"Hour: {game.time_system.hour}")
    
    # Run multiple times to account for probability
    triggered = False
    for i in range(10):
        hints = clark.check_location_hints(game)
        if hints:
            triggered = True
            print(f"Hints (attempt {i+1}): {hints}")
            break
    
    if triggered:
        print("PASS: Location hint triggered when away from expected room.")
    else:
        print("FAIL: Location hint did not trigger (may be RNG, try again).")
    
    # Test 3: Get ambient warnings from GameState
    print(f"\n--- Test 3: GameState.get_ambient_warnings() ---")
    warnings = game.get_ambient_warnings()
    print(f"Ambient Warnings: {warnings}")
    if warnings:
        print("PASS: Ambient warnings system working.")
    else:
        print("INFO: No warnings (depends on RNG and crew positions).")

if __name__ == "__main__":
    test_location_hints()
