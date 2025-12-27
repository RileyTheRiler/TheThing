import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from engine import GameState

def test_characters():
    print("Initializing GameState...")
    try:
        game = GameState()
    except Exception as e:
        print(f"FAILED to init GameState: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"Loaded {len(game.crew)} characters.")
    expected_names = ["MacReady", "Childs", "Blair", "Garry", "Copper", "Nauls", "Norris", "Palmer", "Fuchs", "Bennings", "Clark"]
    # Removed Sanchez as he's not in the 11-member config I saw
    
    missing = []
    for name in expected_names:
        found = any(c.name == name for c in game.crew)
        if not found:
            missing.append(name)
            
    if missing:
        print(f"MISSING CHARACTERS: {missing}")
    else:
        print(f"All {len(expected_names)} expected characters present.")

    # detailed check on MacReady
    mac = next((c for c in game.crew if c.name == "MacReady"), None)
    if mac:
        print(f"\nStats for MacReady: {mac.attributes} {mac.skills}")
        
        print("\n--- Baseline Description ---")
        print(mac.get_description(game))
        
        print("\n--- Infecting MacReady ---")
        mac.is_infected = True
        
        print("Checking for Slips (20 iterations):")
        slips = 0
        for i in range(20):
            d = mac.get_description(game)
            is_slip = "black spheres" in d or "unnaturally still" in d
            if is_slip:
                slips += 1
                print(f"SLIP: {d}")
        
        print(f"Total Slips: {slips}/20")
        
        print("\n--- Dialogue Check ---")
        # Set temp to < 0 to see vapor logic
        game.time_system.temperature = -10
        for i in range(5):
            print(mac.get_dialogue(game))
            
if __name__ == "__main__":
    test_characters()
