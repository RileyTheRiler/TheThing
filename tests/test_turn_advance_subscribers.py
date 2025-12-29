import pytest

from core.event_system import event_bus, EventType, GameEvent
from systems.architect import RandomnessEngine
from systems.weather import WeatherSystem
from systems.sabotage import SabotageManager


@pytest.fixture
def clean_bus():
    """Isolate event bus subscribers for this test."""
    original = {k: list(v) for k, v in event_bus._subscribers.items()}
    event_bus._subscribers = {}
    try:
        yield
    finally:
        event_bus._subscribers = original


def test_turn_advance_subscribers_run_once(clean_bus):
    rng = RandomnessEngine(seed=123)

    # Subscribing systems
    weather = WeatherSystem()
    sabotage = SabotageManager()

    turn_inventory = {
        "weather": 0,
        "sabotage": 0,
        "ai": 0,
        "random_events": 0,
        "random_event_triggered": None,
    }

    event = GameEvent(
        EventType.TURN_ADVANCE,
        {"rng": rng, "turn_inventory": turn_inventory},
    )

    event_bus.emit(event)

    assert turn_inventory["weather"] == 1
    assert turn_inventory["sabotage"] == 1
    assert all(
        turn_inventory[key] == 0 for key in ["ai", "random_events"]
    )

    # Cleanup to avoid lingering subscriptions
    weather.cleanup()
    sabotage.cleanup()
