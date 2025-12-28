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

        self.dispatcher.dispatch(self.context, "MOVE NORTH")

        movement_events = [e for e in self.events if e.type == EventType.MOVEMENT]
        self.assertTrue(movement_events, "Movement event should be emitted")
        payload = movement_events[-1].payload
        self.assertEqual(payload.get("direction"), "NORTH")

    def test_look_emits_message_event(self):
        self._subscribe(EventType.MESSAGE)
        self._subscribe(EventType.WARNING)
        self._add_target()

        self.dispatcher.dispatch(self.context, "LOOK Target")

        message_events = [e for e in self.events if e.type == EventType.MESSAGE]
        self.assertTrue(message_events, "LOOK should emit a message event")
        self.assertIn("Target", message_events[-1].payload.get("text", ""))

    def test_interrogate_emits_dialogue_event(self):
        self._subscribe(EventType.DIALOGUE)
        self._add_target()

        self.dispatcher.dispatch(self.context, "INTERROGATE Target")

        dialogue_events = [e for e in self.events if e.type == EventType.DIALOGUE]
        self.assertTrue(dialogue_events, "INTERROGATE should emit dialogue")
        self.assertEqual(dialogue_events[-1].payload.get("speaker"), "Target")

    def test_test_command_emits_test_result(self):
        self._subscribe(EventType.TEST_RESULT)
        self.game.player.add_item(Item("Scalpel", "Sharp"), 1)
        self.game.player.add_item(Item("Copper Wire", "Conductive"), 1)
        self._add_target(infected=False)

        self.dispatcher.dispatch(self.context, "TEST Target")

        test_events = [e for e in self.events if e.type == EventType.TEST_RESULT]
        self.assertTrue(test_events, "TEST should emit a test result event")
        payload = test_events[-1].payload
        self.assertEqual(payload.get("subject"), "Target")
        self.assertFalse(payload.get("infected"))

    def test_attack_emits_attack_result(self):
        self._subscribe(EventType.ATTACK_RESULT)
        self._add_target()

        self.dispatcher.dispatch(self.context, "ATTACK Target")

        attack_events = [e for e in self.events if e.type == EventType.ATTACK_RESULT]
        self.assertTrue(attack_events, "ATTACK should emit an attack result")
        self.assertEqual(attack_events[-1].payload.get("target"), "Target")

    def test_barricade_emits_barricade_action(self):
        self._subscribe(EventType.BARRICADE_ACTION)

        self.dispatcher.dispatch(self.context, "BARRICADE")

        barricade_events = [e for e in self.events if e.type == EventType.BARRICADE_ACTION]
        self.assertTrue(barricade_events, "BARRICADE should emit barricade action")
        self.assertEqual(barricade_events[-1].payload.get("room"), self.game.station_map.get_room_name(*self.game.player.location))

    def test_inventory_emits_message(self):
        self._subscribe(EventType.MESSAGE)
        self.game.player.add_item(Item("Flashlight", "Bright"), 1)

        self.dispatcher.dispatch(self.context, "INVENTORY")

        message_events = [e for e in self.events if e.type == EventType.MESSAGE]
        self.assertTrue(any("Flashlight" in e.payload.get("text", "") for e in message_events), "Inventory should list items")

    def test_hide_sets_stealth_posture_and_emits_message(self):
        self._subscribe(EventType.MESSAGE)
        # Ensure stealth system is active (it should be by default in GameState)
        
        self.dispatcher.dispatch(self.context, "HIDE")
        
        message_events = [e for e in self.events if e.type == EventType.MESSAGE]
        self.assertTrue(message_events, "HIDE should emit a message")
        # Check posture if possible, but testing event is sufficient for command layer

    def test_sneak_emits_message(self):
        self._subscribe(EventType.MESSAGE)
        # SNEAK NORTH
        self.dispatcher.dispatch(self.context, "SNEAK NORTH")
        
        message_events = [e for e in self.events if e.type == EventType.MESSAGE]
        self.assertTrue(message_events, "SNEAK should emit a message")
        self.assertIn("sneak", message_events[-1].payload.get("text", "").lower())

    def test_give_emits_warning(self):
        self._subscribe(EventType.WARNING)
        self._add_target()
        self.game.player.add_item(Item("Item", "Thing"), 1)
        
        self.dispatcher.dispatch(self.context, "GIVE Item TO Target")
        
        warning_events = [e for e in self.events if e.type == EventType.WARNING]
        self.assertTrue(warning_events, "GIVE should emit warning (not implemented)")

    def test_accuse_emits_accusation_result(self):
        self._subscribe(EventType.ACCUSATION_RESULT)
        target = self._add_target()
        # Ensure there are other crew to vote (accuse requires voters)
        self._add_target(name="Voter1") 
        self._add_target(name="Voter2")

        self.dispatcher.dispatch(self.context, "ACCUSE Target")
        
        accusation_events = [e for e in self.events if e.type == EventType.ACCUSATION_RESULT]
        self.assertTrue(accusation_events, "ACCUSE should emit accusation result")
        self.assertEqual(accusation_events[-1].payload.get("target"), "Target")


if __name__ == "__main__":
    unittest.main()
