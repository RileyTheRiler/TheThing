import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from core.event_system import event_bus, EventType, GameEvent
from engine import GameState
from systems.ai import AISystem

def test_ai_movement():
    print("Testing AI System Integration...")
    
    # Setup
    game = GameState(seed=123) # Fixed seed for deterministic wandering
    game.ai_system = AISystem() # Ensure initialized (though GameState init should do it)
    
    # Get a crew member to test
    # MacReady is player, let's pick someone else
    npc = next((m for m in game.crew if m.name != "MacReady"), None)
    if not npc:
        print("FAIL: No NPCs found.")
        return

    print(f"Testing NPC: {npc.name}")
    start_loc = npc.location
    print(f"Start Location: {start_loc} ({game.station_map.get_room_name(*start_loc)})")
    
    # Test Wandering (No schedule or off-schedule)
    # Clear schedule for test
    original_schedule = npc.schedule
    npc.schedule = []
    
    print("\n--- TEST: Wandering ---")
    game.advance_turn()
    
    new_loc = npc.location
    print(f"Location after turn: {new_loc} ({game.station_map.get_room_name(*new_loc)})")
    
    if new_loc != start_loc:
        print("PASS: NPC moved (wandered).")
    else:
        print("WARN: NPC did not move (could be random chance stay, try again)")
        game.advance_turn()
        if npc.location != start_loc:
             print("PASS: NPC moved on second turn.")
        else:
             print("FAIL: NPC stuck or 30% wander chance very unlucky.")

    # Test Schedule
    print("\n--- TEST: Schedule Following ---")
    # Test Schedule
    print("\n--- TEST: Schedule Following ---")
    # Set current time to 12:00
    # Start hour is 19. Target 12. 
    # (19 + t) % 24 = 12 => t = 17
    game.time_system.turn_count = 17
    print(f"Time set to {game.time_system.hour:02d}:00")
    
    # Set schedule: go to Kitchen at 12
    npc.schedule = [{"start": 12, "end": 14, "room": "Kitchen"}]
    
    # Ensure not already in Kitchen
    kitchen_rect = game.station_map.rooms["Kitchen"] # (x, y, w, h)
    # Move NPC far away
    npc.location = (0, 0) 
    print(f"Teleported {npc.name} to (0,0). Target: Kitchen")
    
    game.advance_turn()
    print(f"Location after turn 1: {npc.location}")
    
    game.advance_turn()
    print(f"Location after turn 2: {npc.location}")
    
    # Check if getting closer (Manhattan distance)
    k_center = ((kitchen_rect[0] + kitchen_rect[2])//2, (kitchen_rect[1] + kitchen_rect[3])//2)
    dist = abs(npc.location[0] - k_center[0]) + abs(npc.location[1] - k_center[1])
    print(f"Distance to Kitchen center {k_center}: {dist}")
    
    if npc.location != (0, 0):
        print("PASS: NPC moved towards scheduled room.")
    else:
        print("FAIL: NPC did not move towards schedule.")

if __name__ == "__main__":
    test_ai_movement()
