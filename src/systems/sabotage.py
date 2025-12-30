from enum import Enum
from core.event_system import event_bus, EventType, GameEvent

class SabotageEvent(Enum):
    POWER_OUTAGE = "power_outage"
    RADIO_SMASHING = "radio_smashing"
    CHOPPER_DESTRUCTION = "chopper_destruction"
    BLOOD_SABOTAGE = "blood_sabotage"


class SabotageManager:
    """
    Manages sabotage events. Reacts to TURN_ADVANCE and emits signals.
    """
    
    def __init__(self, difficulty_settings=None):
        # Operational status of critical systems
        self.radio_operational = True
        self.helicopter_operational = True
        
        # Event tracking
        self.events_triggered = {
            SabotageEvent.POWER_OUTAGE: False,
            SabotageEvent.RADIO_SMASHING: False,
            SabotageEvent.CHOPPER_DESTRUCTION: False,
            SabotageEvent.BLOOD_SABOTAGE: False,
        }
        
        # Cooldowns (turns until event can trigger again)
        self.cooldowns = {
            SabotageEvent.POWER_OUTAGE: 0,
            SabotageEvent.RADIO_SMASHING: 0,
            SabotageEvent.CHOPPER_DESTRUCTION: 0,
            SabotageEvent.BLOOD_SABOTAGE: 0,
        }
        
        # Power can be restored; tracks if currently off due to sabotage
        self.power_sabotaged = False
        
        # Subscribe to turn advances
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
    
    def on_turn_advance(self, event: GameEvent):
        """Subscriber for TURN_ADVANCE event."""
        turn_inventory = event.payload.get("turn_inventory", {})
        if isinstance(turn_inventory, dict):
            turn_inventory["sabotage"] = turn_inventory.get("sabotage", 0) + 1
        self.tick()

    def can_trigger(self, event):
        """Check if an event can be triggered (not on cooldown)."""
        return self.cooldowns.get(event, 0) <= 0
    
    def tick(self):
        """Reduce cooldowns each turn."""
        for event in self.cooldowns:
            if self.cooldowns[event] > 0:
                self.cooldowns[event] -= 1
    
    def trigger_power_outage(self, game_state, duration=5):
        """
        Cuts power to the station. Emits POWER_FAILURE event.
        """
        if not self.can_trigger(SabotageEvent.POWER_OUTAGE):
            return None
        
        game_state.power_on = False
        self.power_sabotaged = True
        self.events_triggered[SabotageEvent.POWER_OUTAGE] = True
        self.cooldowns[SabotageEvent.POWER_OUTAGE] = duration + 10  
        
        # Emit event for other systems to react
        event_bus.emit(GameEvent(EventType.POWER_FAILURE, {"duration": duration}))
        event_bus.emit(GameEvent(EventType.ENVIRONMENTAL_STATE_CHANGE, {
            "change_type": "power_loss",
            "power_on": False
        }))
        
        return "SABOTAGE: POWER OUTAGE. The lights flicker and die."
    
    def restore_power(self, game_state):
        if self.power_sabotaged:
            game_state.power_on = True
            self.power_sabotaged = False
            
            # Emit environmental state change event
            event_bus.emit(GameEvent(EventType.ENVIRONMENTAL_STATE_CHANGE, {
                "change_type": "power_restored",
                "power_on": True
            }))
            
            return "Power restored."
        return None
    
    def trigger_radio_smashing(self, game_state, perpetrator=None):
        if not self.radio_operational:
            return None 
        
        self.radio_operational = False
        if hasattr(game_state, "radio_operational"):
            game_state.radio_operational = False
        self.events_triggered[SabotageEvent.RADIO_SMASHING] = True
        return "SABOTAGE: RADIO DESTROYED"
    
    def trigger_chopper_destruction(self, game_state, perpetrator=None):
        if not self.helicopter_operational:
            return None 
        
        self.helicopter_operational = False
        if hasattr(game_state, "helicopter_status"):
            game_state.helicopter_status = "BROKEN"
        if hasattr(game_state, "helicopter_operational"):
            game_state.helicopter_operational = False
        self.events_triggered[SabotageEvent.CHOPPER_DESTRUCTION] = True
        return "SABOTAGE: HELICOPTER DESTROYED"
    
    def trigger_blood_sabotage(self, game_state):
        if self.events_triggered[SabotageEvent.BLOOD_SABOTAGE]:
            return None
            
        self.events_triggered[SabotageEvent.BLOOD_SABOTAGE] = True
        game_state.blood_bank_destroyed = True
        
        # Mark Infirmary as BLOODY
        game_state.room_states.mark_bloody("Infirmary")
        
        return (
            "*** SABOTAGE: BLOOD BANK DESTROYED ***\n"
            "The blood containers in the Infirmary have been smashed.\n"
            "Serum testing is now impossible."
        )
    
    def get_status(self):
        radio = "OK" if self.radio_operational else "DESTROYED"
        chopper = "OK" if self.helicopter_operational else "DESTROYED"
        return f"RADIO: {radio} | HELICOPTER: {chopper}"
    
    def can_call_for_help(self):
        return self.radio_operational
    
    def can_escape_by_air(self):
        return self.helicopter_operational

    # Backwards-compatible alias for legacy references
    @property
    def chopper_operational(self):
        return self.helicopter_operational

    @chopper_operational.setter
    def chopper_operational(self, value):
        self.helicopter_operational = value
