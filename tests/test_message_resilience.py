import sys
import os

# Add src directory to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_path = os.path.join(project_root, "src")
for path in (project_root, src_path):
    if path not in sys.path:
        sys.path.insert(0, path)

from engine import GameState
from systems.architect import Verbosity
from ui.message_reporter import emit_combat, emit_message, emit_warning
from core.event_system import event_bus, EventType, GameEvent

class MockCRT:
    def __init__(self):
        self.outputs = []
        self.warnings = []

    def output(self, text, crawl=False):
        self.outputs.append(text)
        print(f"[CRT] {text}")

    def warning(self, text):
        self.warnings.append(text)
        print(f"[CRT-WARN] {text}")

def test_combat_batching():
    # Clear event bus to avoid interference from previous tests
    if hasattr(event_bus, 'clear'):
        event_bus.clear()
    print("\n--- Testing Combat Batching ---")
    mock_crt = MockCRT()
    game = GameState()
    game.crt = mock_crt
    game.reporter.crt = mock_crt
    game.verbosity = Verbosity.STANDARD

    # Simulate 5 identical attacks
    for _ in range(5):
        emit_combat(attacker="MacReady", target="Thing-Childs", action="attacks", damage=10, result="Hit")
    
    # Should not have output yet (batched)
    assert len(mock_crt.outputs) == 0
    
    # Flush
    game.advance_turn()
    
    # Should have 1 coalesced output (plus any random turn events)
    assert any("MacReady attacks Thing-Childs 5 times" in out for out in mock_crt.outputs)
    assert any("total 50 damage" in out for out in mock_crt.outputs)
    print("Combat Batching Test Passed!")

def test_movement_batching():
    if hasattr(event_bus, 'clear'):
        event_bus.clear()
    print("\n--- Testing Movement Batching ---")
    mock_crt = MockCRT()
    game = GameState()
    game.crt = mock_crt
    game.reporter.crt = mock_crt
    game.verbosity = Verbosity.VERBOSE

    # Simulate multiple NPCs moving to same room
    actors = ["Childs", "Bennings", "Copper", "Clark", "Garry"]
    for actor in actors:
        event_bus.emit(GameEvent(EventType.MOVEMENT, {
            'actor': actor,
            'destination': 'Rec Room'
        }))
    
    # Reporter flushes movement at 5 events automatically
    assert len(mock_crt.outputs) == 1
    assert "Childs, Bennings and 3 others moved to Rec Room." in mock_crt.outputs[0]
    print("Movement Batching Test Passed!")

def test_verbosity_filtering():
    if hasattr(event_bus, 'clear'):
        event_bus.clear()
    print("\n--- Testing Verbosity Filtering ---")
    mock_crt = MockCRT()
    game = GameState()
    game.crt = mock_crt
    game.reporter.crt = mock_crt
    
    # Minimal Verbosity
    game.verbosity = Verbosity.MINIMAL
    print("Level: MINIMAL")
    emit_message("Standard message") # Should be hidden
    emit_warning("Critical warning") # Should be shown
    event_bus.emit(GameEvent(EventType.MOVEMENT, {'actor': 'Nauls', 'destination': 'Kitchen'})) # Should be hidden
    
    assert len(mock_crt.outputs) == 0
    assert len(mock_crt.warnings) == 1
    
    # Standard Verbosity
    game.verbosity = Verbosity.STANDARD
    mock_crt.outputs = []
    print("Level: STANDARD")
    emit_message("Standard message") # Should be shown
    event_bus.emit(GameEvent(EventType.MOVEMENT, {'actor': 'Nauls', 'destination': 'Kitchen'})) # Should be hidden
    
    assert len(mock_crt.outputs) == 1
    
    # Verbose
    game.verbosity = Verbosity.VERBOSE
    mock_crt.outputs = []
    game.reporter.flush() # Clear batches
    print("Level: VERBOSE")
    event_bus.emit(GameEvent(EventType.MOVEMENT, {'actor': 'Nauls', 'destination': 'Kitchen'}))
    game.reporter.flush()
    
    assert len(mock_crt.outputs) == 1
    assert "Nauls moved to Kitchen." in mock_crt.outputs[0]
    
    print("Verbosity Filtering Test Passed!")

if __name__ == "__main__":
    try:
        test_combat_batching()
        test_movement_batching()
        test_verbosity_filtering()
        print("\nALL RESILIENCE TESTS PASSED!")
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAN ERROR OCCURRED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
