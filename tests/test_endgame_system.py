import unittest
from unittest.mock import MagicMock
from core.event_system import event_bus, EventType, GameEvent
from systems.endgame import EndgameSystem
from systems.architect import GameMode
from entities.crew_member import CrewMember

class TestEndgameSystem(unittest.TestCase):
    def setUp(self):
        # Clear event bus for clean tests
        event_bus.clear()
        
        # Mock DesignRegistry and Config
        self.mock_registry = MagicMock()
        self.mock_config = {
            "states": {
                "ESCAPE": {"name": "Escape", "message": "Escaped!"},
                "RESCUE": {"name": "Rescue", "message": "Rescued!"},
                "EXTERMINATION": {"name": "Extermination", "message": "Exterminated!"},
                "SOLE_SURVIVOR": {"name": "Sole Survivor", "message": "Alone..."},
                "CONSUMPTION": {"name": "Consumption", "message": "Consumed!"},
                "DEATH": {"name": "Death", "message": "Dead!"}
            }
        }
        self.mock_registry.get_brief.return_value = self.mock_config
        
        # Initialize System
        self.system = EndgameSystem(self.mock_registry)
        
        # Mock GameState
        self.game = MagicMock()
        self.player = CrewMember("MacReady", "Pilot", "Cynical")
        self.player.is_infected = False
        self.player.is_revealed = False
        self.game.player = self.player
        self.game.crew = [self.player]
        self.game.turn = 10
        self.game.rescue_signal_active = False
        self.game.rescue_turns_remaining = None

        # Track emitted reports
        self.reports = []
        event_bus.subscribe(EventType.ENDING_REPORT, self.on_ending_report)

    def on_ending_report(self, event):
        self.reports.append(event)

    def tearDown(self):
        self.system.cleanup()
        event_bus.clear()

    def test_escape_ending(self):
        """Test the helicopter escape ending."""
        event_bus.emit(GameEvent(EventType.ESCAPE_SUCCESS, {"game_state": self.game}))
        
        self.assertEqual(len(self.reports), 1)
        report = self.reports[0].payload
        self.assertEqual(report["result"], "win")
        self.assertEqual(report["ending_type"], "ESCAPE")
        self.assertTrue(self.system.resolved)

    def test_rescue_ending(self):
        """Test the rescue arrival ending."""
        self.game.rescue_signal_active = True
        self.game.rescue_turns_remaining = 0
        
        event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": self.game}))
        
        self.assertEqual(len(self.reports), 1)
        report = self.reports[0].payload
        self.assertEqual(report["ending_type"], "RESCUE")

    def test_player_death_ending(self):
        """Test ending triggered by player death."""
        event_bus.emit(GameEvent(EventType.CREW_DEATH, {
            "name": "MacReady",
            "game_state": self.game
        }))
        
        self.assertEqual(len(self.reports), 1)
        report = self.reports[0].payload
        self.assertEqual(report["result"], "loss")
        self.assertEqual(report["ending_type"], "DEATH")

    def test_sole_survivor_ending(self):
        """Test ending when only MacReady survives."""
        # Setup: MacReady is alone
        self.game.crew = [self.player]
        self.player.is_alive = True
        
        event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": self.game}))
        
        self.assertEqual(len(self.reports), 1)
        report = self.reports[0].payload
        self.assertEqual(report["ending_type"], "SOLE_SURVIVOR")

    def test_extermination_ending(self):
        """Test ending when all Things are killed but crew remains."""
        other_human = CrewMember("Childs", "Mechanic", "Practical")
        other_human.is_infected = False
        self.game.crew = [self.player, other_human]
        
        event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": self.game}))
        
        self.assertEqual(len(self.reports), 1)
        report = self.reports[0].payload
        self.assertEqual(report["ending_type"], "EXTERMINATION")

    def test_consumption_ending_revealed(self):
        """Test ending when player is infected and revealed."""
        self.player.is_infected = True
        self.player.is_revealed = True
        
        event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {"game_state": self.game}))
        
        self.assertEqual(len(self.reports), 1)
        report = self.reports[0].payload
        self.assertEqual(report["result"], "loss")
        self.assertEqual(report["ending_type"], "CONSUMPTION")

if __name__ == '__main__':
    unittest.main()
