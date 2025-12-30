import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import time

sys.path.append(os.path.join(os.getcwd(), 'src'))

from systems.crafting import CraftingSystem
from audio.audio_manager import AudioManager, Sound
from core.event_system import event_bus, EventType, GameEvent
from entities.item import Item

class TestTier7And9(unittest.TestCase):
    def setUp(self):
        # Mock dependencies for Audio
        self.mock_rng = MagicMock()
        self.mock_player = MagicMock()
        self.mock_map = MagicMock()
        self.mock_player.location = (0, 0, 0)
        self.mock_map.get_room_name.return_value = "Radio Room"
        
        # Initialize Audio Manager with disabled backend to prevent actual sound
        # We will mock the internal play methods
        with patch('audio.audio_manager.AUDIO_AVAILABLE', True):
            self.audio = AudioManager(enabled=True, rng=self.mock_rng, player_ref=self.mock_player, station_map=self.mock_map)
        
        # Mock the queue put method to verify calls
        self.audio.queue = MagicMock()

    def tearDown(self):
        self.audio.cleanup()

    def test_audio_event_trigger(self):
        """Test that events trigger audio queuing."""
        # 1. Trigger a simple event (e.g., ITEM_PICKUP -> CLICK)
        event = GameEvent(EventType.ITEM_PICKUP, {"actor": "MacReady", "item": "TestItem", "room": "Radio Room"})
        self.audio.handle_game_event(event)
        
        # Verify queue.put was called with Sound.CLICK
        # queue.put called with (Sound.CLICK, priority)
        args, _ = self.audio.queue.put.call_args
        sound, priority = args[0]
        self.assertEqual(sound, Sound.CLICK)

    def test_ambient_loop_priming(self):
        """Test that ambient sound is set based on room."""
        # Setup: Map returns "Generator" for current room
        self.mock_map.get_room_name.return_value = "Generator Room"
        
        # Trigger room update manually or via event
        self.audio._prime_room_ambient()
        
        # Check if ambient_sound is set to THRUM
        self.assertEqual(self.audio.ambient_sound, Sound.THRUM)
        self.assertTrue(self.audio.ambient_running)

    def test_advanced_crafting_recipes(self):
        """Test that new Tier 9 recipes are loaded."""
        crafting = CraftingSystem() # Should load real json
        
        # Check for Stun Baton
        self.assertIn("stun_baton", crafting.recipes)
        baton_recipe = crafting.recipes["stun_baton"]
        self.assertEqual(baton_recipe["name"], "Stun Baton")
        self.assertEqual(baton_recipe["effect"], "stun")

        # Check for Riot Shield
        self.assertIn("riot_shield", crafting.recipes)
        shield_recipe = crafting.recipes["riot_shield"]
        self.assertEqual(shield_recipe["category"], "armor")

    def test_crafting_validation(self):
        """Test validation logic for a new item."""
        crafting = CraftingSystem()
        
        # Mock crafter with ingredients for Stun Baton
        # Ingredients: Mop Handle, Copper Wire, Metal Scrap
        crafter = MagicMock()
        crafter.name = "MacReady"
        crafter.inventory = [
            Item("Mop Handle", "wood"),
            Item("Copper Wire", "wire"),
            Item("Metal Scrap", "scrap")
        ]
        
        # Validate should pass
        self.assertTrue(crafting.validate_ingredients(crafter, "stun_baton"))
        
        # Remove one item
        crafter.inventory.pop()
        self.assertFalse(crafting.validate_ingredients(crafter, "stun_baton"))

if __name__ == '__main__':
    unittest.main()
