import os
import sys

import pytest

# Add project root and src directory to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
sys.path.insert(0, PROJECT_ROOT)

from core.event_system import event_bus, EventType
from core.resolution import Skill
from engine import GameState


@pytest.fixture(autouse=True)
def clear_event_bus():
    event_bus.clear()
    yield
    event_bus.clear()


def test_helicopter_escape_emits_endgame_event():
    captured = []
    game = GameState(seed=1)
    event_bus.subscribe(EventType.ENDING_REPORT, captured.append)
    game.rng.calculate_success = lambda pool: {"success": True, "success_count": pool, "dice": [6] * pool}

    hangar = game.station_map.rooms["Hangar"]
    game.player.location = (hangar[0], hangar[1])
    game.helicopter_status = "FIXED"
    game.player.skills[Skill.PILOT] = 5

    game.attempt_escape()

    assert captured, "Endgame system should emit an ending event on helicopter escape"
    assert captured[0].payload["ending_id"] == "helicopter_escape"


def test_radio_rescue_emits_endgame_event_on_arrival():
    captured = []
    game = GameState(seed=2)
    event_bus.subscribe(EventType.ENDING_REPORT, captured.append)
    game.rng.calculate_success = lambda pool: {"success": True, "success_count": pool, "dice": [6] * pool}

    radio_room = game.station_map.rooms["Radio Room"]
    game.player.location = (radio_room[0], radio_room[1])

    game.attempt_radio_signal()
    game.rescue_turns_remaining = 1

    game.advance_turn()

    assert captured, "Endgame system should emit when rescue arrives after SOS"
    assert captured[0].payload["ending_id"] == "radio_rescue"


def test_sole_survivor_emits_endgame_event():
    captured = []
    game = GameState(seed=3)
    event_bus.subscribe(EventType.ENDING_REPORT, captured.append)

    for member in game.crew:
        if member != game.player:
            member.is_alive = False

    game.advance_turn()

    assert captured, "Endgame system should emit when only the player remains"
    assert captured[0].payload["ending_id"] == "sole_survivor"
