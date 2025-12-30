"""
Tests for Meta-Progression System (Tier 10.1)
"""

import sys
import os
import json
import tempfile
import shutil

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from systems.meta_progression import MetaProgressionSystem, LifetimeStats


class TestMetaProgressionSystem:
    """Test meta-progression functionality."""

    def setup_method(self):
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.progress_file = os.path.join(self.temp_dir, "meta_progress.json")
        self.unlockables_file = os.path.join(self.temp_dir, "unlockables.json")
        
        # Create test unlockables
        unlockables = {
            "roles": {
                "default": {
                    "name": "Default",
                    "description": "Standard role",
                    "unlock_condition": None,
                    "bonuses": {}
                },
                "veteran": {
                    "name": "Veteran",
                    "description": "Combat bonus",
                    "unlock_condition": {"stat": "games_won", "threshold": 3},
                    "bonuses": {"combat_modifier": 2}
                },
                "scientist": {
                    "name": "Scientist",
                    "description": "Start with Test Kit",
                    "unlock_condition": {"stat": "blood_tests_performed", "threshold": 10},
                    "bonuses": {"starting_items": ["Test Kit"]}
                }
            }
        }
        with open(self.unlockables_file, 'w') as f:
            json.dump(unlockables, f)

    def teardown_method(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir)

    def test_init_creates_default_stats(self):
        """Test that initialization creates default lifetime stats."""
        system = MetaProgressionSystem(
            progress_file=self.progress_file,
            unlockables_file=self.unlockables_file
        )
        
        assert system.stats.games_won == 0
        assert system.stats.blood_tests_performed == 0
        system.cleanup()

    def test_unlock_veteran_after_3_wins(self):
        """Test that Veteran role unlocks after 3 wins."""
        system = MetaProgressionSystem(
            progress_file=self.progress_file,
            unlockables_file=self.unlockables_file
        )
        
        # Simulate 3 wins
        for i in range(3):
            system.record_game_end(won=True, ending_type="ESCAPE")
        
        assert "veteran" in system.unlocked_roles
        assert system.stats.games_won == 3
        system.cleanup()

    def test_veteran_bonus_applies(self):
        """Test that Veteran role provides combat modifier."""
        system = MetaProgressionSystem(
            progress_file=self.progress_file,
            unlockables_file=self.unlockables_file
        )
        
        # Unlock and select veteran
        for i in range(3):
            system.record_game_end(won=True, ending_type="ESCAPE")
        
        system.select_role("veteran")
        assert system.get_combat_modifier() == 2
        system.cleanup()

    def test_progress_persists_to_file(self):
        """Test that progress saves and loads correctly."""
        # Create system and add some progress
        system1 = MetaProgressionSystem(
            progress_file=self.progress_file,
            unlockables_file=self.unlockables_file
        )
        system1.record_game_end(won=True, ending_type="ESCAPE")
        system1.cleanup()
        
        # Load in new system
        system2 = MetaProgressionSystem(
            progress_file=self.progress_file,
            unlockables_file=self.unlockables_file
        )
        
        assert system2.stats.games_won == 1
        system2.cleanup()

    def test_get_available_roles(self):
        """Test listing available roles with unlock status."""
        system = MetaProgressionSystem(
            progress_file=self.progress_file,
            unlockables_file=self.unlockables_file
        )
        
        roles = system.get_available_roles()
        
        # Should have all roles listed
        assert len(roles) == 3
        
        # Default should be unlocked
        default_role = next(r for r in roles if r["id"] == "default")
        assert default_role["unlocked"] is True
        
        # Veteran should not be unlocked
        veteran_role = next(r for r in roles if r["id"] == "veteran")
        assert veteran_role["unlocked"] is False
        
        system.cleanup()

    def test_select_locked_role_fails(self):
        """Test that selecting a locked role fails."""
        system = MetaProgressionSystem(
            progress_file=self.progress_file,
            unlockables_file=self.unlockables_file
        )
        
        success = system.select_role("veteran")
        assert success is False
        system.cleanup()


def run_tests():
    """Run all tests."""
    test = TestMetaProgressionSystem()
    
    tests = [
        ("init creates default stats", test.test_init_creates_default_stats),
        ("unlock veteran after 3 wins", test.test_unlock_veteran_after_3_wins),
        ("veteran bonus applies", test.test_veteran_bonus_applies),
        ("progress persists to file", test.test_progress_persists_to_file),
        ("get available roles", test.test_get_available_roles),
        ("select locked role fails", test.test_select_locked_role_fails),
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
