from core.resolution import Attribute
from core.event_system import event_bus, EventType, GameEvent

class PsychologySystem:
    MAX_STRESS = 10
    
    # Paranoia Thresholds
    CONCERNED_THRESHOLD = 33
    PANICKED_THRESHOLD = 66
    
    def __init__(self, crew=None):
        # Register for turn advance
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.subscribe(EventType.SEARCHLIGHT_HARVEST, self.on_searchlight_harvest)
        self.prev_paranoia_level = 0

    def on_searchlight_harvest(self, event: GameEvent):
        """
        Psychic Tremor Effect.
        Sensitive characters (High Logic/Empathy) feel uneasy when a harvest happens nearby.
        """
        location = event.payload.get("location")
        game_state = event.payload.get("game_state")
        
        if not game_state or not location:
            return
            
        harvest_room = game_state.station_map.get_room_name(*location)
        
        for member in game_state.crew:
            if not member.is_alive or member.is_infected:
                continue
                
            # Check sensitivity
            # High Logic = Notice patterns/anomalies (Subconscious)
            # High Empathy = Feel the loss of life
            logic = member.attributes.get(Attribute.LOGIC, 1)
            empathy = member.skills.get(Attribute.INFLUENCE, 0) # Use Influence/Empathy proxy if needed, or check skill list
            
            # Using raw skill check if available, else attributes
            is_sensitive = logic >= 4 or empathy >= 2
            
            if is_sensitive:
                # Check proximity
                member_room = game_state.station_map.get_room_name(*member.location)
                
                # If in same room or adjacent (simple check: same room for now)
                if member_room == harvest_room:
                    event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                        "text": f"{member.name} shudders suddenly. (Psychic Tremor)"
                    }))
                    self.add_stress(member, 2)
                    if member == game_state.player:
                        event_bus.emit(GameEvent(EventType.MESSAGE, {
                            "text": "You feel a sudden, hollow ache in your chest. Something is wrong.",
                            "crawl": True
                        }))

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def update(self, game_state):
        """
        Main update loop for psychology.
        - Checks for environmental stress.
        - Resolves panic triggers.
        """
        # 1. Environmental Stress (Cold)
        if game_state.temperature < 0:
            for m in game_state.crew:
                if m.is_alive:
                    # Increment stress (+1 per -10 degrees below zero, capped)
                    stress_gain = abs(game_state.temperature) // 20
                    self.add_stress(m, max(1, int(stress_gain)))

        # 2. Isolation Checks
        # Humans gain stress when alone (fear of being picked off)
        room_counts = {}
        for m in game_state.crew:
            if m.is_alive:
                room_name = game_state.station_map.get_room_name(*m.location)
                room_counts[room_name] = room_counts.get(room_name, 0) + 1
        
        for m in game_state.crew:
            if m.is_alive and not m.is_infected: # Things don't feel isolation stress
                room_name = game_state.station_map.get_room_name(*m.location)
                if room_counts[room_name] == 1:
                    self.add_stress(m, 1)

        # 3. Panic Resolution & Cascades
        for m in game_state.crew:
            if m.is_alive:
                is_panic, effect = self.resolve_panic(m, game_state)
                if is_panic:
                    game_state.journal.append(f"[TURN {game_state.turn}] {m.name} PANICKED: {effect}!")
                    if m == game_state.player:
                        print(f"\n*** SYSTEM WARNING: {m.name.upper()} IS PANICKING! Effect: {effect.upper()} ***")
                    
                    # Panic Cascade: Everyone in the same room gains stress
                    room_name = game_state.station_map.get_room_name(*m.location)
                    for witness in game_state.crew:
                        if witness != m and witness.is_alive:
                            witness_room = game_state.station_map.get_room_name(*witness.location)
                            if witness_room == room_name:
                                self.add_stress(witness, 2)
                                if witness == game_state.player:
                                    print(f"Seeing {m.name} lose it makes you uneasy. (+2 Stress)")

    def calculate_panic_threshold(self, character):
        """
        Panic Threshold = RESOLVE Attribute + 2.
        """
        resolve = character.attributes.get(Attribute.RESOLVE, 
                  character.attributes.get(Attribute.LOGIC, 2))
        return resolve + 2

    def add_stress(self, character, amount):
        character.stress += amount
        if character.stress > self.MAX_STRESS:
            character.stress = self.MAX_STRESS
        return character.stress

    def resolve_panic(self, character, game_state):
        """
        Polls for a panic reaction if stress is high enough.
        """
        threshold = self.calculate_panic_threshold(character)
        if character.stress <= threshold:
            return False, None
            
        panic_intensity = character.stress - threshold
        roll = game_state.rng.roll_d6()
        
        if roll <= panic_intensity:
            effects = [
                "drops their primary item in terror",
                "freezes, unable to take actions next turn",
                "screams, alerting anyone nearby",
                "flees to a random nearby room",
                "lash out at a random crew member"
            ]
            effect = game_state.rng.choose(effects)
            
            if "flees" in effect:
                dx = game_state.rng.choose([-2, -1, 1, 2])
                dy = game_state.rng.choose([-2, -1, 1, 2])
                character.move(dx, dy, game_state.station_map)
                 
            return True, effect
            
        return False, "is visibly shaking"

    def on_turn_advance(self, event: GameEvent):
        """Handle turn advancement via event bus."""
        game_state = event.payload.get("game_state")
        if game_state:
            old_level = self.prev_paranoia_level
            
            # Update paranoia level
            game_state.paranoia_level = min(100, game_state.paranoia_level + 1)
            
            # Process Local Environment Paranoia Modifiers
            player_room = game_state.station_map.get_room_name(*game_state.player.location)
            paranoia_mod = game_state.room_states.get_paranoia_modifier(player_room)
            if paranoia_mod > 0:
                game_state.paranoia_level = min(100, game_state.paranoia_level + paranoia_mod)
            
            new_level = game_state.paranoia_level
            
            # Threshold Check
            thresholds = [self.CONCERNED_THRESHOLD, self.PANICKED_THRESHOLD]
            for t in thresholds:
                if old_level < t and new_level >= t:
                    event_bus.emit(GameEvent(EventType.PARANOIA_THRESHOLD_CROSSED, {
                        "threshold": t,
                        "direction": "UP",
                        "new_value": new_level,
                        "old_value": old_level
                    }))
                elif old_level >= t and new_level < t:
                    event_bus.emit(GameEvent(EventType.PARANOIA_THRESHOLD_CROSSED, {
                        "threshold": t,
                        "direction": "DOWN",
                        "new_value": new_level,
                        "old_value": old_level
                    }))
            
            self.prev_paranoia_level = new_level
                
            self.update(game_state)
