"""
Environmental Contract - Formal specification for power/temperature/visibility interactions.

This module defines how environmental systems (Weather, Sabotage, RoomState) interact
and provides a unified interface for querying environmental effects on game mechanics.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum, auto


class TemperatureLevel(Enum):
    """Temperature severity levels."""
    NORMAL = auto()       # Above -30°C
    SEVERE_COLD = auto()  # -30°C to -50°C
    CRITICAL_COLD = auto() # Below -50°C


class VisibilityLevel(Enum):
    """Visibility severity levels."""
    CLEAR = auto()        # > 90%
    REDUCED = auto()      # 60-90%
    POOR = auto()         # 30-60%
    WHITEOUT = auto()     # < 30%


@dataclass
class EnvironmentalThresholds:
    """Configurable threshold values for environmental state transitions."""
    
    # Temperature thresholds (Celsius)
    severe_cold_threshold: float = -30.0
    critical_cold_threshold: float = -50.0
    
    # Visibility thresholds (0.0 to 1.0)
    reduced_visibility_threshold: float = 0.9
    poor_visibility_threshold: float = 0.6
    whiteout_threshold: float = 0.3
    
    # Storm intensity thresholds (0 to 100)
    moderate_storm_threshold: int = 30
    severe_storm_threshold: int = 60
    extreme_storm_threshold: int = 80


@dataclass
class EnvironmentalSnapshot:
    """Captures current environmental state at a point in time."""
    
    # Power state
    power_on: bool = True
    
    # Temperature
    temperature: float = 10.0
    temperature_level: TemperatureLevel = TemperatureLevel.NORMAL
    
    # Weather
    storm_intensity: int = 20
    visibility: float = 1.0
    visibility_level: VisibilityLevel = VisibilityLevel.CLEAR
    wind_chill: int = 0
    
    # Derived states
    rooms_dark: int = 0
    rooms_frozen: int = 0
    
    def get_temperature_level(self, thresholds: EnvironmentalThresholds) -> TemperatureLevel:
        """Calculate temperature severity level."""
        if self.temperature < thresholds.critical_cold_threshold:
            return TemperatureLevel.CRITICAL_COLD
        elif self.temperature < thresholds.severe_cold_threshold:
            return TemperatureLevel.SEVERE_COLD
        else:
            return TemperatureLevel.NORMAL
    
    def get_visibility_level(self, thresholds: EnvironmentalThresholds) -> VisibilityLevel:
        """Calculate visibility severity level."""
        if self.visibility >= thresholds.reduced_visibility_threshold:
            return VisibilityLevel.CLEAR
        elif self.visibility >= thresholds.poor_visibility_threshold:
            return VisibilityLevel.REDUCED
        elif self.visibility >= thresholds.whiteout_threshold:
            return VisibilityLevel.POOR
        else:
            return VisibilityLevel.WHITEOUT
    
    def should_emit_warning(self, previous: Optional['EnvironmentalSnapshot'], 
                           thresholds: EnvironmentalThresholds) -> Dict[str, str]:
        """
        Determine if warnings should be emitted based on threshold crossings.
        
        Returns:
            Dict of warning_type -> warning_message
        """
        warnings = {}
        
        # Temperature warnings
        current_temp_level = self.get_temperature_level(thresholds)
        if previous:
            prev_temp_level = previous.get_temperature_level(thresholds)
            if current_temp_level != prev_temp_level:
                if current_temp_level == TemperatureLevel.SEVERE_COLD:
                    warnings['temperature'] = f"WARNING: Temperature dropped to {self.temperature:.1f}°C - Severe cold conditions"
                elif current_temp_level == TemperatureLevel.CRITICAL_COLD:
                    warnings['temperature'] = f"CRITICAL: Temperature at {self.temperature:.1f}°C - Freezing conditions imminent"
        
        # Visibility warnings
        current_vis_level = self.get_visibility_level(thresholds)
        if previous:
            prev_vis_level = previous.get_visibility_level(thresholds)
            if current_vis_level != prev_vis_level:
                if current_vis_level == VisibilityLevel.POOR:
                    warnings['visibility'] = "WARNING: Visibility severely reduced - Navigation hazardous"
                elif current_vis_level == VisibilityLevel.WHITEOUT:
                    warnings['visibility'] = "CRITICAL: WHITEOUT CONDITIONS - Zero visibility"
        
        # Power failure warnings
        if previous and previous.power_on and not self.power_on:
            warnings['power'] = "ALERT: POWER FAILURE - All systems going dark"
        
        return warnings


@dataclass
class EnvironmentalEffects:
    """Defines the cumulative impact of environmental conditions on game mechanics."""
    
    # Combat modifiers
    attack_pool_modifier: int = 0
    defense_pool_modifier: int = 0
    
    # Perception modifiers
    observation_pool_modifier: int = 0
    stealth_detection_modifier: float = 0.0
    
    # Skill modifiers
    repair_modifier: int = 0
    mechanics_modifier: int = 0
    
    # Social modifiers
    paranoia_modifier: int = 0
    communion_chance_modifier: float = 0.0
    
    # Movement
    movement_restricted: bool = False
    
    def apply_power_failure(self):
        """Apply effects of power failure (darkness)."""
        self.attack_pool_modifier -= 1
        self.observation_pool_modifier -= 1
        self.stealth_detection_modifier -= 0.15
        self.paranoia_modifier += 2
        self.communion_chance_modifier += 0.4
    
    def apply_severe_cold(self):
        """Apply effects of severe cold (-30°C to -50°C)."""
        self.repair_modifier -= 1
        self.mechanics_modifier -= 1
    
    def apply_critical_cold(self):
        """Apply effects of critical cold (< -50°C)."""
        self.attack_pool_modifier -= 1
        self.defense_pool_modifier -= 1
        self.observation_pool_modifier -= 1
        self.repair_modifier -= 2
        self.mechanics_modifier -= 2
        self.movement_restricted = True
    
    def apply_poor_visibility(self):
        """Apply effects of poor visibility."""
        self.observation_pool_modifier -= 1
        self.attack_pool_modifier -= 1
    
    def apply_whiteout(self):
        """Apply effects of whiteout conditions."""
        self.observation_pool_modifier -= 2
        self.attack_pool_modifier -= 2
        self.movement_restricted = True
    
    @classmethod
    def calculate_from_snapshot(cls, snapshot: EnvironmentalSnapshot, 
                               thresholds: EnvironmentalThresholds,
                               in_dark_room: bool = False,
                               in_frozen_room: bool = False) -> 'EnvironmentalEffects':
        """
        Calculate cumulative environmental effects from a snapshot.
        
        Args:
            snapshot: Current environmental state
            thresholds: Threshold configuration
            in_dark_room: Whether the location is dark (power off or barricaded)
            in_frozen_room: Whether the location is frozen
        
        Returns:
            EnvironmentalEffects with all applicable modifiers
        """
        effects = cls()
        
        # Apply power/darkness effects
        if not snapshot.power_on or in_dark_room:
            effects.apply_power_failure()
        
        # Apply temperature effects
        temp_level = snapshot.get_temperature_level(thresholds)
        if temp_level == TemperatureLevel.SEVERE_COLD or in_frozen_room:
            effects.apply_severe_cold()
        if temp_level == TemperatureLevel.CRITICAL_COLD:
            effects.apply_critical_cold()
        
        # Apply visibility effects
        vis_level = snapshot.get_visibility_level(thresholds)
        if vis_level == VisibilityLevel.POOR:
            effects.apply_poor_visibility()
        elif vis_level == VisibilityLevel.WHITEOUT:
            effects.apply_whiteout()
        
        return effects
    
    def get_summary(self) -> str:
        """Generate a human-readable summary of environmental effects."""
        parts = []
        
        if self.attack_pool_modifier != 0:
            parts.append(f"Combat: {self.attack_pool_modifier:+d}")
        if self.observation_pool_modifier != 0:
            parts.append(f"Observation: {self.observation_pool_modifier:+d}")
        if self.stealth_detection_modifier != 0.0:
            parts.append(f"Detection: {self.stealth_detection_modifier:+.0%}")
        if self.repair_modifier != 0:
            parts.append(f"Repair: {self.repair_modifier:+d}")
        if self.paranoia_modifier != 0:
            parts.append(f"Paranoia: {self.paranoia_modifier:+d}")
        if self.communion_chance_modifier != 0.0:
            parts.append(f"Communion: {self.communion_chance_modifier:+.0%}")
        if self.movement_restricted:
            parts.append("Movement: RESTRICTED")
        
        return " | ".join(parts) if parts else "No environmental effects"
