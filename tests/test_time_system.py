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
