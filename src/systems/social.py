from core.event_system import event_bus, EventType, GameEvent

__all__ = ['TrustMatrix', 'LynchMobSystem', 'DialogueManager']

class TrustMatrix:
    def __init__(self, crew):
        # Dictionary of dictionaries: self.matrix[observer][subject] = trust_value
        # Default trust is 50
        self.matrix = {m.name: {other.name: 50 for other in crew} for m in crew}
        self._set_initial_biases()
        
        # Subscribe to events
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def _set_initial_biases(self):
        # Hierarchical Distrust
        # Check if keys exist before setting to avoid key errors if partial crew
        if "Childs" in self.matrix and "Garry" in self.matrix["Childs"]:
            self.matrix["Childs"]["Garry"] = 30
        if "Palmer" in self.matrix and "Garry" in self.matrix["Palmer"]:
            self.matrix["Palmer"]["Garry"] = 25
        
        # Scientific Bond: Blair, Copper, Fuchs
        scientists = ["Blair", "Copper", "Fuchs"]
        for s1 in scientists:
            for s2 in scientists:
                if s1 != s2 and s1 in self.matrix and s2 in self.matrix:
                    self.matrix[s1][s2] = 75

        # The Loner Penalty: MacReady and Clark
        loners = ["MacReady", "Clark"]
        for target in loners:
            for member in self.matrix:
                if target in self.matrix[member]:
                    self.matrix[member][target] -= 10

    def update_trust(self, observer_name, subject_name, amount):
        """Adjusts trust based on witnessed events."""
        if observer_name in self.matrix and subject_name in self.matrix[observer_name]:
            current = self.matrix[observer_name][subject_name]
            self.matrix[observer_name][subject_name] = max(0, min(100, current + amount))

    def get_trust(self, observer_name, subject_name):
        """Returns the trust score observer has for subject."""
        if observer_name in self.matrix and subject_name in self.matrix[observer_name]:
            return self.matrix[observer_name][subject_name]
        return 50 # Default neutral

    def get_average_trust(self, subject_name):
        """The 'Global Trust' used to determine if a character is tied up."""
        total = 0
        count = 0
        for observer_name in self.matrix:
            if observer_name != subject_name:
                if subject_name in self.matrix[observer_name]:
                    total += self.matrix[observer_name][subject_name]
                    count += 1
        return total / count if count > 0 else 50.0

    def check_for_lynch_mob(self, crew, game_state=None):
        """If global trust in a human falls below 20%, they are targeted."""
        for member in crew:
            if member.is_alive:
                avg = self.get_average_trust(member.name)
                # Lynch threshold
                if avg < 20:
                    # Emit LYNCH_MOB_TRIGGER event
                    if game_state:
                        event_bus.emit(GameEvent(EventType.LYNCH_MOB_TRIGGER, {
                            "target": member.name,
                            "location": member.location,
                            "average_trust": avg
                        }))
                    return member 
        return None

    def on_turn_advance(self, event: GameEvent):
        """
        Check for lynch mob conditions each turn and apply paranoia decay.
        """
        game_state = event.payload.get("game_state")
        if game_state:
            # Global Trust Decay based on Paranoia
            # For every 20 points of paranoia, lose 1 trust with everyone per turn
            decay_amount = int(game_state.paranoia_level / 20)
            if decay_amount > 0:
                for observer in self.matrix:
                    for subject in self.matrix[observer]:
                        if observer != subject:
                            self.matrix[observer][subject] = max(0, self.matrix[observer][subject] - decay_amount)

            targeted = self.check_for_lynch_mob(game_state.crew, game_state)
            if targeted and targeted.is_alive:
                # Event is emitted by check_for_lynch_mob, mechanics handled by listeners
                pass


def on_evidence_tagged(event: GameEvent):
    game_state = event.payload.get("game_state")
    target = event.payload.get("target")
    if game_state and target:
        # If someone is tagged as suspicious, everyone's trust in them drops
        for member in game_state.crew:
            if hasattr(game_state, 'trust_system'):
                game_state.trust_system.update_trust(member.name, target, -10)
        print(f"[SOCIAL] Global suspicion rises for {target}.")

# Register listeners
event_bus.subscribe(EventType.EVIDENCE_TAGGED, on_evidence_tagged)


class LynchMobSystem:
    def __init__(self, trust_system):
        self.trust_system = trust_system
        self.active_mob = False
        self.target = None
        
        event_bus.subscribe(EventType.LYNCH_MOB_TRIGGER, self.on_lynch_mob_trigger)

    def cleanup(self):
        event_bus.unsubscribe(EventType.LYNCH_MOB_TRIGGER, self.on_lynch_mob_trigger)

    def on_lynch_mob_trigger(self, event: GameEvent):
        target_name = event.payload.get("target")
        # We need the actual object, but we only have name/loc in payload usually.
        # But TrustMatrix emits target object? No, payload has "target": member.name.
        # We store the name or need game state to resolve.
        # Let's check TrustMatrix trigger: "target": member.name
        self.active_mob = True
        # We can't easily resolve the object here without game_state in this class, but we can store the name.
        # We'll just store the name for now.
        # Wait, check_thresholds used self.target (object).
        # Let's rely on event payload updates.
        print(f"\n*** EMERGENCY: THE CREW HAS TURNED ON {target_name.upper()}! ***")
        print(f"They are dragging {target_name} to the Rec Room to be tied up.")
    
    def check_thresholds(self, crew):
        # Deprecated manual check, handled by TrustMatrix event
        pass

    def form_mob(self, target):
        # Logic moved to on_lynch_mob_trigger mostly, but this might be called by Accuse command
        self.active_mob = True
        self.target = target # Object
        event_bus.emit(GameEvent(EventType.LYNCH_MOB_TRIGGER, {
            "target": target.name,
            "location": target.location
        }))

    def disband_mob(self):
        target_name = self.target.name if self.target else "Unknown"
        print(f"[SOCIAL] Lynch mob against {target_name} disbanded.")
        self.active_mob = False
        self.target = None


class DialogueManager:
    """
    Manages branching dialogue based on game mode and trust levels.
    """
    def __init__(self):
        pass

    def get_response(self, speaker, listener_name, game_state):
        rng = game_state.rng
        trust = game_state.trust_system.get_trust(speaker.name, listener_name)
        
        # 1. Determine Tone
        tone = "NEUTRAL"
        if trust < 30:
            tone = "HOSTILE"
        elif trust > 70:
            tone = "FRIENDLY"
            
        # 2. Check for Mode
        mode = game_state.mode.value # Investigative, Emergency, etc.
        
        # 3. Check for Slips (Agent 3 integration references)
        # Assuming speaker.get_dialogue handles the "base" slip logic, 
        # but DialogueManager wraps it with social context.
        
        # 4. Check for Knowledge Tags (Agent 3: Missionary System)
        # If the speaker has "harvested" knowledge, they can use it to feign humanity.
        if hasattr(speaker, 'knowledge_tags') and speaker.knowledge_tags:
            # 30% chance to use a knowledge tag to boost credibility
            if rng.random_float() < 0.3:
                tag = rng.choose(speaker.knowledge_tags) if hasattr(rng, 'choose') else speaker.knowledge_tags[0]
                if "Protocol" in tag:
                    role = tag.split(": ")[1]
                    return f"I'm following {role} protocols exactly. You have nothing to worry about."
                elif "Memory" in tag:
                    interaction = tag.split(": ")[1]
                    return f"I remember the {interaction}. I'm still me."

        # For now, let's generate context-aware lines
        if tone == "HOSTILE":
            options = [
                f"Back off, {listener_name}. I'm watching you.",
                "I don't trust you. Keep your distance.",
                f"You're acting strange, {listener_name}."
            ]
        elif tone == "FRIENDLY":
            options = [
                f"Glad you're here, {listener_name}.",
                "Watch my back, okay?",
                "We need to stick together."
            ]
        else: # Neutral
            options = [
                "It's getting cold.",
                "Seen anything suspicious?",
                f"What do you think, {listener_name}?"
            ]
            
        # Emergency Override
        if mode == "Emergency":
            options = [
                "WE NEED TO SECURE THE AREA!",
                "WHO DID THIS?!",
                "STAY CALM!"
            ]
            
        base_line = rng.choose(options) if hasattr(rng, 'choose') else options[0]
        return base_line
