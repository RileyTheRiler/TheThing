import unittest
import sys
import os
from unittest.mock import Mock, MagicMock

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.event_system import event_bus, EventType, GameEvent
from systems.endgame import EndgameSystem
from systems.commands import CommandDispatcher, GameContext, RepairCommand, FlyCommand, SOSCommand
from engine import GameState
from systems.architect import Difficulty

class TestEndgameIntegration(unittest.TestCase):
    def setUp(self):
        event_bus.clear()
        # Initialize GameState
        self.game_state = GameState(difficulty=Difficulty.EASY)
        self.context = GameContext(self.game_state)
        self.dispatcher = CommandDispatcher()
        
        # Capture ending report
        self.ending_report = None
        def on_ending(event):
            self.ending_report = event.payload
        event_bus.subscribe(EventType.ENDING_REPORT, on_ending)

    def tearDown(self):
        self.game_state.cleanup()
        event_bus.clear()

    def test_helicopter_escape_flow(self):
        """Test the full flow from repairing to flying away."""
        # 1. Setup: Move to Hangar
        self.game_state.player.location = (7, 17) # In Hangar
        
        # 2. Give items to player
        from entities.item import Item
        self.game_state.player.inventory.append(Item("Tools", "Heavy duty tools"))
        self.game_state.player.inventory.append(Item("Replacement Parts", "Engine components"))
        
        # 3. Repair Helicopter
        self.dispatcher.dispatch(self.context, "REPAIR HELICOPTER")
        self.assertEqual(self.game_state.helicopter_status, "FIXED")
        
        # 4. Fly away
        self.dispatcher.dispatch(self.context, "FLY")
        
        # 5. Verify ending
        self.assertIsNotNone(self.ending_report)
        self.assertEqual(self.ending_report['result'], "win")
        self.assertEqual(self.ending_report['ending_type'], "ESCAPE")

    def test_radio_sos_flow(self):
        """Test SOS signal and rescue arrival."""
        # 1. Setup: Move to Radio Room
        self.game_state.player.location = (12, 2) # In Radio Room
        
        # 2. Repair Radio if needed (assume damaged initially for test)
        self.game_state.sabotage.radio_operational = False
        from entities.item import Item
        self.game_state.player.inventory.append(Item("Tools", "Tools"))
        
        self.dispatcher.dispatch(self.context, "REPAIR RADIO")
        self.assertTrue(self.game_state.sabotage.radio_operational)
        
        # 3. Send SOS
        self.dispatcher.dispatch(self.context, "SOS")
        self.assertTrue(self.game_state.rescue_signal_active)
        self.assertEqual(self.game_state.rescue_turns_remaining, 19)
        
        # 4. Advance turns to trigger rescue
        for _ in range(20):
            self.game_state.advance_turn()
            
        # 5. Verify ending
        self.assertIsNotNone(self.ending_report)
        self.assertEqual(self.ending_report['result'], "win")
        self.assertEqual(self.ending_report['ending_type'], "RESCUE")

    def test_consumption_loss(self):
        """Test loss when player is revealed as infected."""
        self.game_state.player.is_infected = True
        self.game_state.player.is_revealed = True
        
        self.game_state.advance_turn()
        
        self.assertIsNotNone(self.ending_report)
        self.assertEqual(self.ending_report['result'], "loss")
        self.assertEqual(self.ending_report['ending_type'], "CONSUMPTION")

if __name__ == '__main__':
    unittest.main()
