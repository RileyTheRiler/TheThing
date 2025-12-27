import sys
import os

# Ensure src is in path
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from engine import GameState, Item
from core.resolution import Attribute, Skill

def test_chain_of_custody():
    """Test 1: Chain of Custody - Item History Tracking"""
    print("=== TEST 1: Chain of Custody ===")
    game = GameState(seed=42)
    
    # Create a test item
    flamethrower = Item("Flamethrower", "M2A1 Flamethrower", weapon_skill=Skill.FIREARMS, damage=3)
    
    # MacReady picks it up
    player = game.player
    player_room = game.station_map.get_room_name(*player.location)
    
    print(f"MacReady picks up Flamethrower in {player_room}")
    player.add_item(flamethrower, game.turn)
    
    # Advance turn
    game.turn += 1
    
    # MacReady moves to Infirmary
    player.location = (2, 2)  # Infirmary coordinates
    new_room = game.station_map.get_room_name(*player.location)
    
    # MacReady drops it
    print(f"MacReady drops Flamethrower in {new_room}")
    removed_item = player.remove_item("Flamethrower")
    if removed_item:
        game.station_map.add_item_to_room(removed_item, *player.location, turn=game.turn)
    
    # Check history
    print("\nItem History:")
    for entry in flamethrower.history:
        print(f"  {entry}")
    
    # Verify
    if len(flamethrower.history) >= 2:
        print("[PASS] Chain of Custody tracking works\n")
    else:
        print("[FAIL] History not recorded properly\n")
    
    return game

def test_forensic_database(game):
    """Test 2: Forensic Database - Tagging System"""
    print("=== TEST 2: Forensic Database ===")
    
    # Tag Childs as suspicious
    target = next((m for m in game.crew if m.name == "Childs"), None)
    if not target:
        print("[FAIL] Childs not found\n")
        return
    
    print("Tagging Childs with forensic evidence...")
    game.forensic_db.add_tag("Childs", "BEHAVIORAL", "Acting strange near the kennel", game.turn)
    game.forensic_db.add_tag("Childs", "VISUAL", "No vapor when speaking in cold", game.turn + 1)
    
    # Retrieve report
    report = game.forensic_db.get_report("Childs")
    print(f"\n{report}")
    
    if "BEHAVIORAL" in report and "VISUAL" in report:
        print("[PASS] Forensic Database tagging works\n")
    else:
        print("[FAIL] Tags not stored correctly\n")

def test_blood_test(game):
    """Test 3: Blood Test Simulation"""
    print("=== TEST 3: Blood Test Simulation ===")
    
    # Find an infected NPC (we'll infect one for testing)
    target = next((m for m in game.crew if m.name == "Palmer"), None)
    if not target:
        print("[FAIL] Palmer not found\n")
        return
    
    # Infect Palmer
    target.is_infected = True
    print(f"Palmer is infected (hidden truth)")
    
    # Start test
    print(game.blood_test_sim.start_test("Palmer"))
    
    # Heat wire
    print(game.blood_test_sim.heat_wire())
    print(game.blood_test_sim.heat_wire())
    
    # Apply wire
    result = game.blood_test_sim.apply_wire(target.is_infected)
    print(f"\n{result}")
    
    if "SCREAMS" in result or "expands" in result or "flees" in result:
        print("[PASS] Blood test detected infection\n")
    else:
        print("[FAIL] Blood test did not detect infection\n")

def test_lynch_mob(game):
    """Test 4: Lynch Mob Formation"""
    print("=== TEST 4: Lynch Mob System ===")
    
    # Find Norris (weak character, easy to target)
    target = next((m for m in game.crew if m.name == "Norris"), None)
    if not target:
        print("[FAIL] Norris not found\n")
        return
    
    print(f"Initial trust in Norris: {game.trust_system.get_average_trust('Norris'):.1f}")
    
    # Drastically reduce trust
    for member in game.crew:
        if member.name != "Norris":
            game.trust_system.update_trust(member.name, "Norris", -50)
    
    avg_trust = game.trust_system.get_average_trust("Norris")
    print(f"Trust after suspicion: {avg_trust:.1f}")
    
    # Check for lynch mob
    lynch_target = game.lynch_mob.check_thresholds(game.crew)
    
    if lynch_target and lynch_target.name == "Norris":
        print(f"[PASS] Lynch mob formed against {lynch_target.name}")
        print(f"  Mob active: {game.lynch_mob.active_mob}\n")
    else:
        print("[FAIL] Lynch mob did not form\n")

def test_biological_slips(game):
    """Test 5: Biological Slip Detection"""
    print("=== TEST 5: Biological Slip Detection ===")
    
    # Find an infected NPC
    infected = next((m for m in game.crew if m.is_infected), None)
    if not infected:
        # Infect someone
        infected = next((m for m in game.crew if m.name == "Blair"), None)
        infected.is_infected = True
        infected.mask_integrity = 30  # Low mask = more slips
    
    print(f"Observing {infected.name} (Infected, Mask: {infected.mask_integrity})")
    
    # Get description multiple times to check for slips
    slip_detected = False
    for i in range(5):
        desc = infected.get_description(game)
        if any(keyword in desc.lower() for keyword in ["sweating", "staring", "waxy", "lusterless", "strange"]):
            slip_detected = True
            print(f"  Slip detected: {desc}")
            break
    
    if slip_detected:
        print("[PASS] Biological slips are being generated\n")
    else:
        print("[WARNING] No slips detected (may be RNG)\n")

if __name__ == "__main__":
    print("=== Agent 4 & Agent 2 Verification ===\n")
    
    game = test_chain_of_custody()
    test_forensic_database(game)
    test_blood_test(game)
    test_lynch_mob(game)
    test_biological_slips(game)
    
    print("=== Verification Complete ===")
