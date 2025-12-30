"""
Tests for newly implemented features:
- Tripwire trigger mechanism
- Thermal blanket integration
- Portable Blood Test Kit
- Enhanced search memory (spiral pattern)
- Audio event mappings
"""

import os
import sys
import pytest

# Add src to path so imports resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entities.item import Item
from entities.crew_member import CrewMember
from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, Skill


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Reset event bus before each test."""
    event_bus.clear()
    yield
    event_bus.clear()


class MockStationMap:
    """Mock station map for testing."""
    def __init__(self):
        self.walkable = {}

    def get_room_name(self, x, y):
        return "Rec Room"

    def is_walkable(self, x, y):
        return self.walkable.get((x, y), True)


class MockRNG:
    """Mock RNG for deterministic tests."""
    def __init__(self, value=0.5):
        self.value = value

    def random_float(self):
        return self.value

    def random(self):
        return self.value

    def choose(self, items):
        return items[0] if items else None


class TestTripwireTrigger:
    """Tests for tripwire trigger mechanism in AI."""

    def test_tripwire_triggers_when_npc_walks_over(self):
        """Tripwire should trigger when NPC moves to its location."""
        from systems.ai import AISystem

        # Setup
        ai_system = AISystem()
        station_map = MockStationMap()

        class MockGameState:
            def __init__(self):
                self.turn = 1
                self.station_map = station_map
                self.deployed_items = {
                    (5, 5): {
                        'item_name': 'Tripwire Alarm',
                        'room': 'Rec Room',
                        'turn_deployed': 1,
                        'effect': 'alerts_on_trigger',
                        'triggered': False
                    }
                }

        game_state = MockGameState()

        # Create NPC at tripwire location
        npc = CrewMember("Childs", "Mechanic", "Aggressive")
        npc.location = (5, 5)

        # Track events
        warnings = []
        perception_events = []
        event_bus.subscribe(EventType.WARNING, warnings.append)
        event_bus.subscribe(EventType.PERCEPTION_EVENT, perception_events.append)

        # Trigger tripwire check
        ai_system._check_tripwire_trigger(npc, game_state)

        # Verify tripwire triggered
        assert len(warnings) > 0
        assert "Tripwire Alarm" in warnings[0].payload.get("text", "")
        assert "Childs" in warnings[0].payload.get("text", "")

        # Verify perception event emitted
        assert len(perception_events) > 0
        assert perception_events[0].payload.get("source") == "tripwire"

        # Verify tripwire removed
        assert (5, 5) not in game_state.deployed_items

    def test_tripwire_does_not_trigger_twice(self):
        """Already triggered tripwire should not trigger again."""
        from systems.ai import AISystem

        ai_system = AISystem()
        station_map = MockStationMap()

        class MockGameState:
            def __init__(self):
                self.turn = 1
                self.station_map = station_map
                self.deployed_items = {
                    (5, 5): {
                        'item_name': 'Tripwire Alarm',
                        'room': 'Rec Room',
                        'turn_deployed': 1,
                        'effect': 'alerts_on_trigger',
                        'triggered': True  # Already triggered
                    }
                }

        game_state = MockGameState()
        npc = CrewMember("Childs", "Mechanic", "Aggressive")
        npc.location = (5, 5)

        warnings = []
        event_bus.subscribe(EventType.WARNING, warnings.append)

        ai_system._check_tripwire_trigger(npc, game_state)

        # No warnings should be emitted
        assert len(warnings) == 0


class TestThermalBlanketIntegration:
    """Tests for thermal blanket heat masking."""

    def test_thermal_blanket_reduces_detection_pool(self):
        """Thermal blanket should reduce Thing's thermal detection pool."""
        from systems.stealth import StealthSystem

        stealth_system = StealthSystem()

        # Create player with thermal blanket
        class MockPlayer:
            def __init__(self):
                self.name = "MacReady"
                self.inventory = []
                self.attributes = {Attribute.PROWESS: 2}
                self.skills = {Skill.STEALTH: 1}

        player = MockPlayer()

        # Add thermal blanket
        blanket = Item("Thermal Blanket", "Heat masking blanket")
        blanket.effect = "masks_heat"
        blanket.effect_value = 3
        blanket.uses = 5
        player.inventory.append(blanket)

        # Check bonus
        bonus = stealth_system._get_thermal_blanket_bonus(player)
        assert bonus == 3

    def test_no_bonus_without_blanket(self):
        """No thermal bonus without blanket."""
        from systems.stealth import StealthSystem

        stealth_system = StealthSystem()

        class MockPlayer:
            def __init__(self):
                self.name = "MacReady"
                self.inventory = []

        player = MockPlayer()
        bonus = stealth_system._get_thermal_blanket_bonus(player)
        assert bonus == 0

    def test_no_bonus_when_blanket_depleted(self):
        """No bonus when thermal blanket has no uses left."""
        from systems.stealth import StealthSystem

        stealth_system = StealthSystem()

        class MockPlayer:
            def __init__(self):
                self.name = "MacReady"
                self.inventory = []

        player = MockPlayer()

        # Add depleted thermal blanket
        blanket = Item("Thermal Blanket", "Heat masking blanket")
        blanket.effect = "masks_heat"
        blanket.effect_value = 3
        blanket.uses = 0  # Depleted
        player.inventory.append(blanket)

        bonus = stealth_system._get_thermal_blanket_bonus(player)
        assert bonus == 0


class TestPortableBloodTestKit:
    """Tests for Portable Blood Test Kit functionality."""

    def test_kit_allows_testing(self):
        """Portable Blood Test Kit should allow testing without scalpel/wire."""
        from systems.commands import TestCommand, GameContext

        class MockPlayer:
            def __init__(self):
                self.name = "MacReady"
                self.location = (5, 5)
                self.inventory = []

        class MockTarget:
            def __init__(self):
                self.name = "Childs"
                self.location = (5, 5)
                self.is_infected = False

        class MockBloodTestSim:
            def start_test(self, name):
                return f"Testing {name}..."

            def heat_wire(self, rng):
                return "Wire heating..."

            def apply_wire(self, is_infected, rng):
                return "NORMAL"

        class MockMissionary:
            def trigger_reveal(self, target, reason):
                pass

        class MockStationMap:
            def get_room_name(self, x, y):
                return "Rec Room"

        class MockGameState:
            def __init__(self):
                self.player = MockPlayer()
                self.crew = [MockTarget()]
                self.station_map = MockStationMap()
                self.blood_test_sim = MockBloodTestSim()
                self.missionary_system = MockMissionary()
                self.rng = MockRNG()

        game_state = MockGameState()

        # Add Portable Blood Test Kit
        kit = Item("Portable Blood Test Kit", "Portable testing kit")
        kit.effect = "portable_test"
        kit.uses = 3
        game_state.player.inventory.append(kit)

        # Track events
        messages = []
        event_bus.subscribe(EventType.MESSAGE, messages.append)

        cmd = TestCommand()
        context = GameContext(game_state)
        cmd.execute(context, ["Childs"])

        # Should have used the kit
        assert any("Portable Blood Test Kit" in m.payload.get("text", "") for m in messages)

        # Kit should have one less use
        assert kit.uses == 2

    def test_kit_depletes_after_uses(self):
        """Kit should be removed when depleted."""
        from systems.commands import TestCommand, GameContext

        class MockPlayer:
            def __init__(self):
                self.name = "MacReady"
                self.location = (5, 5)
                self.inventory = []

        class MockTarget:
            def __init__(self):
                self.name = "Childs"
                self.location = (5, 5)
                self.is_infected = False

        class MockBloodTestSim:
            def start_test(self, name):
                return f"Testing {name}..."

            def heat_wire(self, rng):
                return "Wire heating..."

            def apply_wire(self, is_infected, rng):
                return "NORMAL"

        class MockMissionary:
            def trigger_reveal(self, target, reason):
                pass

        class MockStationMap:
            def get_room_name(self, x, y):
                return "Rec Room"

        class MockGameState:
            def __init__(self):
                self.player = MockPlayer()
                self.crew = [MockTarget()]
                self.station_map = MockStationMap()
                self.blood_test_sim = MockBloodTestSim()
                self.missionary_system = MockMissionary()
                self.rng = MockRNG()

        game_state = MockGameState()

        # Add Portable Blood Test Kit with 1 use
        kit = Item("Portable Blood Test Kit", "Portable testing kit")
        kit.effect = "portable_test"
        kit.uses = 1
        game_state.player.inventory.append(kit)

        # Track events
        warnings = []
        event_bus.subscribe(EventType.WARNING, warnings.append)

        cmd = TestCommand()
        context = GameContext(game_state)
        cmd.execute(context, ["Childs"])

        # Kit should be removed (depleted)
        assert len(game_state.player.inventory) == 0
        assert any("depleted" in w.payload.get("text", "").lower() for w in warnings)


class TestEnhancedSearchMemory:
    """Tests for enhanced search memory with spiral pattern."""

    def test_search_history_initialization(self):
        """Search should initialize search_history set."""
        from systems.ai import AISystem

        ai_system = AISystem()
        station_map = MockStationMap()

        class MockGameState:
            def __init__(self):
                self.turn = 1
                self.station_map = station_map

        game_state = MockGameState()

        npc = CrewMember("Childs", "Mechanic", "Aggressive")
        npc.location = (5, 5)

        ai_system._enter_search_mode(npc, (5, 5), "Rec Room", game_state)

        # Should have search_history
        assert hasattr(npc, 'search_history')
        assert isinstance(npc.search_history, set)

        # Should have search_anchor
        assert hasattr(npc, 'search_anchor')
        assert npc.search_anchor == (5, 5)

    def test_search_turns_extended(self):
        """Search turns should be extended to 8."""
        from systems.ai import AISystem

        assert AISystem.SEARCH_TURNS == 8

    def test_search_spiral_radius(self):
        """Search should have spiral radius configuration."""
        from systems.ai import AISystem

        assert AISystem.SEARCH_SPIRAL_RADIUS == 3

    def test_search_adds_multiple_rooms(self):
        """Search should add adjacent rooms, not just corridors."""
        from systems.ai import AISystem

        ai_system = AISystem()
        station_map = MockStationMap()

        class MockGameState:
            def __init__(self):
                self.turn = 1
                self.station_map = station_map

        game_state = MockGameState()

        npc = CrewMember("Childs", "Mechanic", "Aggressive")
        npc.location = (5, 5)

        ai_system._enter_search_mode(npc, (5, 5), "Rec Room", game_state)

        # Should have multiple search targets (spiral pattern)
        assert len(npc.search_targets) > 1

    def test_search_history_tracks_checked_locations(self):
        """Search should track checked locations in history."""
        from systems.ai import AISystem

        ai_system = AISystem()
        station_map = MockStationMap()

        class MockGameState:
            def __init__(self):
                self.turn = 1
                self.station_map = station_map

        game_state = MockGameState()

        npc = CrewMember("Childs", "Mechanic", "Aggressive")
        npc.location = (5, 5)
        npc.search_targets = [(5, 5), (5, 6)]
        npc.search_turns_remaining = 5
        npc.current_search_target = (5, 5)
        npc.search_history = set()

        # Simulate reaching target
        ai_system._execute_search(npc, game_state)

        # Should have added location to history
        assert (5, 5) in npc.search_history or "Rec Room" in npc.search_history


class TestAudioEventMappings:
    """Tests for audio event mappings."""

    def test_stealth_report_has_audio_mapping(self):
        """STEALTH_REPORT should have audio mapping."""
        from audio.audio_manager import AudioManager, Sound

        assert EventType.STEALTH_REPORT in AudioManager.EVENT_MAP
        assert AudioManager.EVENT_MAP[EventType.STEALTH_REPORT] == Sound.TENSION

    def test_combat_log_has_audio_mapping(self):
        """COMBAT_LOG should have audio mapping."""
        from audio.audio_manager import AudioManager, Sound

        assert EventType.COMBAT_LOG in AudioManager.EVENT_MAP
        assert AudioManager.EVENT_MAP[EventType.COMBAT_LOG] == Sound.IMPACT

    def test_trust_threshold_has_audio_mapping(self):
        """TRUST_THRESHOLD_CROSSED should have audio mapping."""
        from audio.audio_manager import AudioManager, Sound

        assert EventType.TRUST_THRESHOLD_CROSSED in AudioManager.EVENT_MAP
        assert AudioManager.EVENT_MAP[EventType.TRUST_THRESHOLD_CROSSED] == Sound.SUSPICION

    def test_new_sounds_have_frequencies(self):
        """New sounds should have frequency mappings."""
        from audio.audio_manager import AudioManager, Sound

        assert Sound.TENSION in AudioManager.FREQUENCIES
        assert Sound.SUSPICION in AudioManager.FREQUENCIES
        assert Sound.IMPACT in AudioManager.FREQUENCIES

    def test_new_sounds_have_durations(self):
        """New sounds should have duration mappings."""
        from audio.audio_manager import AudioManager, Sound

        assert Sound.TENSION in AudioManager.DURATIONS
        assert Sound.SUSPICION in AudioManager.DURATIONS
        assert Sound.IMPACT in AudioManager.DURATIONS


class TestCrewMemberSearchSerialization:
    """Tests for search memory serialization."""

    def test_search_history_serializes(self):
        """Search history should serialize to list."""
        npc = CrewMember("Childs", "Mechanic", "Aggressive")
        npc.search_history = {(1, 2), (3, 4), "Rec Room"}
        npc.search_anchor = (5, 5)
        npc.search_spiral_radius = 2
        npc.search_targets = [(1, 1), (2, 2)]
        npc.search_turns_remaining = 5

        data = npc.to_dict()

        assert "search_history" in data
        assert isinstance(data["search_history"], list)
        assert "search_anchor" in data
        assert data["search_anchor"] == (5, 5)
        assert data["search_spiral_radius"] == 2
        assert data["search_turns_remaining"] == 5

    def test_search_history_deserializes(self):
        """Search history should deserialize from list to set."""
        data = {
            "name": "Childs",
            "role": "Mechanic",
            "behavior_type": "Aggressive",
            "location": [5, 5],
            "search_history": [(1, 2), (3, 4)],
            "search_anchor": [5, 5],
            "search_spiral_radius": 2,
            "search_targets": [[1, 1], [2, 2]],
            "search_turns_remaining": 5
        }

        npc = CrewMember.from_dict(data)

        assert isinstance(npc.search_history, set)
        assert npc.search_anchor == (5, 5)
        assert npc.search_spiral_radius == 2
        assert len(npc.search_targets) == 2
        assert npc.search_turns_remaining == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
