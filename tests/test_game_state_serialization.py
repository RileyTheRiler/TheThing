import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from engine import GameState  # noqa: E402
from entities.crew_member import CrewMember  # noqa: E402
from entities.item import Item  # noqa: E402


def test_game_state_round_trip_preserves_entities():
    game = GameState(seed=42)
    game.player.add_item(Item("Smoke Test Item", "Ensures serialization works"), turn=game.turn)

    crew_names = [member.name for member in game.crew]
    room_item_snapshot = {
        room: [item.name for item in items]
        for room, items in game.station_map.room_items.items()
    }

    serialized = game.to_dict()
    loaded = GameState.from_dict(serialized)

    try:
        assert [member.name for member in loaded.crew] == crew_names
        assert all(isinstance(member, CrewMember) for member in loaded.crew)
        assert any(item.name == "Smoke Test Item" for item in loaded.player.inventory)
        assert {
            room: [item.name for item in items]
            for room, items in loaded.station_map.room_items.items()
        } == room_item_snapshot
        assert all(isinstance(item, Item) for items in loaded.station_map.room_items.values() for item in items)
    finally:
        game.cleanup()
        loaded.cleanup()
