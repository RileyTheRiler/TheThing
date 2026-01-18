
import unittest
import os
import json
import shutil
from src.systems.persistence import SaveManager

class MockGameState:
    def __init__(self, name="Test"):
        self.name = name
        self.turn = 1
        self.crew = []
        self.player_location = [0, 0]

    def to_dict(self):
        return {
            "name": self.name,
            "turn": self.turn,
            "crew": self.crew,
            "player_location": self.player_location
        }

    @classmethod
    def from_dict(cls, data):
        g = cls(data.get("name", "Test"))
        g.turn = data.get("turn", 1)
        g.crew = data.get("crew", [])
        g.player_location = data.get("player_location", [0, 0])
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

if __name__ == '__main__':
    unittest.main()
