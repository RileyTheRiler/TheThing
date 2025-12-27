import unittest
from typing import List

from engine import GameState
from entities.crew_member import CrewMember
from entities.item import Item
from systems.architect import Difficulty
from systems.commands import CommandDispatcher, GameContext
from core.event_system import event_bus, EventType, GameEvent


class CommandEventTests(unittest.TestCase):
    def setUp(self):
        self.game = GameState(difficulty=Difficulty.NORMAL)
        self.game.player.location = (5, 5)
        self.dispatcher = CommandDispatcher()
        self.context = GameContext(game=self.game)
        self.events: List[GameEvent] = []
        self._subscriptions = []

    def tearDown(self):
        for event_type, callback in self._subscriptions:
            event_bus.unsubscribe(event_type, callback)
        self.events.clear()

    def _capture(self, event: GameEvent):
        self.events.append(event)

    def _subscribe(self, event_type: EventType):
        event_bus.subscribe(event_type, self._capture)
        self._subscriptions.append((event_type, self._capture))

    def _add_target(self, name="Target", infected=False):
        target = CrewMember(name, "Scientist", "Calm")
        target.location = tuple(self.game.player.location)
        target.is_infected = infected
        self.game.crew.append(target)
        return target

    def test_move_emits_movement_event(self):
        self._subscribe(EventType.MOVEMENT)

        moved = self.dispatcher.dispatch("MOVE", ["NORTH"], self.context)

        self.assertTrue(moved, "MOVE should dispatch")
        movement_events = [e for e in self.events if e.type == EventType.MOVEMENT]
        self.assertTrue(movement_events, "Movement event should be emitted")
        payload = movement_events[-1].payload
        self.assertEqual(payload.get("direction"), "NORTH")

    def test_look_emits_message_event(self):
        self._subscribe(EventType.MESSAGE)
        self._add_target()

        self.dispatcher.dispatch("LOOK", ["Target"], self.context)

        message_events = [e for e in self.events if e.type == EventType.MESSAGE]
        self.assertTrue(message_events, "LOOK should emit a message event")
        self.assertIn("Target", message_events[-1].payload.get("text", ""))

    def test_interrogate_emits_dialogue_event(self):
        self._subscribe(EventType.DIALOGUE)
        self._add_target()

        self.dispatcher.dispatch("INTERROGATE", ["Target"], self.context)

        dialogue_events = [e for e in self.events if e.type == EventType.DIALOGUE]
        self.assertTrue(dialogue_events, "INTERROGATE should emit dialogue")
        self.assertEqual(dialogue_events[-1].payload.get("speaker"), "Target")

    def test_test_command_emits_test_result(self):
        self._subscribe(EventType.TEST_RESULT)
        self.game.player.add_item(Item("Scalpel", "Sharp"), 1)
        self.game.player.add_item(Item("Copper Wire", "Conductive"), 1)
        self._add_target(infected=False)

        self.dispatcher.dispatch("TEST", ["Target"], self.context)

        test_events = [e for e in self.events if e.type == EventType.TEST_RESULT]
        self.assertTrue(test_events, "TEST should emit a test result event")
        payload = test_events[-1].payload
        self.assertEqual(payload.get("subject"), "Target")
        self.assertFalse(payload.get("infected"))

    def test_attack_emits_attack_result(self):
        self._subscribe(EventType.ATTACK_RESULT)
        self._add_target()

        self.dispatcher.dispatch("ATTACK", ["Target"], self.context)

        attack_events = [e for e in self.events if e.type == EventType.ATTACK_RESULT]
        self.assertTrue(attack_events, "ATTACK should emit an attack result")
        self.assertEqual(attack_events[-1].payload.get("target"), "Target")

    def test_barricade_emits_barricade_action(self):
        self._subscribe(EventType.BARRICADE_ACTION)

        self.dispatcher.dispatch("BARRICADE", [], self.context)

        barricade_events = [e for e in self.events if e.type == EventType.BARRICADE_ACTION]
        self.assertTrue(barricade_events, "BARRICADE should emit barricade action")
        self.assertEqual(barricade_events[-1].payload.get("room"), self.game.station_map.get_room_name(*self.game.player.location))


if __name__ == "__main__":
    unittest.main()
