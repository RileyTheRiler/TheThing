import unittest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from systems.architect import TimeSystem
from entities.crew_member import CrewMember
from core.event_system import event_bus, EventType, GameEvent

class MockStationMap:
    def __init__(self):
        self.rooms = {"Rec Room": (0,0,5,5), "Generator": (10,10,15,15)}
    
    def get_room_name(self, x, y):
        # Simple mock
        if 0 <= x <= 5: return "Rec Room"
        if 10 <= x <= 15: return "Generator"
        return "Corridor"
        
    def is_walkable(self, x, y):
        return True

class MockLynchMob:
    def __init__(self):
        self.active_mob = False
        self.target = None

class MockRNG:
    def random_float(self): return 0.9 # High so no wander
    def choose(self, opts): return opts[0]

class MockRoomStates:
    def is_entry_blocked(self, room): return False
    def get_status_icons(self, room): return ""
    def get_room_description_modifiers(self, room): return ""

class MockGameState:
    def __init__(self):
        self.time_system = TimeSystem(start_hour=19)
        self.station_map = MockStationMap()
        self.lynch_mob = MockLynchMob()
        self.room_states = MockRoomStates()
        self.rng = MockRNG()
        self.crew = []
        self.turn = 1 # GameState turn

class TestSocialSchedule(unittest.TestCase):
    def test_schedule_following(self):
        game = MockGameState()
        
        # Schedule: 19:00 - 20:00 Rec Room
        schedule = [{"start": 19, "end": 20, "room": "Rec Room"}]
        npc = CrewMember("TestNPC", "Role", "Behavior", schedule=schedule)
        npc.location = (12, 12) # In Generator area (roughly)
        
        game.crew.append(npc)
        
        # Initial Time: 19:00
        self.assertEqual(game.time_system.hour, 19)
        
        # Update AI
        # Logic: update_ai calls _pathfind_step if scheduled
        # We need to verify that it TRIES to move to Rec Room
        
        # Mocking move is hard without full pathfinder or trusting `_pathfind_step`
        # But we can check if it moved closer to Rec Room (0,0)
        initial_dist = npc.location[0] + npc.location[1]
        
        npc.update_ai(game)
        
        new_dist = npc.location[0] + npc.location[1]
        self.assertTrue(new_dist < initial_dist, "NPC should move towards Rec Room")
        
        # Advance Time to 20:00 (1 turn)
        event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": game}))
        self.assertEqual(game.time_system.hour, 20)
        
        # Schedule ENDED at 20.
        # It should wander or do nothing (RNG returns 0.9 -> no wander)
        
        pos_after_schedule = npc.location
        npc.update_ai(game)
        
        self.assertEqual(npc.location, pos_after_schedule, "NPC should not move (idling)")

if __name__ == "__main__":
    unittest.main()
