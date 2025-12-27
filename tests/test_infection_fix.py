import os
import sys
import unittest

# Add src to path so we can import modules without src. prefix
sys.path.append(os.path.join(os.getcwd(), 'src'))

from systems.infection import check_for_communion
from core.resolution import ResolutionSystem
from core.event_system import event_bus, EventType

# Mock classes
class MockRNG:
    def random_float(self): return 0.0 # Force infection if risk > 0

class MockMember:
    def __init__(self, name, location, infected=False):
        self.name = name
        self.location = location
        self.is_alive = True
        self.is_infected = infected
        self.mask_integrity = 0.5 # Ensure some risk

class MockGameState:
    def __init__(self):
        self.crew = []
        self.power_on = True
        self.paranoia_level = 0
        self.rng = MockRNG()

class TestInfectionPerformance(unittest.TestCase):
    def setUp(self):
        self.game_state = MockGameState()
        # Setup: 1 infected, 1 non-infected in same location
        self.game_state.crew = [
            MockMember("Infected_Zero", (5, 5), True),
            MockMember("Victim_One", (5, 5), False)
        ]

    def test_infection_loop_safety(self):
        """
        Verify that check_for_communion runs without crashing.
        This tests the fix for the TypeError.
        """
        try:
            check_for_communion(self.game_state)
        except Exception as e:
            self.fail(f"check_for_communion raised exception: {e}")

    def test_infection_logic(self):
        """
        Verify that infection actually happens (logic is preserved).
        """
        # With RNG returning 0.0, infection should be guaranteed if risk > 0
        check_for_communion(self.game_state)
        victim = next(m for m in self.game_state.crew if m.name == "Victim_One")
        self.assertTrue(victim.is_infected, "Victim should have been infected")

if __name__ == '__main__':
    unittest.main()
