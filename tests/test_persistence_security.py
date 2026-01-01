
import unittest
import os
import shutil
from src.systems.persistence import SaveManager
from src.engine import GameState

class TestPersistenceSecurity(unittest.TestCase):
    def setUp(self):
        self.save_dir = "tests/test_saves_security"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        self.manager = SaveManager(save_dir=self.save_dir)
        self.game = GameState()
        # Mock necessary fields to pass validation
        self.game.crew = []
        self.game.turn = 1

        # Ensure we can save/load valid games first
        self.assertTrue(self.manager.save_game(self.game, "valid_slot"))

    def tearDown(self):
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)

    def test_path_traversal_save(self):
        """Test that attempting to save with path traversal characters is sanitized."""
        exploit_slot = "../exploit_save"

        # This should succeed, but save to 'exploit_save.json' inside save_dir
        self.assertTrue(self.manager.save_game(self.game, exploit_slot))

        # Check that it did NOT save outside
        outside_path = os.path.join(os.path.dirname(self.save_dir), "exploit_save.json")
        self.assertFalse(os.path.exists(outside_path), "File saved outside save directory!")

        # Check that it DID save inside with sanitized name
        sanitized_name = "exploit_save.json" # '..' and '/' removed
        inside_path = os.path.join(self.save_dir, sanitized_name)
        self.assertTrue(os.path.exists(inside_path), "Sanitized file not created!")

    def test_path_traversal_load(self):
        """Test that loading sanitizes the input as well."""
        # Create a file manually inside save dir
        target_file = os.path.join(self.save_dir, "target.json")
        self.manager.save_game(self.game, "target")

        # Attempt to load using traversal to reach it (mimicking behavior if we were trying to escape)
        # In this case, we just want to verify load_game calls sanitize.
        # If we pass "../target", it should sanitize to "target" and successfully load the file at saves/target.json

        loaded = self.manager.load_game("../target")
        self.assertIsNotNone(loaded, "Failed to load game with sanitized path")

    def test_special_characters_sanitization(self):
        """Test that special characters are removed."""
        weird_slot = "slot$#@!_test"
        self.manager.save_game(self.game, weird_slot)

        expected_name = "slottest.json" # $#@!_ removed? No, underscore is kept.
        # My regex was [^a-zA-Z0-9_-]
        # So $ # @ ! should be removed. _ is kept.
        expected_name = "slot_test.json"

        self.assertTrue(os.path.exists(os.path.join(self.save_dir, expected_name)))

if __name__ == '__main__':
    unittest.main()
