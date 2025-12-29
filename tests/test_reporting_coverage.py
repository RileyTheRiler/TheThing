import unittest
from engine import GameState
from core.event_system import event_bus, EventType, GameEvent
from systems.commands import GameContext, CommandDispatcher
from core.resolution import Skill

class TestReportingCoverage(unittest.TestCase):
    def setUp(self):
        self.game = GameState(seed=42)
        self.context = GameContext(game=self.game)
        self.dispatcher = CommandDispatcher()
        self.events_received = []
        
        # Subscribe to all reporting events
        for event_type in EventType:
            event_bus.subscribe(event_type, self._capture_event)

    def tearDown(self):
        event_bus.clear()

    def _capture_event(self, event):
        self.events_received.append(event)

    def test_attack_reporting(self):
        """Verify that the ATTACK command emits an ATTACK_RESULT event."""
        # Find a target in the same room
        player_room = self.game.station_map.get_room_name(*self.game.player.location)
        target = next(m for m in self.game.crew if m != self.game.player and self.game.station_map.get_room_name(*m.location) == player_room)
        
        self.dispatcher.dispatch(self.context, f"ATTACK {target.name}")
        
        attack_events = [e for e in self.events_received if e.type == EventType.ATTACK_RESULT]
        self.assertTrue(len(attack_events) > 0, "No ATTACK_RESULT event emitted")
        self.assertEqual(attack_events[0].payload['attacker'], self.game.player.name)
        self.assertEqual(attack_events[0].payload['target'], target.name)

    def test_interrogate_reporting(self):
        """Verify that the TALK command (or interrogation) emits DIALOGUE and/or INTERROGATION events."""
        # Note: TALK command in commands.py uses emit_dialogue
        self.dispatcher.dispatch(self.context, "TALK")
        
        dialogue_events = [e for e in self.events_received if e.type == EventType.DIALOGUE]
        self.assertTrue(len(dialogue_events) > 0, "No DIALOGUE event emitted")

    def test_barricade_reporting(self):
        """Verify that BARRICADE command emits a message (currently MESSAGE event)."""
        self.dispatcher.dispatch(self.context, "BARRICADE")
        
        # Barricade command currently uses emit_message
        msg_events = [e for e in self.events_received if e.type == EventType.MESSAGE]
        self.assertTrue(len(msg_events) > 0, "No MESSAGE event emitted for BARRICADE")

if __name__ == "__main__":
    unittest.main()
