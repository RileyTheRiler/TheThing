
import sys
import os
import unittest
import time
from unittest.mock import MagicMock, patch

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Mock winsound before importing audio_manager
mock_winsound = MagicMock()
sys.modules['winsound'] = mock_winsound

# Import audio and event system
from audio.audio_manager import AudioManager, Sound
from core.event_system import event_bus, EventType, GameEvent

class TestAudioEvents(unittest.TestCase):
    def setUp(self):
        # Reset event bus before each test
        event_bus.clear()
        mock_winsound.reset_mock()
        
        # Create audio manager
        self.audio = AudioManager(enabled=True)
        # Ensure it's treated as enabled for testing even if no audio backend
        self.audio.enabled = True
        
        # We need to wait a tiny bit for the worker thread to start?
        # Or better, we test the queueing mechanism.
        # But handle_game_event calls self.play, which puts in queue.
        # For unit testing the logic, we can mock self.play or test _play_sound.

    def tearDown(self):
        self.audio.shutdown()

    def test_event_to_sound_mapping(self):
        """Assert that specific events trigger the correct sound queueing."""
        # We'll mock the 'play' method to assert cues are selected correctly
        with patch.object(self.audio, 'play') as mock_play:
            # Test Power Failure -> Sound.POWER_DOWN
            event_bus.emit(GameEvent(EventType.POWER_FAILURE))
            mock_play.assert_called_with(Sound.POWER_DOWN, 10)
            
            mock_play.reset_mock()
            
            # Test Lynch Mob -> Sound.SCREECH
            event_bus.emit(GameEvent(EventType.LYNCH_MOB_TRIGGER))
            mock_play.assert_called_with(Sound.SCREECH, 10)
            
            mock_play.reset_mock()
            
            # Test Warning -> Sound.ALERT
            event_bus.emit(GameEvent(EventType.WARNING))
            mock_play.assert_called_with(Sound.ALERT, 5)

    def test_respects_settings(self):
        """Assert that disabled audio manager does not trigger sounds."""
        self.audio.enabled = False
        
        with patch.object(self.audio, 'play') as mock_play:
            event_bus.emit(GameEvent(EventType.WARNING))
            mock_play.assert_not_called()

    def test_queue_processing(self):
        """Regression: ensure queue worker actually calls _play_sound."""
        # This is more of an integration test
        with patch.object(self.audio, '_play_sound') as mock_play_internal:
            self.audio.play(Sound.BEEP)
            
            # Wait for worker thread to process
            timeout = 1.0
            start = time.time()
            while mock_play_internal.call_count == 0 and time.time() - start < timeout:
                time.sleep(0.01)
                
            mock_play_internal.assert_called_with(Sound.BEEP)

    def test_spatial_filtering(self):
        """Assert that sounds in other rooms are filtered appropriately."""
        # Create a mock player and station map
        player = MagicMock()
        player.location = (5, 5) # Rec Room center
        
        station_map = MagicMock()
        # Mock room names
        def mock_get_room(x, y):
            if x == 5 and y == 5: return "Rec Room"
            if x == 0 and y == 0: return "Infirmary"
            return "Corridor"
        station_map.get_room_name.side_effect = mock_get_room
        
        self.audio.player_ref = player
        self.audio.station_map = station_map
        
        with patch.object(self.audio, 'play') as mock_play:
            # 1. Sound in SAME room -> Should play
            event_bus.emit(GameEvent(EventType.ITEM_PICKUP, {"room": "Rec Room"}))
            mock_play.assert_called_with(Sound.CLICK, 5)
            
            mock_play.reset_mock()
            
            # 2. Sound in DIFFERENT room (Priority <= 7) -> Should NOT play
            event_bus.emit(GameEvent(EventType.ITEM_PICKUP, {"room": "Infirmary"}))
            mock_play.assert_not_called()
            
            # 3. Critical sound in DIFFERENT room (Priority 10) -> Should play
            event_bus.emit(GameEvent(EventType.POWER_FAILURE, {"room": "Generator"}))
            mock_play.assert_called_with(Sound.POWER_DOWN, 10)

if __name__ == '__main__':
    unittest.main()
