import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import unittest

from unittest.mock import MagicMock, patch
from core.event_system import event_bus, EventType, GameEvent
from systems.ai import AISystem
from systems.social import on_perception_event
from entities.crew_member import StealthPosture

class TestAIPerception(unittest.TestCase):
    def setUp(self):
        self.ai = AISystem()
        self.mock_game_state = MagicMock()
        self.mock_observer = MagicMock()
        self.mock_observer.name = "Observer"
        self.mock_observer.is_revealed = False
        self.mock_observer.is_alive = True
        self.mock_observer.investigating = False
        self.mock_observer.last_known_player_location = None
        self.mock_observer.suspicion_level = 0
        
        self.mock_player = MagicMock()
        self.mock_player.name = "Player"
        self.mock_player.location = (5, 5)
        self.mock_player.is_infected = False
        self.mock_player.is_alive = True
        self.mock_player.stealth_posture = StealthPosture.STANDING

        self.mock_game_state.crew = [self.mock_observer, self.mock_player]
        self.mock_game_state.player = self.mock_player
        self.mock_game_state.station_map = MagicMock()
        self.mock_game_state.station_map.get_room_name.return_value = "Corridor"
        
        # Mock trust system
        self.mock_game_state.trust_system = MagicMock()

    def tearDown(self):
        self.ai.cleanup()
        # Unsubscribe social listener manually since it's a module level function we can't easily reach 
        # (Though in real app it stays, for test we rely on event_bus logic or just ignore)
        pass

    def test_investigation_trigger(self):
        """Test that margin < 2 triggers investigation."""
        payload = {
            "game_state": self.mock_game_state,
            "opponent_ref": self.mock_observer,
            "player_ref": self.mock_player,
            "outcome": "evaded",
            "player_successes": 5,
            "opponent_successes": 4, # Margin = 1
            "room": "Corridor"
        }
        
        # Directly call handler to avoid async issues or ensure direct path
        self.ai.on_perception_event(GameEvent(EventType.PERCEPTION_EVENT, payload))
        
        self.assertTrue(self.mock_observer.investigating, "Observer should be investigating")
        self.assertEqual(self.mock_observer.last_known_player_location, (5, 5))
        self.assertEqual(self.mock_observer.suspicion_level, 5)

    def test_social_consequence(self):
        """Test that getting caught sneaking lowers trust."""
        self.mock_player.stealth_posture = StealthPosture.CROUCHING
        
        payload = {
            "game_state": self.mock_game_state,
            "opponent_ref": self.mock_observer,
            "player_ref": self.mock_player,
            "outcome": "detected",
            "room": "Corridor"
        }
        
        # Call the social handler directly
        on_perception_event(GameEvent(EventType.PERCEPTION_EVENT, payload))
        
        self.mock_game_state.trust_system.update_trust.assert_called_with("Observer", "Player", -5)

    def test_thing_ambush_logic(self):
        """Test that Thing AI chooses to wait/ambush in suitable conditions."""
        self.mock_observer.is_revealed = True
        self.mock_observer.is_infected = True
        self.mock_observer.location = (10, 10)
        self.mock_player.location = (14, 10) # Distance 4
        self.mock_player.is_infected = False
        self.mock_player.is_alive = True
        
        # Setup room states to be DARK
        self.mock_game_state.room_states = MagicMock()
        self.mock_game_state.room_states.has_state.return_value = True # Dark
        
        # Mock RNG to choose "Wait" (random_float < 0.7)
        self.mock_game_state.rng.random_float.return_value = 0.5 
        
        # To test, we call _update_thing_ai
        # We need to mock move/pathfind_step to ensure they ARE NOT called if it waits
        self.ai._pathfind_step = MagicMock()
        self.mock_observer.move = MagicMock()
        
        self.ai._update_thing_ai(self.mock_observer, self.mock_game_state)
        
        self.ai._pathfind_step.assert_not_called()
        self.mock_observer.move.assert_not_called()

    def test_vent_ambush_logic(self):
        """Test that Thing AI chooses to wait/ambush if at a vent."""
        self.mock_observer.is_revealed = True
        self.mock_observer.is_infected = True
        self.mock_observer.location = (2, 2) # A known vent location
        self.mock_player.location = (6, 2) # Distance 4
        self.mock_player.is_infected = False
        self.mock_player.is_alive = True
        
        # Room NOT dark
        self.mock_game_state.room_states = MagicMock()
        self.mock_game_state.room_states.has_state.return_value = False 
        
        # Verify station map handles is_at_vent
        # We'll use the real station map or mock it
        self.mock_game_state.station_map.is_at_vent.return_value = True
        
        # Mock RNG to choose "Wait"
        self.mock_game_state.rng.random_float.return_value = 0.5 
        
        self.ai._pathfind_step = MagicMock()
        
        self.ai._update_thing_ai(self.mock_observer, self.mock_game_state)
        
        self.ai._pathfind_step.assert_not_called()

if __name__ == '__main__':
    unittest.main()
