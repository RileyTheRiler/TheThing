from enum import Enum, auto
from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, Skill, ResolutionModifiers


class RoomState(Enum):
    DARK = auto()       # No light - increased communion chance
    FROZEN = auto()     # Below freezing - health drain, resolve checks
    BARRICADED = auto() # Blocked entry - must break barricade
    BLOODY = auto()     # Evidence of violence - paranoia increase


class RoomStateManager:
    """
    Manages environmental states for each room. Reacts to GameEvents.
    """

    # Barricade strength levels
    BARRICADE_MAX_STRENGTH = 3  # Requires 3 successful break attempts

    def __init__(self, room_names):
        # room_name -> set of RoomState
        self.room_states = {name: set() for name in room_names}
        # room_name -> barricade strength (0 = broken)
        self.barricade_strength = {}
        self._set_initial_states()

        # Subscribe to events
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.subscribe(EventType.POWER_FAILURE, self.on_power_failure)
        event_bus.subscribe(EventType.TEMPERATURE_THRESHOLD_CROSSED, self.on_temperature_threshold)
        event_bus.subscribe(EventType.ENVIRONMENTAL_STATE_CHANGE, self.on_environmental_change)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.unsubscribe(EventType.POWER_FAILURE, self.on_power_failure)
        event_bus.unsubscribe(EventType.TEMPERATURE_THRESHOLD_CROSSED, self.on_temperature_threshold)
        event_bus.unsubscribe(EventType.ENVIRONMENTAL_STATE_CHANGE, self.on_environmental_change)
    
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
    
    def on_temperature_threshold(self, event: GameEvent):
        """React to temperature threshold crossings."""
        direction = event.payload.get('direction')
        
        if direction == 'falling':
            # Temperature dropped below freezing threshold - add FROZEN state
            for room_name in self.room_states:
                if room_name != "Generator":
                    self.add_state(room_name, RoomState.FROZEN)
        elif direction == 'rising':
            # Temperature rose above freezing threshold - remove FROZEN state
            for room_name in self.room_states:
                self.remove_state(room_name, RoomState.FROZEN)
    
    def on_environmental_change(self, event: GameEvent):
        """React to environmental state changes (e.g., power restoration)."""
        change_type = event.payload.get('change_type')
        power_on = event.payload.get('power_on')
        
        if change_type == 'power_restored' and power_on:
            # Remove darkness from all non-barricaded rooms
            for room_name in self.room_states:
                if not self.has_state(room_name, RoomState.BARRICADED):
                    self.remove_state(room_name, RoomState.DARK)

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
        # Emit event instead of returning string (Tier 2.6)
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            'text': f"Blood spatters across {room_name}."
        }))
        return f"Blood spatters across {room_name}."

    def get_paranoia_modifier(self, room_name):
        """Return paranoia modifier based on room states (e.g., BLOODY)."""
        states = self.get_states(room_name)
        if RoomState.BLOODY in states:
            return 2
        return 0

    def barricade_room(self, room_name, actor="You"):
        """Create or reinforce a barricade on a room."""
        self.add_state(room_name, RoomState.BARRICADED)
        self.add_state(room_name, RoomState.DARK)
        # Set barricade strength if new, or reinforce if already barricaded
        current = self.barricade_strength.get(room_name, 0)
        self.barricade_strength[room_name] = min(
            current + 1,
            self.BARRICADE_MAX_STRENGTH
        )
        action = 'reinforced' if current > 0 else 'built'
        strength = self.barricade_strength[room_name]

        # Emit event (Tier 2.6 Reporting Pattern)
        event_bus.emit(GameEvent(EventType.BARRICADE_ACTION, {
            'action': action,
            'room': room_name,
            'strength': strength,
            'actor': actor
        }))

        return f"Barricade {'reinforced' if current > 0 else 'erected'}. Strength: {strength}/{self.BARRICADE_MAX_STRENGTH}"

    def get_barricade_strength(self, room_name):
        """Get the current barricade strength for a room."""
        if not self.has_state(room_name, RoomState.BARRICADED):
            return 0
        return self.barricade_strength.get(room_name, 0)

    def attempt_break_barricade(self, room_name, breaker, rng, is_thing=False):
        """Attempt to break through a barricade.

        Args:
            room_name: The room with the barricade
            breaker: The creature/person trying to break through
            rng: Random number generator
            is_thing: If True, the breaker is a revealed Thing (bonus strength)

        Returns:
            (success, message, remaining_strength)
        """
        if not self.has_state(room_name, RoomState.BARRICADED):
            return True, "There is no barricade here.", 0

        current_strength = self.barricade_strength.get(room_name, 1)
        breaker_name = getattr(breaker, 'name', 'Something')

        # Roll PROWESS + MELEE to break
        prowess = breaker.attributes.get(Attribute.PROWESS, 1)
        melee = breaker.skills.get(Skill.MELEE, 0)
        pool = prowess + melee

        # Things get bonus dice (alien strength)
        if is_thing:
            pool += 3

        result = rng.calculate_success(pool)

        if result['success']:
            # Damage the barricade
            damage = 1 + result['success_count']  # More successes = more damage
            self.barricade_strength[room_name] = max(0, current_strength - damage)

            if self.barricade_strength[room_name] <= 0:
                # Barricade destroyed
                self.remove_state(room_name, RoomState.BARRICADED)
                del self.barricade_strength[room_name]

                # Emit event (Tier 2.6)
                event_bus.emit(GameEvent(EventType.BARRICADE_ACTION, {
                    'action': 'broken',
                    'room': room_name,
                    'strength': 0,
                    'actor': breaker_name
                }))

                return True, "*** The barricade SHATTERS! ***", 0
            else:
                remaining = self.barricade_strength[room_name]

                # Emit event (Tier 2.6)
                event_bus.emit(GameEvent(EventType.BARRICADE_ACTION, {
                    'action': 'damaged',
                    'room': room_name,
                    'strength': remaining,
                    'actor': breaker_name
                }))

                return False, f"The barricade cracks and splinters! (Strength: {remaining}/{self.BARRICADE_MAX_STRENGTH})", remaining
        else:
            return False, "You slam against the barricade but it holds firm.", current_strength

    def break_barricade(self, room_name):
        """Instantly destroy a barricade (for scripted events)."""
        self.remove_state(room_name, RoomState.BARRICADED)
        if room_name in self.barricade_strength:
            del self.barricade_strength[room_name]

    def is_entry_blocked(self, room_name):
        """Check if entry to a room is blocked by a barricade."""
        return self.has_state(room_name, RoomState.BARRICADED)
    
    def get_communion_modifier(self, room_name):
        return 0.4 if self.has_state(room_name, RoomState.DARK) else 0.0
    
    def get_paranoia_modifier(self, room_name):
        modifier = 0
        if self.has_state(room_name, RoomState.BLOODY): modifier += 5
        if self.has_state(room_name, RoomState.DARK): modifier += 2
        return modifier

    def get_resolution_modifiers(self, room_name):
        """Return modifiers that affect ResolutionSystem calculations."""
        modifiers = ResolutionModifiers()
        states = self.get_states(room_name)

        if RoomState.DARK in states:
            modifiers.attack_pool -= 1
            modifiers.observation_pool -= 1
            modifiers.stealth_detection -= 0.15  # Harder to spot someone in the dark
            # HEAD had more granular modifiers (Firearms -2, Melee -1, Empathy -1)
            # These are roughly covered by attack_pool -= 1.

        if RoomState.FROZEN in states:
            modifiers.attack_pool -= 1  # Numb hands, sluggish attacks
            modifiers.observation_pool -= 1  # Frosted visors, breath mist

        return modifiers
