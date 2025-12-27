import unittest
from src.core.resolution import ResolutionSystem
from src.systems.architect import TimeSystem
from src.core.event_system import event_bus, EventType, GameEvent

class MockGameState:
    def __init__(self, power_on=True):
        self.power_on = power_on

class TestThermalDecay(unittest.TestCase):
    def test_thermal_decay_cooling_fast(self):
        """
        Verify that thermal decay with power OFF uses k=0.5 for rapid cooling.
        """
        res = ResolutionSystem()
        start_temp = 20.0
        # Expected formula: T_new = T + (-0.5 * (T - (-60)))
        # Turn 1: 20 + (-0.5 * (80)) = 20 - 40 = -20
        new_temp = res.calculate_thermal_decay(start_temp, power_on=False)
        self.assertAlmostEqual(new_temp, -20.0, places=1)

        # Turn 2: -20 + (-0.5 * (-20 - (-60))) = -20 + (-0.5 * 40) = -20 - 20 = -40
        new_temp_2 = res.calculate_thermal_decay(new_temp, power_on=False)
        self.assertAlmostEqual(new_temp_2, -40.0, places=1)

    def test_thermal_decay_heating(self):
        """
        Verify that heating uses k=0.05.
        """
        res = ResolutionSystem()
        start_temp = 0.0
        # Power ON, target = 15.0
        # Delta = 0.05 * (15 - 0) = 0.75
        new_temp = res.calculate_thermal_decay(start_temp, power_on=True)
        self.assertAlmostEqual(new_temp, 0.75, places=2)

    def test_time_system_integration(self):
        """
        Verify that TimeSystem uses the correct ResolutionSystem logic.
        """
        ts = TimeSystem(start_temp=20.0)
        # Power OFF -> Rapid cooling
        change, new_temp = ts.update_environment(power_on=False)
        self.assertAlmostEqual(new_temp, -20.0, places=1)
        self.assertEqual(ts.temperature, new_temp)

    def test_time_system_event_handling(self):
        """
        Verify that TimeSystem responds to TURN_ADVANCE events.
        """
        ts = TimeSystem(start_temp=20.0)
        # Verify event subscription happened in init

        game_state = MockGameState(power_on=False)
        event = GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state})

        # Simulate event emission (or direct handler call if testing handler logic)
        # Since TimeSystem subscribes in init, we can just trigger the handler directly for unit testing
        # OR we can emit if we want to test the bus. Let's call handler directly to avoid global state issues.
        ts.on_turn_advance(event)

        # Should have cooled down
        self.assertAlmostEqual(ts.temperature, -20.0, places=1)
        self.assertEqual(ts.turn_count, 1)

if __name__ == '__main__':
    unittest.main()
