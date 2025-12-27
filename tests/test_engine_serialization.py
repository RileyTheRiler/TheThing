import tempfile
import unittest

from entities.crew_member import CrewMember
from entities.item import Item
from entities.station_map import StationMap
from systems.persistence import SaveManager
from src.engine import GameState


class TestGameStateSerialization(unittest.TestCase):
    def test_round_trip_uses_shared_models(self):
        """Ensure save/load round-trip hydrates shared entity models."""
        with tempfile.TemporaryDirectory() as tmpdir:
            game = GameState(seed=123)

            # Add a custom item to validate inventory serialization.
            game.player.add_item(Item("Test Sample", "Round-trip token"), game.turn)

            manager = SaveManager(save_dir=tmpdir, game_state_factory=GameState.from_dict)
            self.assertTrue(manager.save_game(game, "roundtrip"))

            loaded = manager.load_game("roundtrip")
            self.assertIsInstance(loaded, GameState)
            self.assertIsInstance(loaded.station_map, StationMap)
            self.assertTrue(all(isinstance(member, CrewMember) for member in loaded.crew))
            self.assertTrue(any(item.name == "Test Sample" for item in loaded.player.inventory))

            for member in loaded.crew:
                for item in member.inventory:
                    self.assertIsInstance(item, Item)


if __name__ == "__main__":
    unittest.main()
