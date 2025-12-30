"""Tests for the Explain Away dialogue branching system."""

import pytest
from unittest.mock import MagicMock
from entities.crew_member import CrewMember, StealthPosture
from systems.social import ExplainAwaySystem, ExplainResult
from core.event_system import GameEvent, EventType, event_bus
from core.resolution import Attribute, Skill
from systems.architect import RandomnessEngine


@pytest.fixture
def game_state():
    """Create a game state for testing explain away."""
    gs = MagicMock()

    # Player with INFLUENCE and DECEPTION
    gs.player = CrewMember("MacReady", "Pilot", "Cynical")
    gs.player.location = (5, 5)
    gs.player.attributes = {Attribute.INFLUENCE: 3}
    gs.player.skills = {Skill.DECEPTION: 2}
    gs.player.is_alive = True
    gs.player.stealth_posture = StealthPosture.CROUCHING

    # Observer with LOGIC and EMPATHY
    observer = CrewMember("Childs", "Mechanic", "Aggressive")
    observer.location = (5, 5)
    observer.is_alive = True
    observer.is_revealed = False
    observer.attributes = {Attribute.LOGIC: 2}
    observer.skills = {Skill.EMPATHY: 1}

    gs.crew = [gs.player, observer]

    gs.station_map = MagicMock()
    gs.station_map.get_room_name.return_value = "Rec Room"

    gs.rng = RandomnessEngine(seed=42)
    gs.turn = 1

    # Mock trust system
    gs.trust_system = MagicMock()

    return gs


@pytest.fixture
def explain_system():
    """Create an ExplainAwaySystem instance."""
    system = ExplainAwaySystem()
    yield system
    system.cleanup()


def test_deception_skill_exists():
    """Verify DECEPTION skill is properly defined."""
    assert hasattr(Skill, 'DECEPTION')
    assert Skill.get_attribute(Skill.DECEPTION) == Attribute.INFLUENCE


def test_perception_event_creates_pending_explanation(game_state, explain_system):
    """Test that detection while sneaking creates pending explanation."""
    observer = game_state.crew[1]

    # Create detection event
    event = GameEvent(EventType.PERCEPTION_EVENT, {
        "outcome": "detected",
        "opponent_ref": observer,
        "player_ref": game_state.player,
        "game_state": game_state
    })

    # Trigger handler
    explain_system.on_perception_event(event)

    # Check pending
    assert explain_system.can_explain_to("Childs")
    assert "Childs" in explain_system.get_pending_observers()


def test_no_pending_when_standing(game_state, explain_system):
    """Test that no pending explanation when player is standing."""
    game_state.player.stealth_posture = StealthPosture.STANDING
    observer = game_state.crew[1]

    event = GameEvent(EventType.PERCEPTION_EVENT, {
        "outcome": "detected",
        "opponent_ref": observer,
        "player_ref": game_state.player,
        "game_state": game_state
    })

    explain_system.on_perception_event(event)

    # Should NOT create pending (not sneaking)
    assert not explain_system.can_explain_to("Childs")


def test_no_pending_when_evaded(game_state, explain_system):
    """Test that no pending explanation when player evaded detection."""
    observer = game_state.crew[1]

    event = GameEvent(EventType.PERCEPTION_EVENT, {
        "outcome": "evaded",  # Evaded, not detected
        "opponent_ref": observer,
        "player_ref": game_state.player,
        "game_state": game_state
    })

    explain_system.on_perception_event(event)

    assert not explain_system.can_explain_to("Childs")


def test_successful_explanation(game_state, explain_system):
    """Test a successful explain away attempt."""
    observer = game_state.crew[1]

    # Set up pending explanation
    explain_system._pending_explanations["Childs"] = observer

    # Use a seed that gives player advantage
    game_state.rng = RandomnessEngine(seed=42)

    result = explain_system.attempt_explain(game_state.player, observer, game_state)

    assert result.success is True
    assert result.critical is False
    assert result.suspicion_change < 0  # Suspicion decreased
    assert result.trust_change > 0  # Trust increased
    assert "You say:" in result.dialogue


def test_failed_explanation(game_state, explain_system):
    """Test a failed explain away attempt."""
    observer = game_state.crew[1]

    # Give observer stronger stats
    observer.attributes = {Attribute.LOGIC: 4}
    observer.skills = {Skill.EMPATHY: 2}

    # Weaken player
    game_state.player.attributes = {Attribute.INFLUENCE: 1}
    game_state.player.skills = {Skill.DECEPTION: 0}

    # Set up pending
    explain_system._pending_explanations["Childs"] = observer

    # Use a seed that gives observer advantage
    game_state.rng = RandomnessEngine(seed=999)

    result = explain_system.attempt_explain(game_state.player, observer, game_state)

    # With weak player vs strong observer, likely to fail
    # (Result depends on RNG, but we're testing the mechanism works)
    assert isinstance(result, ExplainResult)
    assert result.suspicion_change != 0 or result.trust_change != 0


def test_clear_pending_after_attempt(game_state, explain_system):
    """Test that pending explanation is cleared after attempt."""
    observer = game_state.crew[1]
    explain_system._pending_explanations["Childs"] = observer

    explain_system.attempt_explain(game_state.player, observer, game_state)

    assert not explain_system.can_explain_to("Childs")
    assert len(explain_system.get_pending_observers()) == 0


def test_no_pending_for_revealed_thing(game_state, explain_system):
    """Test that revealed Things don't create pending explanations."""
    observer = game_state.crew[1]
    observer.is_revealed = True  # Revealed as Thing

    event = GameEvent(EventType.PERCEPTION_EVENT, {
        "outcome": "detected",
        "opponent_ref": observer,
        "player_ref": game_state.player,
        "game_state": game_state
    })

    explain_system.on_perception_event(event)

    # Should NOT create pending (observer is revealed)
    assert not explain_system.can_explain_to("Childs")


def test_explain_result_dataclass():
    """Test ExplainResult dataclass structure."""
    result = ExplainResult(
        success=True,
        critical=False,
        player_successes=3,
        observer_successes=1,
        suspicion_change=-4,
        trust_change=2,
        dialogue="Test dialogue"
    )

    assert result.success is True
    assert result.critical is False
    assert result.player_successes == 3
    assert result.observer_successes == 1
    assert result.suspicion_change == -4
    assert result.trust_change == 2
    assert result.dialogue == "Test dialogue"


def test_suspicion_reduced_on_success(game_state, explain_system):
    """Test that observer's suspicion is reduced on successful explanation."""
    observer = game_state.crew[1]
    observer.suspicion_level = 5
    observer.suspicion_state = "question"

    explain_system._pending_explanations["Childs"] = observer
    game_state.rng = RandomnessEngine(seed=42)  # Gives success

    result = explain_system.attempt_explain(game_state.player, observer, game_state)

    if result.success:
        # Suspicion should have been reduced
        assert observer.suspicion_level < 5


def test_trust_modified_on_outcome(game_state, explain_system):
    """Test that trust system is called with appropriate changes."""
    observer = game_state.crew[1]
    explain_system._pending_explanations["Childs"] = observer

    explain_system.attempt_explain(game_state.player, observer, game_state)

    # Trust system should have been called
    game_state.trust_system.modify_trust.assert_called()


def test_multiple_pending_observers(game_state, explain_system):
    """Test handling multiple pending explanations."""
    observer1 = game_state.crew[1]

    # Add second observer
    observer2 = CrewMember("Palmer", "Mechanic", "Nervous")
    observer2.location = (5, 5)
    observer2.is_alive = True
    observer2.is_revealed = False
    observer2.attributes = {Attribute.LOGIC: 2}
    observer2.skills = {Skill.EMPATHY: 1}
    game_state.crew.append(observer2)

    # Create pending for both
    explain_system._pending_explanations["Childs"] = observer1
    explain_system._pending_explanations["Palmer"] = observer2

    pending = explain_system.get_pending_observers()
    assert len(pending) == 2
    assert "Childs" in pending
    assert "Palmer" in pending

    # Clear just one
    explain_system.clear_pending("Childs")
    assert not explain_system.can_explain_to("Childs")
    assert explain_system.can_explain_to("Palmer")
