
import sys
import os
import unittest

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from engine import GameState
from entities.crew_member import CrewMember
from systems.missionary import MissionarySystem

class TestMissionaryCommunion(unittest.TestCase):
    def setUp(self):
        self.game = GameState()
        # Clear crew for clean testing
        self.game.crew = []

        # Agent
        self.agent = CrewMember("Agent", "Pilot", "Normal")
        self.agent.is_infected = True
        self.agent.mask_integrity = 100
        self.game.crew.append(self.agent)

        # Target
        self.target = CrewMember("Target", "Mechanic", "Normal")
        self.target.is_infected = False
        self.game.crew.append(self.target)

        # System
        self.missionary = MissionarySystem()

        # Mock perform_communion to track calls instead of side effects
        self.communion_calls = 0
        self.original_perform = self.missionary.perform_communion

        def mock_perform(agent, target, game_state):
            self.communion_calls += 1

        self.missionary.perform_communion = mock_perform

    def test_room_no_witness(self):
        # Both in Rec Room (5, 5)
        self.agent.location = (5, 5)
        self.target.location = (6, 6) # Same room

        self.missionary.attempt_communion_ai(self.agent, self.game)
        self.assertEqual(self.communion_calls, 1, "Should commune when alone in room")

    def test_room_with_witness(self):
        # Both in Rec Room
        self.agent.location = (5, 5)
        self.target.location = (6, 6)

        # Witness
        witness = CrewMember("Witness", "Biologist", "Normal")
        witness.location = (7, 7) # Same room
        self.game.crew.append(witness)

        self.missionary.attempt_communion_ai(self.agent, self.game)
        self.assertEqual(self.communion_calls, 0, "Should NOT commune with witness in room")

    def test_room_with_infected_witness(self):
        # Both in Rec Room
        self.agent.location = (5, 5)
        self.target.location = (6, 6)

        # Witness (Infected)
        witness = CrewMember("WitnessThing", "Biologist", "Normal")
        witness.location = (7, 7)
        witness.is_infected = True
        self.game.crew.append(witness)

        self.missionary.attempt_communion_ai(self.agent, self.game)
        self.assertEqual(self.communion_calls, 1, "Should commune if witness is infected")

    def test_corridor_no_witness(self):
        # Corridor locations (e.g. 10, 15 is Corridor)
        # Check map logic: get_room_name(10, 15) -> "Corridor (Sector 10,15)"

        self.agent.location = (10, 15)
        self.target.location = (10, 16) # Adjacent

        self.missionary.attempt_communion_ai(self.agent, self.game)
        self.assertEqual(self.communion_calls, 1, "Should commune in corridor if adjacent and alone")

    def test_corridor_too_far(self):
        self.agent.location = (10, 15)
        self.target.location = (10, 17) # Dist 2 (Communion range is 1)

        self.missionary.attempt_communion_ai(self.agent, self.game)
        self.assertEqual(self.communion_calls, 0, "Should NOT commune if target too far in corridor")

    def test_corridor_with_witness_near(self):
        self.agent.location = (10, 15)
        self.target.location = (10, 16)

        witness = CrewMember("Witness", "Biologist", "Normal")
        witness.location = (10, 14) # Dist 1 from agent, 2 from target. Within visual range (4)
        self.game.crew.append(witness)

        self.missionary.attempt_communion_ai(self.agent, self.game)
        self.assertEqual(self.communion_calls, 0, "Should NOT commune with witness nearby in corridor")

    def test_corridor_with_witness_far(self):
        self.agent.location = (10, 15)
        self.target.location = (10, 16)

        witness = CrewMember("Witness", "Biologist", "Normal")
        witness.location = (10, 10) # Dist 5. Out of visual range (4)
        self.game.crew.append(witness)

        self.missionary.attempt_communion_ai(self.agent, self.game)
        self.assertEqual(self.communion_calls, 1, "Should commune if witness is far away in corridor")

if __name__ == '__main__':
    unittest.main()
