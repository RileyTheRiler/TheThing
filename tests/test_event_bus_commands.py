import sys
import os
from types import SimpleNamespace

import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.event_system import event_bus, EventType
from systems.architect import RandomnessEngine
from systems.commands import AttackCommand, GameContext
from systems.interrogation import InterrogationSystem, InterrogationTopic
from systems.room_state import RoomStateManager
from entities.station_map import StationMap
from entities.crew_member import CrewMember
from core.resolution import Attribute, Skill


@pytest.fixture(autouse=True)
def clear_event_bus():
    """Ensure the global event bus has no subscribers between tests."""
    event_bus.clear()
    yield
    event_bus.clear()


@pytest.fixture
def sample_crew():
    """Create sample crew members for interrogation tests."""
    macready = CrewMember(
        name="MacReady",
        role="Pilot",
        behavior_type="cautious",
        attributes={Attribute.PROWESS: 3, Attribute.LOGIC: 2, Attribute.RESOLVE: 3},
        skills={Skill.PILOT: 3, Skill.FIREARMS: 2, Skill.MELEE: 1},
    )
    childs = CrewMember(
        name="Childs",
        role="Mechanic",
        behavior_type="aggressive",
        attributes={Attribute.PROWESS: 4, Attribute.LOGIC: 2, Attribute.RESOLVE: 2},
        skills={Skill.MELEE: 3, Skill.REPAIR: 2},
    )
    return [macready, childs]


def test_attack_command_emits_event():
    """Attack command should emit ATTACK_RESULT instead of printing."""
    events = []
    event_bus.subscribe(EventType.ATTACK_RESULT, lambda e: events.append(e))

    class DummyMember:
        def __init__(self, name, roll_counts, health=3):
            self.name = name
            self.inventory = []
            self.location = (0, 0)
            self.is_alive = True
            self.roll_counts = roll_counts
            self.health = health

        def roll_check(self, *_args):
            return self.roll_counts.pop(0)

        def take_damage(self, amount):
            self.health -= amount
            if self.health <= 0:
                self.is_alive = False
                return True
            return False

    weapon = SimpleNamespace(name="Axe", weapon_skill=Skill.MELEE, damage=2)
    player = DummyMember("MacReady", [{"success_count": 3}], health=3)
    player.inventory = [weapon]
    target = DummyMember("Palmer", [{"success_count": 0}], health=2)

    station_map = StationMap()
    game_state = SimpleNamespace(
        player=player,
        crew=[player, target],
        station_map=station_map,
        rng=RandomnessEngine(seed=1),
    )

    context = GameContext(game=game_state)
    AttackCommand().execute(context, ["Palmer"])

    assert len(events) == 1
    payload = events[0].payload
    assert payload["attacker"] == "MacReady"
    assert payload["target"] == "Palmer"
    assert payload["hit"] is True
    assert payload["damage"] > 0


def test_interrogation_emits_event(sample_crew):
    """Interrogations emit INTERROGATION_RESULT for UI routing."""
    events = []
    event_bus.subscribe(EventType.INTERROGATION_RESULT, lambda e: events.append(e))

    macready, childs = sample_crew
    station_map = StationMap()
    game_state = SimpleNamespace(crew=sample_crew, station_map=station_map, rng=RandomnessEngine(seed=7))

    interrogation = InterrogationSystem(game_state.rng)
    interrogation.interrogate(macready, childs, InterrogationTopic.WHEREABOUTS, game_state)

    assert len(events) == 1
    payload = events[0].payload
    assert payload["interrogator"] == macready.name
    assert payload["subject"] == childs.name
    assert payload["topic"] == InterrogationTopic.WHEREABOUTS.value
    assert payload["dialogue"]


def test_barricade_command_emits_event():
    """Barricading a room emits BARRICADE_ACTION for UI."""
    events = []
    event_bus.subscribe(EventType.BARRICADE_ACTION, lambda e: events.append(e))

    manager = RoomStateManager(["Rec Room"])
    manager.barricade_room("Rec Room", actor="MacReady")

    assert len(events) == 1
    payload = events[0].payload
    assert payload["action"] in {"built", "reinforced"}
    assert payload["room"] == "Rec Room"
    assert payload["actor"] == "MacReady"
    assert payload["strength"] >= 1
