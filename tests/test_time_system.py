from src.systems.architect import TimeSystem
from core.event_system import event_bus, EventType, GameEvent


def test_rollover_and_decay():
    """Hour should roll over at 24 and temperature should decay when power is off."""
    prior_subscribers = {k: v.copy() for k, v in event_bus._subscribers.items()}
    ts = TimeSystem(start_temp=-40, start_hour=23)

    events = []

    def handler(event: GameEvent):
        events.append(event)

    event_bus.subscribe(EventType.TURN_ADVANCE, handler)

    try:
        ts.advance_turn(power_on=False, game_state=None, rng=None)

        assert ts.hour == 0
        assert ts.temperature == -45
        assert len(events) == 1
    finally:
        event_bus.unsubscribe(EventType.TURN_ADVANCE, handler)
        event_bus._subscribers = prior_subscribers
import pytest

from core.event_system import EventType, event_bus
from systems.architect import TimeSystem


@pytest.fixture(autouse=True)
def reset_event_bus():
    event_bus.clear()
    yield
    event_bus.clear()


def test_hour_rollover_from_turn_count():
    ts = TimeSystem(start_hour=22)
    ts.turn_count = 3  # 22 -> 1:00
    assert ts.hour == 1


def test_advance_turn_emits_event_and_rolls_hour():
    ts = TimeSystem(start_temp=-20, start_hour=23)
    captured = []
    event_bus.subscribe(EventType.TURN_ADVANCE, captured.append)

    try:
        ts.advance_turn(power_on=True)
        ts.advance_turn(power_on=True)
    finally:
        event_bus.unsubscribe(EventType.TURN_ADVANCE, captured.append)

    assert [e.payload["hour"] for e in captured] == [0, 1]
    assert ts.temperature == -16  # Warmed twice with power on


def test_time_system_serialization_preserves_start_hour():
    ts = TimeSystem(start_temp=-10, start_hour=5)
    ts.turn_count = 7

    restored = TimeSystem.from_dict(ts.to_dict())

    assert restored.start_hour == 5
    assert restored.turn_count == 7
    assert restored.hour == ts.hour
