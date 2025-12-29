import sys
import os
import pytest
from unittest.mock import MagicMock

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from core.event_system import event_bus, EventType, GameEvent
from systems.social import TrustMatrix
from systems.psychology import PsychologySystem
from entities.crew_member import CrewMember
from systems.architect import RandomnessEngine

@pytest.fixture
def rng():
    return RandomnessEngine(seed=42)

@pytest.fixture
def sample_crew():
    return [
        CrewMember(name="MacReady", role="Pilot", behavior_type="cautious"),
        CrewMember(name="Childs", role="Mechanic", behavior_type="aggressive"),
        CrewMember(name="Garry", role="Commander", behavior_type="cautious")
    ]

@pytest.fixture
def mock_game_state(rng, sample_crew):
    class MockGameState:
        def __init__(self):
            self.crew = sample_crew
            self.rng = rng
            self.paranoia_level = 0
            self.player = sample_crew[0]
            self.station_map = MagicMock()
            self.station_map.get_room_name.return_value = "Rec Room"
            self.room_states = MagicMock()
            self.room_states.get_paranoia_modifier.return_value = 0
            self.trust_system = TrustMatrix(sample_crew)
    return MockGameState()

def test_trust_threshold_events(mock_game_state):
    tm = mock_game_state.trust_system
    events = []
    
    def on_event(event):
        events.append(event)
    
    event_bus.subscribe(EventType.TRUST_THRESHOLD_CROSSED, on_event)
    
    # Initial trust is 50. HOSTILE_THRESHOLD is 40.
    # Drop trust of MacReady for everyone
    for observer in tm.matrix:
        if observer != "MacReady":
            tm.update_trust(observer, "MacReady", -11) # 50 -> 39
            
    # Need to call check_for_lynch_mob to trigger the event detection logic
    tm.check_for_lynch_mob(mock_game_state.crew, mock_game_state)
    
    assert len(events) > 0
    crossed_event = next((e for e in events if e.payload["target"] == "MacReady" and e.payload["threshold"] == 40), None)
    assert crossed_event is not None
    assert crossed_event.payload["direction"] == "DOWN"
    assert crossed_event.payload["new_value"] < 40
    
    event_bus.unsubscribe(EventType.TRUST_THRESHOLD_CROSSED, on_event)

def test_paranoia_threshold_events(mock_game_state):
    ps = PsychologySystem()
    events = []
    
    def on_event(event):
        events.append(event)
    
    event_bus.subscribe(EventType.PARANOIA_THRESHOLD_CROSSED, on_event)
    
    # CONCERNED_THRESHOLD = 33
    mock_game_state.paranoia_level = 32
    ps.prev_paranoia_level = 32
    
    # Trigger turn advance (paranoia + 1)
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": mock_game_state}))
    
    assert len(events) > 0
    crossed_event = next((e for e in events if e.payload["threshold"] == 33), None)
    assert crossed_event is not None
    assert crossed_event.payload["direction"] == "UP"
    assert crossed_event.payload["new_value"] == 33
    
    event_bus.unsubscribe(EventType.PARANOIA_THRESHOLD_CROSSED, on_event)

def test_lynch_mob_parameterized_trigger(mock_game_state):
    tm = mock_game_state.trust_system
    events = []
    
    def on_event(event):
        events.append(event)
    
    event_bus.subscribe(EventType.LYNCH_MOB_TRIGGER, on_event)
    
    # LYNCH_THRESHOLD = 20
    for observer in tm.matrix:
        if observer != "Garry":
            # Set trust to exactly 21
            tm.matrix[observer]["Garry"] = 21
            
    # One more drop to 19
    for observer in tm.matrix:
        if observer != "Garry":
            tm.update_trust(observer, "Garry", -2)
            
    tm.check_for_lynch_mob(mock_game_state.crew, mock_game_state)
    
    assert len(events) > 0
    lynch_event = next((e for e in events if e.payload["target"] == "Garry"), None)
    assert lynch_event is not None
    assert lynch_event.payload["average_trust"] < 20
    
    event_bus.unsubscribe(EventType.LYNCH_MOB_TRIGGER, on_event)

def test_trust_decay_from_paranoia(mock_game_state):
    tm = mock_game_state.trust_system
    # Initial trust 50
    # Paranoia level 40 -> decay_amount = 40 // 20 = 2
    mock_game_state.paranoia_level = 40
    
    # Advance turn to trigger decay
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": mock_game_state}))
    
    # MacReady trust for Childs should be 50 - 2 = 48
    assert tm.get_trust("MacReady", "Childs") == 48
