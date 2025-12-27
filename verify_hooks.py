"""
Verification Script for Inter-Agent Hooks
Tests: Biological Slip, Lynch Mob, Forensic Contract
"""

import sys
sys.path.insert(0, 'src')

from src.core.event_system import event_bus, EventType, GameEvent
from src.core.resolution import Attribute, Skill
from src.systems.architect import RandomnessEngine
from src.systems.social import TrustMatrix
from src.systems.missionary import MissionarySystem
from src.engine import CrewMember, GameState

def test_biological_slip():
    """Test that infected characters emit BIOLOGICAL_SLIP events in cold."""
    print("\n=== TEST 1: Biological Slip Hook ===")
    
    # Create a minimal game state
    game = GameState(seed=42)
    
    # Find an infected character or infect one
    test_char = game.crew[0]
    test_char.is_infected = True
    test_char.mask_integrity = 30  # Low integrity = high slip chance
    
    # Track events
    slip_events = []
    def on_slip(event):
        slip_events.append(event)
    event_bus.subscribe(EventType.BIOLOGICAL_SLIP, on_slip)
    
    # Set cold temperature
    game.time_system.temperature = -30
    
    # Advance turn (should trigger missionary system update)
    game.advance_turn()
    
    # Check if slip event was emitted
    if slip_events:
        print(f"[PASS] BIOLOGICAL_SLIP event emitted for {slip_events[0].payload.get('character_name')}")
        print(f"  Slip type: {slip_events[0].payload.get('type')}")
        
        # Check if flag was set
        if test_char.slipped_vapor:
            print(f"[PASS] slipped_vapor flag set on character")
        else:
            print(f"[FAIL] slipped_vapor flag NOT set")
    else:
        print("[FAIL] No BIOLOGICAL_SLIP events emitted (may be due to RNG)")
    
    # Cleanup
    event_bus.clear()

def test_lynch_mob():
    """Test that low trust triggers LYNCH_MOB_TRIGGER event."""
    print("\n=== TEST 2: Lynch Mob Hook ===")
    
    game = GameState(seed=42)
    
    # Track events
    lynch_events = []
    def on_lynch(event):
        lynch_events.append(event)
    event_bus.subscribe(EventType.LYNCH_MOB_TRIGGER, on_lynch)
    
    # Drop trust for one character below threshold
    target = game.crew[1]
    for observer in game.crew:
        if observer != target:
            game.trust_system.update_trust(observer.name, target.name, -50)
    
    # Check average trust
    avg = game.trust_system.get_average_trust(target.name)
    print(f"  {target.name} average trust: {avg:.1f}")
    
    # Trigger lynch mob check
    game.trust_system.check_for_lynch_mob(game.crew, game)
    
    if lynch_events:
        print(f"[PASS] LYNCH_MOB_TRIGGER event emitted for {lynch_events[0].payload.get('target')}")
        print(f"  Average trust: {lynch_events[0].payload.get('average_trust'):.1f}")
    else:
        print("[FAIL] No LYNCH_MOB_TRIGGER events emitted")
    
    # Cleanup
    event_bus.clear()

def test_forensic_contract():
    """Test that EVIDENCE_TAGGED event affects trust."""
    print("\n=== TEST 3: Forensic Contract Hook ===")
    
    game = GameState(seed=42)
    
    target = game.crew[2]
    initial_trust = game.trust_system.get_average_trust(target.name)
    print(f"  {target.name} initial average trust: {initial_trust:.1f}")
    
    # Emit EVIDENCE_TAGGED event
    event_bus.emit(GameEvent(EventType.EVIDENCE_TAGGED, {
        "game_state": game,
        "target": target.name
    }))
    
    # Check if trust dropped
    new_trust = game.trust_system.get_average_trust(target.name)
    print(f"  {target.name} new average trust: {new_trust:.1f}")
    
    if new_trust < initial_trust:
        print(f"[PASS] Trust penalty applied (-{initial_trust - new_trust:.1f})")
    else:
        print("[FAIL] No trust penalty detected")
    
    # Cleanup
    event_bus.clear()

def test_vapor_suppression():
    """Test that slipped_vapor flag suppresses [VAPOR] tag."""
    print("\n=== TEST 4: Vapor Suppression ===")
    
    game = GameState(seed=42)
    game.time_system.temperature = -30
    
    # Create infected character
    test_char = game.crew[0]
    test_char.is_infected = True
    test_char.slipped_vapor = True  # Manually set flag
    
    # Get dialogue
    dialogue = test_char.get_dialogue(game)
    
    if "[NO VAPOR]" in dialogue:
        print(f"[PASS] Vapor suppressed for infected character")
        print(f"  Dialogue: {dialogue}")
    else:
        print(f"[FAIL] Vapor NOT suppressed")
        print(f"  Dialogue: {dialogue}")

if __name__ == "__main__":
    print("="*40)
    print("  INTER-AGENT HOOKS VERIFICATION")
    print("="*40)
    
    try:
        test_biological_slip()
        test_lynch_mob()
        test_forensic_contract()
        test_vapor_suppression()
        
        print("\n" + "="*40)
        print("VERIFICATION COMPLETE")
        print("="*40)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
