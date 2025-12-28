import os
import sys
from types import SimpleNamespace

import pytest

# Ensure src is on path
sys.path.append(os.getcwd())

from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent
from entities.item import Item
from systems.crafting import CraftingSystem
from systems.commands import CommandDispatcher, GameContext


class DummyMember:
    def __init__(self, name):
        self.name = name
        self.inventory = []

    def add_item(self, item, turn=0):
        self.inventory.append(item)
        item.add_history(turn, f"Added to {self.name}")


@pytest.fixture(autouse=True)
def reset_event_bus():
    event_bus.clear()
    yield
    event_bus.clear()


def test_valid_recipe_consumes_ingredients_and_emits_events():
    registry = DesignBriefRegistry()
    crafter = DummyMember("MacReady")
    crafter.inventory = [Item("Lantern", "Light source"), Item("Copper Wire", "Wiring")]
    game_state = SimpleNamespace(turn=4, crafting_system=None, player=crafter)

    crafting = CraftingSystem(registry)
    game_state.crafting_system = crafting

    crafted_events = []
    pickup_events = []
    event_bus.subscribe(EventType.CRAFTING_REPORT, crafted_events.append)
    event_bus.subscribe(EventType.ITEM_PICKUP, pickup_events.append)

    queued = crafting.queue_craft(crafter, "makeshift_torch", game_state, crafter.inventory)
    assert queued
    event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state}))

    names = [item.name for item in crafter.inventory]
    assert "Lantern" not in names
    assert "Copper Wire" not in names
    assert "Makeshift Torch" in names
    assert any(e.payload.get("event") == "completed" for e in crafted_events)
    assert pickup_events[0].payload.get("item") == "Makeshift Torch"


def test_invalid_recipe_rejected_and_reports_error():
    registry = DesignBriefRegistry()
    crafter = DummyMember("Nauls")
    crafter.inventory = [Item("Lantern", "Light source")]
    game_state = SimpleNamespace(turn=1, crafting_system=None, player=crafter)
    crafting = CraftingSystem(registry)
    game_state.crafting_system = crafting

    crafted_events = []
    error_events = []
    event_bus.subscribe(EventType.CRAFTING_REPORT, crafted_events.append)
    event_bus.subscribe(EventType.ERROR, error_events.append)

    queued = crafting.queue_craft(crafter, "makeshift_torch", game_state, crafter.inventory)

    assert not queued
    assert not crafting.active_jobs
    assert crafted_events and crafted_events[0].payload.get("event") == "invalid"
    assert error_events
    assert all(item.name != "Makeshift Torch" for item in crafter.inventory)


def test_craft_command_dispatches_to_system_and_emits_queue_event():
    registry = DesignBriefRegistry()
    crafter = DummyMember("Nauls")
    crafter.inventory = [Item("Lantern", "Light source"), Item("Copper Wire", "Wiring")]
    game_state = SimpleNamespace(turn=2, crafting_system=None, player=crafter)

    crafting = CraftingSystem(registry)
    game_state.crafting_system = crafting
    dispatcher = CommandDispatcher()
    context = GameContext(game_state)

    crafted_events = []
    event_bus.subscribe(EventType.CRAFTING_REPORT, crafted_events.append)

    dispatched = dispatcher.dispatch("CRAFT", ["makeshift_torch"], context)
    assert dispatched
    assert crafting.active_jobs
    assert crafted_events and crafted_events[0].payload.get("event") == "queued"
