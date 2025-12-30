"""Tests for Stealth Skill Progression (XP System).

Verifies that:
- Successful evasions grant stealth XP
- XP thresholds trigger level ups
- Level bonuses apply correctly (noise reduction, pool bonus)
"""

import sys
sys.path.insert(0, "src")

from core.resolution import Attribute, Skill


class MockCrewMember:
    """Mock crew member for testing."""
    def __init__(self, name):
        self.name = name
        self.stealth_xp = 0
        self.stealth_level = 0
        self.silent_takedown_unlocked = False
        self.attributes = {Attribute.PROWESS: 2}
        self.skills = {Skill.STEALTH: 1}


def test_progression_system_init():
    """Test that ProgressionSystem initializes correctly."""
    from systems.progression import ProgressionSystem

    system = ProgressionSystem()

    assert system.STEALTH_LEVEL_THRESHOLDS == [100, 300, 600, 1000]
    assert len(system.LEVEL_BENEFITS) == 4

    system.cleanup()
    print("[PASS] ProgressionSystem initializes correctly")


def test_calculate_stealth_level():
    """Test level calculation from XP."""
    from systems.progression import ProgressionSystem

    system = ProgressionSystem()

    # Level 0: 0-99 XP
    assert system.calculate_stealth_level(0) == 0
    assert system.calculate_stealth_level(50) == 0
    assert system.calculate_stealth_level(99) == 0

    # Level 1: 100-299 XP
    assert system.calculate_stealth_level(100) == 1
    assert system.calculate_stealth_level(200) == 1
    assert system.calculate_stealth_level(299) == 1

    # Level 2: 300-599 XP
    assert system.calculate_stealth_level(300) == 2
    assert system.calculate_stealth_level(450) == 2

    # Level 3: 600-999 XP
    assert system.calculate_stealth_level(600) == 3
    assert system.calculate_stealth_level(800) == 3

    # Level 4: 1000+ XP
    assert system.calculate_stealth_level(1000) == 4
    assert system.calculate_stealth_level(2000) == 4

    system.cleanup()
    print("[PASS] Stealth level calculation works correctly")


def test_award_stealth_xp():
    """Test XP award and level up."""
    from systems.progression import ProgressionSystem

    system = ProgressionSystem()
    character = MockCrewMember("MacReady")

    # Award XP below level 1 threshold
    system.award_stealth_xp(character, 50)
    assert character.stealth_xp == 50
    assert character.stealth_level == 0

    # Award XP to reach level 1
    system.award_stealth_xp(character, 60)  # Now at 110 XP
    assert character.stealth_xp == 110
    assert character.stealth_level == 1

    system.cleanup()
    print("[PASS] XP award and level up works correctly")


def test_level_benefits():
    """Test that level benefits are correctly defined."""
    from systems.progression import ProgressionSystem

    system = ProgressionSystem()

    # Check benefits exist for each level
    assert 1 in system.LEVEL_BENEFITS
    assert 2 in system.LEVEL_BENEFITS
    assert 3 in system.LEVEL_BENEFITS
    assert 4 in system.LEVEL_BENEFITS

    # Level 4 should mention Silent Takedown
    assert "Silent Takedown" in system.LEVEL_BENEFITS[4]

    system.cleanup()
    print("[PASS] Level benefits are correctly defined")


def test_silent_takedown_unlock():
    """Test that level 4 unlocks silent takedown."""
    from systems.progression import ProgressionSystem

    system = ProgressionSystem()
    character = MockCrewMember("MacReady")

    # Award enough XP to reach level 4
    system.award_stealth_xp(character, 1000)

    assert character.stealth_level == 4
    assert character.silent_takedown_unlocked == True

    system.cleanup()
    print("[PASS] Silent takedown unlocks at level 4")


def test_noise_reduction_bonus():
    """Test noise reduction from stealth levels."""
    from entities.crew_member import CrewMember, StealthPosture

    member = CrewMember("Test", "Engineer", "Neutral")
    member.stealth_posture = StealthPosture.STANDING

    # Base noise
    base_noise = member.get_noise_level()

    # Level 1: -1 noise
    member.stealth_level = 1
    level1_noise = member.get_noise_level()
    assert level1_noise == base_noise - 1

    # Level 3: -2 noise total
    member.stealth_level = 3
    level3_noise = member.get_noise_level()
    assert level3_noise == base_noise - 2

    print("[PASS] Noise reduction bonus works correctly")


def test_pool_bonus():
    """Test stealth pool bonus from levels."""
    from entities.crew_member import CrewMember

    member = CrewMember("Test", "Engineer", "Neutral")

    # Level 0: no bonus
    member.stealth_level = 0
    assert member.get_stealth_level_pool_bonus() == 0

    # Level 2: +1 pool
    member.stealth_level = 2
    assert member.get_stealth_level_pool_bonus() == 1

    # Level 4: +2 pool total
    member.stealth_level = 4
    assert member.get_stealth_level_pool_bonus() == 2

    print("[PASS] Stealth pool bonus works correctly")


def test_get_stealth_progress():
    """Test progress tracking."""
    from systems.progression import ProgressionSystem

    system = ProgressionSystem()
    character = MockCrewMember("MacReady")
    character.stealth_xp = 150
    character.stealth_level = 1

    progress = system.get_stealth_progress(character)

    assert progress["xp"] == 150
    assert progress["level"] == 1
    assert progress["next_threshold"] == 300
    assert progress["max_level"] == False
    assert progress["xp_to_next"] == 150

    system.cleanup()
    print("[PASS] Progress tracking works correctly")


def test_max_level():
    """Test max level handling."""
    from systems.progression import ProgressionSystem

    system = ProgressionSystem()
    character = MockCrewMember("MacReady")
    character.stealth_xp = 1500
    character.stealth_level = 4

    progress = system.get_stealth_progress(character)

    assert progress["level"] == 4
    assert progress["max_level"] == True
    assert progress["progress"] == 100.0

    system.cleanup()
    print("[PASS] Max level handling works correctly")


if __name__ == "__main__":
    test_progression_system_init()
    test_calculate_stealth_level()
    test_award_stealth_xp()
    test_level_benefits()
    test_silent_takedown_unlock()
    test_noise_reduction_bonus()
    test_pool_bonus()
    test_get_stealth_progress()
    test_max_level()

    print("\n=== ALL PROGRESSION SYSTEM TESTS PASSED ===")
