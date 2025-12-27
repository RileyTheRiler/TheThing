
import sys
import os

# Ensure project root is in path
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.append(project_root)
    
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.append(src_path)

from src.engine import GameState
from src.core.event_system import event_bus, EventType, GameEvent

def run_verification():
    print("=== VERIFYING DECOUPLED EVENT ARCHITECTURE ===")
    
    # 1. Initialize Game
    game = GameState(seed=123)
    initial_hour = game.time_system.hour
    initial_temp = game.time_system.temperature
    print(f"Initial: Hour={initial_hour}, Temp={initial_temp:.1f}C")

    # 2. Advance Turn (Should trigger event)
    print("\n[ACTION] Advancing turn...")
    game.advance_turn()
    
    # 3. Check TimeSystem update via event
    new_hour = game.time_system.hour
    new_temp = game.time_system.temperature
    print(f"After Turn Increment: Hour={new_hour}, Temp={new_temp:.1f}C")
    
    if new_hour == (initial_hour + 1) % 24:
        print("PASS: TimeSystem advanced hour via EventBus.")
    else:
        print(f"FAIL: Hour mismatch ({new_hour} != {(initial_hour + 1) % 24})")

    if new_temp != initial_temp:
        print("PASS: Temperature changed via EventBus.")
    else:
        print("FAIL: Temperature stayed identical.")

    # 4. Check NPC Schedule
    print("\n[TEST] NPC Schedule Handling")
    # MacReady's schedule from JSON: 08:00 to 20:00 -> Rec Room
    # Turn 1 -> Hour 8 -> Rec Room
    # Turn 2 -> Hour 9 -> Rec Room
    mac = next((m for m in game.crew if m.name == "MacReady"), None)
    if mac:
        print(f"MacReady Location at Hour {new_hour}: {mac.location}")
        # Note: CrewMember.move happens in update_ai which is called in advance_turn
        # After turn 1 -> Hour 9.
        # He should be moving towards/staying in Rec Room (5,5 to 10,10)
        room = game.station_map.get_room_name(*mac.location)
        print(f"MacReady Room: {room}")
        if room == "Rec Room":
            print("PASS: MacReady follows his Rec Room schedule.")
        else:
            print("FAIL: MacReady is not in Rec Room.")

    # 5. Clean up
    print("\nVerification Complete.")

if __name__ == "__main__":
    run_verification()
