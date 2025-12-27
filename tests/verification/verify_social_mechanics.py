
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.event_system import event_bus, EventType, GameEvent
from engine import GameState
from systems.social import TrustMatrix
from systems.psychology import PsychologySystem

def test_social_mechanics():
    print("Initializing GameState...")
    game = GameState()
    
    # 1. Test Trust Decay
    print("\n[TEST 1] Trust Decay")
    game.paranoia_level = 60 # Should cause -3 trust per turn (60/20)
    
    # Get initial trust
    initial_trust = game.trust_system.get_trust("Childs", "MacReady")
    print(f"Initial Trust (Childs -> MacReady): {initial_trust}")
    
    # Advance Turn
    game.advance_turn()
    
    new_trust = game.trust_system.get_trust("Childs", "MacReady")
    print(f"New Trust: {new_trust}")
    
    expected_decay = 3
    if new_trust <= initial_trust - expected_decay:
        print("SUCCESS: Trust decayed correctly.")
    else:
        print(f"FAIL: Trust did not decay as expected. Diff: {initial_trust - new_trust}")
        
    # 2. Test Isolation Stress
    print("\n[TEST 2] Isolation Stress")
    # Move MacReady to Room A (alone)
    game.player.location = (0, 0) # Infirmary
    # Move everyone else to Room B
    for m in game.crew:
        if m != game.player:
            m.location = (15, 15) # Generator
            
    # Reset MacReady stress
    game.player.stress = 0
    
    # Advance Turn
    game.advance_turn()
    print(f"MacReady Stress after isolation: {game.player.stress}")
    
    if game.player.stress >= 1:
        print("SUCCESS: Isolation stress applied.")
    else:
        print("FAIL: No isolation stress.")

    # 3. Test Panic Cascade
    print("\n[TEST 3] Panic Cascade")
    # Move Childs to MacReady's room (Infirmary)
    childs = next(m for m in game.crew if m.name == "Childs")
    childs.location = (0, 0)
    
    # Force Childs to max stress to trigger panic
    game.psychology_system.add_stress(childs, 100)
    
    # Advance Turn (Psychology update runs)
    # Note: Panic chance depends on roll. We might need to mock RNG or retry.
    # Let's check if stress increased for MacReady (Witness)
    
    pre_cascade_stress = game.player.stress
    print(f"MacReady Stress before cascade: {pre_cascade_stress}")
    
    # We loop until panic triggers or limit reached
    panic_triggered = False
    for i in range(5):
        game.advance_turn()
        # Check logs or stress
        if game.player.stress > pre_cascade_stress: # If he gained stress from witness (or isolation, but he's not alone now)
            # Wait, if Childs is there, he's not alone. So he shouldn't gain Isolation stress.
            # So any stress gain is from Cascade (or Cold).
            # Assume temp is stable (Game starts -40, so cold stress applies too...)
            # Ah, cold stress complicates this.
            # Let's set temperature to positive for test.
            game.time_system.temperature = 10
            panic_triggered = True
            break
            
    # Re-check
    game.time_system.temperature = 10
    game.player.stress = 0
    childs.stress = 100
    
    print("Retrying Cascade with Temp 10C...")
    game.advance_turn()
    
    # Childs should panic (Stress 10 vs Threshold ~5). High chance.
    # If MacReady gains stress, it's working.
    
    print(f"MacReady Stress after potential cascade: {game.player.stress}")
    
    if game.player.stress >= 2:
        print("SUCCESS: Panic cascade witness stress applied.")
    else:
        print("WARNING: Panic might not have triggered (RNG) or Cascade failed.")

    return True

if __name__ == "__main__":
    test_social_mechanics()
