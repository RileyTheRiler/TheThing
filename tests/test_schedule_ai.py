import json

import pytest

from engine import GameState


def _write_config(path, config):
    with open(path, "w") as f:
        json.dump(config, f)


def _minimal_character(room_name="Rec Room", start=0, end=6):
    return {
        "name": "Tester",
        "role": "Pilot",
        "behavior": "Calm",
        "attributes": {
            "Prowess": 1,
            "Logic": 1,
            "Influence": 1
        },
        "skills": {
            "Pilot": 1
        },
        "schedule": [
            {
                "start": start,
                "end": end,
                "room": room_name
            }
        ]
    }


def test_invalid_schedule_room_rejected(tmp_path):
    config_path = tmp_path / "characters.json"
    _write_config(config_path, [_minimal_character(room_name="Nonexistent")])

    with pytest.raises(ValueError):
        GameState(seed=1, characters_path=str(config_path))


def test_invalid_schedule_hours_rejected(tmp_path):
    config_path = tmp_path / "characters.json"
    _write_config(config_path, [_minimal_character(start=-1, end=24)])

    with pytest.raises(ValueError):
        GameState(seed=1, characters_path=str(config_path))


def test_npc_follows_schedule_over_day_cycle():
    game = GameState(seed=1, start_hour=0)
    childs = next(m for m in game.crew if m.name == "Childs")

    # Disable random events to keep movement deterministic for this test.
    game.random_events.events = []

    # Start from a consistent location to avoid random placement variance.
    childs.location = (0, 0)

    reached_generator = False
    returned_to_rec_room = False

    for hour in range(24):
        game.time_system.set_time(hour)
        game.ai_system.update_member_ai(childs, game)
        room = game.station_map.get_room_name(*childs.location)

        if 9 <= hour <= 17 and room == "Generator":
            reached_generator = True
        if (hour >= 20 or hour < 8) and room == "Rec Room":
            returned_to_rec_room = True

    assert reached_generator
    assert returned_to_rec_room


def test_lynch_mob_overrides_schedule_destination():
    game = GameState(seed=1, start_hour=10)
    childs = next(m for m in game.crew if m.name == "Childs")
    target = next(m for m in game.crew if m.name != childs.name)

    childs.location = (10, 10)
    target.location = (0, 0)
    game.time_system.set_time(10)

    # Trigger lynch mob override.
    game.lynch_mob.active_mob = True
    game.lynch_mob.target = target

    # Without override, Childs would step toward Generator from (10, 10) -> (11, 11)
    expected_schedule_step = (11, 11)

    game.ai_system.update_member_ai(childs, game)

    assert childs.location != expected_schedule_step
    assert childs.location[0] < 10
    assert childs.location[1] < 10
