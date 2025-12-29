"""Tests for Station-Wide Alert System.

Verifies that when a human NPC detects the player, a station-wide alert
is triggered that makes all NPCs more vigilant for a set duration.
"""

import sys
sys.path.insert(0, "src")

from unittest.mock import MagicMock, patch


class MockRng:
    """Deterministic RNG for testing."""
    def __init__(self):
        pass

    def calculate_success(self, pool_size):
        return {
            "success": pool_size > 0,
            "success_count": pool_size // 2,
            "dice": [6] * (pool_size // 2) + [1] * (pool_size - pool_size // 2)
        }


class MockCrewMember:
    """Mock crew member for testing."""
    def __init__(self, name, is_infected=False):
        self.name = name
        self.is_infected = is_infected
        self.is_alive = True
        self.location = (5, 5)


class MockGameState:
    """Mock game state for testing."""
    def __init__(self):
        self.turn = 1
        self.journal = []
        self.rng = MockRng()


def test_alert_system_initialization():
    """Test that AlertSystem initializes correctly."""
    from systems.alert import AlertSystem

    system = AlertSystem()

    assert system.is_active == False
    assert system.turns_remaining == 0
    assert system.get_observation_bonus() == 0

    system.cleanup()
    print("[PASS] AlertSystem initializes correctly")


def test_alert_trigger_on_human_detection():
    """Test that alert is triggered when a human NPC detects the player."""
    from systems.alert import AlertSystem
    from core.event_system import event_bus, EventType, GameEvent

    game_state = MockGameState()
    system = AlertSystem(game_state)

    # Simulate a human NPC detecting the player
    human_observer = MockCrewMember("Windows", is_infected=False)

    event = GameEvent(EventType.PERCEPTION_EVENT, {
        "outcome": "detected",
        "opponent_ref": human_observer,
        "game_state": game_state
    })

    # Manually call the handler
    system.on_perception_event(event)

    assert system.is_active == True
    assert system.turns_remaining == 10  # DEFAULT_ALERT_DURATION
    assert system.get_observation_bonus() == 2  # OBSERVATION_BONUS

    system.cleanup()
    print("[PASS] Alert triggers on human NPC detection")


def test_no_alert_on_infected_detection():
    """Test that infected NPCs don't trigger station-wide alerts."""
    from systems.alert import AlertSystem
    from core.event_system import EventType, GameEvent

    game_state = MockGameState()
    system = AlertSystem(game_state)

    # Simulate an infected NPC detecting the player
    infected_observer = MockCrewMember("Norris", is_infected=True)

    event = GameEvent(EventType.PERCEPTION_EVENT, {
        "outcome": "detected",
        "opponent_ref": infected_observer,
        "game_state": game_state
    })

    system.on_perception_event(event)

    assert system.is_active == False
    assert system.turns_remaining == 0

    system.cleanup()
    print("[PASS] Infected NPCs don't trigger alerts")


def test_no_alert_on_evaded():
    """Test that successful evasion doesn't trigger alert."""
    from systems.alert import AlertSystem
    from core.event_system import EventType, GameEvent

    game_state = MockGameState()
    system = AlertSystem(game_state)

    human_observer = MockCrewMember("Clark", is_infected=False)

    event = GameEvent(EventType.PERCEPTION_EVENT, {
        "outcome": "evaded",  # Player successfully evaded
        "opponent_ref": human_observer,
        "game_state": game_state
    })

    system.on_perception_event(event)

    assert system.is_active == False

    system.cleanup()
    print("[PASS] Evasion doesn't trigger alert")


def test_alert_decay():
    """Test that alert decays each turn."""
    from systems.alert import AlertSystem
    from core.event_system import EventType, GameEvent

    game_state = MockGameState()
    system = AlertSystem(game_state)

    # Manually trigger alert
    system.force_trigger(5)  # 5 turns
    assert system.turns_remaining == 5

    # Simulate turn advances
    for i in range(5):
        event = GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state})
        system.on_turn_advance(event)

        if i < 4:
            assert system.is_active == True
            assert system.turns_remaining == 4 - i
        else:
            assert system.is_active == False
            assert system.turns_remaining == 0

    system.cleanup()
    print("[PASS] Alert decays correctly each turn")


def test_observation_bonus():
    """Test that observation bonus is applied during alert."""
    from systems.alert import AlertSystem

    system = AlertSystem()

    # No bonus when inactive
    assert system.get_observation_bonus() == 0

    # Trigger alert
    system.force_trigger()
    assert system.get_observation_bonus() == 2

    system.cleanup()
    print("[PASS] Observation bonus applied correctly")


def test_alert_serialization():
    """Test that alert state can be saved and restored."""
    from systems.alert import AlertSystem

    game_state = MockGameState()
    system = AlertSystem(game_state)

    # Trigger and partially decay
    system.force_trigger(10)
    system._alert_turns_remaining = 7
    system._triggering_observer = "Blair"

    # Serialize
    data = system.to_dict()
    assert data["alert_active"] == True
    assert data["alert_turns_remaining"] == 7
    assert data["triggering_observer"] == "Blair"

    # Deserialize
    new_system = AlertSystem.from_dict(data, game_state)
    assert new_system.is_active == True
    assert new_system.turns_remaining == 7

    system.cleanup()
    new_system.cleanup()
    print("[PASS] Alert state serializes correctly")


def test_no_retrigger_during_active_alert():
    """Test that alert doesn't retrigger when already on high alert."""
    from systems.alert import AlertSystem
    from core.event_system import EventType, GameEvent

    game_state = MockGameState()
    system = AlertSystem(game_state)

    # Trigger alert
    system.force_trigger(10)
    assert system.turns_remaining == 10

    # Simulate decay to 6 turns (still above half of 10)
    system._alert_turns_remaining = 6

    # Try to trigger again
    human_observer = MockCrewMember("Childs", is_infected=False)
    event = GameEvent(EventType.PERCEPTION_EVENT, {
        "outcome": "detected",
        "opponent_ref": human_observer,
        "game_state": game_state
    })
    system.on_perception_event(event)

    # Should not reset to 10
    assert system.turns_remaining == 6

    # But if decayed below half, it should retrigger
    system._alert_turns_remaining = 4
    system.on_perception_event(event)
    assert system.turns_remaining == 10

    system.cleanup()
    print("[PASS] Alert retrigger logic works correctly")


def test_stealth_integration():
    """Test that stealth system applies alert bonus."""
    # This test simulates the integration without running full game loop
    from systems.alert import AlertSystem

    class MockGameStateWithAlert:
        def __init__(self):
            self.alert_system = AlertSystem()

    game_state = MockGameStateWithAlert()

    # Base observer pool calculation
    base_pool = 3  # logic + observation

    # Without alert
    assert game_state.alert_system.get_observation_bonus() == 0
    observer_pool = base_pool + game_state.alert_system.get_observation_bonus()
    assert observer_pool == 3

    # With alert
    game_state.alert_system.force_trigger()
    observer_pool = base_pool + game_state.alert_system.get_observation_bonus()
    assert observer_pool == 5  # +2 bonus

    game_state.alert_system.cleanup()
    print("[PASS] Stealth integration works correctly")


def test_journal_logging():
    """Test that alert trigger is logged to journal."""
    from systems.alert import AlertSystem
    from core.event_system import EventType, GameEvent

    game_state = MockGameState()
    game_state.turn = 5
    system = AlertSystem(game_state)

    human_observer = MockCrewMember("Garry", is_infected=False)
    event = GameEvent(EventType.PERCEPTION_EVENT, {
        "outcome": "detected",
        "opponent_ref": human_observer,
        "game_state": game_state
    })

    system.on_perception_event(event)

    assert len(game_state.journal) == 1
    assert "STATION ALERT" in game_state.journal[0]
    assert "Garry" in game_state.journal[0]
    assert "Turn 5" in game_state.journal[0]

    system.cleanup()
    print("[PASS] Alert logged to journal correctly")


if __name__ == "__main__":
    test_alert_system_initialization()
    test_alert_trigger_on_human_detection()
    test_no_alert_on_infected_detection()
    test_no_alert_on_evaded()
    test_alert_decay()
    test_observation_bonus()
    test_alert_serialization()
    test_no_retrigger_during_active_alert()
    test_stealth_integration()
    test_journal_logging()

    print("\n=== ALL ALERT SYSTEM TESTS PASSED ===")
