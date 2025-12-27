from enum import Enum, auto
from src.core.event_system import event_bus, EventType, GameEvent

class RoomState(Enum):
    DARK = auto()       # No light - increased communion chance
    FROZEN = auto()     # Below freezing - health drain, resolve checks
    BARRICADED = auto() # Blocked entry - must break barricade
    BLOODY = auto()     # Evidence of violence - paranoia increase


class RoomStateManager:
    """
    Manages environmental states for each room. Reacts to GameEvents.
    """
    
    def __init__(self, room_names):
        # room_name -> set of RoomState
        self.room_states = {name: set() for name in room_names}
        self._set_initial_states()
        
        # Subscribe to events
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.subscribe(EventType.POWER_FAILURE, self.on_power_failure)
    
    def _set_initial_states(self):
        if "Kennel" in self.room_states:
            self.room_states["Kennel"].add(RoomState.FROZEN)
    
    def on_turn_advance(self, event: GameEvent):
        """Subscriber for TURN_ADVANCE event."""
        game_state = event.payload.get("game_state")
        if game_state:
            self.tick(game_state)

    def on_power_failure(self, event: GameEvent):
        """React immediately to power failure."""
        for room_name in self.room_states:
            if room_name != "Generator":
                self.add_state(room_name, RoomState.DARK)

    def add_state(self, room_name, state):
        if room_name in self.room_states:
            self.room_states[room_name].add(state)
            return True
        return False
    
    def remove_state(self, room_name, state):
        if room_name in self.room_states:
            self.room_states[room_name].discard(state)
            return True
        return False
    
    def has_state(self, room_name, state):
        if room_name in self.room_states:
            return state in self.room_states[room_name]
        return False
    
    def get_states(self, room_name):
        return self.room_states.get(room_name, set())
    
    def tick(self, game_state):
        """Update room states each turn based on game conditions."""
        # If power is off, ensure darkness persists
        if not game_state.power_on:
            for room_name in self.room_states:
                if room_name != "Generator":
                    self.add_state(room_name, RoomState.DARK)
        else:
            # Power is on - remove darkness unless barricaded
            for room_name in self.room_states:
                if not self.has_state(room_name, RoomState.BARRICADED):
                    self.remove_state(room_name, RoomState.DARK)
        
        # Freezing logic
        if not game_state.power_on and game_state.temperature < -50:
            for room_name in self.room_states:
                if room_name != "Generator":
                    self.add_state(room_name, RoomState.FROZEN)
    
    def get_room_description_modifiers(self, room_name):
        states = self.get_states(room_name)
        if not states: return ""
        descriptions = []
        if RoomState.DARK in states: descriptions.append("The room is pitch black.")
        if RoomState.FROZEN in states: descriptions.append("Ice crystals coat every surface.")
        if RoomState.BARRICADED in states: descriptions.append("The entrance is blocked.")
        if RoomState.BLOODY in states: descriptions.append("Dark stains mar the floor.")
        return " ".join(descriptions)
    
    def get_status_icons(self, room_name):
        states = self.get_states(room_name)
        icons = []
        if RoomState.DARK in states: icons.append("[DARK]")
        if RoomState.FROZEN in states: icons.append("[COLD]")
        if RoomState.BARRICADED in icons: icons.append("[BARR]")
        if RoomState.BLOODY in states: icons.append("[BLOOD]")
        return " ".join(icons)
    
    def mark_bloody(self, room_name):
        self.add_state(room_name, RoomState.BLOODY)
        return f"Blood spatters across {room_name}."
    
    def barricade_room(self, room_name):
        self.add_state(room_name, RoomState.BARRICADED)
        self.add_state(room_name, RoomState.DARK)
    
    def break_barricade(self, room_name):
        self.remove_state(room_name, RoomState.BARRICADED)
    
    def get_communion_modifier(self, room_name):
        return 0.4 if self.has_state(room_name, RoomState.DARK) else 0.0
    
    def get_paranoia_modifier(self, room_name):
        modifier = 0
        if self.has_state(room_name, RoomState.BLOODY): modifier += 5
        if self.has_state(room_name, RoomState.DARK): modifier += 2
        return modifier
