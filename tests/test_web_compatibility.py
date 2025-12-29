
import sys
import os
import unittest
from unittest.mock import MagicMock

# Add src to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_path = os.path.join(project_root, "src")
sys.path.insert(0, src_path)

from ui.crt_effects import CRTOutput

class TestWebBuffering(unittest.TestCase):
    def test_crt_buffering(self):
        """Test that CRTOutput correctly buffers messages when in capture mode."""
        crt = CRTOutput()
        
        # Normal mode (should print)
        # We can't easily assert print, but we can assert buffer is empty
        crt.output("Normal message")
        self.assertEqual(len(crt.buffer), 0)
        
        # Capture mode
        crt.start_capture()
        self.assertTrue(crt.capture_mode)
        
        crt.output("Buffered message 1")
        crt.warning("Buffered warning")
        
        self.assertEqual(len(crt.buffer), 2)
        self.assertEqual(crt.buffer[0], "Buffered message 1")
        self.assertEqual(crt.buffer[1], "[WARNING] Buffered warning")
        
        # Stop capture
        messages = crt.stop_capture()
        self.assertFalse(crt.capture_mode)
        self.assertEqual(len(messages), 2)
        self.assertEqual(len(crt.buffer), 0) # Buffer should be cleared or reset on next start, 
                                            # strictly speaking stop_capture returns it but doesn't necessarily clear if we don't want.
                                            # My implementation sets capture_mode False. 
                                            # start_capture clears it.

    def test_mock_server_flow(self):
        """Simulate the flow in server.py."""
        # Setup
        game_mock = MagicMock()
        game_mock.crt = CRTOutput()
        
        # Start Capture
        game_mock.crt.start_capture()
        
        # Simulate command execution generating messages
        game_mock.crt.output("Combat log 1")
        game_mock.crt.output("Movement log 1")
        
        # Simulate return from _execute_game_command (which might return its own direct output)
        command_result = "You moved North."
        
        # Stop Capture
        extra_messages = game_mock.crt.stop_capture()
        
        # Combine
        if extra_messages:
            full_result = command_result + "\n" + "\n".join(extra_messages)
        else:
            full_result = command_result
            
        expected = "You moved North.\nCombat log 1\nMovement log 1"
        self.assertEqual(full_result, expected)
        print("Buffered Output Flow Verified:")
        print(full_result)

if __name__ == '__main__':
    unittest.main()
