
import unittest
from src.systems.forensics import BloodTestSim, ForensicsSystem, GameEvent, EventType

class TestForensicsCooling(unittest.TestCase):
    def setUp(self):
        self.sim = BloodTestSim()
        self.fs = ForensicsSystem()
        self.fs.blood_test = self.sim

    def test_cooling_active_heating(self):
        """Test that the wire cools down when active and in HEATING state."""
        self.sim.start_test("MacReady")
        self.sim.wire_temp = 80
        self.sim.state = "HEATING"

        # Simulate turn advance by manually calling on_turn_advance
        event = GameEvent(EventType.TURN_ADVANCE, {})
        self.fs.on_turn_advance(event)

        # Should cool by 10
        self.assertEqual(self.sim.wire_temp, 70)
        self.assertEqual(self.sim.state, "HEATING")

    def test_cooling_active_ready(self):
        """Test that the wire cools down and changes state from READY to HEATING if too cold."""
        self.sim.start_test("MacReady")
        self.sim.wire_temp = 95
        self.sim.state = "READY"

        # Turn 1: 95 -> 85. Should drop below 90, so state -> HEATING
        event = GameEvent(EventType.TURN_ADVANCE, {})
        self.fs.on_turn_advance(event)

        self.assertEqual(self.sim.wire_temp, 85)
        self.assertEqual(self.sim.state, "HEATING")

    def test_cooling_floor(self):
        """Test that cooling stops at 20 degrees."""
        self.sim.start_test("MacReady")
        self.sim.wire_temp = 25
        self.sim.state = "HEATING"

        event = GameEvent(EventType.TURN_ADVANCE, {})
        self.fs.on_turn_advance(event)

        self.assertEqual(self.sim.wire_temp, 20) # 25 - 10 = 15, but floor is 20

    def test_cooling_inactive(self):
        """Test that cooling does not happen if test is inactive."""
        self.sim.active = False
        self.sim.wire_temp = 80

        event = GameEvent(EventType.TURN_ADVANCE, {})
        self.fs.on_turn_advance(event)

        self.assertEqual(self.sim.wire_temp, 80)

if __name__ == '__main__':
    unittest.main()
