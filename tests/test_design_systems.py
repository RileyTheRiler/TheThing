import os
import sys
from types import SimpleNamespace

import pytest

# Ensure src is on path
sys.path.append(os.getcwd())

from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent
from systems.stealth import StealthSystem
from systems.crafting import CraftingSystem
from systems.endgame import EndgameSystem
from systems.architect import RandomnessEngine
from entities.item import Item


class DummyStationMap:
    def get_room_name(self, *_):
        return "Rec Room"


class DummyMember:
    def __init__(self, name, infected=False, location=(0, 0)):
        self.name = name
        self.is_infected = infected
        self.is_alive = True
        self.location = location
        self.inventory = []

    def add_item(self, item, turn=0):
        self.inventory.append(item)
        item.add_history(turn, f"Added to {self.name}")


@pytest.fixture(autouse=True)
def reset_event_bus():
    event_bus.clear()
    yield
    event_bus.clear()


def test_stealth_system_emits_report_on_encounter():
    registry = DesignBriefRegistry()
    rng = RandomnessEngine(seed=1)
    rng.random_float = lambda: 0.0  # Force detection path

    player = DummyMember("MacReady", infected=False, location=(1, 1))
    infected = DummyMember("Palmer", infected=True, location=(1, 1))
    game_state = SimpleNamespace(
        player=player,
        crew=[player, infected],
        station_map=DummyStationMap(),
        turn=1
    )

    StealthSystem(registry)
    captured = []
    event_bus.subscribe(EventType.STEALTH_REPORT, captured.append)

    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state, "rng": rng}))

    assert registry.event_type_name("stealth") == "STEALTH_REPORT"
    assert captured, "Stealth system should emit a report event"
    assert captured[0].payload["opponent"] == "Palmer"
    assert captured[0].payload["outcome"] == "detected"


def test_crafting_system_completes_recipe_and_emits_event():
    registry = DesignBriefRegistry()
    rng = RandomnessEngine(seed=2)
    crafter = DummyMember("Nauls")
    crafter.inventory = [
        Item("Lantern", "Light source"),
        Item("Copper Wire", "Wiring")
    ]

    game_state = SimpleNamespace(turn=3)
    crafting = CraftingSystem(registry)
    crafting.queue_craft(crafter, "makeshift_torch", game_state, crafter.inventory)

    crafted_events = []
    event_bus.subscribe(EventType.CRAFTING_REPORT, crafted_events.append)

    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state, "rng": rng}))

    crafted_names = [item.name for item in crafter.inventory]
    assert registry.event_type_name("crafting") == "CRAFTING_REPORT"
    assert any(e.payload.get("event") == "completed" for e in crafted_events)
    assert "Makeshift Torch" in crafted_names
    assert not any(item.name == "Copper Wire" for item in crafter.inventory)


def test_endgame_system_emits_on_game_over():
    registry = DesignBriefRegistry()
    rng = RandomnessEngine(seed=3)
    endgame = EndgameSystem(registry)

    game_state = SimpleNamespace(turn=9)
    game_state.check_game_over = lambda: (True, True, "Rescue team touches down.")

    captured = []
    event_bus.subscribe(EventType.ENDING_REPORT, captured.append)

    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state, "rng": rng}))

    assert registry.event_type_name("endings") == "ENDING_REPORT"
    assert captured, "Endgame system should emit when game over is reached"
    assert captured[0].payload["result"] == "win"
    assert "Rescue team" in captured[0].payload["message"]
