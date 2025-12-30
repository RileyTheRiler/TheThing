"""
Tests for save/load validation features including versioning,
checksum integrity, backup creation, and migration.
"""

import os
import sys
import json
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.systems.persistence import (
    SaveManager,
    compute_checksum,
    validate_save_data,
    migrate_save,
    CURRENT_SAVE_VERSION
)


class MockGameState:
    """Mock game state for testing."""
    def __init__(self, name="Test"):
        self.name = name
        self.turn = 1
        self.crew = []
        self.player_location = [5, 5]

    def to_dict(self):
        return {
            "name": self.name,
            "turn": self.turn,
            "crew": self.crew,
            "player_location": self.player_location,
            "difficulty": "NORMAL",
            "rng": {},
            "time_system": {},
            "station_map": {},
            "journal": [],
            "trust": {},
            "crafting": {},
            "alert_system": {},
            "security_system": {}
        }

    @classmethod
    def from_dict(cls, data):
        g = cls(data.get("name", "Restored"))
        g.turn = data.get("turn", 1)
        g.crew = data.get("crew", [])
        g.player_location = list(data.get("player_location", [5, 5]))
        return g


class TestChecksumComputation(unittest.TestCase):
    """Test checksum computation for save data integrity."""

    def test_checksum_is_consistent(self):
        """Same data should produce same checksum."""
        data = {"turn": 5, "crew": ["MacReady"], "player_location": [3, 4]}
        checksum1 = compute_checksum(data)
        checksum2 = compute_checksum(data)
        self.assertEqual(checksum1, checksum2)

    def test_checksum_changes_with_data(self):
        """Different data should produce different checksums."""
        data1 = {"turn": 5, "crew": ["MacReady"], "player_location": [3, 4]}
        data2 = {"turn": 6, "crew": ["MacReady"], "player_location": [3, 4]}
        self.assertNotEqual(compute_checksum(data1), compute_checksum(data2))

    def test_checksum_ignores_checksum_field(self):
        """Checksum computation should ignore existing _checksum field."""
        data = {"turn": 5, "crew": [], "player_location": [3, 4]}
        checksum_without = compute_checksum(data)
        data["_checksum"] = "old_checksum"
        checksum_with = compute_checksum(data)
        self.assertEqual(checksum_without, checksum_with)


class TestSaveDataValidation(unittest.TestCase):
    """Test save data validation logic."""

    def test_valid_save_data_passes(self):
        """Valid save data should pass validation."""
        data = {
            "turn": 5,
            "crew": [],
            "player_location": [3, 4],
            "difficulty": "NORMAL",
            "rng": {},
            "time_system": {},
            "station_map": {},
            "save_version": 2,
            "checksum": "mock" # mocked
        }
        # We need a real checksum for it to pass if we include it
        # But validate_save_data checks for required fields first
        # It calls compute_checksum if checksum is present
        data["checksum"] = compute_checksum(data)

        is_valid, error = validate_save_data(data)
        self.assertTrue(is_valid, f"Validation failed: {error}")
        self.assertIsNone(error)

    def test_missing_required_fields_fails(self):
        """Save data missing required fields should fail."""
        data = {"turn": 5}  # Missing 'crew' and 'player_location'
        is_valid, error = validate_save_data(data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required fields", error)

    def test_checksum_mismatch_fails(self):
        """Save data with invalid checksum should fail."""
        data = {
            "turn": 5,
            "crew": [],
            "player_location": [3, 4],
            "difficulty": "NORMAL",
            "rng": {},
            "time_system": {},
            "station_map": {},
            "save_version": 2
        }
        data["checksum"] = "invalid_checksum"
        is_valid, error = validate_save_data(data)
        self.assertFalse(is_valid)
        self.assertIn("checksum mismatch", error)

    def test_valid_checksum_passes(self):
        """Save data with valid checksum should pass."""
        data = {
            "turn": 5,
            "crew": [],
            "player_location": [3, 4],
            "difficulty": "NORMAL",
            "rng": {},
            "time_system": {},
            "station_map": {},
            "save_version": 2
        }
        data["checksum"] = compute_checksum(data)
        is_valid, error = validate_save_data(data)
        self.assertTrue(is_valid, f"Validation failed: {error}")
        self.assertIsNone(error)

    def test_non_dict_data_fails(self):
        """Non-dictionary data should fail validation."""
        is_valid, error = validate_save_data("not a dict")
        self.assertFalse(is_valid)
        self.assertIn("not a valid dictionary", error)


class TestSaveMigration(unittest.TestCase):
    """Test save version migration."""

    def test_migrate_updates_version(self):
        """Migration should update save version."""
        data = {"turn": 5, "crew": [], "player_location": [3, 4], "_save_version": 0}
        migrated = migrate_save(data, 0, CURRENT_SAVE_VERSION)
        self.assertEqual(migrated["_save_version"], CURRENT_SAVE_VERSION)

    def test_migrate_preserves_data(self):
        """Migration should preserve existing data."""
        data = {"turn": 10, "crew": ["A", "B"], "player_location": [7, 8]}
        migrated = migrate_save(data, 0, CURRENT_SAVE_VERSION)
        self.assertEqual(migrated["turn"], 10)
        self.assertEqual(migrated["crew"], ["A", "B"])
        self.assertEqual(migrated["player_location"], [7, 8])


class TestSaveManagerWithValidation(unittest.TestCase):
    """Test SaveManager with validation features."""

    def setUp(self):
        self.save_dir = "tests/test_saves_validation"
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)
        os.makedirs(self.save_dir)

    def tearDown(self):
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)

    def test_save_adds_version_and_checksum(self):
        """Saving should add version and checksum to save data."""
        manager = SaveManager(save_dir=self.save_dir)
        game = MockGameState("TestGame")
        game.turn = 5

        manager.save_game(game, "versioned_slot")

        # Read raw file
        filepath = os.path.join(self.save_dir, "versioned_slot.json")
        with open(filepath) as f:
            data = json.load(f)

        self.assertIn("_save_version", data)
        self.assertEqual(data["_save_version"], CURRENT_SAVE_VERSION)
        self.assertIn("checksum", data)
        self.assertIn("_saved_at", data)

    def test_backup_created_on_overwrite(self):
        """Overwriting a save should create a backup."""
        manager = SaveManager(save_dir=self.save_dir)

        # First save
        game1 = MockGameState("First")
        manager.save_game(game1, "backup_test")

        # Second save (overwrites)
        game2 = MockGameState("Second")
        manager.save_game(game2, "backup_test")

        # Check backup exists
        backup_dir = os.path.join(self.save_dir, "backups")
        self.assertTrue(os.path.exists(backup_dir))

        backups = [f for f in os.listdir(backup_dir) if f.startswith("backup_test")]
        self.assertGreater(len(backups), 0)

    def test_load_validates_checksum(self):
        """Loading should validate checksum."""
        manager = SaveManager(save_dir=self.save_dir)
        game = MockGameState("ChecksumTest")
        manager.save_game(game, "checksum_slot")

        # Load should work with valid checksum
        data = manager.load_game("checksum_slot")
        self.assertIsNotNone(data)

    def test_load_rejects_corrupted_file(self):
        """Loading corrupted file should fail or load from backup."""
        manager = SaveManager(save_dir=self.save_dir)
        game = MockGameState("CorruptTest")
        manager.save_game(game, "corrupt_slot")

        # Corrupt the file
        filepath = os.path.join(self.save_dir, "corrupt_slot.json")
        with open(filepath, 'r') as f:
            data = json.load(f)
        data["turn"] = 999  # Change data to invalidate checksum
        with open(filepath, 'w') as f:
            json.dump(data, f)

        # Load should fail (checksum mismatch)
        result = manager.load_game("corrupt_slot")
        # Result will be None since there's no backup yet
        self.assertIsNone(result)


class TestBackupCleanup(unittest.TestCase):
    """Test backup file management."""

    def setUp(self):
        self.save_dir = "tests/test_backup_cleanup"
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)
        os.makedirs(self.save_dir)

    def tearDown(self):
        if os.path.exists(self.save_dir):
            shutil.rmtree(self.save_dir)

    def test_old_backups_cleaned_up(self):
        """Only most recent backups should be kept."""
        manager = SaveManager(save_dir=self.save_dir)

        # Create many saves to trigger cleanup
        for i in range(8):
            game = MockGameState(f"Iteration{i}")
            game.turn = i
            manager.save_game(game, "cleanup_test")

        backup_dir = os.path.join(self.save_dir, "backups")
        if os.path.exists(backup_dir):
            backups = [f for f in os.listdir(backup_dir) if f.startswith("cleanup_test")]
            # Should keep only 5 backups
            self.assertLessEqual(len(backups), 5)


if __name__ == '__main__':
    unittest.main()
