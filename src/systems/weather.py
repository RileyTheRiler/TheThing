from enum import Enum
from core.event_system import event_bus, EventType, GameEvent
from systems.architect import RandomnessEngine

class WindDirection(Enum):
    NORTH = "north"
    NORTHEAST = "northeast"
    EAST = "east"
    SOUTHEAST = "southeast"
    SOUTH = "south"
    SOUTHWEST = "southwest"
    WEST = "west"
    NORTHWEST = "northwest"

class WeatherSystem:
    """
    Manages dynamic weather conditions affecting visibility and temperature.
    Decoupled via EventBus.
    """
    
    def __init__(self):
        # Storm intensity: 0 = calm, 100 = whiteout blizzard
        self.storm_intensity = 20  
        self.wind_direction = WindDirection.NORTHWEST
        
        # Modifiers calculated from conditions
        self.visibility_modifier = 0.0  
        self.temperature_modifier = 0   
        
        # Event tracking
        self.northeasterly_active = False
        self.northeasterly_turns_remaining = 0
        
        # Temperature threshold tracking
        self.FREEZING_THRESHOLD = -50
        self.below_freezing_threshold = False
        
        self._recalculate_modifiers()
        
        # Subscribe to turn advances
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
    
    def _recalculate_modifiers(self):
        """Update visibility and temperature modifiers based on current conditions."""
        if self.storm_intensity < 30:
            self.visibility_modifier = 0.0
        elif self.storm_intensity < 60:
            self.visibility_modifier = -0.3
        elif self.storm_intensity < 80:
            self.visibility_modifier = -0.6
        else:
            self.visibility_modifier = -1.0  # Whiteout
        
        # Wind chill: -1C per 10 intensity, worse from northeast
        base_chill = -(self.storm_intensity // 10)
        if self.wind_direction == WindDirection.NORTHEAST:
            base_chill -= 5  # The Nasty Northeasterly
        self.temperature_modifier = base_chill
    
    def on_turn_advance(self, event: GameEvent):
        """Subscriber for TURN_ADVANCE event."""
        rng = event.payload.get("rng")
        if not rng:
            return
            
        events = self.tick(rng)
        game_state = event.payload.get("game_state")
        turn_inventory = event.payload.get("turn_inventory", {})
        if isinstance(turn_inventory, dict):
            turn_inventory["weather"] = turn_inventory.get("weather", 0) + 1

        if not rng or not game_state:
            return
            
        messages = self.tick(rng, game_state)
        
        # Emit messages to the reporting system
        for msg in messages:
            if "ALERT" in msg or "WARNING" in msg:
                event_bus.emit(GameEvent(EventType.WARNING, {'text': msg}))
            else:
                event_bus.emit(GameEvent(EventType.MESSAGE, {'text': msg}))
    
    def tick(self, rng: RandomnessEngine, game_state=None):
        """
        Advance weather by one turn. Uses provided RNG for determinism.
        """
        messages = []
        
        # Handle active Northeasterly event
        if self.northeasterly_active:
            self.northeasterly_turns_remaining -= 1
            if self.northeasterly_turns_remaining <= 0:
                self.northeasterly_active = False
                self.storm_intensity = max(20, self.storm_intensity - 40)
                self.wind_direction = rng.choose(list(WindDirection))
                messages.append("The Northeasterly subsides. Visibility improves.")
        else:
            # Natural weather variance
            change = rng.roll_d6() * 2 - 7 # -5 to +5 range approx
            self.storm_intensity = max(0, min(100, self.storm_intensity + change))
            
            # Random wind shifts (10% chance)
            if rng.random_float() < 0.1:
                self.wind_direction = rng.choose(list(WindDirection))
        
        # Random trigger check
        if not self.northeasterly_active and rng.random_float() < 0.02:
            msg = self.trigger_northeasterly()
            messages.append(msg)
            
        self._recalculate_modifiers()
        
        # Check temperature threshold crossing
        if game_state:
            self._check_temperature_threshold(game_state)
        
        return messages
    
    def trigger_northeasterly(self, duration=5):
        """Trigger the 'Nasty Northeasterly' event."""
        self.northeasterly_active = True
        self.northeasterly_turns_remaining = duration
        self.wind_direction = WindDirection.NORTHEAST
        self.storm_intensity = min(100, self.storm_intensity + 50)
        self._recalculate_modifiers()
        
        return "WEATHER ALERT: NASTY NORTHEASTERLY INCOMING"
    
    def _check_temperature_threshold(self, game_state):
        """Check if temperature has crossed the freezing threshold and emit event."""
        current_temp = getattr(game_state, 'temperature', 0)
        effective_temp = self.get_effective_temperature(current_temp)
        
        currently_below = effective_temp < self.FREEZING_THRESHOLD
        
        # Check if we've crossed the threshold
        if currently_below and not self.below_freezing_threshold:
            # Temperature just dropped below threshold
            self.below_freezing_threshold = True
            event_bus.emit(GameEvent(EventType.TEMPERATURE_THRESHOLD_CROSSED, {
                'temperature': effective_temp,
                'crossed_threshold': self.FREEZING_THRESHOLD,
                'direction': 'falling'
            }))
        elif not currently_below and self.below_freezing_threshold:
            # Temperature just rose above threshold
            self.below_freezing_threshold = False
            event_bus.emit(GameEvent(EventType.TEMPERATURE_THRESHOLD_CROSSED, {
                'temperature': effective_temp,
                'crossed_threshold': self.FREEZING_THRESHOLD,
                'direction': 'rising'
            }))
    
    def get_visibility(self):
        return max(0.0, 1.0 + self.visibility_modifier)
    
    def get_effective_temperature(self, base_temp):
        return base_temp + self.temperature_modifier
    
    def get_visibility_description(self):
        vis = self.get_visibility()
        if vis >= 0.9: return "Clear"
        elif vis >= 0.6: return "Reduced"
        elif vis >= 0.3: return "Poor"
        else: return "WHITEOUT"
    
    def get_status(self):
        vis_desc = self.get_visibility_description()
        wind = self.wind_direction.value.upper()
        intensity = self.storm_intensity
        status = f"WIND: {wind} {intensity}% | VIS: {vis_desc}"
        if self.northeasterly_active:
            status += " [STORM!]"
        return status
