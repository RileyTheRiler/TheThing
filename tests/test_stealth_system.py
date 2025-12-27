import os
import sys
from types import SimpleNamespace

import pytest

# Ensure src is on path
sys.path.append(os.getcwd())

from core.event_system import event_bus
from core.resolution import Attribute, Skill
from systems.architect import RandomnessEngine
from systems.room_state import RoomState, RoomStateManager
from systems.stealth import StealthPosture, StealthSystem
from entities.station_map import StationMap


class DummyMember:
    def __init__(self, name, logic=2, observation=1, location=(0, 0)):
        self.name = name
        self.attributes = {Attribute.LOGIC: logic}
        self.skills = {Skill.OBSERVATION: observation}
        self.location = location
        self.is_alive = True


@pytest.fixture(autouse=True)
def reset_event_bus():
    event_bus.clear()
    yield
    event_bus.clear()


def _build_game_state(player, observer, power_on=True):
    station_map = StationMap()
    room_states = RoomStateManager(list(station_map.rooms.keys()))
    return SimpleNamespace(
        power_on=power_on,
        player=player,
        crew=[player, observer],
        station_map=station_map,
        room_states=room_states,
        rng=RandomnessEngine(seed=99),
    )


def test_detection_probability_drops_in_darkness():
    player = DummyMember("Player", location=(11, 11))  # Lab
    observer = DummyMember("Observer", logic=3, observation=2, location=(11, 11))
    game_state = _build_game_state(player, observer, power_on=True)

    stealth = StealthSystem()
    bright = stealth.get_detection_chance(observer, player, game_state, noise_level=0)

    # Lights off and room in darkness should reduce detection odds
    game_state.power_on = False
    game_state.room_states.add_state("Lab", RoomState.DARK)
    dark = stealth.get_detection_chance(observer, player, game_state, noise_level=0)

    stealth.cleanup()

    assert dark < bright
    assert dark > 0


def test_noise_increases_detection_probability():
    player = DummyMember("Player", location=(11, 11))
    observer = DummyMember("Observer", logic=2, observation=2, location=(11, 11))
    game_state = _build_game_state(player, observer, power_on=True)

    stealth = StealthSystem()
    quiet = stealth.get_detection_chance(observer, player, game_state, noise_level=0)
    loud = stealth.get_detection_chance(observer, player, game_state, noise_level=3)

    stealth.cleanup()

    assert loud > quiet
    assert loud <= 1.0


def test_hidden_posture_reduces_detection():
    player = DummyMember("Player", location=(11, 11))
    observer = DummyMember("Observer", logic=2, observation=1, location=(11, 11))
    game_state = _build_game_state(player, observer, power_on=True)

    stealth = StealthSystem()
    stealth.set_posture(player, StealthPosture.HIDDEN)
    hidden = stealth.get_detection_chance(observer, player, game_state, noise_level=0)

    stealth.set_posture(player, StealthPosture.EXPOSED)
    exposed = stealth.get_detection_chance(observer, player, game_state, noise_level=0)

    stealth.cleanup()

    assert hidden < exposed
