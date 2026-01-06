
import unittest
import os
import json
import shutil
from src.systems.persistence import SaveManager

class MockGameState:
    def __init__(self, name="Test"):
        self.name = name
        self.turn = 1
        self.player_location = (0, 0)
        self.crew = []
        self.difficulty = "NORMAL"
        self.rng = {}
        self.time_system = {}
        self.station_map = {}

    def to_dict(self):
        return {
            "name": self.name,
            "turn": self.turn,
            "player_location": list(self.player_location),
            "crew": self.crew,
            "difficulty": self.difficulty,
            "rng": self.rng,
            "time_system": self.time_system,
            "station_map": self.station_map
        }

    @classmethod
    def from_dict(cls, data):
        g = cls(data.get("name", "Test"))
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

    def test_path_traversal_prevention(self):
        """Test that path traversal attempts are sanitized."""
        manager = SaveManager(save_dir=self.save_dir)
        game = MockGameState("SecurityTest")

        # Attempt to save to a traversal path
        traversal_attempt = "../outside_save_dir"
        manager.save_game(game, traversal_attempt)

        # Check that file was NOT created outside
        outside_path = os.path.join(self.save_dir, "..", "outside_save_dir.json")
        self.assertFalse(os.path.exists(outside_path))

        # Check that it was saved to a sanitized name inside the dir
        # The sanitizer allows underscores, so `outside_save_dir` is expected
        sanitized_name = "outside_save_dir"
        expected_path = os.path.join(self.save_dir, f"{sanitized_name}.json")
        self.assertTrue(os.path.exists(expected_path))

if __name__ == '__main__':
    unittest.main()
