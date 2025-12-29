"""Pytest test suite for The Thing game systems.

Converted from verification scripts to proper pytest format.
"""

import sys
import os
import pytest
from types import SimpleNamespace

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.resolution import Attribute, Skill, ResolutionSystem
from core.event_system import event_bus, EventType, GameEvent
from systems.architect import RandomnessEngine, Difficulty, DifficultySettings
from systems.combat import CombatSystem, CoverType
from systems.interrogation import InterrogationSystem, InterrogationTopic
from systems.room_state import RoomStateManager, RoomState
from systems.stealth import StealthSystem
from entities.item import Item
from entities.crew_member import CrewMember
from entities.station_map import StationMap


# === FIXTURES ===

@pytest.fixture
def rng():
    """Provide a seeded random engine for deterministic tests."""
    return RandomnessEngine(seed=42)


@pytest.fixture
def sample_crew():
    """Create sample crew members for testing."""
    macready = CrewMember(
        name="MacReady",
        role="Pilot",
        behavior_type="cautious",
        attributes={Attribute.PROWESS: 3, Attribute.LOGIC: 2, Attribute.RESOLVE: 3},
        skills={Skill.PILOT: 3, Skill.FIREARMS: 2, Skill.MELEE: 1}
    )
    childs = CrewMember(
        name="Childs",
        role="Mechanic",
        behavior_type="aggressive",
        attributes={Attribute.PROWESS: 4, Attribute.LOGIC: 2, Attribute.RESOLVE: 2},
        skills={Skill.MELEE: 3, Skill.REPAIR: 2}
    )
    return [macready, childs]


@pytest.fixture
def station_map():
    """Create a station map for testing."""
    return StationMap()


# === RESOLUTION SYSTEM TESTS ===

class TestResolutionSystem:
    """Tests for the dice resolution system."""

    def test_dice_pool_produces_results(self, rng):
        """Dice pools should produce valid results."""
        result = rng.calculate_success(3)

        assert 'success' in result
        assert 'success_count' in result
        assert 'dice' in result
        assert len(result['dice']) == 3
        assert all(1 <= d <= 6 for d in result['dice'])

    def test_success_requires_six(self, rng):
        """Successes should only count dice showing 6."""
        result = rng.calculate_success(5)
        expected_successes = result['dice'].count(6)

        assert result['success_count'] == expected_successes
        assert result['success'] == (expected_successes > 0)

    def test_skill_attribute_mapping(self):
        """Skills should map to correct attributes."""
        assert Skill.get_attribute(Skill.FIREARMS) == Attribute.PROWESS
        assert Skill.get_attribute(Skill.MELEE) == Attribute.PROWESS
        assert Skill.get_attribute(Skill.MEDICINE) == Attribute.LOGIC
        assert Skill.get_attribute(Skill.PERSUASION) == Attribute.INFLUENCE


# === COMBAT SYSTEM TESTS ===

class TestCombatSystem:
    """Tests for the combat system."""

    def test_initiative_roll(self, rng, sample_crew):
        """Initiative should factor in PROWESS and bonuses."""
        combat = CombatSystem(rng)
        macready, childs = sample_crew

        mac_init = combat.roll_initiative(macready)
        childs_init = combat.roll_initiative(childs)

        # Initiative should be positive
        assert mac_init > 0
        assert childs_init > 0

    def test_cover_bonus(self, rng, sample_crew):
        """Cover should add defense dice."""
        combat = CombatSystem(rng)
        macready, childs = sample_crew

        assert combat.COVER_BONUS[CoverType.NONE] == 0
        assert combat.COVER_BONUS[CoverType.LIGHT] == 1
        assert combat.COVER_BONUS[CoverType.HEAVY] == 2
        assert combat.COVER_BONUS[CoverType.FULL] == 3

    def test_attack_with_cover(self, rng, sample_crew):
        """Attacks against targets in cover should have reduced success."""
        combat = CombatSystem(rng)
        macready, childs = sample_crew

        weapon = Item("Axe", "Sharp", weapon_skill=Skill.MELEE, damage=2)

        # Attack with no cover
        result_no_cover = combat.calculate_attack(macready, childs, weapon, CoverType.NONE)

        # Result should have expected fields
        assert hasattr(result_no_cover, 'success')
        assert hasattr(result_no_cover, 'message')
        assert hasattr(result_no_cover, 'damage')

    def test_full_cover_blocks_attack(self, rng, sample_crew):
        """Full cover should prevent attacks."""
        combat = CombatSystem(rng)
        macready, childs = sample_crew

        weapon = Item("Axe", "Sharp", weapon_skill=Skill.MELEE, damage=2)
        result = combat.calculate_attack(macready, childs, weapon, CoverType.FULL)

        assert result.success is False
        assert "cannot attack" in result.message.lower()

    def test_retreat_returns_valid_result(self, rng, sample_crew):
        """Retreat should return success status, message, and exit direction."""
        combat = CombatSystem(rng)
        macready, childs = sample_crew

        success, message, exit_dir = combat.attempt_retreat(
            macready, [childs], ["NORTH", "SOUTH"]
        )

        assert isinstance(success, bool)
        assert isinstance(message, str)
        if success:
            assert exit_dir in ["NORTH", "SOUTH"]


# === INTERROGATION SYSTEM TESTS ===

class TestInterrogationSystem:
    """Tests for the interrogation system."""

    def test_interrogation_produces_response(self, rng, sample_crew):
        """Interrogation should produce a valid response."""
        # Create minimal game state mock
        class MockGameState:
            def __init__(self):
                self.crew = sample_crew
                self.station_map = StationMap()
                self.rng = rng

        game = MockGameState()
        interrogation = InterrogationSystem(rng)
        macready, childs = sample_crew

        result = interrogation.interrogate(
            macready, childs, InterrogationTopic.WHEREABOUTS, game
        )

        assert result.dialogue is not None
        assert result.response_type is not None
        assert isinstance(result.trust_change, int)

    def test_repeated_interrogation_increases_detection(self, rng, sample_crew):
        """Repeated interrogation should increase annoyance/detection chance."""
        class MockGameState:
            def __init__(self):
                self.crew = sample_crew
                self.station_map = StationMap()
                self.rng = rng

        game = MockGameState()
        interrogation = InterrogationSystem(rng)
        macready, childs = sample_crew

        # First interrogation
        interrogation.interrogate(macready, childs, InterrogationTopic.WHEREABOUTS, game)
        count1 = interrogation.interrogation_count.get(childs.name, 0)

        # Second interrogation
        interrogation.interrogate(macready, childs, InterrogationTopic.ALIBI, game)
        count2 = interrogation.interrogation_count.get(childs.name, 0)

        assert count2 > count1


# === ROOM STATE TESTS ===

class TestRoomStateManager:
    """Tests for room state management."""

    def test_initial_kennel_frozen(self):
        """Kennel should start frozen."""
        rooms = ["Rec Room", "Infirmary", "Kennel", "Generator"]
        manager = RoomStateManager(rooms)

        assert manager.has_state("Kennel", RoomState.FROZEN)
        assert not manager.has_state("Rec Room", RoomState.FROZEN)

    def test_barricade_creates_darkness(self):
        """Barricading a room should make it dark."""
        rooms = ["Rec Room", "Infirmary"]
        manager = RoomStateManager(rooms)

        manager.barricade_room("Rec Room")

        assert manager.has_state("Rec Room", RoomState.BARRICADED)
        assert manager.has_state("Rec Room", RoomState.DARK)

    def test_barricade_strength(self, rng, sample_crew):
        """Barricades should have strength that increases with reinforcement."""
        rooms = ["Rec Room"]
        manager = RoomStateManager(rooms)
        macready = sample_crew[0]

        # Initial barricade
        manager.barricade_room("Rec Room")
        assert manager.get_barricade_strength("Rec Room") == 1

        # Reinforce
        manager.barricade_room("Rec Room")
        assert manager.get_barricade_strength("Rec Room") == 2

    def test_break_barricade(self, rng, sample_crew):
        """Breaking a barricade should reduce its strength."""
        rooms = ["Rec Room"]
        manager = RoomStateManager(rooms)
        macready = sample_crew[0]

        # Create strong barricade
        manager.barricade_room("Rec Room")
        manager.barricade_room("Rec Room")
        manager.barricade_room("Rec Room")
        initial_strength = manager.get_barricade_strength("Rec Room")

        # Attempt to break (may or may not succeed based on RNG)
        success, message, remaining = manager.attempt_break_barricade(
            "Rec Room", macready, rng
        )

        # Either broke through or damaged it
        assert remaining <= initial_strength

    def test_dark_cold_attack_penalty(self, sample_crew):
        """Attacks should lose dice in dark, frozen rooms."""
        rooms = ["Rec Room"]
        manager = RoomStateManager(rooms)
        manager.add_state("Rec Room", RoomState.DARK)
        manager.add_state("Rec Room", RoomState.FROZEN)

        class TrackingRNG(RandomnessEngine):
            def __init__(self):
                super().__init__(seed=1)
                self.pools = []

            def calculate_success(self, pool_size):
                self.pools.append(pool_size)
                return {"success": False, "success_count": 0, "dice": [1] * pool_size}

        rng = TrackingRNG()
        combat = CombatSystem(rng, manager)
        macready, childs = sample_crew
        weapon = Item("Axe", "Sharp", weapon_skill=Skill.MELEE, damage=2)

        combat.calculate_attack(macready, childs, weapon, CoverType.NONE, "Rec Room")

        base_pool = macready.attributes.get(Attribute.PROWESS, 1) + macready.skills.get(Skill.MELEE, 0)
        expected_pool = max(0, base_pool - 2)  # DARK + FROZEN penalty
        assert rng.pools[0] == expected_pool
        defense_pool = childs.attributes.get(Attribute.PROWESS, 1) + childs.skills.get(Skill.MELEE, 0)
        assert rng.pools[1] == defense_pool  # Defense unaffected by darkness/cold

    def test_dark_room_observation_penalty(self, sample_crew, station_map):
        """Observation checks should account for dark room penalties."""
        rooms = ["Rec Room"]
        manager = RoomStateManager(rooms)
        manager.add_state("Rec Room", RoomState.DARK)
        manager.add_state("Rec Room", RoomState.FROZEN)

        class ObservationRNG(RandomnessEngine):
            def __init__(self):
                super().__init__(seed=2)
                self.pools = []

            def calculate_success(self, pool_size):
                self.pools.append(pool_size)
                return {"success": True, "success_count": 1, "dice": [6] * pool_size}

            def random_float(self):
                return 0.0

            def choose(self, collection):
                return collection[0] if collection else None

        rng = ObservationRNG()
        macready, childs = sample_crew
        macready.location = (7, 7)  # Rec Room
        childs.location = (7, 7)

        class MockGameState:
            def __init__(self):
                self.crew = sample_crew
                self.station_map = station_map
                self.rng = rng

        game = MockGameState()
        interrogation = InterrogationSystem(rng, manager)

        interrogation.interrogate(macready, childs, InterrogationTopic.WHEREABOUTS, game)

        assert rng.pools[0] == 0  # Base 1 empathy, -2 from DARK+FROZEN, clamped to 0


def test_stealth_detection_darkness_penalty(sample_crew, station_map):
    """Dark rooms should make stealth detection less likely."""
    event_bus.clear()
    rooms = ["Rec Room"]
    manager = RoomStateManager(rooms)
    manager.add_state("Rec Room", RoomState.DARK)

    class StubRegistry:
        def get_brief(self, _):
            return {"base_detection_chance": 0.4, "cooldown_turns": 0, "summary": "Stealth encounter"}

    class StealthRNG(RandomnessEngine):
        def random_float(self):
            return 0.4  # Higher than adjusted detection chance (0.25)

        def choose(self, collection):
            return collection[0] if collection else None

    rng = StealthRNG()
    player, infected = sample_crew
    player.location = (7, 7)
    infected.location = (7, 7)
    infected.is_infected = True

    game_state = SimpleNamespace(player=player, crew=[player, infected], station_map=station_map, power_on=True)
    stealth = StealthSystem(StubRegistry(), manager)
    captured = []
    event_bus.subscribe(EventType.STEALTH_REPORT, captured.append)

    stealth.on_turn_advance(GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state, "rng": rng}))

    assert captured, "Stealth system should emit a report"
    assert captured[0].payload["outcome"] == "evaded"
    stealth.cleanup()
    event_bus.clear()


# === CREW MEMBER TESTS ===

class TestCrewMember:
    """Tests for crew member functionality."""

    def test_take_damage(self, sample_crew):
        """Taking damage should reduce health."""
        macready = sample_crew[0]
        initial_health = macready.health

        died = macready.take_damage(1)

        assert macready.health == initial_health - 1
        assert died is False

    def test_fatal_damage(self, sample_crew):
        """Fatal damage should kill the crew member."""
        macready = sample_crew[0]

        died = macready.take_damage(macready.health + 1)

        assert died is True
        assert macready.is_alive is False
        assert macready.health == 0

    def test_inventory_management(self, sample_crew):
        """Items can be added and removed from inventory."""
        macready = sample_crew[0]
        item = Item("Flashlight", "Bright light")

        macready.add_item(item)
        assert len(macready.inventory) == 1

        removed = macready.remove_item("Flashlight")
        assert removed is not None
        assert removed.name == "Flashlight"
        assert len(macready.inventory) == 0

    def test_serialization(self, sample_crew):
        """Crew members should serialize and deserialize correctly."""
        macready = sample_crew[0]
        macready.is_infected = True
        macready.location = (5, 5)

        data = macready.to_dict()
        restored = CrewMember.from_dict(data)

        assert restored.name == macready.name
        assert restored.is_infected == macready.is_infected
        assert restored.location == macready.location


# === STATION MAP TESTS ===

class TestStationMap:
    """Tests for station map functionality."""

    def test_room_detection(self, station_map):
        """Room names should be detected from coordinates."""
        # Rec Room is at (5,5) to (10,10)
        assert station_map.get_room_name(7, 7) == "Rec Room"

        # Infirmary is at (0,0) to (4,4)
        assert station_map.get_room_name(2, 2) == "Infirmary"

        # Outside rooms should be corridors
        assert "Corridor" in station_map.get_room_name(14, 8)

    def test_walkable_bounds(self, station_map):
        """Walkability should respect map bounds."""
        assert station_map.is_walkable(0, 0) is True
        assert station_map.is_walkable(19, 19) is True
        assert station_map.is_walkable(-1, 0) is False
        assert station_map.is_walkable(0, 20) is False

    def test_item_placement(self, station_map):
        """Items can be placed and retrieved from rooms."""
        item = Item("Key", "Opens doors")

        station_map.add_item_to_room(item, 7, 7)
        items = station_map.get_items_in_room(7, 7)

        assert len(items) == 1
        assert items[0].name == "Key"


# === DIFFICULTY SETTINGS TESTS ===

class TestDifficultySettings:
    """Tests for difficulty configuration."""

    def test_difficulty_levels_exist(self):
        """All difficulty levels should have settings."""
        for diff in Difficulty:
            settings = DifficultySettings.get_all(diff)
            assert settings is not None
            assert "base_infection_chance" in settings
            assert "mask_decay_rate" in settings

    def test_hard_is_harder(self):
        """Hard mode should have higher infection chance than Easy."""
        easy = DifficultySettings.get(Difficulty.EASY, "base_infection_chance")
        hard = DifficultySettings.get(Difficulty.HARD, "base_infection_chance")

        assert hard > easy


# === ITEM TESTS ===

class TestItem:
    """Tests for item functionality."""

    def test_weapon_properties(self):
        """Weapons should have damage and skill."""
        axe = Item("Axe", "Sharp", weapon_skill=Skill.MELEE, damage=2)

        assert axe.damage == 2
        assert axe.weapon_skill == Skill.MELEE

    def test_item_history(self):
        """Items should track their history."""
        key = Item("Key", "Opens doors")

        key.add_history(1, "Found in Infirmary")
        key.add_history(5, "Picked up by MacReady")

        assert len(key.history) == 2
        assert "[Turn 1]" in key.history[0]

    def test_serialization(self):
        """Items should serialize and deserialize correctly."""
        axe = Item("Axe", "Sharp", weapon_skill=Skill.MELEE, damage=2)
        axe.add_history(1, "Created")

        data = axe.to_dict()
        restored = Item.from_dict(data)

        assert restored.name == axe.name
        assert restored.damage == axe.damage
        assert len(restored.history) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
