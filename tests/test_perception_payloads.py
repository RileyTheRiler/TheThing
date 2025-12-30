import pytest
from unittest.mock import MagicMock

from core.event_system import EventType, GameEvent, event_bus
from core.perception import normalize_perception_payload, severity_from_noise
from systems.stealth import StealthSystem
from entities.crew_member import CrewMember, StealthPosture
from core.resolution import Attribute, Skill
from systems.architect import RandomnessEngine


def test_severity_from_noise_thresholds():
    assert severity_from_noise(None) == "low"
    assert severity_from_noise(0) == "low"
    assert severity_from_noise(3) == "medium"
    assert severity_from_noise(5) == "medium"
    assert severity_from_noise(6) == "high"
    assert severity_from_noise(9) == "high"
    assert severity_from_noise(10) == "extreme"


@pytest.fixture
def game_state():
    gs = MagicMock()
    gs.player = CrewMember("MacReady", "Pilot", "Cynical")
    gs.player.location = (1, 1)
    gs.player.attributes = {Attribute.PROWESS: 2}
    gs.player.skills = {Skill.STEALTH: 2}

    npc = CrewMember("Childs", "Mechanic", "Aggressive")
    npc.location = (1, 1)
    npc.is_infected = True
    npc.is_alive = True
    npc.attributes = {Attribute.LOGIC: 3}
    npc.skills = {Skill.OBSERVATION: 1}

    gs.crew = [gs.player, npc]

    gs.station_map = MagicMock()
    gs.station_map.get_room_name.return_value = "Rec Room"
    gs.station_map.get_hiding_spot.return_value = None

    gs.room_states = MagicMock()
    gs.room_states.has_state.return_value = False
    modifier = MagicMock()
    modifier.stealth_detection = 0.0
    gs.room_states.get_resolution_modifiers.return_value = modifier

    gs.alert_system = None

    # Ensure ResolutionSystem math paths receive ints
    def mock_adjust_pool(base, mod):
        return base + (mod or 0)
    gs.room_states.adjust_pool = mock_adjust_pool

    gs.rng = RandomnessEngine(seed=1337)
    gs.rng.random_float = lambda: 0.0  # Force detection path to emit perception event
    return gs


def test_perception_event_normalized_payload(game_state):
    system = StealthSystem()

    perception_events = []

    def on_perception(event):
        perception_events.append(normalize_perception_payload(event.payload))

    event_bus.subscribe(EventType.PERCEPTION_EVENT, on_perception)

    event = GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state, "rng": game_state.rng})
    system.on_turn_advance(event)

    assert perception_events, "PERCEPTION_EVENT should be emitted"
    payload = perception_events[0]

    # Normalized fields
    assert payload["location"] == (1, 1)
    assert payload["room"] == "Rec Room"
    assert payload["noise_level"] is not None
    assert payload["severity"] in {"low", "medium", "high", "extreme"}
    assert payload.get("actor") == "MacReady"
    assert payload.get("observer") == "Childs"

    event_bus.unsubscribe(EventType.PERCEPTION_EVENT, on_perception)


def test_forensics_detection_logs(game_state):
    # Wire up a simple forensic db to the mocked state
    from systems.forensics import ForensicDatabase, EvidenceLog, ForensicsSystem

    game_state.forensic_db = ForensicDatabase()
    game_state.evidence_log = EvidenceLog()

    forensics_system = ForensicsSystem(rng=game_state.rng)

    # Emit a detection payload
    payload = normalize_perception_payload({
        "game_state": game_state,
        "room": "Rec Room",
        "location": (1, 1),
        "outcome": "detected",
        "player_ref": game_state.player,
        "opponent_ref": game_state.crew[1],
        "noise_level": 5,
    })

    event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, payload))

    # Ensure forensic log was written
    assert "MacReady" in game_state.forensic_db.tags
    tags = game_state.forensic_db.tags["MacReady"]
    assert any(tag["category"] == "DETECTION" for tag in tags)

    history = game_state.evidence_log.log.get("MacReady", [])
    assert history, "Evidence log should record detection events"

    forensics_system.cleanup()
