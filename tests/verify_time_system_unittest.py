import unittest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from systems.architect import TimeSystem
from core.event_system import event_bus, EventType, GameEvent

class MockGameState:
    def __init__(self, power_on=True):
        self.power_on = power_on

class TestTimeSystem(unittest.TestCase):
    def test_hour_initialization(self):
        """Test default and custom start hours."""
        ts = TimeSystem(start_hour=19)
        self.assertEqual(ts.hour, 19)
        self.assertEqual(ts.turn_count, 0)

        ts_custom = TimeSystem(start_hour=10)
        self.assertEqual(ts_custom.hour, 10)

    def test_hour_rollover(self):
        """Test that hour wraps around 24 correctly using turn count."""
        ts = TimeSystem(start_hour=23)
        self.assertEqual(ts.hour, 23)
        
        # Advance 1 turn -> 00:00
        ts.turn_count = 1
        self.assertEqual(ts.hour, 0)
        
        # Advance to turn 2 -> 01:00
        ts.turn_count = 2
        self.assertEqual(ts.hour, 1)
        
        # Large turn count
        ts.turn_count = 25  # 23 + 25 = 48 -> 00:00
        self.assertEqual(ts.hour, 0)

    def test_event_subscription(self):
        """Test that TimeSystem responds to TURN_ADVANCE events."""
        print(f"\nDEBUG: Test EventBus ID: {id(event_bus)}")
        ts = TimeSystem(start_hour=12)
        initial_turn = ts.turn_count
        
        print(f"DEBUG: Subscribers after init: {event_bus._subscribers.keys()}")
        if EventType.TURN_ADVANCE in event_bus._subscribers:
             print(f"DEBUG: TURN_ADVANCE subscribers: {event_bus._subscribers[EventType.TURN_ADVANCE]}")
        
        event = GameEvent(EventType.TURN_ADVANCE, {"game_state": MockGameState(power_on=True)})
        event_bus.emit(event)
        
        print(f"DEBUG: Turn count after emit: {ts.turn_count}")
        self.assertEqual(ts.turn_count, initial_turn + 1)
        self.assertEqual(ts.hour, 13)
        
        ts.cleanup()

    def test_thermal_decay(self):
        """Test temperature changes based on power state via update_environment (triggered by event)."""
        ts = TimeSystem(start_temp=10)
        
        # Power ON -> Temperature increases (heating)
        # Mock event with power ON
        event_on = GameEvent(EventType.TURN_ADVANCE, {"game_state": MockGameState(power_on=True)})
        event_bus.emit(event_on)
        # 10 + 0.05 * (15 - 10) = 10.25
        self.assertEqual(ts.temperature, 10.25)
        
        # Power OFF -> Temperature drops drastically
        event_off = GameEvent(EventType.TURN_ADVANCE, {"game_state": MockGameState(power_on=False)})
        event_bus.emit(event_off)
        # 10.25 - 0.5 * (10.25 - (-60)) = 10.25 - 0.5 * 70.25 = 10.25 - 35.125 = -24.875
        self.assertEqual(ts.temperature, -24.875)
        
        ts.cleanup()

    def test_serialization(self):
        """Test to_dict and from_dict."""
        ts = TimeSystem(start_temp=-20, start_hour=18)
        ts.turn_count = 5
        
        data = ts.to_dict()
        self.assertEqual(data["temperature"], -20)
        self.assertEqual(data["start_hour"], 18)
        self.assertEqual(data["turn_count"], 5)
        
        restored = TimeSystem.from_dict(data)
        self.assertEqual(restored.temperature, -20)
        self.assertEqual(restored.start_hour, 18)
        self.assertEqual(restored.turn_count, 5)
        # 18 + 5 = 23
        self.assertEqual(restored.hour, 23)

if __name__ == "__main__":
    unittest.main()
