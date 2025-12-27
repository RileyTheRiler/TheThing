import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from engine import GameState
from core.event_system import event_bus, EventType, GameEvent
from systems.missionary import MissionarySystem
from systems.psychology import PsychologySystem
from systems.social import TrustMatrix

def test_integration():
    print("Initializing GameState for Integration Test...")
    game = GameState()
    
    # Verify Subscriptions
    print("\n--- Verifying Subscriptions ---")
    # Subscriptions happen in __init__ of the systems, which are created in GameState
    # However, GameState created them. Let's check if they responded.
    
    # We can't easily peek into EventBus internal subscribers mostly because it's a simple list.
    # Instead, let's trigger an event and check side effects.
    
    player = game.player
    print(f"Initial Turn: {game.turn}")
    print(f"Paranoia: {game.paranoia_level}")
    
    # 1. Test Missionary Decay (Agent 3)
    # Infect a crew member
    victim = game.crew[1]
    victim.is_infected = True
    victim.mask_integrity = 100.0
    print(f"Infecting {victim.name}. Mask: {victim.mask_integrity}")
    
    # 2. Test Psychology Stress (Agent 7)
    # Set temp to extreme cold to trigger stress
    game.time_system.temperature = -60
    victim.stress = 0
    print(f"Setting Temp to -60C. Expect Stress increase.")
    
    # 3. Test Lynch Mob (Agent 2)
    # Lower trust of victim
    game.trust_system.matrix["Childs"][victim.name] = 5
    game.trust_system.matrix["Garry"][victim.name] = 5
    # Force average roughly below 20 if possible, or just check logs
    
    print("\n>>> ADVANCING TURN (Triggering Event Bus) <<<")
    game.advance_turn()
    
    # CHECK RESULTS
    print("\n--- Checking Results ---")
    
    # Missionary Check
    expected_mask = 100.0 - 2.0 * 1.5 # Base 2.0 * 1.5 for temp -60
    # Wait, Missionary decay logic:
    # if temp < -50: decay *= 1.5. Base is 2.0. So 3.0 decay.
    # Mask should be 97.0
    print(f"Missionary: {victim.name} Mask Integrity = {victim.mask_integrity} (Expected < 100)")
    if victim.mask_integrity < 100:
        print("[PASS] Missionary System responded.")
    else:
        print("[FAIL] Missionary System did not decay mask.")
        
    # Psychology Check
    # Temp -60. update() -> abs(-60)//20 = 3 stress.
    print(f"Psychology: {victim.name} Stress = {victim.stress} (Expected > 0)")
    if victim.stress > 0:
        print("[PASS] Psychology System responded.")
    else:
        print("[FAIL] Psychology System did not apply stress.")

    # Social Check (Lynch Mob)
    # Did it print EMERGENCY? We can't see print output easily here programmatically, 
    # but we can check if they moved to Rec Room (7, 7)
    # Wait, lynch mob logic forces location to (7,7)
    # Let's force trust really low first.
    # Actually, verify_integration might be running on a fresh game where GameState init attached listeners.
    # Check if 'on_turn_advance' was actually called.
    
    if victim.location == (7, 7):
         print("[PASS] Social System triggered Lynch Mob (Moved to 7,7).")
    else:
         print(f"[NOTE] Social System did not trigger lynch mob. Loc: {victim.location}")

if __name__ == "__main__":
    test_integration()
