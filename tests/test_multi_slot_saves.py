"""
Tests for Multi-Slot Save System (Tier 10.3)
"""

import sys
import os
import json
import tempfile
import shutil

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from systems.persistence import SaveManager, SAVE_SLOTS, AUTO_SAVE_INTERVAL


class MockGameState:
    """Mock game state for testing saves."""
    
    def __init__(self, name="Test"):
        self.name = name
        self.turn = 1
        self.crew = []
        self.player_location = (5, 5)
        self.difficulty = "Normal"
    
    def to_dict(self):
        return {
            "name": self.name,
            "turn": self.turn,
            "crew": self.crew,
            "player_location": list(self.player_location),
            "difficulty": self.difficulty
        }
    
    @classmethod
    def from_dict(cls, data):
        g = cls(data.get("name", "Restored"))
        g.turn = data.get("turn", 1)
        g.crew = data.get("crew", [])
        g.player_location = tuple(data.get("player_location", (5, 5)))
        g.difficulty = data.get("difficulty", "Normal")
        return g


class TestMultiSlotSaves:
    """Test multi-slot save functionality."""

    def setup_method(self):
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SaveManager(save_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up temp directory."""
        self.manager.cleanup()
        shutil.rmtree(self.temp_dir)

    def test_five_slots_available(self):
        """Test that 5 save slots are defined."""
        assert len(SAVE_SLOTS) == 5
        assert SAVE_SLOTS == ["slot_1", "slot_2", "slot_3", "slot_4", "slot_5"]

    def test_autosave_interval_is_10(self):
        """Test that auto-save interval is 10 turns."""
        assert AUTO_SAVE_INTERVAL == 10

    def test_save_to_numbered_slot(self):
        """Test saving to a numbered slot."""
        game = MockGameState("SlotTest")
        game.turn = 25
        
        success = self.manager.save_to_slot(game, 3)
        assert success is True
        
        # Verify file exists
        filepath = os.path.join(self.temp_dir, "slot_3.json")
        assert os.path.exists(filepath)

    def test_load_from_numbered_slot(self):
        """Test loading from a numbered slot."""
        game = MockGameState("LoadTest")
        game.turn = 42
        
        self.manager.save_to_slot(game, 2)
        
        data = self.manager.load_from_slot(2)
        assert data is not None
        assert data.get("turn") == 42
        assert data.get("name") == "LoadTest"

    def test_get_slot_metadata(self):
        """Test retrieving slot metadata without full load."""
        game = MockGameState("MetaTest")
        game.turn = 15
        game.difficulty = "Hard"
        
        self.manager.save_to_slot(game, 1)
        
        metadata = self.manager.get_slot_metadata("slot_1")
        
        assert metadata is not None
        assert metadata["turn"] == 15
        assert metadata["difficulty"] == "Hard"
        assert "timestamp" in metadata

    def test_list_all_slots(self):
        """Test listing all slots with status."""
        # Save to slots 1 and 3
        game1 = MockGameState("Game1")
        game1.turn = 10
        self.manager.save_to_slot(game1, 1)
        
        game2 = MockGameState("Game2")
        game2.turn = 20
        self.manager.save_to_slot(game2, 3)
        
        slots = self.manager.list_save_slots()
        
        # Should have 5 slots listed
        slot_names = [s["slot_name"] for s in slots if s["slot_name"].startswith("slot_")]
        assert len(slot_names) == 5
        
        # Slot 1 should not be empty
        slot_1 = next(s for s in slots if s["slot_name"] == "slot_1")
        assert slot_1["empty"] is False
        assert slot_1["turn"] == 10
        
        # Slot 2 should be empty
        slot_2 = next(s for s in slots if s["slot_name"] == "slot_2")
        assert slot_2["empty"] is True

    def test_delete_slot(self):
        """Test deleting a save slot."""
        game = MockGameState("DeleteTest")
        self.manager.save_to_slot(game, 4)
        
        # Verify it exists
        assert self.manager.get_slot_metadata("slot_4") is not None
        
        # Delete it
        success = self.manager.delete_slot(4)
        assert success is True
        
        # Verify it's gone
        assert self.manager.get_slot_metadata("slot_4") is None

    def test_invalid_slot_number(self):
        """Test that invalid slot numbers are rejected."""
        game = MockGameState("InvalidTest")
        
        # Slot 0 is invalid
        success = self.manager.save_to_slot(game, 0)
        assert success is False
        
        # Slot 6 is invalid
        success = self.manager.save_to_slot(game, 6)
        assert success is False

    def test_campaign_save_load(self):
        """Test campaign save and load."""
        campaign_state = {
            "current_run": 2,
            "carryover_items": ["Flamethrower", "Medical Kit"],
            "difficulty_modifier": 2
        }
        
        success = self.manager.save_campaign(campaign_state)
        assert success is True
        
        loaded = self.manager.load_campaign()
        assert loaded is not None
        assert loaded["current_run"] == 2
        assert "Flamethrower" in loaded["carryover_items"]

    def test_delete_campaign(self):
        """Test campaign deletion (permadeath)."""
        campaign_state = {"current_run": 1}
        self.manager.save_campaign(campaign_state)
        
        # Verify exists
        assert self.manager.load_campaign() is not None
        
        # Delete
        success = self.manager.delete_campaign()
        assert success is True
        
        # Verify gone
        assert self.manager.load_campaign() is None


def run_tests():
    """Run all tests."""
    test = TestMultiSlotSaves()
    
    tests = [
        ("5 slots available", test.test_five_slots_available),
        ("autosave interval is 10", test.test_autosave_interval_is_10),
        ("save to numbered slot", test.test_save_to_numbered_slot),
        ("load from numbered slot", test.test_load_from_numbered_slot),
        ("get slot metadata", test.test_get_slot_metadata),
        ("list all slots", test.test_list_all_slots),
        ("delete slot", test.test_delete_slot),
        ("invalid slot number", test.test_invalid_slot_number),
        ("campaign save and load", test.test_campaign_save_load),
        ("delete campaign", test.test_delete_campaign),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        test.setup_method()
        try:
            test_func()
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1
        finally:
            test.teardown_method()
    
    print(f"\n=== RESULTS: {passed} passed, {failed} failed ===")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
