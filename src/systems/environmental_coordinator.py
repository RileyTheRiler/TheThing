"""
Environmental Coordinator - Manages interplay between weather, power, and room states.

This system subscribes to environmental events and emits cohesive system logs
describing the combined impact of environmental conditions.
"""

from typing import Optional, Dict
from core.event_system import event_bus, EventType, GameEvent
from systems.environmental_contract import (
    EnvironmentalSnapshot, EnvironmentalThresholds, EnvironmentalEffects,
    TemperatureLevel, VisibilityLevel
)


class EnvironmentalCoordinator:
    """
    Coordinates environmental systems and emits unified status updates.
    
    Subscribes to:
    - TURN_ADVANCE: Update environmental state each turn
    - POWER_FAILURE: React to power outages
    - TEMPERATURE_THRESHOLD_CROSSED: Log temperature warnings
    
    Emits:
    - SYSTEM_LOG: Environmental status updates
    - WARNING: Critical environmental conditions
    - ENVIRONMENTAL_STATE_CHANGE: Coordinated state changes
    """
    
    def __init__(self, thresholds: Optional[EnvironmentalThresholds] = None):
        self.thresholds = thresholds or EnvironmentalThresholds()
        self.current_snapshot: Optional[EnvironmentalSnapshot] = None
        self.previous_snapshot: Optional[EnvironmentalSnapshot] = None
        
        # Environmental history for forensic analysis
        self.history: list[EnvironmentalSnapshot] = []
        self.max_history = 100
        
        # Subscribe to events
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.subscribe(EventType.POWER_FAILURE, self.on_power_failure)
    
    def cleanup(self):
        """Unsubscribe from events."""
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.unsubscribe(EventType.POWER_FAILURE, self.on_power_failure)
    
    def on_turn_advance(self, event: GameEvent):
        """Process environmental state each turn."""
        game_state = event.payload.get("game_state")
        if not game_state:
            return
        
        # Create snapshot from current game state
        snapshot = self._create_snapshot(game_state)
        
        # Store history
        self.previous_snapshot = self.current_snapshot
        self.current_snapshot = snapshot
        self.history.append(snapshot)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        # Check for threshold crossings and emit warnings
        warnings = snapshot.should_emit_warning(self.previous_snapshot, self.thresholds)
        for warning_type, message in warnings.items():
            event_bus.emit(GameEvent(EventType.WARNING, {
                'text': message,
                'warning_type': warning_type,
                'snapshot': snapshot
            }))
            
            # Also emit temperature threshold event for specific tracking
            if warning_type == 'temperature':
                event_bus.emit(GameEvent(EventType.TEMPERATURE_THRESHOLD_CROSSED, {
                    'temperature': snapshot.temperature,
                    'level': snapshot.temperature_level.name,
                    'previous_level': self.previous_snapshot.temperature_level.name if self.previous_snapshot else None
                }))
        
        # Emit environmental state change if significant
        if self._is_significant_change(self.previous_snapshot, snapshot):
            self._emit_state_change(snapshot)
    
    def on_power_failure(self, event: GameEvent):
        """React immediately to power failure."""
        duration = event.payload.get('duration', 5)
        
        # Emit coordinated state change
        event_bus.emit(GameEvent(EventType.ENVIRONMENTAL_STATE_CHANGE, {
            'change_type': 'power_failure',
            'duration': duration,
            'effects': 'All rooms becoming DARK. Temperature will begin dropping.'
        }))
        
        event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
            'text': f"POWER FAILURE: Station going dark. Estimated duration: {duration} hours.",
            'category': 'environmental'
        }))
    
    def _create_snapshot(self, game_state) -> EnvironmentalSnapshot:
        """Create environmental snapshot from game state."""
        snapshot = EnvironmentalSnapshot(
            power_on=game_state.power_on,
            temperature=game_state.temperature
        )
        
        # Get weather data if available
        if hasattr(game_state, 'weather'):
            snapshot.storm_intensity = game_state.weather.storm_intensity
            snapshot.visibility = game_state.weather.get_visibility()
            snapshot.wind_chill = game_state.weather.temperature_modifier
        
        # Count room states
        if hasattr(game_state, 'room_states'):
            from systems.room_state import RoomState
            for room_name in game_state.room_states.room_states:
                states = game_state.room_states.get_states(room_name)
                if RoomState.DARK in states:
                    snapshot.rooms_dark += 1
                if RoomState.FROZEN in states:
                    snapshot.rooms_frozen += 1
        
        # Calculate derived levels
        snapshot.temperature_level = snapshot.get_temperature_level(self.thresholds)
        snapshot.visibility_level = snapshot.get_visibility_level(self.thresholds)
        
        return snapshot
    
    def _is_significant_change(self, previous: Optional[EnvironmentalSnapshot], 
                               current: EnvironmentalSnapshot) -> bool:
        """Determine if environmental change is significant enough to log."""
        if not previous:
            return True
        
        # Power state change
        if previous.power_on != current.power_on:
            return True
        
        # Temperature level change
        if previous.temperature_level != current.temperature_level:
            return True
        
        # Visibility level change
        if previous.visibility_level != current.visibility_level:
            return True
        
        # Significant room state changes
        if abs(previous.rooms_dark - current.rooms_dark) >= 3:
            return True
        if abs(previous.rooms_frozen - current.rooms_frozen) >= 3:
            return True
        
        return False
    
    def _emit_state_change(self, snapshot: EnvironmentalSnapshot):
        """Emit coordinated environmental state change event."""
        # Build status summary
        status_parts = []
        
        if not snapshot.power_on:
            status_parts.append("POWER: OFF")
        
        if snapshot.temperature_level == TemperatureLevel.CRITICAL_COLD:
            status_parts.append(f"TEMP: CRITICAL ({snapshot.temperature:.1f}°C)")
        elif snapshot.temperature_level == TemperatureLevel.SEVERE_COLD:
            status_parts.append(f"TEMP: SEVERE ({snapshot.temperature:.1f}°C)")
        
        if snapshot.visibility_level == VisibilityLevel.WHITEOUT:
            status_parts.append("VIS: WHITEOUT")
        elif snapshot.visibility_level == VisibilityLevel.POOR:
            status_parts.append("VIS: POOR")
        
        if snapshot.rooms_frozen > 0:
            status_parts.append(f"FROZEN ROOMS: {snapshot.rooms_frozen}")
        
        if status_parts:
            status = " | ".join(status_parts)
            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                'text': f"ENVIRONMENTAL STATUS: {status}",
                'category': 'environmental',
                'snapshot': snapshot
            }))
    
    def get_current_modifiers(self, room_name: str, game_state) -> EnvironmentalEffects:
        """
        Get aggregated environmental modifiers for a specific room.
        
        Args:
            room_name: Name of the room
            game_state: Current game state
        
        Returns:
            EnvironmentalEffects with all applicable modifiers
        """
        # Always rebuild a fresh snapshot so power/weather toggles are reflected immediately
        self.current_snapshot = self._create_snapshot(game_state)
        
        # Check room-specific states
        in_dark_room = False
        in_frozen_room = False
        
        if hasattr(game_state, 'room_states'):
            from systems.room_state import RoomState
            states = game_state.room_states.get_states(room_name)
            in_dark_room = RoomState.DARK in states
            in_frozen_room = RoomState.FROZEN in states
        
        return EnvironmentalEffects.calculate_from_snapshot(
            self.current_snapshot,
            self.thresholds,
            in_dark_room=in_dark_room,
            in_frozen_room=in_frozen_room
        )
    
    def get_environmental_summary(self) -> str:
        """Get a human-readable summary of current environmental conditions."""
        if not self.current_snapshot:
            return "Environmental data unavailable"
        
        snapshot = self.current_snapshot
        
        parts = [
            f"Power: {'ON' if snapshot.power_on else 'OFF'}",
            f"Temp: {snapshot.temperature:.1f}°C ({snapshot.temperature_level.name})",
            f"Visibility: {snapshot.visibility_level.name}",
            f"Storm: {snapshot.storm_intensity}%"
        ]
        
        if snapshot.rooms_dark > 0:
            parts.append(f"Dark Rooms: {snapshot.rooms_dark}")
        if snapshot.rooms_frozen > 0:
            parts.append(f"Frozen Rooms: {snapshot.rooms_frozen}")
        
        return " | ".join(parts)
    
    def get_history_summary(self, last_n: int = 10) -> list[str]:
        """Get summary of recent environmental history."""
        recent = self.history[-last_n:] if len(self.history) > last_n else self.history
        summaries = []
        
        for i, snapshot in enumerate(recent):
            turn = len(self.history) - len(recent) + i + 1
            summary = (
                f"Turn {turn}: "
                f"Temp={snapshot.temperature:.1f}°C, "
                f"Power={'ON' if snapshot.power_on else 'OFF'}, "
                f"Vis={snapshot.visibility_level.name}"
            )
            summaries.append(summary)
        
        return summaries
