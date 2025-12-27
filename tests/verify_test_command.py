import sys
import os
import unittest
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from game_loop import _execute_command
from engine import GameState
from entities.crew_member import CrewMember
from entities.item import Item
from systems.architect import Difficulty

class TestCommandVerification(unittest.TestCase):
    def setUp(self):
        # Setup minimal game state
        self.game = GameState(difficulty=Difficulty.NORMAL)
        self.game.crt = MagicMock() # Mock CRT

        # Setup player
        self.player = self.game.player
        self.player.location = (5, 5)
        self.player.inventory = []

        # Setup target
        self.target = CrewMember("TestSubject", "Scientist", "Nervous")
        self.target.location = (5, 5)
        self.game.crew.append(self.target)

    def test_test_command_flow(self):
        # Add required items
        self.player.add_item(Item("Scalpel", "Sharp"), 1)
        self.player.add_item(Item("Copper Wire", "Conductive"), 1)

        from io import StringIO
        captured_output = StringIO()
        sys.stdout = captured_output

        # 1. Start TEST
        _execute_command(self.game, ["TEST", "TestSubject"])

        # Verify test started but didn't finish
        self.assertTrue(self.game.blood_test_sim.active, "Test should be active")
        self.assertEqual(self.game.blood_test_sim.state, "HEATING", "State should be HEATING")

        # 2. Heat the wire manually
        initial_temp = self.game.blood_test_sim.wire_temp
        _execute_command(self.game, ["HEAT"])
        self.assertGreater(self.game.blood_test_sim.wire_temp, initial_temp, "Wire temp should increase")

        # Heat until ready (approx 3-4 times)
        for _ in range(5):
             _execute_command(self.game, ["HEAT"])

        self.assertGreaterEqual(self.game.blood_test_sim.wire_temp, 90, "Wire should be hot enough")

        # 3. Apply
        _execute_command(self.game, ["APPLY"])

        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        # Check output for confirmation
        self.assertIn("Prepared blood sample", output)
        self.assertIn("Heating wire", output)
        self.assertIn("HUMAN", output) # Since target is not infected
        self.assertFalse(self.game.blood_test_sim.active, "Test should be finished")

if __name__ == '__main__':
    unittest.main()
