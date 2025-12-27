"""
Verification script for Agent 2: The Social Psychologist
Tests LynchMobSystem and DialogueManager functionality.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.systems.social import TrustMatrix, LynchMobSystem, DialogueManager
from src.systems.architect import RandomnessEngine, GameMode
from src.engine import CrewMember

def test_lynch_mob_formation():
    print("Testing Lynch Mob Formation...")
    
    # Create test crew
    crew = [
        CrewMember("MacReady", "Pilot", "Cynical"),
        CrewMember("Norris", "Geologist", "Nervous"),
        CrewMember("Childs", "Mechanic", "Aggressive")
    ]
    
    for m in crew:
        m.location = (5, 5)
    
    # Initialize trust system
    trust = TrustMatrix(crew)
    
    # Manually lower Norris's trust
    for member in crew:
        if member.name != "Norris":
            trust.update_trust(member.name, "Norris", -40)
    
    avg_trust = trust.get_average_trust("Norris")
    print(f"  Norris average trust: {avg_trust:.1f}")
    
    # Initialize lynch mob system
    lynch_mob = LynchMobSystem(trust)
    
    # Check for mob formation
    target = lynch_mob.check_thresholds(crew)
    
    if target and target.name == "Norris":
        print(f"  [PASS] Lynch mob formed against {target.name}")
        assert lynch_mob.active_mob == True
        assert lynch_mob.target == target
    else:
        print(f"  [FAIL] Lynch mob should have formed against Norris")
        sys.exit(1)

def test_dialogue_manager():
    print("\nTesting DialogueManager...")
    
    # Create test crew
    crew = [
        CrewMember("MacReady", "Pilot", "Cynical"),
        CrewMember("Childs", "Mechanic", "Aggressive")
    ]
    
    # Mock game state
    class MockGameState:
        def __init__(self):
            self.rng = RandomnessEngine(42)
            self.trust_system = TrustMatrix(crew)
            self.mode = GameMode.INVESTIGATIVE
    
    game_state = MockGameState()
    dialogue_mgr = DialogueManager()
    
    # Test hostile dialogue (low trust)
    game_state.trust_system.update_trust("MacReady", "Childs", -40)
    response = dialogue_mgr.get_response(crew[0], "Childs", game_state)
    print(f"  Hostile dialogue: '{response}'")
    assert any(word in response.lower() for word in ["back", "trust", "strange", "watching"])
    
    # Test friendly dialogue (high trust)
    game_state.trust_system.update_trust("MacReady", "Childs", 50)
    response = dialogue_mgr.get_response(crew[0], "Childs", game_state)
    print(f"  Friendly dialogue: '{response}'")
    
    print("  [PASS] DialogueManager works")

def test_lynch_mob_disbanding():
    print("\nTesting Lynch Mob Disbanding...")
    
    crew = [
        CrewMember("MacReady", "Pilot", "Cynical"),
        CrewMember("Norris", "Geologist", "Nervous")
    ]
    
    trust = TrustMatrix(crew)
    lynch_mob = LynchMobSystem(trust)
    
    # Force mob formation
    for member in crew:
        if member.name != "Norris":
            trust.update_trust(member.name, "Norris", -40)
    
    lynch_mob.check_thresholds(crew)
    assert lynch_mob.active_mob == True
    
    # Kill the target
    crew[1].is_alive = False
    
    # Check should disband the mob
    lynch_mob.check_thresholds(crew)
    
    if not lynch_mob.active_mob:
        print("  [PASS] Mob disbanded when target died")
    else:
        print("  [FAIL] Mob should disband when target dies")
        sys.exit(1)

if __name__ == "__main__":
    try:
        test_lynch_mob_formation()
        test_dialogue_manager()
        test_lynch_mob_disbanding()
        print("\n*** ALL SOCIAL PSYCHOLOGIST TESTS PASSED ***")
    except Exception as e:
        print(f"\n[FAIL] Social tests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
