import sys
import os

# Add root to path so we can import src.*
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.systems.weather import WeatherSystem
from src.core.event_system import event_bus, EventType, GameEvent
from src.systems.architect import RandomnessEngine, TimeSystem
from src.systems.random_events import RandomEventSystem

class MockGameState:
    def __init__(self):
        self.weather = WeatherSystem()
        self.time_system = TimeSystem()
        self.paranoia_level = 0
        self.turn = 1
        self.power_on = True
        self.crew = []

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
    rng = RandomnessEngine(seed=123)

    print("\n--- TEST 1: Direct Weather Tick ---")
    # Force a weather event message by manipulating internal state
    weather.northeasterly_active = True
    weather.northeasterly_turns_remaining = 1

    event = GameEvent(EventType.TURN_ADVANCE, payload={'rng': rng})
    weather.on_turn_advance(event)

    found_tick = False
    for e in captured_events:
        if e.type == EventType.MESSAGE and "The Northeasterly subsides" in e.payload['text']:
            found_tick = True

    if found_tick:
        print("PASS: Weather tick event captured.")
    else:
        print("FAIL: Weather tick event not captured.")
        sys.exit(1)

    print("\n--- TEST 2: Random Event (Blizzard) ---")
    # This verifies the fix in random_events.py calling the correct method
    game = MockGameState()
    res = RandomEventSystem(rng)

    try:
        res._effect_blizzard(game)
        print("PASS: _effect_blizzard executed without crash.")

        if game.weather.northeasterly_active:
             print("PASS: Blizzard triggered Northeasterly.")
        else:
             print("FAIL: Blizzard did not trigger Northeasterly.")
             sys.exit(1)

    except Exception as e:
        print(f"FAIL: _effect_blizzard crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_weather_display()
