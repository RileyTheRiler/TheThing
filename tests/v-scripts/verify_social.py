import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from engine import GameState, CrewMember
from systems.architect import GameMode

def test_social_systems():
    print("--- VERIFYING SOCIAL SYSTEMS ---")
    game = GameState(seed=42)
    
    # 1. Verify Schedules
    print("\n1. Testing NPC Schedules...")
    # Blair starts at Rec Room (usually) but has a schedule for Infirmary from 8-18.
    blair = next(m for m in game.crew if m.name == "Blair")
    # Set turn_count so the derived hour is 10:00 AM (Infirmary shift)
    desired_hour = 10
    game.time_system.turn_count = (desired_hour - game.time_system.start_hour) % 24
    
    print(f"Blair current location: {blair.location} ({game.station_map.get_room_name(*blair.location)})")
    print("Advancing turn to trigger movement towards Infirmary...")
    for _ in range(10): # Give him some turns to walk there
        game.advance_turn()
    
    print(f"Blair location after movement: {blair.location} ({game.station_map.get_room_name(*blair.location)})")
    if game.station_map.get_room_name(*blair.location) == "Infirmary":
        print("[SUCCESS] NPC followed schedule to Infirmary.")
    else:
        print("[PENDING] NPC moving towards Infirmary.")

    # 2. Verify Trust-Based Dialogue
    print("\n2. Testing Trust-Based Dialogue...")
    mac = game.player
    # Lower trust from Childs to MacReady
    game.trust_system.matrix["Childs"]["MacReady"] = 10 
    childs = next(m for m in game.crew if m.name == "Childs")
    
    dialogue = childs.get_dialogue(game)
    print(f"Childs (Low Trust) says: {dialogue}")
    if "suspicious look" in dialogue or "Stay back" in dialogue:
        print("[SUCCESS] Dialogue changed based on low trust.")
    else:
        print("[FAILURE] Dialogue did not reflect low trust.")
        
    # Raise trust
    game.trust_system.matrix["Childs"]["MacReady"] = 90
    dialogue = childs.get_dialogue(game)
    print(f"Childs (High Trust) says: {dialogue}")
    if "Glad it's you" in dialogue:
        print("[SUCCESS] Dialogue changed based on high trust.")

    # 3. Verify Invariants (Slip Test)
    print("\n3. Testing Behavioral Invariants (Infected Slip)...")
    # Make Palmer infected
    palmer = next(m for m in game.crew if m.name == "Palmer")
    palmer.is_infected = True
    
    found_slip = False
    print("Checking Palmer's dialogue for slips (may take multiple tries)...")
    for _ in range(20):
        d = palmer.get_dialogue(game)
        if "scientific jargon" in d:
            print(f"Slip found! Palmer says: {d}")
            found_slip = True
            break
    if found_slip:
        print("[SUCCESS] Infected NPC exhibited a behavioral slip.")
    else:
        print("[FAILURE] No slips detected in 20 attempts.")

    # 4. Verify Lynch Mob
    print("\n4. Testing Lynch Mob Logic...")
    # Tank Garry's trust to trigger lynch mob
    for member in game.crew:
        if member.name != "Garry":
            game.trust_system.matrix[member.name]["Garry"] = 5
            
    print("Advancing turn to trigger lynch mob check...")
    game.advance_turn()
    
    if game.mode == GameMode.STANDOFF:
        print("[SUCCESS] Game entered STANDOFF mode due to lynch mob.")
    else:
        print(f"[FAILURE] Game mode is {game.mode}, expected STANDOFF.")

if __name__ == "__main__":
    try:
        test_social_systems()
    except Exception as e:
        print(f"ERROR DURING VERIFICATION: {e}")
        import traceback
        traceback.print_exc()
