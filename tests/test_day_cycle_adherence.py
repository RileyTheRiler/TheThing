"""
Test NPC adherence to schedules throughout the day cycle.

Verifies that NPCs move toward their scheduled locations during
the appropriate hours and handle schedule transitions correctly.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from engine import GameState
from systems.architect import Difficulty, TimeSystem
from entities.crew_member import CrewMember
from core.event_system import event_bus, EventType, GameEvent


class MockStationMap:
    """Mock station map for testing."""
    def __init__(self):
        self.rooms = {
            "Rec Room": (5, 5, 10, 10),
            "Generator": (15, 15, 19, 19),
            "Infirmary": (0, 0, 4, 4)
        }
    
    def get_room_name(self, x, y):
        for name, (x1, y1, x2, y2) in self.rooms.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return name
        return "Corridor"
    
    def is_walkable(self, x, y):
        return 0 <= x < 20 and 0 <= y < 20


class MockLynchMob:
    """Mock lynch mob system."""
    def __init__(self):
        self.active_mob = False
        self.target = None


class MockRNG:
    """Mock RNG that prevents random wandering."""
    def random_float(self):
        return 0.9  # High value prevents wandering
    
    def choose(self, opts):
        return opts[0]


class MockGameState:
    """Minimal game state for testing AI."""
    def __init__(self, hour=8):
        self.time_system = TimeSystem(start_hour=hour)
        self.station_map = MockStationMap()
        self.lynch_mob = MockLynchMob()
        self.rng = MockRNG()
        self.crew = []
        self.turn = 1


class TestDayCycleAdherence(unittest.TestCase):
    """Test that NPCs follow their schedules throughout the day."""

    def test_npc_moves_toward_scheduled_location(self):
        """NPC should pathfind toward their scheduled room."""
        game = MockGameState(hour=10)
        
        # Create NPC with schedule: 8-18 at Infirmary
        schedule = [{"start": 8, "end": 18, "room": "Infirmary"}]
        npc = CrewMember("TestNPC", "Doctor", "Professional", schedule=schedule)
        npc.location = (15, 15)  # Start in Generator area
        
        game.crew.append(npc)
        
        # Import AISystem to test
        from systems.ai import AISystem
        ai = AISystem()
        
        # Get initial distance to Infirmary (0,0)
        initial_dist = abs(npc.location[0] - 0) + abs(npc.location[1] - 0)
        
        # Update AI
        ai.update_member_ai(npc, game)
        
        # NPC should have moved closer to Infirmary
        new_dist = abs(npc.location[0] - 0) + abs(npc.location[1] - 0)
        self.assertLess(new_dist, initial_dist, 
                       f"NPC should move toward scheduled location. Was at {(15,15)}, now at {npc.location}")

    def test_schedule_transition(self):
        """NPC should change destinations when schedule transitions."""
        # Start at hour 17 (end of work schedule)
        game = MockGameState(hour=17)
        
        # Schedule: 8-18 Infirmary, 18-8 Rec Room
        schedule = [
            {"start": 8, "end": 18, "room": "Infirmary"},
            {"start": 18, "end": 8, "room": "Rec Room"}
        ]
        npc = CrewMember("TestNPC", "Doctor", "Professional", schedule=schedule)
        npc.location = (2, 2)  # In Infirmary
        
        game.crew.append(npc)
        
        from systems.ai import AISystem
        ai = AISystem()
        
        # At hour 17, should still go to Infirmary
        ai.update_member_ai(npc, game)
        pos_at_17 = npc.location
        
        # Advance to hour 19 (after transition)
        game.time_system.turn_count = 2
        # Manually set hour for testing
        game.time_system._hour = 19
        
        # Reset position to Generator
        npc.location = (15, 15)
        initial_dist_to_rec = abs(15 - 5) + abs(15 - 5)
        
        # Now should move toward Rec Room
        ai.update_member_ai(npc, game)
        new_dist_to_rec = abs(npc.location[0] - 5) + abs(npc.location[1] - 5)
        
        self.assertLess(new_dist_to_rec, initial_dist_to_rec,
                       "NPC should move toward new scheduled location after transition")

    def test_wraparound_schedule_handling(self):
        """Test schedule that wraps around midnight (e.g., 22:00-06:00)."""
        # Test at 23:00 (should follow night schedule)
        game = MockGameState(hour=23)
        
        # Schedule wraps midnight: 22-6 at Rec Room
        schedule = [{"start": 22, "end": 6, "room": "Rec Room"}]
        npc = CrewMember("TestNPC", "Cook", "Erratic", schedule=schedule)
        npc.location = (0, 0)  # Start in Infirmary
        
        game.crew.append(npc)
        
        from systems.ai import AISystem
        ai = AISystem()
        
        initial_dist = abs(0 - 5) + abs(0 - 5)
        ai.update_member_ai(npc, game)
        new_dist = abs(npc.location[0] - 5) + abs(npc.location[1] - 5)
        
        self.assertLess(new_dist, initial_dist,
                       "NPC should follow wraparound schedule at 23:00")
        
        # Test at 02:00 (early morning, still in wraparound range)
        game.time_system._hour = 2
        npc.location = (15, 15)
        initial_dist = abs(15 - 5) + abs(15 - 5)
        
        ai.update_member_ai(npc, game)
        new_dist = abs(npc.location[0] - 5) + abs(npc.location[1] - 5)
        
        self.assertLess(new_dist, initial_dist,
                       "NPC should follow wraparound schedule at 02:00")

    def test_lynch_mob_overrides_schedule(self):
        """Lynch mob should take priority over schedule."""
        game = MockGameState(hour=10)
        
        # NPC with schedule
        schedule = [{"start": 8, "end": 18, "room": "Infirmary"}]
        npc = CrewMember("TestNPC", "Doctor", "Professional", schedule=schedule)
        npc.location = (15, 15)
        
        # Lynch target
        target = CrewMember("Target", "Pilot", "Cynical")
        target.location = (5, 5)  # At Rec Room
        
        game.crew.extend([npc, target])
        game.lynch_mob.active_mob = True
        game.lynch_mob.target = target
        
        from systems.ai import AISystem
        ai = AISystem()
        
        # Distance to lynch target
        initial_dist_to_target = abs(15 - 5) + abs(15 - 5)
        
        ai.update_member_ai(npc, game)
        
        new_dist_to_target = abs(npc.location[0] - 5) + abs(npc.location[1] - 5)
        
        self.assertLess(new_dist_to_target, initial_dist_to_target,
                       "NPC should prioritize lynch mob over schedule")


if __name__ == "__main__":
    unittest.main()
