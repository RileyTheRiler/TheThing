import json
import os
import sys
from pathlib import Path

import pytest

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from engine import GameState  # noqa: E402
from entities.item import Item  # noqa: E402
from entities.crew_member import CrewMember  # noqa: E402
from entities.station_map import StationMap  # noqa: E402


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    with open(FIXTURES / name, "r") as handle:
        return json.load(handle)


def test_partial_save_hydrates_defaults():
    data = load_fixture("partial_save.json")

    game = GameState.from_dict(data)

    assert game.turn == data["turn"]
    assert game.power_on is False
    assert game.rng.seed == data["rng"]["seed"]
    assert game.station_map.width == data["station_map"]["width"]
    assert game.station_map.height == data["station_map"]["height"]
    # Crew list should fall back to generated defaults when missing/empty in save
    assert len(game.crew) > 0
    # Trust matrix should hydrate when present
    assert game.trust_system.matrix == data["trust"]
    assert game.journal == data["journal"]


def test_corrupted_item_raises_clear_error():
    data = load_fixture("corrupted_item.json")

    with pytest.raises(ValueError):
        Item.from_dict(data)


def test_corrupted_crew_raises_clear_error():
    data = load_fixture("corrupted_crew.json")

    with pytest.raises(ValueError):
        CrewMember.from_dict(data)


def test_station_map_handles_missing_room_items():
    raw_data = {"width": 6, "height": 6}

    sm = StationMap.from_dict(raw_data)

    assert sm.width == 6
    assert sm.height == 6
    assert sm.room_items == {}


def test_schema_file_captures_core_sections():
    schema_path = Path("docs/save_schema.json")
    assert schema_path.exists(), "Save schema file should be present."

    with open(schema_path, "r") as handle:
        schema = json.load(handle)

    definitions = schema.get("definitions", {})
    for key in ("item", "crewMember", "rngState", "stationMap"):
        assert key in definitions, f"Schema missing definition for {key}"
