"""
Tests for the DEPLOY command which allows players to place
deployable items like tripwire alarms at their location.
"""

import os
import sys
import pytest
from types import SimpleNamespace

# Add src to path so imports resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entities.item import Item
from core.event_system import event_bus, EventType, GameEvent
from systems.commands import DeployCommand, GameContext


class MockPlayer:
    """Mock player for testing."""
    def __init__(self, location=(5, 5)):
        self.name = "MacReady"
        self.location = location
        self.inventory = []

    def add_item(self, item, turn=0):
        self.inventory.append(item)

    def remove_item(self, item_name):
        for i, item in enumerate(self.inventory):
            if item.name.upper() == item_name.upper():
                return self.inventory.pop(i)
        return None


class MockStationMap:
    """Mock station map for testing."""
    def get_room_name(self, x, y):
        return "Rec Room"


@pytest.fixture(autouse=True)
def reset_event_bus():
    event_bus.clear()
    yield
    event_bus.clear()


@pytest.fixture
def game_state():
    """Create a mock game state for testing."""
    class MockGameState:
        def __init__(self):
            self.player = MockPlayer()
            self.station_map = MockStationMap()
            self.turn = 1
            self.deployed_items = {}

        def advance_turn(self):
            self.turn += 1

    return MockGameState()


@pytest.fixture
def deployable_item():
    """Create a deployable tripwire item."""
    item = Item("Tripwire Alarm", "A deployable wire trap")
    item.deployable = True
    item.effect = "alerts_on_trigger"
    item.uses = 1
    return item


@pytest.fixture
def non_deployable_item():
    """Create a non-deployable item."""
    return Item("Copper Wire", "A roll of wire")


class TestDeployCommand:
    """Tests for the DEPLOY command."""

    def test_deploy_requires_item_name(self, game_state):
        """DEPLOY without item name should show error."""
        errors = []
        event_bus.subscribe(EventType.ERROR, errors.append)

        cmd = DeployCommand()
        context = GameContext(game_state)
        cmd.execute(context, [])

        assert len(errors) > 0
        assert "Usage" in errors[0].payload.get("text", "")

    def test_deploy_item_not_in_inventory(self, game_state):
        """DEPLOY item not in inventory should warn."""
        warnings = []
        event_bus.subscribe(EventType.WARNING, warnings.append)

        cmd = DeployCommand()
        context = GameContext(game_state)
        cmd.execute(context, ["tripwire"])

        assert len(warnings) > 0
        assert "don't have" in warnings[0].payload.get("text", "")

    def test_deploy_non_deployable_item(self, game_state, non_deployable_item):
        """DEPLOY non-deployable item should warn."""
        game_state.player.add_item(non_deployable_item)
        warnings = []
        event_bus.subscribe(EventType.WARNING, warnings.append)

        cmd = DeployCommand()
        context = GameContext(game_state)
        cmd.execute(context, ["copper wire"])

        assert len(warnings) > 0
        assert "can't be deployed" in warnings[0].payload.get("text", "")

    def test_deploy_success(self, game_state, deployable_item):
        """Successfully deploying an item should work."""
        game_state.player.add_item(deployable_item)
        messages = []
        event_bus.subscribe(EventType.MESSAGE, messages.append)

        initial_turn = game_state.turn
        cmd = DeployCommand()
        context = GameContext(game_state)
        cmd.execute(context, ["tripwire alarm"])

        # Item should be removed from inventory
        assert len(game_state.player.inventory) == 0

        # Item should be in deployed_items
        player_pos = game_state.player.location
        assert player_pos in game_state.deployed_items
        deployed = game_state.deployed_items[player_pos]
        assert deployed['item_name'] == "Tripwire Alarm"
        assert deployed['room'] == "Rec Room"
        assert deployed['triggered'] is False

        # Turn should advance
        assert game_state.turn == initial_turn + 1

        # Message should be emitted
        assert any("deploy" in m.payload.get("text", "").lower() for m in messages)

    def test_cannot_deploy_at_same_location_twice(self, game_state, deployable_item):
        """Cannot deploy two items at the same location."""
        # Deploy first item
        game_state.player.add_item(deployable_item)
        cmd = DeployCommand()
        context = GameContext(game_state)
        cmd.execute(context, ["tripwire alarm"])

        # Try to deploy second item
        second_item = Item("Another Tripwire", "Another trap")
        second_item.deployable = True
        game_state.player.add_item(second_item)

        warnings = []
        event_bus.subscribe(EventType.WARNING, warnings.append)
        cmd.execute(context, ["another tripwire"])

        assert len(warnings) > 0
        assert "already" in warnings[0].payload.get("text", "").lower()

    def test_deploy_tracks_turn_deployed(self, game_state, deployable_item):
        """Deployed item should record the turn it was deployed."""
        game_state.turn = 10
        game_state.player.add_item(deployable_item)

        cmd = DeployCommand()
        context = GameContext(game_state)
        cmd.execute(context, ["tripwire alarm"])

        player_pos = game_state.player.location
        deployed = game_state.deployed_items[player_pos]
        assert deployed['turn_deployed'] == 10

    def test_deploy_stores_effect(self, game_state, deployable_item):
        """Deployed item should store its effect type."""
        game_state.player.add_item(deployable_item)

        cmd = DeployCommand()
        context = GameContext(game_state)
        cmd.execute(context, ["tripwire alarm"])

        player_pos = game_state.player.location
        deployed = game_state.deployed_items[player_pos]
        assert deployed['effect'] == 'alerts_on_trigger'


class TestDeployCommandListsDeployables:
    """Test that DEPLOY command shows available deployable items."""

    def test_shows_deployable_items_when_no_args(self, game_state, deployable_item):
        """DEPLOY without args should list deployable items if any."""
        game_state.player.add_item(deployable_item)
        messages = []
        event_bus.subscribe(EventType.MESSAGE, messages.append)

        cmd = DeployCommand()
        context = GameContext(game_state)
        cmd.execute(context, [])

        # Should show available deployables
        assert any("Tripwire Alarm" in m.payload.get("text", "") for m in messages)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
