import os
import json
import pytest
import sys
from unittest.mock import patch, MagicMock

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.event_system import event_bus, EventType, GameEvent
from systems.statistics import StatisticsManager, STATS_FILE

class TestStatisticsTelemetry:
    @pytest.fixture
    def stats_manager(self, tmp_path):
        # Use a temporary file for stats to avoid messing with user's actual stats
        test_stats_file = tmp_path / "test_stats.json"
        with patch("systems.statistics.STATS_FILE", str(test_stats_file)):
            manager = StatisticsManager()
            yield manager

    def test_stealth_encounter_tracking(self, stats_manager):
        stats_manager.start_session()
        
        # Emit a stealth report event
        event_bus.emit(GameEvent(EventType.STEALTH_REPORT, {
            "room": "Lab",
            "opponent": "Palmer",
            "outcome": "evaded"
        }))
        
        assert stats_manager.current_session.stealth_encounters == 1
        
        stats_manager.end_session("victory", 10)
        assert stats_manager.career.total_stealth_encounters == 1

    def test_crafting_success_tracking(self, stats_manager):
        stats_manager.start_session()
        
        # Emit a successful crafting report
        event_bus.emit(GameEvent(EventType.CRAFTING_REPORT, {
            "event": "completed",
            "recipe": "molotov",
            "actor": "MacReady",
            "item_name": "Molotov Cocktail"
        }))
        
        # Emit an unsuccessful/queued crafting report (should not count as success)
        event_bus.emit(GameEvent(EventType.CRAFTING_REPORT, {
            "event": "queued",
            "recipe": "radio",
            "actor": "MacReady"
        }))
        
        assert stats_manager.current_session.crafting_successes == 1
        
        stats_manager.end_session("victory", 10)
        assert stats_manager.career.total_crafting_successes == 1

    def test_ending_type_tracking(self, stats_manager):
        stats_manager.start_session()
        
        # Emit an ending report
        event_bus.emit(GameEvent(EventType.ENDING_REPORT, {
            "result": "win",
            "ending_type": "ESCAPE",
            "name": "The Great Escape",
            "message": "You flew away!",
            "turn": 42
        }))
        
        assert stats_manager.current_session.ending_type == "ESCAPE"
        
        stats_manager.end_session("victory", 42)
        assert stats_manager.career.ending_types_witnessed.get("ESCAPE") == 1

    def test_persistence(self, stats_manager, tmp_path):
        stats_manager.start_session()
        event_bus.emit(GameEvent(EventType.STEALTH_REPORT, {"outcome": "evaded"}))
        stats_manager.end_session("victory", 10)
        
        # Create a new manager instance and check if it loads the same data
        test_stats_file = tmp_path / "test_stats.json"
        with patch("systems.statistics.STATS_FILE", str(test_stats_file)):
            new_manager = StatisticsManager()
            assert new_manager.career.total_stealth_encounters == 1
            assert new_manager.career.victories == 1
