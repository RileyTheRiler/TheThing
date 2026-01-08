
import unittest
import os
import shutil
from src.systems.persistence import SaveManager
from tests.test_persistence import MockGameState

class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.save_dir = "tests/test_saves_security"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        self.manager = SaveManager(save_dir=self.save_dir)

    def tearDown(self):
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)

    def test_path_traversal_prevention(self):
        """Test that directory traversal characters are sanitized."""
        game = MockGameState("SecurityTest")

        # Try to save to a parent directory
        malicious_slot = "../../../passwd"
        self.manager.save_game(game, malicious_slot)

        # Check that it was NOT saved in the parent directory
        # The sanitizer should have stripped the dots and slashes
        # leaving just "passwd" or similar

        expected_sanitized = "passwd"
        expected_path = os.path.join(self.save_dir, f"{expected_sanitized}.json")

        self.assertTrue(os.path.exists(expected_path), "Sanitized file should exist in save dir")
        self.assertFalse(os.path.exists(f"../{expected_sanitized}.json"), "File should not exist in parent dir")

    def test_special_chars_sanitization(self):
        """Test that special characters are removed but spaces kept."""
        game = MockGameState("SecurityTest")

        # Slot with spaces and special chars
        complex_slot = "my save @#$ file!"
        self.manager.save_game(game, complex_slot)

        # Expect only alphanumeric, underscore, hyphen, space
        # "my save  file" (spaces preserved, special chars removed)

        expected_sanitized = "my save  file"
        expected_path = os.path.join(self.save_dir, f"{expected_sanitized}.json")

        self.assertTrue(os.path.exists(expected_path), f"File should be saved as {expected_sanitized}.json")

if __name__ == '__main__':
    unittest.main()
