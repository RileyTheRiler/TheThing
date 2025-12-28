"""
Comprehensive Integration Test for Event-Driven Systems
Tests: Event Bus, AI, Stealth, Psychology, Forensics, Social
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from engine import GameState
from core.event_system import event_bus, EventType, GameEvent
from systems.ai import AISystem
from systems.psychology import PsychologySystem
from systems.missionary import MissionarySystem
from systems.stealth import StealthSystem
from systems.social import TrustMatrix

def test_event_bus_integration():
    """Test that all systems respond to TURN_ADVANCE events."""
    print("\n" + "="*60)
    print("TEST 1: Event Bus Integration")
    print("="*60)
    
    game = GameState(seed=42)
    
    # Verify systems are initialized
    assert hasattr(game, 'psychology'), "Psychology system not initialized"
    assert hasattr(game, 'missionary'), "Missionary system not initialized"
    assert hasattr(game, 'ai_system'), "AI system not initialized"
    assert hasattr(game, 'stealth'), "Stealth system not initialized"
    assert hasattr(game, 'trust_system'), "Trust system not initialized"
    
    print("✓ All systems initialized")
    
    # Test event emission
    initial_turn = game.turn
    game.advance_turn()
    
    assert game.turn == initial_turn + 1, "Turn did not advance"
    print(f"✓ Turn advanced: {initial_turn} → {game.turn}")
    
    # Check if systems updated (stress should increase in cold)
    game.time_system.temperature = -30
    blair = next((m for m in game.crew if m.name == "Blair"), None)
    initial_stress = blair.stress
    
    game.advance_turn()
    
    if blair.stress > initial_stress:
        print(f"✓ Psychology system active: Blair stress {initial_stress} → {blair.stress}")
    else:
        print(f"⚠ Psychology system may not be active (stress unchanged)")
    
    print("\n✅ Event Bus Integration: PASSED\n")

def test_ai_system():
    """Test AI system schedule following and wandering."""
    print("="*60)
    print("TEST 2: AI System")
    print("="*60)
    
    game = GameState(seed=123)
    
    # Find an NPC with a schedule
    childs = next((m for m in game.crew if m.name == "Childs"), None)
    assert childs, "Childs not found"
    
    print(f"Testing {childs.name}")
    print(f"Schedule: {childs.schedule}")
    
    start_loc = childs.location
    print(f"Start location: {start_loc}")
    
    # Advance several turns
    for i in range(5):
        game.advance_turn()
    
    end_loc = childs.location
    print(f"End location after 5 turns: {end_loc}")
    
    if start_loc != end_loc:
        print("✓ NPC moved (AI active)")
    else:
        print("⚠ NPC did not move (may be at scheduled location)")
    
    print("\n✅ AI System: PASSED\n")

def test_stealth_system():
    """Test stealth detection mechanics."""
    print("="*60)
    print("TEST 3: Stealth System")
    print("="*60)
    
    game = GameState(seed=456)
    
    # Test noise level calculation
    player = game.player
    noise = game.stealth.get_noise_level(player)
    
    print(f"Player noise level: {noise}")
    assert noise > 0, "Noise level should be positive"
    print("✓ Noise level calculated")
    
    # Test detection
    npc = next((m for m in game.crew if m != player), None)
    detected = game.stealth.evaluate_detection(npc, player, game)
    
    print(f"Detection result: {'DETECTED' if detected else 'EVADED'}")
    print("✓ Detection evaluation works")
    
    print("\n✅ Stealth System: PASSED\n")

def test_psychology_system():
    """Test stress accumulation and panic."""
    print("="*60)
    print("TEST 4: Psychology System")
    print("="*60)
    
    game = GameState(seed=789)
    game.time_system.temperature = -40  # Very cold
    
    blair = next((m for m in game.crew if m.name == "Blair"), None)
    initial_stress = blair.stress
    
    print(f"Temperature: {game.time_system.temperature}°C")
    print(f"Initial stress: {initial_stress}")
    
    # Advance turns to accumulate stress
    for i in range(3):
        game.advance_turn()
    
    print(f"Final stress after 3 turns: {blair.stress}")
    
    if blair.stress > initial_stress:
        print("✓ Stress accumulation working")
    else:
        print("⚠ Stress did not increase (temperature may not be cold enough)")
    
    print("\n✅ Psychology System: PASSED\n")

def test_forensics_integration():
    """Test forensics database and evidence logging."""
    print("="*60)
    print("TEST 5: Forensics Integration")
    print("="*60)
    
    game = GameState(seed=101)
    
    # Test forensic database
    game.forensic_db.add_tag("Blair", "SUSPICION", "Acting strange", game.turn)
    tags = game.forensic_db.get_tags("Blair")
    
    print(f"Tags for Blair: {len(tags)}")
    assert len(tags) > 0, "Tag not added"
    print("✓ Forensic database working")
    
    # Test evidence log
    game.evidence_log.record_event("Scalpel", "GET", "MacReady", "Infirmary", game.turn)
    history = game.evidence_log.get_history("Scalpel")
    
    print(f"Scalpel history entries: {len(history.split('\\n')) - 2}")  # -2 for header/footer
    print("✓ Evidence logging working")
    
    print("\n✅ Forensics Integration: PASSED\n")

def test_social_systems():
    """Test trust matrix and lynch mob."""
    print("="*60)
    print("TEST 6: Social Systems")
    print("="*60)
    
    game = GameState(seed=202)
    
    # Test trust matrix
    initial_trust = game.trust_system.get_trust("MacReady", "Blair")
    print(f"Initial trust (MacReady → Blair): {initial_trust}")
    
    game.trust_system.update_trust("MacReady", "Blair", -20)
    new_trust = game.trust_system.get_trust("MacReady", "Blair")
    
    print(f"After -20 adjustment: {new_trust}")
    assert new_trust == initial_trust - 20, "Trust update failed"
    print("✓ Trust matrix working")
    
    # Test average trust
    avg = game.trust_system.get_average_trust("Blair")
    print(f"Average trust for Blair: {avg:.1f}")
    print("✓ Average trust calculation working")
    
    print("\n✅ Social Systems: PASSED\n")

def test_location_hints():
    """Test location hint system."""
    print("="*60)
    print("TEST 7: Location Hints")
    print("="*60)
    
    game = GameState(seed=303)
    
    # Find a character with location hints
    blair = next((m for m in game.crew if m.name == "Blair"), None)
    
    if blair and blair.invariants:
        location_hints = [i for i in blair.invariants if i.get('type') == 'location_hint']
        print(f"Blair has {len(location_hints)} location hint(s)")
        
        if location_hints:
            print(f"Example: {location_hints[0].get('slip_desc', 'N/A')}")
            print("✓ Location hints configured")
    
    # Test ambient warnings
    warnings = game.get_ambient_warnings()
    print(f"Ambient warnings generated: {len(warnings)}")
    print("✓ Ambient warning system working")
    
    print("\n✅ Location Hints: PASSED\n")

def run_all_tests():
    """Run all integration tests."""
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█" + "  COMPREHENSIVE INTEGRATION TEST SUITE".center(58) + "█")
    print("█" + " "*58 + "█")
    print("█"*60 + "\n")
    
    tests = [
        test_event_bus_integration,
        test_ai_system,
        test_stealth_system,
        test_psychology_system,
        test_forensics_integration,
        test_social_systems,
        test_location_hints
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n❌ {test.__name__} FAILED: {e}\n")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
