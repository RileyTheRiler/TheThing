import os
import sys
import unittest
from unittest.mock import MagicMock

# Add src to pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.systems.missionary import MissionarySystem
from src.core.logger import hidden_logger

class TestHiddenLogging(unittest.TestCase):
    def setUp(self):
        # Clear log file content if it exists, but don't delete it to preserve the file handle
        if os.path.exists("hidden_state.log"):
            with open("hidden_state.log", "w") as f:
                f.truncate(0)

    def test_assimilation_logging(self):
        # Setup mocks
        system = MissionarySystem()

        agent = MagicMock()
        agent.name = "AgentThing"
        agent.mask_integrity = 50
        agent.invariants = []

        target = MagicMock()
        target.name = "VictimHuman"
        target.is_infected = False
        target.mask_integrity = 80

        game_state = MagicMock()

        # Trigger the action
        system.perform_communion(agent, target, game_state)

        # Verify target state
        self.assertTrue(target.is_infected)
        self.assertEqual(target.mask_integrity, 100)

        # Verify log file content
        self.assertTrue(os.path.exists("hidden_state.log"))

        with open("hidden_state.log", "r") as f:
            content = f.read()
            print(f"Log content: {content}")
            self.assertIn("VictimHuman ASSIMILATED by AgentThing", content)

if __name__ == "__main__":
    unittest.main()
