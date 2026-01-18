"""Tests for the infected NPC coordination (pincer movement) system."""

import pytest
from unittest.mock import MagicMock, patch
from entities.crew_member import CrewMember, StealthPosture
from systems.ai import AISystem
from core.event_system import GameEvent, EventType, event_bus
from core.resolution import Attribute, Skill
from systems.architect import RandomnessEngine


@pytest.fixture
def game_state():
    """Create a game state with multiple infected NPCs for coordination testing."""
    gs = MagicMock()

    # Player
    gs.player = CrewMember("MacReady", "Pilot", "Cynical")
    gs.player.location = (7, 7)
    gs.player.attributes = {Attribute.PROWESS: 2}
    gs.player.skills = {Skill.STEALTH: 2}
    gs.player.is_alive = True
    gs.player.is_infected = False

    # Infected NPC 1 - Leader (detects player)
    infected1 = CrewMember("Palmer", "Mechanic", "Nervous")
    infected1.location = (5, 7)  # Same row, 2 tiles away
    infected1.is_infected = True
    infected1.is_alive = True
    infected1.is_revealed = False
    infected1.attributes = {Attribute.LOGIC: 2, Attribute.PROWESS: 2}
    infected1.skills = {Skill.OBSERVATION: 1}
    infected1.schedule = []

    # Infected NPC 2 - Ally (can coordinate)
    infected2 = CrewMember("Blair", "Biologist", "Analytical")
    infected2.location = (9, 7)  # Same row, opposite side
    infected2.is_infected = True
    infected2.is_alive = True
    infected2.is_revealed = False
    infected2.attributes = {Attribute.LOGIC: 3, Attribute.PROWESS: 1}
    infected2.skills = {Skill.OBSERVATION: 2}
    infected2.schedule = []

    # Non-infected NPC (should not be alerted to coordination)
    human = CrewMember("Childs", "Mechanic", "Aggressive")
    human.location = (7, 5)
    human.is_infected = False
    human.is_alive = True
    human.attributes = {Attribute.LOGIC: 2, Attribute.PROWESS: 3}
    human.skills = {}
    human.schedule = []

    gs.crew = [gs.player, infected1, infected2, human]

    # Station map mock
    gs.station_map = MagicMock()
    gs.station_map.get_room_name.return_value = "Rec Room"
    gs.station_map.is_walkable.return_value = True
    gs.station_map.get_connections.return_value = ["Mess Hall", "Infirmary", "Lab"]
    gs.station_map.width = 20
    gs.station_map.height = 20

    gs.room_states = MagicMock()
    gs.room_states.has_state.return_value = False

    gs.rng = RandomnessEngine(seed=42)
    gs.turn = 1

    # Mock lynch mob (inactive)
    gs.lynch_mob = MagicMock()
    gs.lynch_mob.active_mob = False
    gs.lynch_mob.target = None

    # Mock time system
    gs.time_system = MagicMock()
    gs.time_system.hour = 12

    return gs


@pytest.fixture
def ai_system():
    """Create an AI system instance."""
    return AISystem()


def test_broadcast_infected_alert_coordinates_allies(game_state, ai_system):
    """Test that infected NPCs receive coordination signals from detecting NPC."""
    infected1 = game_state.crew[1]  # Palmer - the detector
    infected2 = game_state.crew[2]  # Blair - the ally

    # Capture coordination events
    coordination_events = []
    def on_coordination(event):
        coordination_events.append(event)

    event_bus.subscribe(EventType.INFECTED_COORDINATION, on_coordination)

    try:
        # Trigger the broadcast
        ai_system._broadcast_infected_alert(infected1, game_state.player.location, game_state)

        # Check that coordination event was emitted
        assert len(coordination_events) == 1
        payload = coordination_events[0].payload
        assert payload["leader"] == "Palmer"
        assert "Blair" in payload["allies"]
        assert payload["target_location"] == (7, 7)

        # Check that ally received coordination state
        assert infected2.coordinating_ambush is True
        assert infected2.ambush_target_location == (7, 7)
        assert infected2.coordination_leader == "Palmer"
        assert infected2.coordination_turns_remaining == 5
        assert infected2.suspicion_state == "coordinating"

        # Check that leader also has coordination state
        assert infected1.coordinating_ambush is True
        assert infected1.coordination_leader == "Palmer"
        assert infected1.suspicion_state == "coordinating"
        assert infected2.suspicion_state == "coordinating"

    finally:
        event_bus.unsubscribe(EventType.INFECTED_COORDINATION, on_coordination)


def test_coordination_does_not_affect_humans(game_state, ai_system):
    """Test that human NPCs are not added to coordination."""
    infected1 = game_state.crew[1]  # Palmer
    human = game_state.crew[3]  # Childs

    ai_system._broadcast_infected_alert(infected1, game_state.player.location, game_state)

    # Human should NOT have coordination state
    assert getattr(human, 'coordinating_ambush', False) is False
    assert getattr(human, 'coordination_leader', None) is None


def test_coordination_does_not_affect_revealed_things(game_state, ai_system):
    """Test that revealed Things act independently and don't coordinate."""
    infected1 = game_state.crew[1]  # Palmer
    infected2 = game_state.crew[2]  # Blair

    # Make Blair revealed (transforms into Thing creature)
    infected2.is_revealed = True

    ai_system._broadcast_infected_alert(infected1, game_state.player.location, game_state)

    # Revealed Thing should NOT coordinate
    assert getattr(infected2, 'coordinating_ambush', False) is False


def test_flanking_position_calculation(game_state, ai_system):
    """Test that flanking positions are calculated correctly."""
    target = (10, 10)
    leader_pos = (8, 10)  # Approaching from the left
    flankers = game_state.crew[1:3]

    positions = ai_system._calculate_flanking_positions(
        target, leader_pos, flankers, game_state.station_map, current_turn=game_state.turn
    )

    # Should have positions on opposite side or perpendicular
    assert len(positions) >= 1
    assert len(positions) <= len(flankers)

    # Positions should not be the same as target
    for pos in positions:
        assert pos != target


def test_execute_coordinated_ambush_moves_to_flank(game_state, ai_system):
    """Test that coordinating NPCs move toward their flank positions."""
    infected2 = game_state.crew[2]  # Blair

    # Set up coordination state
    infected2.coordinating_ambush = True
    infected2.ambush_target_location = (7, 7)
    infected2.flank_position = (7, 10)  # Flanking position
    infected2.coordination_leader = "Palmer"
    infected2.coordination_turns_remaining = 5
    infected2.location = (9, 7)

    original_location = infected2.location

    # Execute coordination behavior
    result = ai_system._execute_coordinated_ambush(infected2, game_state)

    assert result is True
    # Should have moved (location changed or pathfind called)
    assert infected2.coordination_turns_remaining == 4


def test_coordination_expires_after_turns(game_state, ai_system):
    """Test that coordination state expires after the timer runs out."""
    infected2 = game_state.crew[2]  # Blair

    # Set up coordination state
    infected2.coordinating_ambush = True
    infected2.ambush_target_location = (7, 7)
    infected2.flank_position = (7, 10)
    infected2.coordination_leader = "Palmer"
    infected2.coordination_turns_remaining = 1

    # Execute - should decrement to 0 and clear
    ai_system._execute_coordinated_ambush(infected2, game_state)

    # Should be cleared
    assert infected2.coordinating_ambush is False
    assert infected2.coordination_leader is None
    assert infected2.suspicion_state == "idle"


def test_clear_coordination(game_state, ai_system):
    """Test the coordination clearing helper."""
    infected = game_state.crew[1]

    # Set up coordination state
    infected.coordinating_ambush = True
    infected.ambush_target_location = (5, 5)
    infected.flank_position = (3, 3)
    infected.coordination_leader = "Palmer"
    infected.coordination_turns_remaining = 3

    # Clear it
    ai_system._clear_coordination(infected)

    # All state should be reset
    assert infected.coordinating_ambush is False
    assert infected.ambush_target_location is None
    assert infected.flank_position is None
    assert infected.coordination_leader is None
    assert infected.coordination_turns_remaining == 0


def test_coordinated_ambush_priority_in_ai_update(game_state, ai_system):
    """Test that coordinating NPCs prioritize coordination over other behaviors."""
    infected = game_state.crew[1]

    # Set up coordination state
    infected.coordinating_ambush = True
    infected.ambush_target_location = (7, 7)
    infected.flank_position = None  # Leader approaches directly
    infected.coordination_leader = infected.name
    infected.coordination_turns_remaining = 5

    # Mock that NPC is also in a schedule - coordination should take priority
    infected.schedule = [{"start": 0, "end": 24, "room": "Generator"}]

    # Run AI update - coordination should be executed
    ai_system.cache = MagicMock()
    ai_system.cache.player_location = game_state.player.location
    ai_system.cache.player_room = "Rec Room"
    ai_system.cache.player_noise = 5

    ai_system.update_member_ai(infected, game_state)

    # Should have decremented coordination timer
    assert infected.coordination_turns_remaining == 4
    assert infected.suspicion_state == "coordinating"


def test_coordination_serialization(game_state):
    """Test that coordination state is properly serialized and deserialized."""
    infected = game_state.crew[1]

    # Set up coordination state
    infected.coordinating_ambush = True
    infected.ambush_target_location = (7, 7)
    infected.flank_position = (10, 10)
    infected.coordination_leader = "Palmer"
    infected.coordination_turns_remaining = 3

    # Serialize
    data = infected.to_dict()

    # Check serialized values
    assert data["coordinating_ambush"] is True
    assert data["ambush_target_location"] == (7, 7)
    assert data["flank_position"] == (10, 10)
    assert data["coordination_leader"] == "Palmer"
    assert data["coordination_turns_remaining"] == 3

    # Deserialize
    restored = CrewMember.from_dict(data)

    # Check restored values
    assert restored.coordinating_ambush is True
    assert restored.ambush_target_location == (7, 7)
    assert restored.flank_position == (10, 10)
    assert restored.coordination_leader == "Palmer"
    assert restored.coordination_turns_remaining == 3


def test_no_coordination_when_no_allies_nearby(game_state, ai_system):
    """Test that no coordination happens when no infected allies are nearby."""
    infected1 = game_state.crew[1]  # Palmer
    infected2 = game_state.crew[2]  # Blair

    # Move Blair far away (different room)
    infected2.location = (15, 15)
    game_state.station_map.get_room_name.side_effect = lambda x, y: "Generator" if (x, y) == (15, 15) else "Rec Room"
    game_state.station_map.get_connections.return_value = []  # No adjacent rooms

    coordination_events = []
    def on_coordination(event):
        coordination_events.append(event)

    event_bus.subscribe(EventType.INFECTED_COORDINATION, on_coordination)

    try:
        ai_system._broadcast_infected_alert(infected1, game_state.player.location, game_state)

        # No coordination event should be emitted (no nearby allies)
        assert len(coordination_events) == 0

        # Blair should not be coordinating
        assert getattr(infected2, 'coordinating_ambush', False) is False

    finally:
        event_bus.unsubscribe(EventType.INFECTED_COORDINATION, on_coordination)
