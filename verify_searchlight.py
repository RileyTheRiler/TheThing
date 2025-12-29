"""
Verification Script for Searchlight Harvest Hook
Tests: Memory theft during communion triggers stress in sensitive witnesses
"""

import sys
sys.path.insert(0, 'src')

from src.core.event_system import event_bus, EventType, GameEvent
from src.core.resolution import Attribute, Skill
from src.systems.missionary import MissionarySystem
from src.engine import GameState

def test_searchlight_harvest():
    """Test that communion triggers SEARCHLIGHT_HARVEST and affects sensitive characters."""
    print("\n=== TEST: Searchlight Harvest Hook ===")
    
    # Create game state
    game = GameState(seed=42)
    missionary = MissionarySystem()
    
    # Set up scenario: One infected, one target, one sensitive witness
    if len(game.crew) < 3:
        print("[SKIP] Not enough crew members for test")
        return
    
    agent = game.crew[0]
    target = game.crew[1]
    witness = game.crew[2]
    
    # Configure characters
    agent.is_infected = True
    agent.is_revealed = False
    agent.location = (5, 5)
    
    target.is_infected = False
    target.location = (5, 5)  # Same location as agent
    
    witness.is_infected = False
    witness.location = (5, 5)  # Same room - will witness psychically
    witness.attributes[Attribute.LOGIC] = 5  # High logic = sensitive
    initial_stress = witness.stress
    
    print(f"  Setup:")
    print(f"    Agent: {agent.name} (infected)")
    print(f"    Target: {target.name} (human)")
    print(f"    Witness: {witness.name} (Logic={witness.attributes.get(Attribute.LOGIC, 1)}, Stress={initial_stress})")
    
    # Track events
    harvest_events = []
    def on_harvest(event):
        harvest_events.append(event)
    event_bus.subscribe(EventType.SEARCHLIGHT_HARVEST, on_harvest)
    
    # Force communion
    missionary.perform_communion(agent, target, game)
    
    # Check results
    if harvest_events:
        print(f"[PASS] SEARCHLIGHT_HARVEST event emitted")
        print(f"  Agent: {harvest_events[0].payload.get('agent_name')}")
        print(f"  Target: {harvest_events[0].payload.get('target_name')}")
        
        # Check if witness gained stress
        if witness.stress > initial_stress:
            print(f"[PASS] Sensitive witness gained stress (+{witness.stress - initial_stress})")
        else:
            print(f"[FAIL] Sensitive witness did not gain stress")
            
        # Check if target was infected
        if target.is_infected:
            print(f"[PASS] Target successfully infected")
        else:
            print(f"[FAIL] Target not infected")
            
        # Check if agent's slip chances reduced
        slip_reduced = False
        for inv in agent.invariants:
            if 'slip_chance' in inv and inv['slip_chance'] < 0.5:
                slip_reduced = True
                break
        if slip_reduced:
            print(f"[PASS] Agent's slip chances reduced (improved mimicry)")
        else:
            print(f"[INFO] No slip chance reduction detected (may not have invariants)")
    else:
        print("[FAIL] No SEARCHLIGHT_HARVEST events emitted")
    
    # Cleanup
    event_bus.clear()

def test_psychic_tremor_sensitivity():
    """Test that only sensitive characters react to harvest."""
    print("\n=== TEST: Psychic Tremor Sensitivity ===")
    
    game = GameState(seed=42)
    
    if len(game.crew) < 3:
        print("[SKIP] Not enough crew members")
        return
    
    # Set up two witnesses: one sensitive, one not
    sensitive = game.crew[0]
    insensitive = game.crew[1]
    
    sensitive.location = (5, 5)
    sensitive.attributes[Attribute.LOGIC] = 5
    sensitive.stress = 0
    
    insensitive.location = (5, 5)
    insensitive.attributes[Attribute.LOGIC] = 1
    insensitive.stress = 0
    
    print(f"  Sensitive: {sensitive.name} (Logic={sensitive.attributes.get(Attribute.LOGIC)})")
    print(f"  Insensitive: {insensitive.name} (Logic={insensitive.attributes.get(Attribute.LOGIC)})")
    
    # Emit harvest event manually
    event_bus.emit(GameEvent(EventType.SEARCHLIGHT_HARVEST, {
        "agent_name": "TestAgent",
        "target_name": "TestTarget",
        "location": (5, 5),
        "game_state": game
    }))
    
    # Check results
    if sensitive.stress > 0:
        print(f"[PASS] Sensitive character gained stress ({sensitive.stress})")
    else:
        print(f"[FAIL] Sensitive character did not gain stress")
        
    if insensitive.stress == 0:
        print(f"[PASS] Insensitive character unaffected")
    else:
        print(f"[FAIL] Insensitive character gained stress ({insensitive.stress})")
    
    # Cleanup
    event_bus.clear()

if __name__ == "__main__":
    print("="*40)
    print("  SEARCHLIGHT HARVEST VERIFICATION")
    print("="*40)
    
    try:
        test_searchlight_harvest()
        test_psychic_tremor_sensitivity()
        
        print("\n" + "="*40)
        print("VERIFICATION COMPLETE")
        print("="*40)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
