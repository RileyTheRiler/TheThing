import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from engine import GameState, CrewMember

def test_spatial_logic():
    print("Initializing Game...")
    game = GameState()
    
    # 1. Test Copper (Forbidden: Generator, Kitchen)
    copper = next((m for m in game.crew if m.name == "Copper"), None)
    if not copper:
        print("ERROR: Copper not found.")
        return

    print(f"\nTesting {copper.name} Spatial Logic...")
    print(f"Forbidden Rooms: {copper.forbidden_rooms}")
    
    # Move to Allowed Room (Rec Room)
    game.station_map.rooms["Rec Room"] # ensure exists
    # Move manually
    rec_room_pos = (7, 7) # Middle of Rec Room
    copper.location = rec_room_pos
    
    print(f"Location: {game.station_map.get_room_name(*copper.location)}")
    desc = copper.get_description(game)
    if "Something is wrong" in desc:
        print("FAIL: Spatial slip detected in allowed room.")
    else:
        print("PASS: No spatial slip in Rec Room.")

    # Move to Forbidden Room (Generator)
    gen_room_pos = (16, 16) # Middle of Generator
    copper.location = gen_room_pos
    
    print(f"Location: {game.station_map.get_room_name(*copper.location)}")
    desc = copper.get_description(game)
    print(f"Description: {desc}")
    
    if "Something is wrong" in desc and "Generator" in desc:
        print("PASS: Spatial slip detected in Generator.")
    else:
        print("FAIL: No spatial slip detected in Generator.")

if __name__ == "__main__":
    test_spatial_logic()
