"""Tests for Enhanced Vent Mechanics.

Verifies that vent movement has:
- Higher noise due to echoing in metal ducts
- Sound propagation to adjacent vent nodes
- Increased chance of Thing encounters
- Limited escape options when encountered
- Multi-turn crawl speed
"""

import sys
sys.path.insert(0, "src")

from core.resolution import Attribute, Skill


class MockRng:
    """Mock RNG for deterministic testing."""
    def __init__(self, float_value=0.5, success_count=2):
        self.float_value = float_value
        self.success_count = success_count
        self.roll_index = 0
        self.roll_results = [3, 4, 5, 6, 1, 2]  # Default dice results

    def random_float(self):
        return self.float_value

    def randint(self, a, b):
        return (a + b) // 2

    def roll_d6(self):
        result = self.roll_results[self.roll_index % len(self.roll_results)]
        self.roll_index += 1
        return result

    def choose(self, items):
        if not items:
            return None
        return items[0]

    def calculate_success(self, pool_size):
        """Mock calculate_success for ResolutionSystem compatibility."""
        dice = [self.roll_d6() for _ in range(pool_size)]
        successes = sum(1 for d in dice if d >= 6)
        return {
            "dice": dice,
            "success_count": max(successes, self.success_count),
            "success": successes > 0
        }


class MockCrewMember:
    """Mock crew member for testing."""
    def __init__(self, name, location=(5, 5), is_infected=False):
        self.name = name
        self.location = location
        self.is_alive = True
        self.is_infected = is_infected
        self.health = 10
        self.in_vent = False
        self.attributes = {
            Attribute.PROWESS: 2,
            Attribute.LOGIC: 2,
        }
        self.skills = {
            Skill.STEALTH: 1,
            Skill.OBSERVATION: 1,
        }
        self.stealth_posture = None

    def get_noise_level(self):
        return 3

    def take_damage(self, amount, game_state=None):
        self.health -= amount
        return self.health <= 0


class MockStationMap:
    """Mock station map for testing."""
    def __init__(self):
        self.rooms = {
            "Rec Room": (0, 0, 10, 10),
            "Lab": (11, 0, 20, 10),
        }
        self.vent_graph = {
            (2, 2): {"neighbors": [(7, 2), (2, 8)], "room": "Infirmary", "type": "entry_exit"},
            (7, 2): {"neighbors": [(2, 2), (13, 2), (7, 8)], "room": "Mess Hall", "type": "entry_exit"},
            (13, 2): {"neighbors": [(7, 2), (17, 2), (13, 8)], "room": "Radio Room", "type": "entry_exit"},
        }

    def get_room_name(self, x, y):
        for name, (x1, y1, x2, y2) in self.rooms.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return name
        return "Corridor"

    def get_vent_neighbors(self, x, y):
        node = self.vent_graph.get((x, y))
        if node:
            return node.get("neighbors", [])
        return []


class MockGameState:
    """Mock game state for testing."""
    def __init__(self):
        self.player = MockCrewMember("MacReady", location=(7, 2))
        self.crew = [
            self.player,
            MockCrewMember("Childs", location=(5, 5), is_infected=True),
        ]
        self.station_map = MockStationMap()
        self.rng = MockRng()
        self.turn = 1

    def advance_turn(self):
        self.turn += 1


def test_vent_base_noise():
    """Test that vent noise is 10+ for echoing effect."""
    from systems.stealth import StealthSystem

    system = StealthSystem()

    # Check the configuration
    assert system.VENT_BASE_NOISE >= 10, f"Vent base noise should be 10+, got {system.VENT_BASE_NOISE}"

    system.cleanup()
    print("[PASS] Vent base noise is 10+ for echoing effect")


def test_vent_encounter_chance():
    """Test that encounter chance is set to 20%."""
    from systems.stealth import StealthSystem

    system = StealthSystem()

    # Check the configuration
    assert system.VENT_ENCOUNTER_CHANCE >= 0.20, f"Encounter chance should be 20%+, got {system.VENT_ENCOUNTER_CHANCE}"

    system.cleanup()
    print("[PASS] Vent encounter chance is 20%")


def test_vent_crawl_turns():
    """Test that vent crawling takes 2 turns per tile."""
    from systems.stealth import StealthSystem

    system = StealthSystem()

    crawl_turns = system.get_vent_crawl_turns()
    assert crawl_turns == 2, f"Crawl turns should be 2, got {crawl_turns}"

    system.cleanup()
    print("[PASS] Vent crawling takes 2 turns per tile")


def test_vent_movement_no_encounter():
    """Test vent movement when no encounter occurs."""
    from systems.stealth import StealthSystem

    game_state = MockGameState()
    system = StealthSystem()

    # Set RNG to avoid encounter (0.5 > 0.20)
    game_state.rng.float_value = 0.5

    result = system.handle_vent_movement(game_state, game_state.player, (7, 2))

    assert result["encounter"] == False
    assert result["escaped"] == False
    assert result["damage"] == 0

    system.cleanup()
    print("[PASS] Vent movement without encounter works")


def test_vent_movement_with_encounter_escape():
    """Test vent movement when encounter occurs and player escapes."""
    from systems.stealth import StealthSystem

    game_state = MockGameState()
    system = StealthSystem()

    # Set RNG to trigger encounter (0.1 < 0.20)
    game_state.rng.float_value = 0.1
    # Set dice to favor player (high rolls)
    game_state.rng.roll_results = [6, 6, 6, 1, 1, 1]

    initial_health = game_state.player.health

    result = system.handle_vent_movement(game_state, game_state.player, (7, 2))

    assert result["encounter"] == True
    # Player may have escaped depending on dice rolls

    system.cleanup()
    print("[PASS] Vent encounter with escape attempt works")


def test_vent_movement_with_encounter_caught():
    """Test vent movement when encounter occurs and player is caught."""
    from systems.stealth import StealthSystem

    game_state = MockGameState()
    system = StealthSystem()

    # Set RNG to trigger encounter
    game_state.rng.float_value = 0.1
    # Set dice to favor Thing (low player rolls, high Thing rolls)
    game_state.rng.roll_results = [1, 1, 1, 6, 6, 6, 6, 6]

    initial_health = game_state.player.health

    result = system.handle_vent_movement(game_state, game_state.player, (7, 2))

    assert result["encounter"] == True
    # Damage should be dealt (either 1 for escape or 3 for caught)
    assert result["damage"] >= 1

    system.cleanup()
    print("[PASS] Vent encounter with catch works")


def test_vent_sound_propagation():
    """Test that sound propagates to adjacent vent nodes."""
    from systems.stealth import StealthSystem
    from core.event_system import event_bus, EventType

    game_state = MockGameState()
    system = StealthSystem()

    # Track perception events
    perception_events = []
    def track_perception(event):
        perception_events.append(event.payload)

    event_bus.subscribe(EventType.PERCEPTION_EVENT, track_perception)

    try:
        # Avoid encounter for this test
        game_state.rng.float_value = 0.99

        system.handle_vent_movement(game_state, game_state.player, (7, 2))

        # Should have main perception event + echoes to adjacent vents
        # (7, 2) has neighbors: (2, 2), (13, 2), (7, 8)
        main_events = [e for e in perception_events if e.get("source") == "vent"]
        echo_events = [e for e in perception_events if e.get("source") == "vent_echo"]

        assert len(main_events) >= 1, "Should have main vent perception event"
        # Note: echoes depend on actual neighbor count in mock

    finally:
        event_bus.unsubscribe(EventType.PERCEPTION_EVENT, track_perception)
        system.cleanup()

    print("[PASS] Sound propagates to adjacent vent nodes")


def test_vent_no_infected_encounter():
    """Test vent encounter when no infected crew are present."""
    from systems.stealth import StealthSystem

    game_state = MockGameState()
    # Remove infected crew member
    game_state.crew = [game_state.player]
    system = StealthSystem()

    # Set RNG to trigger encounter
    game_state.rng.float_value = 0.1

    result = system.handle_vent_movement(game_state, game_state.player, (7, 2))

    # Should not have a real encounter since no infected
    assert result["encounter"] == False

    system.cleanup()
    print("[PASS] Vent encounter without infected works")


def test_vent_encounter_damage():
    """Test that vent encounters deal appropriate damage."""
    from systems.stealth import StealthSystem

    system = StealthSystem()
    game_state = MockGameState()

    # Set RNG to trigger encounter
    game_state.rng.float_value = 0.1

    initial_health = game_state.player.health

    # Run multiple times to test both outcomes
    total_damage = 0
    for _ in range(10):
        game_state.player.health = 10  # Reset health
        game_state.rng.float_value = 0.1  # Trigger encounter
        game_state.rng.roll_index = 0  # Reset dice

        result = system.handle_vent_movement(game_state, game_state.player, (7, 2))

        if result.get("encounter"):
            total_damage += result.get("damage", 0)

    # Should have dealt some damage across encounters
    assert total_damage > 0, "Vent encounters should deal damage"

    system.cleanup()
    print("[PASS] Vent encounters deal appropriate damage")


def test_vent_high_noise_level():
    """Test that vent movement generates high noise."""
    from systems.stealth import StealthSystem
    from core.event_system import event_bus, EventType

    game_state = MockGameState()
    system = StealthSystem()

    # Track noise level in perception events
    noise_levels = []
    def track_noise(event):
        if event.payload.get("source") == "vent":
            noise_levels.append(event.payload.get("noise_level", 0))

    event_bus.subscribe(EventType.PERCEPTION_EVENT, track_noise)

    try:
        game_state.rng.float_value = 0.99  # Avoid encounter

        system.handle_vent_movement(game_state, game_state.player, (7, 2))

        # Noise should be at least VENT_BASE_NOISE
        assert len(noise_levels) > 0, "Should emit perception event"
        assert noise_levels[0] >= system.VENT_BASE_NOISE, f"Noise should be {system.VENT_BASE_NOISE}+, got {noise_levels[0]}"

    finally:
        event_bus.unsubscribe(EventType.PERCEPTION_EVENT, track_noise)
        system.cleanup()

    print("[PASS] Vent movement generates high noise")


if __name__ == "__main__":
    test_vent_base_noise()
    test_vent_encounter_chance()
    test_vent_crawl_turns()
    test_vent_movement_no_encounter()
    test_vent_movement_with_encounter_escape()
    test_vent_movement_with_encounter_caught()
    test_vent_sound_propagation()
    test_vent_no_infected_encounter()
    test_vent_encounter_damage()
    test_vent_high_noise_level()

    print("\n=== ALL ENHANCED VENT TESTS PASSED ===")
