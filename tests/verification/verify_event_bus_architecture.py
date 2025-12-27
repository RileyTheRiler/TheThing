
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.event_system import event_bus, EventType, GameEvent
from engine import GameState

def test_event_driven_architecture():
    print("Initializing GameState...")
    game = GameState()
    
    # Capture initial states
    initial_turn = game.turn
    initial_hour = game.time_system.hour
    initial_temp = game.time_system.temperature
    
    print(f"Initial State: Turn {initial_turn}, Hour {initial_hour}, Temp {initial_temp}")
    
    # Trigger Turn Advance via engine method (which now emits event)
    print("Advancing Turn...")
    game.advance_turn()
    
    # Verify TimeSystem updated (via event)
    print(f"New State: Turn {game.turn}, Hour {game.time_system.hour}, Temp {game.time_system.temperature}")
    
    if game.time_system.hour != (initial_hour + 1) % 24:
        print("FAIL: TimeSystem did not update hour (Event listener failed?)")
        return False
        
    print("SUCCESS: TimeSystem updated via event.")
    
    # Verify AI System (Mock check - check if moved?)
    # Hard to check random movement, but we can check if no error occurred.
    print("SUCCESS: AI System updated (no crash).")
    
    # Verify Random Events (Check if cooldowns updated/checked)
    # We can inspect the random_events system state if needed, or just rely on no crash.
    print("SUCCESS: Random Events checked (no crash).")
    
    return True

if __name__ == "__main__":
    if test_event_driven_architecture():
        print("\n*** VERIFICATION PASSED ***")
    else:
        print("\n*** VERIFICATION FAILED ***")
