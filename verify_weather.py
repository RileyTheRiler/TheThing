import sys
import os

# Add root to path so we can import src.*
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.systems.weather import WeatherSystem
from src.core.event_system import event_bus, EventType, GameEvent
from src.systems.architect import RandomnessEngine

def verify_weather_display():
    print("Testing Weather Display Integration...")

    # Mock subscriber to capture events
    captured_events = []
    def capture_event(event):
        captured_events.append(event)

    # Subscribe to MESSAGE and WARNING
    event_bus.subscribe(EventType.MESSAGE, capture_event)
    event_bus.subscribe(EventType.WARNING, capture_event)

    # Initialize WeatherSystem
    weather = WeatherSystem()

    # Mock RNG
    rng = RandomnessEngine(seed=123)

    # Force a weather event message by manipulating internal state
    # We want the Northeasterly to end
    weather.northeasterly_active = True
    weather.northeasterly_turns_remaining = 1
    # Next tick should return "The Northeasterly subsides. Visibility improves."

    # Create a dummy event
    event = GameEvent(EventType.TURN_ADVANCE, payload={'rng': rng})

    print("Triggering turn advance...")
    weather.on_turn_advance(event)

    print(f"Captured events: {len(captured_events)}")
    for e in captured_events:
        print(f"Type: {e.type}, Payload: {e.payload}")

    success = False
    for e in captured_events:
        if e.type == EventType.MESSAGE and "The Northeasterly subsides" in e.payload['text']:
            success = True
            break

    if success:
        print("PASS: Weather event emitted and captured.")
    else:
        print("FAIL: Expected weather event not found.")
        sys.exit(1)

if __name__ == "__main__":
    verify_weather_display()
