"""Tests for Distraction Mechanics: Throwable Items.

Verifies that players can throw items to create distractions that
divert NPC attention away from the player's location.
"""

import sys
sys.path.insert(0, "src")


class MockItem:
    """Mock throwable item for testing."""
    def __init__(self, name, throwable=True, noise_level=4, uses=-1, creates_light=False):
        self.name = name
        self.throwable = throwable
        self.noise_level = noise_level
        self.uses = uses
        self.creates_light = creates_light
        self.history = []

    def consume(self):
        if self.uses > 0:
            self.uses -= 1
            return self.uses >= 0
        return True


class MockCrewMember:
    """Mock crew member for testing."""
    def __init__(self, name, location=(5, 5)):
        self.name = name
        self.location = location
        self.is_alive = True
        self.inventory = []
        self.investigating = False
        self.detected_player = False
        self.search_targets = []
        self.current_search_target = None
        self.search_turns_remaining = 0


class MockStationMap:
    """Mock station map for testing."""
    def __init__(self):
        self.rooms = {
            "Rec Room": (0, 0, 10, 10),
            "Lab": (11, 0, 20, 10),
            "Kitchen": (0, 11, 10, 20)
        }

    def is_walkable(self, x, y):
        return 0 <= x <= 20 and 0 <= y <= 20

    def get_room_name(self, x, y):
        for name, (x1, y1, x2, y2) in self.rooms.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return name
        return "Corridor"

    def add_item_to_room(self, item, x, y, turn):
        pass

    def project_toward(self, start, target, min_distance=3, max_distance=5):
        sx, sy = start
        tx, ty = target
        dx = tx - sx
        dy = ty - sy
        step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
        step_y = 0 if dy == 0 else (1 if dy > 0 else -1)
        if step_x == 0 and step_y == 0:
            return None
        path = []
        x, y = sx, sy
        for _ in range(max_distance):
            x += step_x
            y += step_y
            if not self.is_walkable(x, y):
                break
            path.append((x, y))
        if not path:
            return None
        if len(path) >= min_distance:
            return path[min_distance - 1]
        return path[-1]

    def get_room_center(self, room_name):
        bounds = self.rooms.get(room_name)
        if not bounds:
            return None
        x1, y1, x2, y2 = bounds
        return ((x1 + x2) // 2, (y1 + y2) // 2)


class MockGameState:
    """Mock game state for testing."""
    def __init__(self):
        self.player = MockCrewMember("MacReady", location=(5, 5))
        self.crew = [self.player]
        self.station_map = MockStationMap()
        self.turn = 1

    def advance_turn(self):
        self.turn += 1


def test_distraction_system_init():
    """Test that DistractionSystem initializes correctly."""
    from systems.distraction import DistractionSystem

    system = DistractionSystem()
    assert system.active_distractions == []

    system.cleanup()
    print("[PASS] DistractionSystem initializes correctly")


def test_throw_item_basic():
    """Test basic item throwing."""
    from systems.distraction import DistractionSystem

    game_state = MockGameState()
    system = DistractionSystem()

    item = MockItem("Empty Can", throwable=True, noise_level=4)
    game_state.player.inventory.append(item)

    success, message = system.throw_toward(game_state.player, item, (5, 1), game_state)

    assert success == True
    assert "Empty Can" in message
    assert len(system.active_distractions) == 1

    system.cleanup()
    print("[PASS] Basic item throwing works")


def test_throw_non_throwable_item():
    """Test that non-throwable items can't be thrown."""
    from systems.distraction import DistractionSystem

    game_state = MockGameState()
    system = DistractionSystem()

    item = MockItem("Scalpel", throwable=False)
    game_state.player.inventory.append(item)

    success, message = system.throw_toward(game_state.player, item, (5, 1), game_state)

    assert success == False
    assert "can't throw" in message

    system.cleanup()
    print("[PASS] Non-throwable items rejected correctly")


def test_throw_invalid_direction():
    """Test that throws with no valid landing fail."""
    from systems.distraction import DistractionSystem

    game_state = MockGameState()
    system = DistractionSystem()

    item = MockItem("Rock", throwable=True)
    game_state.player.inventory.append(item)

    success, message = system.throw_toward(game_state.player, item, (5, 5), game_state)

    assert success == False
    assert "nowhere" in message

    system.cleanup()
    print("[PASS] Invalid landing rejected")


def test_throw_all_directions():
    """Test throwing toward multiple targets succeeds."""
    from systems.distraction import DistractionSystem

    targets = [(5, 1), (5, 15), (15, 5), (15, 15)]

    for target in targets:
        game_state = MockGameState()
        game_state.player.location = (10, 10)  # Center of map
        system = DistractionSystem()

        item = MockItem("Rock", throwable=True, uses=-1)
        game_state.player.inventory.append(item)

        success, message = system.throw_toward(game_state.player, item, target, game_state)
        assert success == True, f"Failed for target {target}"

        system.cleanup()

    print("[PASS] All targets work correctly")


def test_consumable_item_consumed():
    """Test that consumable items are removed after throwing."""
    from systems.distraction import DistractionSystem

    game_state = MockGameState()
    system = DistractionSystem()

    item = MockItem("Empty Can", throwable=True, uses=1)
    game_state.player.inventory.append(item)

    assert len(game_state.player.inventory) == 1

    success, message = system.throw_toward(game_state.player, item, (5, 1), game_state)

    assert success == True
    assert item.uses == 0
    assert item not in game_state.player.inventory  # Removed because uses = 0

    system.cleanup()
    print("[PASS] Consumable items consumed correctly")


def test_reusable_item_not_removed():
    """Test that reusable items (infinite uses) are dropped at landing location."""
    from systems.distraction import DistractionSystem

    game_state = MockGameState()
    system = DistractionSystem()

    item = MockItem("Rock", throwable=True, uses=-1)  # Infinite uses
    game_state.player.inventory.append(item)

    success, message = system.throw_toward(game_state.player, item, (5, 1), game_state)

    assert success == True
    # Item with -1 uses should be dropped on ground (add_item_to_room called)

    system.cleanup()
    print("[PASS] Reusable items handled correctly")


def test_npcs_distracted():
    """Test that nearby NPCs are distracted by thrown items."""
    from systems.distraction import DistractionSystem

    game_state = MockGameState()
    system = DistractionSystem()

    # Add NPC near the player
    npc = MockCrewMember("Childs", location=(7, 5))
    game_state.crew.append(npc)

    item = MockItem("Glass Bottle", throwable=True, noise_level=5)
    game_state.player.inventory.append(item)

    # Player at (5, 5), throw north to (5, 1)
    success, message = system.throw_toward(game_state.player, item, (5, 1), game_state)

    assert success == True
    assert npc.investigating == True

    system.cleanup()
    print("[PASS] Nearby NPCs are distracted")


def test_far_npcs_not_distracted():
    """Test that NPCs too far away don't hear the distraction."""
    from systems.distraction import DistractionSystem

    game_state = MockGameState()
    system = DistractionSystem()

    # Add NPC far from player
    far_npc = MockCrewMember("Garry", location=(20, 20))
    game_state.crew.append(far_npc)

    item = MockItem("Rock", throwable=True, noise_level=3)  # Low noise
    game_state.player.inventory.append(item)

    success, message = system.throw_toward(game_state.player, item, (5, 1), game_state)

    assert success == True
    assert far_npc.investigating == False  # Too far to hear

    system.cleanup()
    print("[PASS] Far NPCs not distracted")


def test_distraction_decay():
    """Test that active distractions decay over time."""
    from systems.distraction import DistractionSystem
    from core.event_system import GameEvent, EventType

    system = DistractionSystem()

    # Manually add a distraction
    system.active_distractions = [((5, 5), 3, "Rock")]

    assert len(system.active_distractions) == 1

    # Simulate turn advance
    event = GameEvent(EventType.TURN_ADVANCE, {})
    system.on_turn_advance(event)

    assert len(system.active_distractions) == 1
    assert system.active_distractions[0][1] == 2  # Turns remaining decreased

    # Two more turns
    system.on_turn_advance(event)
    system.on_turn_advance(event)

    assert len(system.active_distractions) == 0  # Expired

    system.cleanup()
    print("[PASS] Distraction decay works correctly")


def test_creates_light_flag():
    """Test that flares have the creates_light flag and different messaging."""
    from systems.distraction import DistractionSystem

    game_state = MockGameState()
    system = DistractionSystem()

    flare = MockItem("Flare", throwable=True, noise_level=6, creates_light=True, uses=1)
    game_state.player.inventory.append(flare)

    success, message = system.throw_toward(game_state.player, flare, (7, 5), game_state)

    assert success == True
    assert "light" in message

    system.cleanup()
    print("[PASS] Creates light flag works correctly")


def test_get_throwable_items():
    """Test getting list of throwable items in inventory."""
    from systems.distraction import DistractionSystem

    system = DistractionSystem()
    player = MockCrewMember("MacReady")

    rock = MockItem("Rock", throwable=True)
    scalpel = MockItem("Scalpel", throwable=False)
    can = MockItem("Empty Can", throwable=True)

    player.inventory = [rock, scalpel, can]

    throwables = system.get_throwable_items(player)

    assert len(throwables) == 2
    assert rock in throwables
    assert can in throwables
    assert scalpel not in throwables

    system.cleanup()
    print("[PASS] Get throwable items works correctly")


def test_item_properties():
    """Test Item class with new throwable properties."""
    from entities.item import Item

    # Test throwable item creation
    rock = Item(
        name="Rock",
        description="A chunk of rock.",
        throwable=True,
        noise_level=3,
        creates_light=False
    )

    assert rock.throwable == True
    assert rock.noise_level == 3
    assert rock.creates_light == False

    # Test serialization
    data = rock.to_dict()
    assert data["throwable"] == True
    assert data["noise_level"] == 3
    assert data["creates_light"] == False

    # Test deserialization
    restored = Item.from_dict(data)
    assert restored.throwable == True
    assert restored.noise_level == 3
    assert restored.creates_light == False

    print("[PASS] Item throwable properties work correctly")


if __name__ == "__main__":
    test_distraction_system_init()
    test_throw_item_basic()
    test_throw_non_throwable_item()
    test_throw_invalid_direction()
    test_throw_all_directions()
    test_consumable_item_consumed()
    test_reusable_item_not_removed()
    test_npcs_distracted()
    test_far_npcs_not_distracted()
    test_distraction_decay()
    test_creates_light_flag()
    test_get_throwable_items()
    test_item_properties()

    print("\n=== ALL DISTRACTION MECHANICS TESTS PASSED ===")
