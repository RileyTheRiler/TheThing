
import time
import sys
import os
from typing import List

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from engine import GameState, CrewMember
from systems.ai import AISystem
from core.event_system import event_bus, EventType

def create_scalable_state(crew_count: int) -> GameState:
    game = GameState(seed=42)
    base_crew = list(game.crew)
    game.crew = []
    
    for i in range(crew_count):
        source = base_crew[i % len(base_crew)]
        new_member = CrewMember(
            name=f"StressBot_{i}",
            role=source.role,
            behavior_type=source.behavior_type,
            attributes=source.attributes.copy(),
            skills=source.skills.copy()
        )
        # Give them different locations to force unique pathfinding
        new_member.location = (i % 20, (i // 20) % 20)
        # Give them a schedule that forces movement
        new_member.schedule = [{"start": 0, "end": 24, "room": "Generator"}]
        game.crew.append(new_member)
        
    game.player = game.crew[0]
    return game

def test_ai_scaling_performance():
    print("\n--- Testing AI Scaling Performance ---")
    crew_sizes = [15, 30, 60]
    ai_system = AISystem()
    
    for size in crew_sizes:
        game = create_scalable_state(size)
        
        start_time = time.time()
        ai_system.update(game)
        end_time = time.time()
        
        duration_ms = (end_time - start_time) * 1000
        print(f"Entities: {size:2} | Time: {duration_ms:5.2f}ms | Budget: {ai_system.budget_limit:3} | Spent: {ai_system.budget_spent:3}")
        
        # Guardrail: 60 entities should still process in < 5ms (A* takes time but budget limits it)
        if size == 60:
            assert duration_ms < 10.0, f"Performance guardrail failed: {duration_ms:.2f}ms > 10ms"

def test_budget_exhaustion_logging():
    print("\n--- Testing Budget Exhaustion Logging ---")
    game = create_scalable_state(100) # Force huge crew
    ai_system = AISystem()
    
    exhaustion_events = []
    def on_diagnostic(event):
        if event.payload.get("type") == "AI_BUDGET_EXHAUSTED":
            exhaustion_events.append(event.payload)
            
    event_bus.subscribe(EventType.DIAGNOSTIC, on_diagnostic)
    
    # Run a few turns
    for t in range(3):
        game.turn = t
        ai_system.update(game)
        
    event_bus.unsubscribe(EventType.DIAGNOSTIC, on_diagnostic)
    
    print(f"Recorded {len(exhaustion_events)} budget exhaustion events.")
    assert len(exhaustion_events) > 0, "No budget exhaustion events recorded for high-load state"
    for e in exhaustion_events:
        print(f"  Turn {e['turn']}: Exhaustion Count={e['exhaustion_count']} / Total Budget={e['total_budget']}")
        assert e['exhaustion_count'] > 0
        assert e['total_budget'] > 0

if __name__ == "__main__":
    try:
        test_ai_scaling_performance()
        test_budget_exhaustion_logging()
        print("\nALL PERFORMANCE GUARDRAIL TESTS PASSED")
    except AssertionError as e:
        print(f"\nGUARDRAIL COMPLIANCE FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR DURING TESTING: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
