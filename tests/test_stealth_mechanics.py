import pytest
from unittest.mock import MagicMock
from entities.crew_member import CrewMember, StealthPosture
from systems.stealth import StealthSystem
from core.event_system import GameEvent, EventType, event_bus
from core.resolution import Attribute, Skill
from systems.architect import RandomnessEngine

@pytest.fixture
def game_state():
    gs = MagicMock()
    gs.player = CrewMember("MacReady", "Pilot", "Cynical")
    gs.player.location = (5, 5)
    gs.player.attributes = {Attribute.PROWESS: 2}
    gs.player.skills = {Skill.STEALTH: 2}
    
    npc = CrewMember("Childs", "Mechanic", "Aggressive")
    npc.location = (5, 5)
    npc.is_infected = True
    npc.is_alive = True
    npc.attributes = {Attribute.LOGIC: 3}
    npc.skills = {Skill.OBSERVATION: 1}
    npc.get_noise_level = lambda: 0
    npc.get_thermal_detection_pool = lambda: 1
    
    gs.crew = [gs.player, npc]
    
    gs.station_map = MagicMock()
    gs.station_map.get_room_name.return_value = "Rec Room"
    gs.station_map.get_hiding_spot.return_value = None
    
    gs.room_states = MagicMock()
    gs.room_states.has_state.return_value = False # Light by default
    mod = MagicMock()
    mod.stealth_detection = 0.0
    gs.room_states.get_resolution_modifiers.return_value = mod
    gs.room_states.adjust_pool = lambda base, mod: base + (mod or 0)
    
    gs.rng = RandomnessEngine(seed=42)
    return gs

def test_stealth_detection_standing_light(game_state):
    """Test detection when standing in a bright room."""
    system = StealthSystem()
    
    # Mock RNG for deterministic results
    # Player Pool: 2 + 2 = 4
    # NPC Pool: 3 + 1 = 4
    # With seed 42, let's see what happens.
    
    reports = []
    def on_report(event):
        reports.append(event)
    
    event_bus.subscribe(EventType.STEALTH_REPORT, on_report)
    
    event = GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state, "rng": game_state.rng})
    system.on_turn_advance(event)
    
    assert len(reports) > 0
    report = reports[0].payload
    assert "outcome" in report
    
    event_bus.unsubscribe(EventType.STEALTH_REPORT, on_report)

def test_stealth_crouching_dark(game_state):
    """Test stealth bonus from crouching and darkness."""
    system = StealthSystem()
    game_state.player.stealth_posture = StealthPosture.CROUCHING
    game_state.room_states.has_state.return_value = True # DARK
    
    reports = []
    def on_report(event):
        reports.append(event)
    
    event_bus.subscribe(EventType.STEALTH_REPORT, on_report)
    
    # Subject Pool: 2 (Prowess) + 2 (Stealth) + 1 (Crouching) + 2 (Dark) = 7
    # Observer Pool: 3 (Logic) + 1 (Observation) - 2 (Dark) = 2
    # Player should almost certainly evade.
    
    event = GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state, "rng": game_state.rng})
    system.on_turn_advance(event)
    
    assert len(reports) > 0
    report = reports[0].payload
    assert report["outcome"] == "evaded"
    assert report["player_successes"] >= 0
    
    event_bus.unsubscribe(EventType.STEALTH_REPORT, on_report)

def test_perception_event_emitted(game_state):
    """Verify PERCEPTION_EVENT is emitted."""
    system = StealthSystem()

    # Force detection branch
    game_state.rng.random_float = lambda: 0.0
    
    perception_events = []
    def on_perception(event):
        perception_events.append(event)
    
    event_bus.subscribe(EventType.PERCEPTION_EVENT, on_perception)
    
    event = GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state, "rng": game_state.rng})
    system.on_turn_advance(event)
    
    assert len(perception_events) == 1
    payload = perception_events[0].payload
    assert "player_successes" in payload
    assert payload.get("observer_pool") is not None
    
    event_bus.unsubscribe(EventType.PERCEPTION_EVENT, on_perception)
