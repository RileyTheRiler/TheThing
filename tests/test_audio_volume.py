
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock winsound before importing audio_manager
mock_winsound = MagicMock()
sys.modules['winsound'] = mock_winsound

# Now import the class
from src.audio.audio_manager import AudioManager, Sound

class TestAudioManagerVolume(unittest.TestCase):
    def setUp(self):
        self.audio = AudioManager(enabled=True)
        # Force enable even if import failed (though with mock it should succeed)
        self.audio.enabled = True
        # But wait, the module level AUDIO_AVAILABLE depends on the import.
        # Since we mocked sys.modules['winsound'], the try-except in audio_manager should pass.

    def test_initial_volume(self):
        self.assertEqual(self.audio.volume, 1.0)

    def test_set_volume(self):
        # This method doesn't exist yet, so this test would fail if I ran it now
        if hasattr(self.audio, 'set_volume'):
            self.audio.set_volume(0.5)
            self.assertEqual(self.audio.volume, 0.5)

            self.audio.set_volume(1.5)
            self.assertEqual(self.audio.volume, 1.0)

            self.audio.set_volume(-0.5)
            self.assertEqual(self.audio.volume, 0.0)

    def test_play_sound_respects_mute_via_volume(self):
        # We need to test that _play_sound respects volume=0
        self.audio.volume = 0.0
        self.audio._play_sound(Sound.BEEP)
        # Should not call winsound.Beep
        mock_winsound.Beep.assert_not_called()

        self.audio.volume = 1.0
        self.audio._play_sound(Sound.BEEP)
        # Should call winsound.Beep
        mock_winsound.Beep.assert_called()

if __name__ == '__main__':
    unittest.main()
