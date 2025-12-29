"""
Integration test for EnvironmentalCoordinator within the real GameState.
"""
import sys
import os
import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from engine import GameState
from core.event_system import event_bus, EventType
from systems.environmental_contract import TemperatureLevel

def test_environmental_coordinator_lifecycle():
    """Test that coordinator is created, updates on turn advance, and cleans up."""
    game = GameState()
    coordinator = game.environmental_coordinator
    
    assert coordinator is not None
    assert coordinator.current_snapshot is None
    
    # Force temperature for testing
    game.time_system.temperature = 20.0
    
    # Advance turn to trigger update
    game.advance_turn()
    
    assert coordinator.current_snapshot is not None
    assert coordinator.current_snapshot.temperature == 20.0
    assert coordinator.current_snapshot.temperature_level == TemperatureLevel.NORMAL
    
    # Check that snapshot was added to history
    assert len(coordinator.history) == 1
    
    # Cleanup
    game.cleanup()

def test_environmental_coordinator_power_failure():
    """Test that coordinator reacts to power failure events."""
    game = GameState()
    coordinator = game.environmental_coordinator
    
    # Track system logs
    logs = []
    def log_tracker(event):
        logs.append(event.payload.get('text', ''))
    
    event_bus.subscribe(EventType.SYSTEM_LOG, log_tracker)
    
    # Trigger power failure
    game.sabotage.trigger_power_outage(game)
    
    # Check that coordinator emitted a log
    assert any("POWER FAILURE" in log for log in logs)
    
    game.cleanup()

def test_environmental_coordinator_threshold_warning():
    """Test that coordinator emits warnings when temperature drops."""
    game = GameState()
    coordinator = game.environmental_coordinator
    
    # Track warnings
    warnings = []
    def warning_tracker(event):
        warnings.append(event.payload.get('text', ''))
    
    event_bus.subscribe(EventType.WARNING, warning_tracker)
    
    # First turn - normal temp
    game.time_system.temperature = 20.0
    game.advance_turn()
    
    # Second turn - drop temp to freezing
    game.time_system.temperature = -60.0
    game.advance_turn()
    
    # Check that warning was emitted
    assert any("FREEZING" in w.upper() for w in warnings)
    
    game.cleanup()
