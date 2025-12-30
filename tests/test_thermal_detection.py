"""Tests for Enhanced Thermal Detection system.

Verifies that:
- Thermal signatures are higher for infected characters (Things)
- Thermal detection works in darkness
- Thermal detection is blocked in frozen rooms
- Thermal goggles provide +3 detection pool bonus
- Reverse detection (Things detecting humans by heat) works
"""

import sys
sys.path.insert(0, "src")

from core.resolution import Attribute, Skill
from entities.item import Item
from systems.room_state import RoomState


class MockRng:
    """Mock RNG for deterministic tests."""
    def __init__(self, values=None):
        self.values = values or [6, 6, 1, 1, 1, 1]
        self.index = 0

    def random_int(self, min_val, max_val):
        val = self.values[self.index % len(self.values)]
        self.index += 1
        return min(max_val, max(min_val, val))

    def random_float(self):
        val = self.values[self.index % len(self.values)]
        self.index += 1
        return val / 10.0

    def calculate_success(self, pool_size):
        dice = []
        successes = 0
        for _ in range(pool_size):
            val = self.values[self.index % len(self.values)]
            self.index += 1
            dice.append(val)
            if val == 6:
                successes += 1
        return {
            'dice': dice,
            'success_count': successes,
            'success': successes > 0
        }


class MockCrewMember:
    """Mock crew member for testing."""
    def __init__(self, name, is_infected=False):
        self.name = name
        self.is_infected = is_infected
        self.is_alive = True
        self.location = (5, 5)
        self.attributes = {Attribute.PROWESS: 2, Attribute.LOGIC: 2, Attribute.THERMAL: 2}
        self.skills = {Skill.STEALTH: 1, Skill.OBSERVATION: 1}
        self.inventory = []
        self.stealth_xp = 0
        self.stealth_level = 0

    def get_thermal_signature(self):
        """Return thermal signature - infected run hotter."""
        base = self.attributes.get(Attribute.THERMAL, 2)
        if self.is_infected:
            return base + 3  # +3 for infected
        return base

    def get_thermal_detection_pool(self):
        """Return thermal detection pool."""
        base_pool = self.attributes.get(Attribute.THERMAL, 2)
        for item in self.inventory:
            if hasattr(item, 'effect') and item.effect == 'thermal_detection':
                base_pool += getattr(item, 'effect_value', 0)
        return base_pool


class MockStationMap:
    """Mock station map for testing."""
    def get_room_name(self, x, y):
        return "Test Room"


class MockRoomStateManager:
    """Mock room state manager for testing."""
    def __init__(self):
        self.room_states = {"Test Room": set()}

    def add_state(self, room_name, state):
        if room_name not in self.room_states:
            self.room_states[room_name] = set()
        self.room_states[room_name].add(state)

    def has_state(self, room_name, state):
        if room_name not in self.room_states:
            return False
        return state in self.room_states[room_name]

    def remove_state(self, room_name, state):
        if room_name in self.room_states:
            self.room_states[room_name].discard(state)

    def cleanup(self):
        pass


class MockGameState:
    """Mock game state for testing."""
    def __init__(self):
        self.rng = MockRng()
        self.player = MockCrewMember("MacReady")
        self.crew = []
        self.station_map = MockStationMap()
        self.room_states = MockRoomStateManager()
        self.room_states.add_state("Test Room", RoomState.DARK)


def test_thermal_signature_human():
    """Test that human characters have base thermal signature."""
    from entities.crew_member import CrewMember

    member = CrewMember("Test", "Engineer", "Neutral")
    member.is_infected = False

    signature = member.get_thermal_signature()

    # Base thermal is 2, no infection bonus
    assert signature == 2
    print("[PASS] Human thermal signature is base value (2)")


def test_thermal_signature_infected():
    """Test that infected characters have elevated thermal signature."""
    from entities.crew_member import CrewMember

    member = CrewMember("Test", "Engineer", "Neutral")
    member.is_infected = True

    signature = member.get_thermal_signature()

    # Base thermal (2) + infection bonus (3) = 5
    assert signature == 5
    print("[PASS] Infected thermal signature is elevated (5)")


def test_thermal_detection_pool_base():
    """Test base thermal detection pool without goggles."""
    from entities.crew_member import CrewMember

    member = CrewMember("Test", "Engineer", "Neutral")

    pool = member.get_thermal_detection_pool()

    # Base pool is the THERMAL attribute (2)
    assert pool == 2
    print("[PASS] Base thermal detection pool is 2")


def test_thermal_detection_pool_with_goggles():
    """Test thermal detection pool with thermal goggles."""
    from entities.crew_member import CrewMember

    member = CrewMember("Test", "Engineer", "Neutral")

    # Add thermal goggles
    goggles = Item(
        name="Thermal Goggles",
        description="Military-grade infrared goggles.",
        effect="thermal_detection",
        effect_value=3
    )
    member.inventory.append(goggles)

    pool = member.get_thermal_detection_pool()

    # Base (2) + goggles bonus (3) = 5
    assert pool == 5
    print("[PASS] Thermal detection pool with goggles is 5")


def test_thermal_detection_only_in_darkness():
    """Test that thermal detection requires darkness."""
    from systems.stealth import StealthSystem

    stealth = StealthSystem()

    observer = MockCrewMember("Observer")
    subject = MockCrewMember("Subject", is_infected=True)
    game_state = MockGameState()

    # Room is dark - detection should work
    ctx = stealth._prepare_detection_context(observer, subject, game_state, 0)
    assert ctx["is_dark"] == True
    assert ctx["is_frozen"] == False

    stealth.cleanup()
    print("[PASS] Thermal detection context includes darkness state")


def test_thermal_detection_blocked_in_frozen():
    """Test that frozen rooms block thermal detection."""
    from systems.stealth import StealthSystem

    stealth = StealthSystem()

    observer = MockCrewMember("Observer")
    subject = MockCrewMember("Subject", is_infected=True)
    game_state = MockGameState()

    # Make room frozen
    game_state.room_states.add_state("Test Room", RoomState.FROZEN)

    ctx = stealth._prepare_detection_context(observer, subject, game_state, 0)
    assert ctx["is_frozen"] == True

    stealth.cleanup()
    print("[PASS] Frozen rooms block thermal detection")


def test_reverse_thermal_detection_requires_infection():
    """Test that reverse thermal detection only works for infected NPCs."""
    from systems.stealth import StealthSystem

    stealth = StealthSystem()

    # Non-infected NPC cannot use reverse thermal detection
    npc = MockCrewMember("NPC", is_infected=False)
    player = MockCrewMember("Player")
    game_state = MockGameState()

    result = stealth.check_reverse_thermal_detection(npc, player, game_state)
    assert result == False

    stealth.cleanup()
    print("[PASS] Non-infected NPCs cannot use reverse thermal detection")


def test_reverse_thermal_detection_same_location():
    """Test that reverse thermal detection requires same location."""
    from systems.stealth import StealthSystem

    stealth = StealthSystem()

    npc = MockCrewMember("NPC", is_infected=True)
    player = MockCrewMember("Player")
    game_state = MockGameState()

    # Different locations
    npc.location = (1, 1)
    player.location = (5, 5)

    result = stealth.check_reverse_thermal_detection(npc, player, game_state)
    assert result == False

    stealth.cleanup()
    print("[PASS] Reverse thermal detection requires same location")


def test_reverse_thermal_detection_darkness_required():
    """Test that reverse thermal detection requires darkness."""
    from systems.stealth import StealthSystem

    stealth = StealthSystem()

    npc = MockCrewMember("NPC", is_infected=True)
    player = MockCrewMember("Player")
    game_state = MockGameState()
    game_state.room_states = MockRoomStateManager()  # No darkness (empty)

    npc.location = (5, 5)
    player.location = (5, 5)

    result = stealth.check_reverse_thermal_detection(npc, player, game_state)
    assert result == False

    stealth.cleanup()
    print("[PASS] Reverse thermal detection requires darkness")


def test_reverse_thermal_detection_frozen_blocks():
    """Test that frozen rooms block reverse thermal detection."""
    from systems.stealth import StealthSystem

    stealth = StealthSystem()

    npc = MockCrewMember("NPC", is_infected=True)
    player = MockCrewMember("Player")
    game_state = MockGameState()

    npc.location = (5, 5)
    player.location = (5, 5)

    # Room is dark AND frozen
    game_state.room_states.add_state("Test Room", RoomState.FROZEN)

    result = stealth.check_reverse_thermal_detection(npc, player, game_state)
    assert result == False

    stealth.cleanup()
    print("[PASS] Frozen rooms block reverse thermal detection")


def test_thermal_goggles_item_definition():
    """Test that thermal goggles item loads correctly."""
    import json

    with open("data/items.json", "r") as f:
        data = json.load(f)

    goggles = next((i for i in data["items"] if i["id"] == "thermal_goggles"), None)

    assert goggles is not None
    assert goggles["effect"] == "thermal_detection"
    assert goggles["effect_value"] == 3
    assert goggles["category"] == "tool"

    print("[PASS] Thermal goggles item defined correctly in items.json")


if __name__ == "__main__":
    test_thermal_signature_human()
    test_thermal_signature_infected()
    test_thermal_detection_pool_base()
    test_thermal_detection_pool_with_goggles()
    test_thermal_detection_only_in_darkness()
    test_thermal_detection_blocked_in_frozen()
    test_reverse_thermal_detection_requires_infection()
    test_reverse_thermal_detection_same_location()
    test_reverse_thermal_detection_darkness_required()
    test_reverse_thermal_detection_frozen_blocks()
    test_thermal_goggles_item_definition()

    print("\n=== ALL THERMAL DETECTION TESTS PASSED ===")
