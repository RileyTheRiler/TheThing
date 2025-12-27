import pytest
from unittest.mock import MagicMock, patch
from src.engine import GameState
from src.core.event_system import event_bus, EventType, GameEvent
from src.systems.missionary import MissionarySystem
from src.systems.psychology import PsychologySystem
from src.systems.sabotage import SabotageManager
from src.systems.persistence import SaveManager

@pytest.fixture
def clean_event_bus():
    """Ensure event bus is clean for tests."""
    original_subscribers = event_bus._subscribers.copy()
    event_bus._subscribers = {}
    yield event_bus
    event_bus._subscribers = original_subscribers

@pytest.fixture
def game_state(clean_event_bus):
    """Create a GameState instance for testing."""
    gs = GameState()
    gs.time_system = MagicMock() # Mock time system to avoid side effects
    return gs

def test_turn_advance_emission(game_state, clean_event_bus):
    """Test that advance_turn emits TURN_ADVANCE event."""
    subscriber = MagicMock()
    clean_event_bus.subscribe(EventType.TURN_ADVANCE, subscriber)
    
    game_state.advance_turn()
    
    assert subscriber.called
    event = subscriber.call_args[0][0]
    assert event.type == EventType.TURN_ADVANCE
    assert event.payload["game_state"] == game_state
    assert event.payload["rng"] == game_state.rng
    assert "turn_inventory" in event.payload

def test_paranoia_update_via_event(game_state, clean_event_bus):
    """Test that PsychologySystem updates paranoia via event."""
    # Setup PsychologySystem
    psych = PsychologySystem()
    game_state.paranoia_level = 10
    
    # Emit TURN_ADVANCE
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state}))
    
    # Check paranoia increased
    assert game_state.paranoia_level == 11
    
    psych.cleanup()

def test_slipped_vapor_reset_via_event(game_state, clean_event_bus):
    """Test that MissionarySystem resets slipped_vapor via event."""
    # Setup MissionarySystem
    miss = MissionarySystem()
    for member in game_state.crew:
        member.slipped_vapor = True
    
    # Emit TURN_ADVANCE
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state}))
    
    # Check all members reset
    for member in game_state.crew:
        assert member.slipped_vapor is False
        
    miss.cleanup()

def test_rescue_timer_update_via_event(game_state, clean_event_bus):
    """Test that SabotageManager updates rescue timer via event."""
    # Setup SabotageManager
    sab = SabotageManager()
    game_state.rescue_signal_active = True
    game_state.rescue_turns_remaining = 10
    game_state.reporter = MagicMock()
    
    # Emit TURN_ADVANCE manual
    # Note: SabotageManager expects 'turn_inventory' in payload if it updates it, 
    # but the rescue timer logic is independent of inventory.
    # However, existing sabotage.on_turn_advance updates inventory if present.
    payload = {"game_state": game_state, "turn_inventory": {}}
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, payload))
    
    assert game_state.rescue_turns_remaining == 9
    
    # Test 5 turns remaining warning
    game_state.rescue_turns_remaining = 6
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, payload))
    assert game_state.rescue_turns_remaining == 5
    game_state.reporter.report_event.assert_called_with("RADIO", "Rescue ETA updated: 5 hours out.", priority=True)
    
    sab.cleanup()

def test_autosave_trigger_via_event(game_state, clean_event_bus):
    """Test that SaveManager triggers autosave via event."""
    # Setup SaveManager with mock
    save_manager = SaveManager()
    save_manager.save_game = MagicMock()
    
    game_state.turn = 5 # Should trigger autosave (turn % 5 == 0)
    
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state}))
    
    save_manager.save_game.assert_called_with(game_state, "autosave")
    
    save_manager.cleanup()
