import sys
import os

# Adjust path to find src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'src'))

print(f"DEBUG: sys.path: {sys.path}")
print(f"DEBUG: Checking for src/systems/infection.py: {os.path.exists(os.path.join(project_root, 'src', 'systems', 'infection.py'))}")

try:
    import systems.infection
    print("DEBUG: Successfully imported systems.infection directly")
except ImportError as e:
    print(f"DEBUG: Failed to import systems.infection directly: {e}")

from src.engine import GameState, Item
from src.systems.forensics import BiologicalSlipGenerator, BloodTestSim

def verify_forensics():
    print("--- Verifying Agent 4: Forensic Analyst ---")
    game = GameState()
    
    # 1. Verify Item History
    print("\n[Test 1] Physical Persistence Log")
    whiskey = Item("Whiskey", "A bottle", is_evidence=True)
    game.player.add_item(whiskey, 1)
    print(f"Added item at Turn 1. History: {whiskey.history}")
    
    if len(whiskey.history) == 1 and "Picked up" in whiskey.history[0]:
        print("PASS: Item logging pickup.")
    else:
        print("FAIL: Item history incorrect.")

    game.station_map.add_item_to_room(whiskey, 5, 5, 2)
    print(f"Dropped item at Turn 2. History: {whiskey.history}")
    if len(whiskey.history) == 2 and "Dropped" in whiskey.history[1]:
        print("PASS: Item logging drop.")
    else:
        print("FAIL: Drop history incorrect.")

    # 2. Verify Biological Slips
    print("\n[Test 2] Biological Slips")
    slip_vis = BiologicalSlipGenerator.get_visual_slip()
    slip_aud = BiologicalSlipGenerator.get_audio_slip()
    print(f"Visual sample: {slip_vis}")
    print(f"Audio sample: {slip_aud}")
    
    if slip_vis and slip_aud:
        print("PASS: Slips generated.")
    else:
        print("FAIL: Slips empty.")

    # 3. Verify Blood Test Sim
    print("\n[Test 3] Blood Test Simulation")
    sim = BloodTestSim()
    print(sim.start_test("Norris"))
    
    # Heat wire
    print("Heating wire...")
    for _ in range(5):
        msg = sim.heat_wire()
        print(msg)
        if "GLOWING HOT" in msg:
            break
            
    if sim.state != "READY":
        print("FAIL: Wire did not reach ready state.")
    else:
        print("PASS: Wire heated successfully.")
        
    # Apply
    res = sim.apply_wire(is_infected=True)
    print(f"Result (Infected): {res}")
    
    if "SCREAMS" in res or "violently" in res or "shatters" in res:
        print("PASS: Infected reaction correct.")
    else:
        print("FAIL: Infected reaction wrong.")

if __name__ == "__main__":
    verify_forensics()
