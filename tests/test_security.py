import os
import shutil
import unittest
from unittest.mock import MagicMock
import sys

# Ensure src is in path
sys.path.insert(0, os.path.abspath("src"))

from systems.persistence import SaveManager

class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.save_dir = "data/test_security_saves"
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)
        self.manager = SaveManager(save_dir=self.save_dir)

        # Mock GameState
        self.mock_game = MagicMock()
        self.mock_game.to_dict.return_value = {
            "turn": 1,
            "crew": [],
            "player_location": (0,0),
            "difficulty": "NORMAL",
            "rng": {},
            "time_system": {},
            "station_map": {}
        }

    def tearDown(self):
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)
        # Also clean up any potential escaped files
        if os.path.exists("traversal_test.json"):
            os.remove("traversal_test.json")

    def test_path_traversal_prevention(self):
        """Test that path traversal characters are sanitized from save slots."""
        # Attempt to save to parent directory
        unsafe_slot = "../traversal_test"

        success = self.manager.save_game(self.mock_game, unsafe_slot)
        self.assertTrue(success, "Save should succeed (by sanitizing name)")

        # Check that file does NOT exist in parent/root
        self.assertFalse(os.path.exists("traversal_test.json"), "File escaped to root directory")

        # Check that sanitized file exists in save dir
        sanitized_path = os.path.join(self.save_dir, "traversal_test.json")
        self.assertTrue(os.path.exists(sanitized_path), f"Sanitized file should exist at {sanitized_path}")

    def test_special_characters_sanitization(self):
        """Test removal of special characters from save slots."""
        unsafe_slot = "save!@#$%^&*()_+name"
        expected_name = "save_name" # Only alphanumeric, _, - allowed. Wait, my regex allowed space too.

        success = self.manager.save_game(self.mock_game, unsafe_slot)

        # Check what file was actually created
        files = os.listdir(self.save_dir)
        self.assertEqual(len(files), 1)
        created_file = files[0]

        # We expect 'save_name.json' (regex: [^a-zA-Z0-9_\-\s])
        # !@#$%^&*()_+ -> _ is allowed. + is not.
        # So "save" + "_" + "name" -> "save_name.json"

        self.assertEqual(created_file, "save_name.json")

if __name__ == "__main__":
    unittest.main()
