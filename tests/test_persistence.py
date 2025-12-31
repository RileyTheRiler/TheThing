
import unittest
import os
import json
import shutil
from src.systems.persistence import SaveManager

class MockGameState:
    def __init__(self, name="Test"):
        self.name = name
        self.turn = 1

    def to_dict(self):
        # Return a dict that satisfies REQUIRED_FIELDS in validate_save_data
        return {
            "name": self.name,
            "turn": self.turn,
            "difficulty": "NORMAL",
            "rng": {},
            "time_system": {},
            "station_map": {},
            "crew": [],
            "player_location": [0, 0], # List, as it's JSON serializable
            "save_version": 2,
            "checksum": "dummy" # Will be recomputed
        }

    @classmethod
    def from_dict(cls, data):
        g = cls(data.get("name", "Unknown"))
        g.turn = data.get("turn", 1)
        return g

class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.save_dir = "tests/test_saves"
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def tearDown(self):
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)

    def test_save_and_load_raw(self):
        """Test saving and loading without a factory (raw dict)."""
        manager = SaveManager(save_dir=self.save_dir)
        game = MockGameState("RawData")

        # Save
        self.assertTrue(manager.save_game(game, "raw_slot"))

        # Load
        data = manager.load_game("raw_slot")
        self.assertIsInstance(data, dict)
        self.assertEqual(data["name"], "RawData")
        self.assertEqual(data["turn"], 1)

    def test_save_and_load_with_factory(self):
        """Test saving and loading with hydration factory."""
        manager = SaveManager(save_dir=self.save_dir, game_state_factory=MockGameState.from_dict)
        game = MockGameState("FactoryData")
        game.turn = 5

        # Save
        self.assertTrue(manager.save_game(game, "factory_slot"))

        # Load
        loaded_game = manager.load_game("factory_slot")
        self.assertIsInstance(loaded_game, MockGameState)
        self.assertEqual(loaded_game.name, "FactoryData")
        self.assertEqual(loaded_game.turn, 5)

    def test_security_sanitization(self):
        """Test that save slot names are sanitized."""
        manager = SaveManager(save_dir=self.save_dir)
        game = MockGameState("SecurityData")

        # Attack vector: Path traversal
        dirty_slot = "../../etc/passwd"

        self.assertTrue(manager.save_game(game, dirty_slot))

        # Expected sanitized name: "etcpasswd" or similar depending on regex
        # My regex: re.sub(r'[^a-zA-Z0-9_\- ]', '', str(slot_name))
        # so "../../etc/passwd" -> "etcpasswd"

        sanitized_name = "etcpasswd.json"
        expected_path = os.path.join(self.save_dir, sanitized_name)

        self.assertTrue(os.path.exists(expected_path), f"File should exist at {expected_path}")
        self.assertFalse(os.path.exists("etc/passwd"), "File should NOT exist at etc/passwd")

if __name__ == '__main__':
    unittest.main()
