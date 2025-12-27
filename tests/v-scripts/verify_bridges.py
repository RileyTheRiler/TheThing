import unittest
import time
from src.core.resolution import ResolutionSystem, Attribute, Skill
from src.core.event_system import EventBus, EventType, GameEvent

class TestAPI_Bridges(unittest.TestCase):
    def setUp(self):
        self.resolution = ResolutionSystem()
        self.bus = EventBus()
        self.bus.clear() # Ensure clean state

    def test_infection_math(self):
        print("\nTesting Infection Probability Math...")
        # Scenario 1: Light, Perfect Mask, No Paranoia
        # Formula: Base(0.05) * (1-1) * ... = 0
        prob = self.resolution.calculate_infection_risk("LIGHT", 1.0, 0)
        self.assertAlmostEqual(prob, 0.0)
        print(f" Light, Full Mask: {prob}")

        # Scenario 2: Dark, Broken Mask, High Paranoia
        # Base(0.40) * (1-0) * (1 + 1.0) = 0.80
        prob = self.resolution.calculate_infection_risk("DARK", 0.0, 100)
        self.assertAlmostEqual(prob, 0.80)
        print(f" Dark, No Mask, Max Paranoia: {prob}")
        
        # Scenario 3: Light, Half Mask, Moderate Paranoia
        # Base(0.05) * (0.5) * (1 + 0.5) = 0.05 * 0.5 * 1.5 = 0.0375
        prob = self.resolution.calculate_infection_risk("LIGHT", 0.5, 50)
        self.assertAlmostEqual(prob, 0.0375)
        print(f" Light, Half Mask, 50 Paranoia: {prob}")

    def test_thermal_decay(self):
        print("\nTesting Thermal Decay...")
        # Power ON -> Warms up towards 15
        current = 0
        new_temp = self.resolution.calculate_thermal_decay(current, True)
        self.assertTrue(new_temp > current)
        print(f" Power On (0 -> {new_temp})")

        # Power OFF -> Cools down towards -60
        current = 0
        new_temp = self.resolution.calculate_thermal_decay(current, False)
        self.assertTrue(new_temp < current)
        print(f" Power Off (0 -> {new_temp})")

    def test_event_bus(self):
        print("\nTesting Event Bus...")
        received_events = []
        
        def listener(event):
            received_events.append(event)
            
        self.bus.subscribe(EventType.BIOLOGICAL_SLIP, listener)
        
        # Emit event
        event = GameEvent(EventType.BIOLOGICAL_SLIP, {"source": "Norris", "type": "VAPOR_FAIL"})
        self.bus.emit(event)
        
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].payload["source"], "Norris")
        print(" Event Received OK")

if __name__ == '__main__':
    unittest.main()
