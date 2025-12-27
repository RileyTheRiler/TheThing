from src.core.event_system import event_bus, EventType, GameEvent

__all__ = ['TrustMatrix', 'LynchMobSystem', 'DialogueManager']

class TrustMatrix:
    def __init__(self, crew):
        # Dictionary of dictionaries: self.matrix[observer][subject] = trust_value
        # Default trust is 50
        self.matrix = {m.name: {other.name: 50 for other in crew} for m in crew}
        self._set_initial_biases()
        
        # Subscribe to events
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

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
        Check for lynch mob conditions each turn.
        """
        game_state = event.payload.get("game_state")
        if game_state:
            targeted = self.check_for_lynch_mob(game_state.crew)
            if targeted and targeted.is_alive:
                print(f"\\n*** EMERGENCY: THE CREW HAS TURNED ON {targeted.name.upper()}! ***")
                print(f"They are dragging {targeted.name} to the Rec Room to be tied up.")
                targeted.location = (7, 7) # Forced move to Rec Room


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
        
    def check_thresholds(self, crew):
        """
        Check if any crew member has fallen below the lynch threshold (20 trust).
        Returns the target if a mob forms.
        """
        # If mob is already active, check if target is still valid (alive)
        if self.active_mob:
            if self.target and not self.target.is_alive:
                self.disband_mob()
            return None

        # Check for new targets
        potential_target = self.trust_system.check_for_lynch_mob(crew)
        if potential_target:
            self.form_mob(potential_target)
            return potential_target
        return None

    def form_mob(self, target):
        self.active_mob = True
        self.target = target
        event_bus.emit(GameEvent(EventType.LYNCH_MOB_TRIGGER, {
            "target": target.name,
            "location": target.location # Will be updated dynamically
        }))
        print(f"[SOCIAL] Lynch mob formed against {target.name}!")

    def disband_mob(self):
        print(f"[SOCIAL] Lynch mob against {self.target.name if self.target else 'Unknown'} disbanded.")
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
