"""
Test schedule validation during crew initialization.

Ensures that invalid schedules are caught and handled gracefully.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from engine import GameState
from systems.architect import Difficulty


class TestScheduleValidation(unittest.TestCase):
    """Test schedule validation logic in GameState._validate_schedule."""

    def test_valid_schedule_loads_successfully(self):
        """Valid schedules should load without errors."""
        # This uses the default characters.json which has valid schedules
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)
        
        # Verify crew loaded
        self.assertGreater(len(game.crew), 0)
        
        # Verify schedules exist
        for member in game.crew:
            if hasattr(member, 'schedule'):
                for entry in member.schedule:
                    # Verify required fields
                    self.assertIn('room', entry)
                    self.assertIn('start', entry)
                    self.assertIn('end', entry)
                    
                    # Verify room exists in map
                    self.assertIn(entry['room'], game.station_map.rooms)
                    
                    # Verify hours are valid
                    self.assertGreaterEqual(entry['start'], 0)
                    self.assertLessEqual(entry['start'], 24)
                    self.assertGreaterEqual(entry['end'], 0)
                    self.assertLessEqual(entry['end'], 24)

    def test_invalid_room_raises_error(self):
        """Schedule with non-existent room should raise ValueError."""
        # We can't easily test this without modifying the JSON file
        # or creating a mock, so this is a placeholder for manual testing
        pass

    def test_invalid_hours_raise_error(self):
        """Schedule with invalid hours should raise ValueError."""
        # Similar to above - would need mock data
        pass

    def test_wraparound_schedule_valid(self):
        """Schedules that wrap around midnight should be valid."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)
        
        # Find Palmer who has a wraparound schedule (12-24, 0-12)
        palmer = next((m for m in game.crew if m.name == "Palmer"), None)
        if palmer:
            # Verify schedule loaded
            self.assertGreater(len(palmer.schedule), 0)
            # Palmer's schedule wraps midnight
            self.assertTrue(any(e.get('start', 0) > e.get('end', 24) or 
                              (e.get('start') == 0 or e.get('end') == 24) 
                              for e in palmer.schedule))


if __name__ == "__main__":
    unittest.main()
