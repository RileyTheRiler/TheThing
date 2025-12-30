import unittest
from unittest.mock import Mock, patch
import sys
import os

sys.path.append(os.path.join(os.getcwd(), 'src'))

from ui.command_parser import CommandParser
from ui.crt_effects import CRTOutput, ANSI

class TestPolishFeatures(unittest.TestCase):
    def setUp(self):
        self.parser = CommandParser()
        self.crt = CRTOutput(palette="amber")
        self.crt.enabled = True 
        # Capture output
        self.crt.start_capture()

    def test_fuzzy_command_repair(self):
        """Test that bad typos resolve to correct commands."""
        # "rpaiar" -> REPAIR
        result = self.parser.parse("rpaiar radio")
        self.assertIsNotNone(result)
        self.assertEqual(result['action'], 'REPAIR')
        
        # "attak" -> ATTACK
        result = self.parser.parse("attak thing")
        self.assertIsNotNone(result)
        self.assertEqual(result['action'], 'ATTACK')

    def test_fuzzy_intent_short(self):
        """Test short commands require high fidelity or context."""
        # "go" -> MOVE
        result = self.parser.parse("go north")
        self.assertEqual(result['action'], 'MOVE')
        
        # "g" -> Bad parsing? "g" isn't standard unless mapped
        # Verify parser handles it gracefully
        result = self.parser.parse("g north")
        # Depending on logic, might fail or fuzzy match "GO"
        # Our implementation requires >0.9 ratio for length <=3
        # "g" vs "go" is 0.66, so should fail/return None or raw
        # Actually checking implementation: if len<=3 ratio>0.9.
        # So "g" won't match "go"
        self.assertIsNone(result)

    def test_crt_colors(self):
        """Test semantic color event logging."""
        self.crt.event("We won!", type="victory")
        output = self.crt.stop_capture()
        self.assertTrue(any("VICTORY" in line for line in output))

    @patch('time.sleep')
    def test_dramatic_pause(self, mock_sleep):
        """Test that crawl_pause calls sleep."""
        self.crt.enabled = True
        self.crt.capture_mode = False # Pause disabled in capture mode
        
        # Verify it calls time.sleep
        self.crt.crawl_pause(0.5)
        mock_sleep.assert_called_with(0.5)

if __name__ == '__main__':
    unittest.main()
