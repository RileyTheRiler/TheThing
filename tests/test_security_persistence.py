import unittest
import os
import shutil
import json
from src.systems.persistence import SaveManager

class MockGameState:
    def __init__(self):
        self.turn = 1
        self.crew = []
        self.player_location = (0, 0)

    def to_dict(self):
        return {
            "turn": self.turn,
            "crew": self.crew,
            "player_location": list(self.player_location)
        }

class TestPathTraversal(unittest.TestCase):
    def setUp(self):
        self.save_dir = "tests/test_saves_traversal"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        # Clean up any previous attack artifacts
        if os.path.exists("traversal_attack.json"):
            os.remove("traversal_attack.json")

    def tearDown(self):
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)
        if os.path.exists("traversal_attack.json"):
            os.remove("traversal_attack.json")

    def test_path_traversal_save(self):
        manager = SaveManager(save_dir=self.save_dir)
        game = MockGameState()

        # Attempt to save outside the directory using path traversal
        # This resolves to ./traversal_attack.json (relative to repo root) if vulnerable
        manager.save_game(game, "../../traversal_attack")

        # Check if file exists in root (Vulnerability Check)
        is_vulnerable = os.path.exists("traversal_attack.json")

        # Check if file was sanitized and saved correctly in save dir
        sanitized_path = os.path.join(self.save_dir, "traversal_attack.json")
        is_sanitized = os.path.exists(sanitized_path)

        if is_vulnerable:
             print("\n[FAIL] File created outside save directory at ./traversal_attack.json")
        else:
             print("\n[SUCCESS] File was NOT created outside save directory")

        if is_sanitized:
             print("[SUCCESS] File was sanitized and created in save directory")
        else:
             print("[FAIL] File was NOT created in save directory")

        self.assertFalse(is_vulnerable, "Vulnerability Fix Failed: File created outside save directory")
        self.assertTrue(is_sanitized, "Sanitization Failed: File not created in save directory")

if __name__ == '__main__':
    unittest.main()
