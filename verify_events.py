import sys
import os

# Add root to path so we can import src.x.y
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.event_system import event_bus, EventType, GameEvent
from engine import GameState, CrewMember
from systems.psychology import PsychologySystem
from systems.missionary import MissionarySystem

def test_event_handling():
    print("Testing Event Bus & System Integration...")
    
    # Setup
    game = GameState()
    
    # Verify Systems initialized in GameState
    print(f"Psychology System present: {hasattr(game, 'psychology_system')}")
    print(f"Missionary System present: {hasattr(game, 'missionary_system')}")
    
    # Test 1: Psychology Update via Event
    print("\n--- TEST: Psychology Event Trigger ---")
    blair = next(m for m in game.crew if m.name == "Blair")
    game.time_system.temperature = -20 # Cold!
    print(f"Temp set to {game.time_system.temperature}. Blair Stress: {blair.stress}")
    
    # Emit Advance Turn
    # Note: Event bus assumes RNG is in payload for some listeners
    print("Emitting TURN_ADVANCE...")
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": game, "rng": game.rng}))
    
    # Check if Stress Increased (Logic: abs(-20)//20 = 1 stress)
    print(f"Blair Stress after event: {blair.stress}")
    if blair.stress > 0:
        print("PASS: Psychology responded to event.")
    else:
        print("FAIL: Stress did not increase.")

    # Test 2: Missionary Update via Event
    print("\n--- TEST: Missionary Event Trigger ---")
    # Infect someone
    norris = next(m for m in game.crew if m.name == "Norris")
    norris.is_infected = True
    norris.mask_integrity = 100
    print(f"Norris infected. Mask: {norris.mask_integrity}")
    
    # Force conditions for decay (High paranoia?)
    game.paranoia_level = 80
    
    print("Emitting TURN_ADVANCE...")
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": game, "rng": game.rng}))
    
    print(f"Norris Mask after event: {norris.mask_integrity}")
    if norris.mask_integrity < 100:
        print("PASS: Missionary system processed decay.")
    else:
        print("FAIL: Mask integrity static (Did agent run?).")

if __name__ == "__main__":
    test_event_handling()
