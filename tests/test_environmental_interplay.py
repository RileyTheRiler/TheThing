"""Integration tests for environmental and weather interplay.

Tests the interaction between WeatherSystem, SabotageManager, and RoomStateManager
via the new TEMPERATURE_THRESHOLD_CROSSED and ENVIRONMENTAL_STATE_CHANGE events.
"""

import sys
import os
import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.event_system import event_bus, EventType, GameEvent
from systems.weather import WeatherSystem
from systems.sabotage import SabotageManager
from systems.room_state import RoomStateManager, RoomState
from systems.architect import RandomnessEngine


class MockGameState:
    """Mock game state for testing."""
    def __init__(self):
        self.temperature = 0
        self.power_on = True
        self.blood_bank_destroyed = False


class TestEnvironmentalInterplay:
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear event bus before and after each test."""
        event_bus.clear()
        yield
        event_bus.clear()
    
    def test_temperature_threshold_crossing_falling(self):
        """Test that crossing below -50°C emits event and freezes rooms."""
        game_state = MockGameState()
        game_state.temperature = -40  # Start above threshold
        
        weather = WeatherSystem()
        room_manager = RoomStateManager(["Lab", "Kennel", "Generator"])
        rng = RandomnessEngine(seed=42)
        
        # Manually set temperature below threshold
        game_state.temperature = -60
        
        # Trigger weather tick
        weather.tick(rng, game_state)
        
        # Check that FROZEN state was added to rooms (except Generator and Kennel which starts frozen)
        assert room_manager.has_state("Lab", RoomState.FROZEN)
        
        # Cleanup
        weather.cleanup()
        room_manager.cleanup()
    
    def test_temperature_threshold_crossing_rising(self):
        """Test that crossing above -50°C removes frozen state."""
        game_state = MockGameState()
        game_state.temperature = -60  # Start below threshold
        
        weather = WeatherSystem()
        room_manager = RoomStateManager(["Lab", "Kennel", "Generator"])
        rng = RandomnessEngine(seed=42)
        
        # First tick to establish below threshold
        weather.tick(rng, game_state)
        
        # Now raise temperature above threshold
        game_state.temperature = -40
        weather.tick(rng, game_state)
        
        # Check that FROZEN state was removed from Lab (Kennel starts frozen)
        assert not room_manager.has_state("Lab", RoomState.FROZEN)
        
        # Cleanup
        weather.cleanup()
        room_manager.cleanup()
    
    def test_power_loss_and_restoration(self):
        """Test power outage and restoration emit correct events and update room states."""
        game_state = MockGameState()
        
        sabotage = SabotageManager()
        room_manager = RoomStateManager(["Lab", "Kennel", "Generator"])
        
        # Track events
        events_received = []
        
        def event_tracker(event):
            events_received.append(event.type)
        
        event_bus.subscribe(EventType.POWER_FAILURE, event_tracker)
        event_bus.subscribe(EventType.ENVIRONMENTAL_STATE_CHANGE, event_tracker)
        
        # Trigger power outage
        sabotage.trigger_power_outage(game_state)
        
        # Check events were emitted
        assert EventType.POWER_FAILURE in events_received
        assert EventType.ENVIRONMENTAL_STATE_CHANGE in events_received
        
        # Check rooms are dark
        assert room_manager.has_state("Lab", RoomState.DARK)
        assert room_manager.has_state("Kennel", RoomState.DARK)
        
        # Clear events
        events_received.clear()
        
        # Restore power
        sabotage.restore_power(game_state)
        
        # Check environmental change event was emitted
        assert EventType.ENVIRONMENTAL_STATE_CHANGE in events_received
        
        # Check darkness was removed
        assert not room_manager.has_state("Lab", RoomState.DARK)
        assert not room_manager.has_state("Kennel", RoomState.DARK)
        
        # Cleanup
        sabotage.cleanup()
        room_manager.cleanup()
    
    def test_combined_effects(self):
        """Test that power loss + temperature drop results in both DARK and FROZEN states."""
        game_state = MockGameState()
        game_state.temperature = -40  # Start above freezing threshold
        
        weather = WeatherSystem()
        sabotage = SabotageManager()
        room_manager = RoomStateManager(["Lab", "Kennel", "Generator"])
        rng = RandomnessEngine(seed=42)
        
        # Trigger power outage
        sabotage.trigger_power_outage(game_state)
        
        # Drop temperature below threshold
        game_state.temperature = -60
        weather.tick(rng, game_state)
        
        # Check Lab has both states
        assert room_manager.has_state("Lab", RoomState.DARK)
        assert room_manager.has_state("Lab", RoomState.FROZEN)
        
        # Restore power
        sabotage.restore_power(game_state)
        
        # Check only FROZEN remains (DARK removed)
        assert not room_manager.has_state("Lab", RoomState.DARK)
        assert room_manager.has_state("Lab", RoomState.FROZEN)
        
        # Cleanup
        weather.cleanup()
        sabotage.cleanup()
        room_manager.cleanup()
    
    def test_barricaded_rooms_stay_dark(self):
        """Test that barricaded rooms remain dark even when power is restored."""
        game_state = MockGameState()
        
        sabotage = SabotageManager()
        room_manager = RoomStateManager(["Lab", "Kennel", "Generator"])
        
        # Barricade the Lab
        room_manager.barricade_room("Lab")
        
        # Trigger power outage
        sabotage.trigger_power_outage(game_state)
        
        # Both Lab and Kennel should be dark
        assert room_manager.has_state("Lab", RoomState.DARK)
        assert room_manager.has_state("Kennel", RoomState.DARK)
        
        # Restore power
        sabotage.restore_power(game_state)
        
        # Lab should still be dark (barricaded), Kennel should not
        assert room_manager.has_state("Lab", RoomState.DARK)
        assert not room_manager.has_state("Kennel", RoomState.DARK)
        
        # Cleanup
        sabotage.cleanup()
        room_manager.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
