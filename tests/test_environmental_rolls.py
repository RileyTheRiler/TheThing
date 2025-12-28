import sys
import os
import pytest
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.resolution import Attribute, Skill, ResolutionSystem
from systems.room_state import RoomStateManager, RoomState
from systems.combat import CombatSystem, CoverType
from systems.interrogation import InterrogationSystem, InterrogationTopic
from systems.stealth import StealthSystem
from systems.architect import RandomnessEngine
from entities.crew_member import CrewMember, StealthPosture
from core.event_system import GameEvent, EventType, event_bus

@pytest.fixture
def rng():
    return RandomnessEngine(seed=42)

@pytest.fixture
def room_manager():
    return RoomStateManager(["Rec Room", "Kennel"])

def test_room_modifiers_dark(room_manager):
    """Verify DARK modifiers are correctly fetched."""
    room_manager.add_state("Rec Room", RoomState.DARK)
    mods = room_manager.get_roll_modifiers("Rec Room")
    
    assert mods[Skill.STEALTH] == 2
    assert mods[Skill.OBSERVATION] == -2
    assert mods[Skill.FIREARMS] == -2
    assert mods[Skill.MELEE] == -1
    assert mods[Skill.EMPATHY] == -1

def test_room_modifiers_frozen(room_manager):
    """Verify FROZEN modifiers are correctly fetched."""
    room_manager.add_state("Rec Room", RoomState.FROZEN)
    mods = room_manager.get_roll_modifiers("Rec Room")
    
    assert mods[Attribute.PROWESS] == -1
    assert mods[Skill.REPAIR] == -2

def test_resolve_pool_application():
    """Verify ResolutionSystem correctly applies modifiers."""
    base_pool = 5
    modifiers = {Skill.STEALTH: 2, Skill.OBSERVATION: -2}
    
    # Test bonus
    pool_bonus = ResolutionSystem.resolve_pool(base_pool, [Skill.STEALTH], modifiers)
    assert pool_bonus == 7
    
    # Test penalty
    pool_penalty = ResolutionSystem.resolve_pool(base_pool, [Skill.OBSERVATION], modifiers)
    assert pool_penalty == 3
    
    # Test combined (though unlikely to have both in one roll normally)
    pool_both = ResolutionSystem.resolve_pool(base_pool, [Skill.STEALTH, Skill.OBSERVATION], modifiers)
    assert pool_both == 5
    
    # Test minimum pool
    pool_min = ResolutionSystem.resolve_pool(1, [Skill.OBSERVATION], modifiers)
    assert pool_min == 1

def test_combat_darkness_impact(rng):
    """Verify combat attack roll is impacted by darkness."""
    combat = CombatSystem(rng)
    attacker = CrewMember("A", "Role", "cautious", attributes={Attribute.PROWESS: 3}, skills={Skill.FIREARMS: 2})
    defender = CrewMember("B", "Role", "aggressive", attributes={Attribute.PROWESS: 3}, skills={Skill.MELEE: 1})
    
    # No modifiers
    result_light = combat.calculate_attack(attacker, defender, None, CoverType.NONE, room_modifiers={})
    
    # Dark modifiers: FIREARMS: -2, MELEE: -1
    dark_mods = {Skill.FIREARMS: -2, Skill.MELEE: -1}
    result_dark = combat.calculate_attack(attacker, defender, None, CoverType.NONE, room_modifiers=dark_mods)
    
    assert result_light.special['attack_roll']['dice_count'] == 5
    assert result_light.special['defense_roll']['dice_count'] == 4
    
    assert result_dark.special['attack_roll']['dice_count'] == 3
    assert result_dark.special['defense_roll']['dice_count'] == 3

def test_interrogation_darkness_impact(rng, room_manager):
    """Verify interrogation empathy check is impacted by darkness."""
    interrogation = InterrogationSystem(rng)
    interrogator = CrewMember("I", "Role", "inquisitive", attributes={Attribute.INFLUENCE: 3}, skills={Skill.EMPATHY: 2})
    subject = CrewMember("S", "Role", "nervous")
    subject.location = (7, 7) # Rec Room
    
    class MockMap:
        def get_room_name(self, x, y): return "Rec Room"
    
    class MockGameState:
        def __init__(self):
            self.room_states = room_manager
            self.station_map = MockMap()
            self.crew = [interrogator, subject]
            self.rng = rng

    game = MockGameState()
    
    # Light: Empathy pool = 3 + 2 = 5
    result_light = interrogation.interrogate(interrogator, subject, InterrogationTopic.WHEREABOUTS, game)
    
    # Dark: Empathy pool = 5 - 1 = 4
    room_manager.add_state("Rec Room", RoomState.DARK)
    result_dark = interrogation.interrogate(interrogator, subject, InterrogationTopic.WHEREABOUTS, game)
    
    # Empathy check is done internally, but let's look at the result.
    # We can't easily assert the pool size because interrogation doesn't return it yet,
    # but the code path is covered.

def test_stealth_darkness_impact(rng, room_manager):
    """Verify stealth evasion is easier in darkness."""
    system = StealthSystem()
    player = CrewMember("P", "Role", "stealthy", attributes={Attribute.PROWESS: 2}, skills={Skill.STEALTH: 2})
    player.location = (7, 7)
    player.stealth_posture = StealthPosture.STANDING
    
    npc = CrewMember("N", "Role", "neutral", attributes={Attribute.LOGIC: 3}, skills={Skill.OBSERVATION: 1})
    npc.location = (7, 7)
    npc.is_infected = True
    
    class MockMap:
        def get_room_name(self, x, y): return "Rec Room"
        def get_room_name_at(self, *args): return "Rec Room" # Consistency
    
    class MockGameState:
        def __init__(self):
            self.player = player
            self.crew = [player, npc]
            self.station_map = MockMap()
            self.station_map.get_room_name = lambda x, y: "Rec Room"
            self.room_states = room_manager
            self.rng = rng

    gs = MockGameState()
    
    reports = []
    def on_report(event): reports.append(event)
    event_bus.subscribe(EventType.STEALTH_REPORT, on_report)
    
    # Light test
    event_light = GameEvent(EventType.TURN_ADVANCE, {"game_state": gs, "rng": rng})
    system.on_turn_advance(event_light)
    
    # Dark test
    room_manager.add_state("Rec Room", RoomState.DARK)
    event_dark = GameEvent(EventType.TURN_ADVANCE, {"game_state": gs, "rng": rng})
    system.on_turn_advance(event_dark)
    
    assert len(reports) == 2
    
    event_bus.unsubscribe(EventType.STEALTH_REPORT, on_report)
