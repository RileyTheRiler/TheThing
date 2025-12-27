from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.event_system import event_bus, EventType, GameEvent

__all__ = ['TrustMatrix', 'LynchMobSystem', 'DialogueManager', 'SocialThresholds', 'bucket_for_thresholds', 'bucket_label']


def bucket_for_thresholds(value: float, thresholds: List[int]) -> int:
    """Return the bucket index for a value given sorted thresholds."""
    for idx, threshold in enumerate(sorted(thresholds)):
        if value < threshold:
            return idx
    return len(thresholds)


def bucket_label(bucket_index: int) -> str:
    """
    Human-friendly label for a threshold bucket.

    More labels are provided than typical thresholds; if we exceed the defaults,
    fall back to a generic label.
    """
    labels = ["critical", "wary", "guarded", "steady", "trusted", "bonded"]
    if bucket_index < len(labels):
        return labels[bucket_index]
    return f"zone-{bucket_index}"


@dataclass
class SocialThresholds:
    trust_thresholds: List[int] = field(default_factory=lambda: [25, 50, 75])
    paranoia_thresholds: List[int] = field(default_factory=lambda: [25, 60, 85])
    lynch_average_threshold: int = 20
    lynch_paranoia_trigger: int = 50

    def __post_init__(self):
        self.trust_thresholds = self._normalize(self.trust_thresholds)
        self.paranoia_thresholds = self._normalize(self.paranoia_thresholds)
        self.lynch_average_threshold = self._clamp(self.lynch_average_threshold)
        self.lynch_paranoia_trigger = self._clamp(self.lynch_paranoia_trigger)

    @staticmethod
    def _normalize(values: List[int]) -> List[int]:
        unique_sorted = sorted({SocialThresholds._clamp(v) for v in values})
        return unique_sorted

    @staticmethod
    def _clamp(value: int) -> int:
        return max(0, min(100, int(value)))

class TrustMatrix:
<<<<<<< HEAD
    # Threshold Constants
    LYNCH_THRESHOLD = 20
    HOSTILE_THRESHOLD = 40
    FRIENDLY_THRESHOLD = 70

    def __init__(self, crew):
        # Dictionary of dictionaries: self.matrix[observer][subject] = trust_value
        # Default trust is 50
        self.matrix = {m.name: {other.name: 50 for other in crew} for m in crew}
        
        # Track previous average trust to detect threshold crossings
        self.prev_avg_trust = {m.name: 50.0 for m in crew}
        
=======
    def __init__(self, crew, thresholds: Optional[SocialThresholds] = None):
        # Dictionary of dictionaries: self.matrix[observer][subject] = trust_value
        # Default trust is 50
        self.matrix = {m.name: {other.name: 50 for other in crew} for m in crew}
        self.thresholds = thresholds or SocialThresholds()
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503
        self._set_initial_biases()
        self._trust_buckets: Dict[str, Dict[str, int]] = {
            observer: {subject: bucket_for_thresholds(value, self.thresholds.trust_thresholds)
                       for subject, value in subjects.items()}
            for observer, subjects in self.matrix.items()
        }
        self._average_values: Dict[str, float] = {m.name: self.get_average_trust(m.name) for m in crew}
        self._average_buckets: Dict[str, int] = {
            name: bucket_for_thresholds(avg, self.thresholds.trust_thresholds)
            for name, avg in self._average_values.items()
        }
        
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
        self.modify_trust(observer_name, subject_name, amount)

    def modify_trust(self, observer_name, subject_name, amount):
        """Adjusts trust and emits threshold events when buckets change."""
        if observer_name in self.matrix and subject_name in self.matrix[observer_name]:
            current = self.matrix[observer_name][subject_name]
            new_value = max(0, min(100, current + amount))
            self.matrix[observer_name][subject_name] = new_value
            self._maybe_emit_trust_threshold(observer_name, subject_name, current, new_value)

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

<<<<<<< HEAD
    def check_for_lynch_mob(self, crew, game_state=None):
        """If global trust in a human falls below LYNCH_THRESHOLD, they are targeted."""
        for member in crew:
            if member.is_alive:
                avg = self.get_average_trust(member.name)
                prev_avg = self.prev_avg_trust.get(member.name, 50.0)
                
                # 1. Detect Threshold Crossings
                thresholds = [self.FRIENDLY_THRESHOLD, self.HOSTILE_THRESHOLD, self.LYNCH_THRESHOLD]
                for t in thresholds:
                    # Dropped below threshold
                    if prev_avg >= t and avg < t:
                        event_bus.emit(GameEvent(EventType.TRUST_THRESHOLD_CROSSED, {
                            "target": member.name,
                            "threshold": t,
                            "direction": "DOWN",
                            "new_value": avg,
                            "old_value": prev_avg
                        }))
                    # Rose above threshold
                    elif prev_avg < t and avg >= t:
                        event_bus.emit(GameEvent(EventType.TRUST_THRESHOLD_CROSSED, {
                            "target": member.name,
                            "threshold": t,
                            "direction": "UP",
                            "new_value": avg,
                            "old_value": prev_avg
                        }))
                
                # Update tracking
                self.prev_avg_trust[member.name] = avg

                # 2. Lynch threshold check
                if avg < self.LYNCH_THRESHOLD:
=======
    def rebuild_buckets(self):
        """Recalculate bucket caches after bulk trust updates (e.g., save hydration)."""
        self._trust_buckets = {
            observer: {subject: bucket_for_thresholds(value, self.thresholds.trust_thresholds)
                       for subject, value in subjects.items()}
            for observer, subjects in self.matrix.items()
        }
        self._average_values = {observer: self.get_average_trust(observer) for observer in self.matrix}
        self._average_buckets = {
            name: bucket_for_thresholds(avg, self.thresholds.trust_thresholds)
            for name, avg in self._average_values.items()
        }

    def _maybe_emit_trust_threshold(self, observer_name: str, subject_name: str, previous_value: float, new_value: float):
        previous_bucket = self._trust_buckets.get(observer_name, {}).get(
            subject_name, bucket_for_thresholds(previous_value, self.thresholds.trust_thresholds)
        )
        new_bucket = bucket_for_thresholds(new_value, self.thresholds.trust_thresholds)

        if new_bucket != previous_bucket:
            self._trust_buckets.setdefault(observer_name, {})[subject_name] = new_bucket
            direction = "up" if new_value > previous_value else "down"
            event_bus.emit(GameEvent(EventType.TRUST_THRESHOLD, {
                "scope": "pair",
                "observer": observer_name,
                "subject": subject_name,
                "value": new_value,
                "previous_value": previous_value,
                "bucket": bucket_label(new_bucket),
                "thresholds": list(self.thresholds.trust_thresholds),
                "direction": direction
            }))

    def _track_average_threshold(self, member_name: str, average_value: float):
        previous_value = self._average_values.get(member_name, average_value)
        previous_bucket = self._average_buckets.get(
            member_name, bucket_for_thresholds(previous_value, self.thresholds.trust_thresholds)
        )
        new_bucket = bucket_for_thresholds(average_value, self.thresholds.trust_thresholds)

        self._average_values[member_name] = average_value
        if new_bucket != previous_bucket:
            self._average_buckets[member_name] = new_bucket
            direction = "up" if average_value > previous_value else "down"
            event_bus.emit(GameEvent(EventType.TRUST_THRESHOLD, {
                "scope": "average",
                "subject": member_name,
                "value": average_value,
                "previous_value": previous_value,
                "bucket": bucket_label(new_bucket),
                "thresholds": list(self.thresholds.trust_thresholds),
                "direction": direction
            }))

    def check_for_lynch_mob(self, crew, game_state=None, lynch_threshold: Optional[int] = None):
        """If global trust in a human falls below the configured threshold, they are targeted."""
        threshold = self.thresholds.lynch_average_threshold if lynch_threshold is None else lynch_threshold
        for member in crew:
            if member.is_alive:
                avg = self.get_average_trust(member.name)
                self._track_average_threshold(member.name, avg)
                # Lynch threshold
                if avg < threshold:
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503
                    # Emit LYNCH_MOB_TRIGGER event
                    if game_state:
                        event_bus.emit(GameEvent(EventType.LYNCH_MOB_TRIGGER, {
                            "target": member.name,
                            "location": member.location,
                            "average_trust": avg,
                            "threshold": threshold
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
        from ui.message_reporter import emit_message
        emit_message(f"[SOCIAL] Global suspicion rises for {target}.")

# Register listeners
event_bus.subscribe(EventType.EVIDENCE_TAGGED, on_evidence_tagged)


class LynchMobSystem:
    def __init__(self, trust_system, thresholds: Optional[SocialThresholds] = None):
        self.trust_system = trust_system
        self.thresholds = thresholds or SocialThresholds()
        self.active_mob = False
        self.target = None
        
    def check_thresholds(self, crew, current_paranoia: Optional[int] = None):
        """
        Check if any crew member has fallen below the configured lynch threshold.
        Returns the target if a mob forms.
        """
        paranoia_blocked = (
            current_paranoia is not None
            and current_paranoia < self.thresholds.lynch_paranoia_trigger
        )

        if paranoia_blocked:
            return None

        # If mob is already active, check if target is still valid (alive)
        if self.active_mob:
            if self.target and not self.target.is_alive:
                self.disband_mob()
            elif self.target:
                # Emit update for dynamic tracking
                event_bus.emit(GameEvent(EventType.LYNCH_MOB_UPDATE, {
                    "target": self.target.name,
                    "location": self.target.location
                }))
            return None

        # Check for new targets
        potential_target = self.trust_system.check_for_lynch_mob(
            crew, lynch_threshold=self.thresholds.lynch_average_threshold
        )
        if potential_target:
            self.form_mob(potential_target)
            return potential_target
        return None
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
        from ui.message_reporter import emit_warning, emit_message
        emit_warning(f"EMERGENCY: THE CREW HAS TURNED ON {target_name.upper()}!")
        emit_message(f"They are dragging {target_name} to the Rec Room to be tied up.", crawl=True)
    
    def check_thresholds(self, crew):
        # Deprecated manual check, handled by TrustMatrix event
        pass

    def form_mob(self, target):
        # Logic moved to on_lynch_mob_trigger mostly, but this might be called by Accuse command
        self.active_mob = True
        self.target = target
        avg_trust = self.trust_system.get_average_trust(target.name)
        event_bus.emit(GameEvent(EventType.LYNCH_MOB_TRIGGER, {
            "target": target.name,
            "location": target.location, # Will be updated dynamically
            "average_trust": avg_trust,
            "threshold": self.thresholds.lynch_average_threshold
        self.target = target # Object
        event_bus.emit(GameEvent(EventType.LYNCH_MOB_TRIGGER, {
            "target": target.name,
            "location": target.location
        }))

    def disband_mob(self):
        target_name = self.target.name if self.target else "Unknown"
        from ui.message_reporter import emit_message
        emit_message(f"[SOCIAL] Lynch mob against {self.target.name} disbanded.")
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
