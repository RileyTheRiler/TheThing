"""Verification script for Random Events System (Tier 6.2)."""

import unittest
import sys
import os
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from systems.random_events import RandomEventSystem, EventCategory, EventSeverity, RandomEvent
from core.resolution import Attribute, Skill
from core.event_system import event_bus, EventType, GameEvent
from systems.architect import RandomnessEngine
from core.design_briefs import DesignBriefRegistry

class TestRandomEvents(unittest.TestCase):
    def setUp(self):
        event_bus.clear()
        self.rng = RandomnessEngine(seed=42)
        
        # Mock design registry
        self.registry = Mock(spec=DesignBriefRegistry)
        self.registry.get_brief.return_value = {
            "base_chance": 1.0,  # Force events for testing
            "paranoia_multiplier": 0.0,
            "events": [
                {
                    "id": "test_blackout",
                    "name": "Test Blackout",
                    "description": "Lights out!",
                    "category": "EQUIPMENT",
                    "severity": "CRITICAL",
                    "weight": 100,
                    "effects": [{"type": "power_off"}]
                },
                {
                    "id": "test_paranoia",
                    "name": "Test Paranoia",
                    "description": "Scary noises!",
                    "category": "ATMOSPHERE", 
                    "severity": "MINOR",
                    "weight": 100,
                    "effects": [{"type": "paranoia", "amount": 10}]
                }
            ]
        }
        
        self.system = RandomEventSystem(self.rng, config_registry=self.registry)
        
        # Mock game state
        self.game_state = Mock()
        self.game_state.turn = 5
        self.game_state.paranoia_level = 0
        self.game_state.power_on = True
        self.game_state.crew = []
        
        # Capture events
        self.emitted_events = []
        def capture(event):
            self.emitted_events.append(event)
        event_bus.subscribe(EventType.MESSAGE, capture)

    def tearDown(self):
        self.system.cleanup()
        event_bus.clear()

    def test_event_loading(self):
        """Verify events are loaded from config."""
        self.assertEqual(len(self.system.events), 2)
        self.assertEqual(self.system.events[0].id, "test_blackout")
        self.assertEqual(self.system.events[0].category, EventCategory.EQUIPMENT)

    def test_trigger_event(self):
        """Verify an event triggers and executes effects."""
        # Force specific roll for selection if needed, but weight is high
        
        event = self.system.check_for_event(self.game_state)
        self.assertIsNotNone(event)
        
        self.system.execute_event(event, self.game_state)
        
        # Check effects
        if event.id == "test_blackout":
            self.assertFalse(self.game_state.power_on)
            # Check message
            messages = [e.payload['text'] for e in self.emitted_events]
            self.assertTrue(any("Lights out!" in m for m in messages))

    def test_paranoia_effect(self):
        """Verify paranoia effect applies."""
        # Setup specific event
        event = next(e for e in self.system.events if e.id == "test_paranoia")
        
        self.system.execute_event(event, self.game_state)
        
        # Check paranoia increase (mock object handling)
        # Note: In real game_state, this is a property, but mock handles attributes fine
        # self.game_state.paranoia_level = min(100, self.game_state.paranoia_level + 10)
        # Verify the code actually executed that logic
        # Since we mocked game_state, we need to check if the attribute was updated.
        # But wait, our execute_effects function does: game_state.paranoia_level = ...
        # For a Mock, this sets the attribute.
        
        # Need to ensure the initial value was treated as int
        # self.game_state.paranoia_level = 0 (set in setUp)
        
        self.assertEqual(self.game_state.paranoia_level, 10)

    def test_sabotage_effect(self):
        """Verify sabotage effect applies."""
        # Mock sabotage manager on game state
        self.game_state.sabotage = Mock()
        self.game_state.sabotage.radio_working = True
        
        # Manually trigger effect logic for test coverage since we mock the registry
        effects = [{"type": "destroy_equipment", "target": "radio"}]
        self.system._execute_effects(self.game_state, effects)
        
        self.assertFalse(self.game_state.sabotage.radio_working)

    def test_npc_action_template(self):
        """Verify NPC event templates work."""
        # Setup mock crew
        npc = Mock()
        npc.name = "Norris"
        npc.is_alive = True
        npc.is_infected = False # Doesn't matter for this test
        
        player = Mock()
        player.name = "MacReady"
        player.is_alive = True
        
        self.game_state.crew = [player, npc]
        self.game_state.player = player
        
        event = RandomEvent(
            id="test_npc",
            name="Test NPC",
            description="{{npc_name}} says hello.",
            category=EventCategory.NPC,
            severity=EventSeverity.MINOR
        )
        
        self.system.execute_event(event, self.game_state)
        
        # Check that {{npc_name}} was replaced
        messages = [e.payload['text'] for e in self.emitted_events if e.payload.get('crawl')]
        self.assertTrue(any("Norris says hello" in m for m in messages))

if __name__ == '__main__':
    unittest.main()
