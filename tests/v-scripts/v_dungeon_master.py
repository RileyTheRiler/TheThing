"""
Verification Script for Agent 6: The Dungeon Master (Architect Version)
Tests Event-Driven Weather System, Sabotage Events, and Room States.
"""
import sys
import os

# Standard Architect Verification Import (Standardized pathing)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.core.event_system import event_bus, EventType, GameEvent
from src.systems.architect import RandomnessEngine
from src.engine import GameState

def test_event_driven_integration():
    """Verify that systems react to TURN_ADVANCE via EventBus."""
    print("\n=== TESTING ARCHITECT INTEGRATION ===")
    
    game = GameState(seed=42) # Deterministic seed
    
    # 1. Test Weather subscription
    initial_intensity = game.weather.storm_intensity
    print(f"Initial Storm Intensity: {initial_intensity}")
    
    # Emit turn advance manually to test reactivity
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {
        "game_state": game,
        "rng": game.rng
    }))
    
    print(f"After Turn 1 Storm Intensity: {game.weather.storm_intensity}")
    assert game.weather.storm_intensity != initial_intensity, "Weather did not react to TURN_ADVANCE"
    print("✓ Weather System reacts to EventBus")
    
    # 2. Test Sabotage -> RoomState signal
    print(f"Rec Room initially dark? {game.room_states.has_state('Rec Room', 'DARK')}")
    game.sabotage.trigger_power_outage(game)
    
    # RoomState should have reacted to POWER_FAILURE
    from src.systems.room_state import RoomState
    assert game.room_states.has_state('Rec Room', RoomState.DARK), "RoomState did not react to POWER_FAILURE"
    print("✓ RoomStateManager reacts to Sabotage signals")
    
    # 3. Test RNG Determinism
    game2 = GameState(seed=42)
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {
        "game_state": game2,
        "rng": game2.rng
    }))
    
    assert game.weather.storm_intensity == game2.weather.storm_intensity, "RNG not deterministic!"
    print("✓ RandomnessEngine provides cross-system determinism")
    
    return True

if __name__ == "__main__":
    try:
        if test_event_driven_integration():
            print("\nVERIFICATION SUCCESSFUL")
            sys.exit(0)
    except Exception as e:
        print(f"\nVERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
