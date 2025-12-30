from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING
from enum import Enum, auto

from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, Skill

if TYPE_CHECKING:
    from engine import GameState, CrewMember

__all__ = ['TrustMatrix', 'LynchMobSystem', 'DialogueManager', 'SocialThresholds',
           'bucket_for_thresholds', 'bucket_label', 'ExplainAwaySystem', 'ExplainResult',
           'MutinyPhase']


class MutinyPhase(Enum):
    """Phases of player mutiny progression."""
    NONE = auto()          # No mutiny active
    WARNING = auto()       # Verbal confrontation, NPCs express distrust
    LOCKOUT = auto()       # NPCs refuse ORDER commands
    IMPRISONMENT = auto()  # Player locked in Generator Room
    EXECUTION = auto()     # NPCs attack player on sight


def bucket_for_thresholds(value: float, thresholds: List[int]) -> int:
    """Return the bucket index for a value given sorted thresholds."""
    for idx, threshold in enumerate(sorted(thresholds)):
        if value < threshold:
            return idx
    return len(thresholds)


def bucket_label(bucket_index: int) -> str:
    """
    Human-friendly label for a threshold bucket.

    Labels align with:
    0: < 20 (Critical/Lynch)
    1: 20-40 (Wary/Hostile)
    2: 40-60 (Guarded/Neutral)
    3: 60-80 (Steady/Friendly)
    4: > 80 (Trusted/Bonded)
    """
    labels = ["critical", "wary", "guarded", "steady", "trusted", "bonded"]
    if bucket_index < len(labels):
        return labels[bucket_index]
    return f"zone-{bucket_index}"


@dataclass
class SocialThresholds:
    # Defaults aligned with test_social_psychology_feedback expectations (40 = Hostile, 20 = Lynch)
    trust_thresholds: List[int] = field(default_factory=lambda: [20, 40, 60, 80])
    paranoia_thresholds: List[int] = field(default_factory=lambda: [33, 66])
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
    def __init__(self, crew, thresholds: Optional[SocialThresholds] = None):
        # Dictionary of dictionaries: self.matrix[observer][subject] = trust_value
        # Default trust is 50
        self.matrix = {m.name: {other.name: 50 for other in crew} for m in crew}
        self.crew_ref = {m.name: m for m in crew} # Keep reference for tag updates
        self.thresholds = thresholds or SocialThresholds()
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
            
            # Find the specific threshold crossed
            crossed_threshold = None
            thresholds = sorted(self.thresholds.trust_thresholds)
            direction = "UP" if new_value > previous_value else "DOWN"

            if direction == "DOWN":
                 for t in reversed(thresholds):
                     if previous_value >= t and new_value < t:
                         crossed_threshold = t
                         break
            else: # UP
                 for t in thresholds:
                     if previous_value < t and new_value >= t:
                         crossed_threshold = t
                         break

            event_bus.emit(GameEvent(EventType.TRUST_THRESHOLD_CROSSED, {
                "scope": "pair",
                "observer": observer_name,
                "subject": subject_name,
                "target": subject_name, # Alias for test compatibility
                "value": new_value,
                "new_value": new_value, # Alias for test compatibility
                "previous_value": previous_value,
                "threshold": crossed_threshold,
                "bucket": bucket_label(new_bucket),
                "direction": direction
            }))

            # Update Relationship Tags
            self._update_relationship_tags(observer_name, subject_name, new_bucket)

    def _update_relationship_tags(self, observer_name: str, subject_name: str, bucket: int):
        """Update Friend/Rival tags based on trust bucket."""
        observer = self.crew_ref.get(observer_name)
        if not observer:
            return

        # Clear existing tags for this subject
        observer.relationship_tags = [t for t in observer.relationship_tags 
                                    if not t.endswith(f":{subject_name}")]

        # Add new tag if applicable
        label = bucket_label(bucket)
        if label in ["trusted", "bonded"]: # > 60 or > 80 depending on config, label mapping: 3=steady, 4=trusted
            # Let's use bucket index for stricter control if needed, but label is readable.
            # Bucket 3 (60-80) = steady, Bucket 4 (>80) = trusted
            if bucket >= 4:
                observer.relationship_tags.append(f"Friend:{subject_name}")
        elif label == "critical": # < 20
             observer.relationship_tags.append(f"Rival:{subject_name}")

    def _track_average_threshold(self, member_name: str, average_value: float):
        previous_value = self._average_values.get(member_name, average_value)
        previous_bucket = self._average_buckets.get(
            member_name, bucket_for_thresholds(previous_value, self.thresholds.trust_thresholds)
        )
        new_bucket = bucket_for_thresholds(average_value, self.thresholds.trust_thresholds)

        self._average_values[member_name] = average_value
        if new_bucket != previous_bucket:
            self._average_buckets[member_name] = new_bucket
            
            # Find the specific threshold crossed
            crossed_threshold = None
            thresholds = sorted(self.thresholds.trust_thresholds)
            if average_value < previous_value: # DOWN
                 direction = "DOWN"
                 for t in reversed(thresholds):
                     if previous_value >= t and average_value < t:
                         crossed_threshold = t
                         break
            else: # UP
                 direction = "UP"
                 for t in thresholds:
                     if previous_value < t and average_value >= t:
                         crossed_threshold = t
                         break

            event_bus.emit(GameEvent(EventType.TRUST_THRESHOLD_CROSSED, {
                "scope": "average",
                "subject": member_name,
                "target": member_name, # Alias for test compatibility
                "value": average_value,
                "new_value": average_value, # Alias for test compatibility
                "previous_value": previous_value,
                "threshold": crossed_threshold,
                "bucket": bucket_label(new_bucket),
                "direction": direction
            }))

    def check_for_lynch_mob(self, crew, game_state=None, lynch_threshold: Optional[int] = None):
        """If global trust in a human falls below the configured threshold, they are targeted."""
        threshold = self.thresholds.lynch_average_threshold if lynch_threshold is None else lynch_threshold
        for member in crew:
            if member.is_alive:
                avg = self.get_average_trust(member.name)
                # This call will emit TRUST_THRESHOLD_CROSSED if buckets change
                self._track_average_threshold(member.name, avg)
                
                # Check for Lynch Trigger specifically
                if avg < threshold:
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
        """Check for lynch mob conditions each turn and apply paranoia decay."""
        game_state = event.payload.get("game_state")
        if game_state:
            # Global Trust Decay based on Paranoia
            decay_amount = int(game_state.paranoia_level / 20)
            if decay_amount > 0:
                for observer in self.matrix:
                    for subject in self.matrix[observer]:
                        if observer != subject:
                            self.matrix[observer][subject] = max(0, self.matrix[observer][subject] - decay_amount)

            targeted = self.check_for_lynch_mob(game_state.crew, game_state)
            if targeted and targeted.is_alive:
                pass


def on_evidence_tagged(event: GameEvent):
    game_state = event.payload.get("game_state")
    target = event.payload.get("target")
    if game_state and target:
        for member in game_state.crew:
            if hasattr(game_state, 'trust_system'):
                game_state.trust_system.update_trust(member.name, target, -10)
        from ui.message_reporter import emit_message
        emit_message(f"[SOCIAL] Global suspicion rises for {target}.")

# Register listeners
event_bus.subscribe(EventType.EVIDENCE_TAGGED, on_evidence_tagged)

def on_perception_event(event: GameEvent):
    payload = event.payload
    if not payload:
        return
        
    game_state = payload.get("game_state")
    observer = payload.get("opponent_ref")
    player = payload.get("player_ref")
    outcome = payload.get("outcome")
    
    if game_state and observer and player and outcome == "detected":
        # Check if player was sneaking (posture check)
        from entities.crew_member import StealthPosture
        is_sneaking = getattr(player, "stealth_posture", StealthPosture.STANDING) != StealthPosture.STANDING
        
        if is_sneaking:
            if hasattr(game_state, 'trust_system'):
                # 5 point trust penalty for suspicious sneaking
                game_state.trust_system.update_trust(observer.name, player.name, -5)
            
            from ui.message_reporter import emit_message
            emit_message(f"[SOCIAL] {observer.name} looks at you with distrust. \"Why are you sneaking around?\"")

event_bus.subscribe(EventType.PERCEPTION_EVENT, on_perception_event)


class LynchMobSystem:
    def __init__(self, trust_system, thresholds: Optional[SocialThresholds] = None):
        self.trust_system = trust_system
        self.thresholds = thresholds or SocialThresholds()
        self.active_mob = False
        self.target = None
        
        # Tier 8: Mutiny phase tracking
        self.mutiny_phase = MutinyPhase.NONE
        self.mutiny_turns_in_phase = 0
        self.mutiny_target = None  # Usually the player
        
        # Load gathering location from config
        self.gathering_location = self._load_gathering_location()
        
        # Subscribe to triggers
        event_bus.subscribe(EventType.LYNCH_MOB_TRIGGER, self.on_lynch_mob_trigger)
        event_bus.subscribe(EventType.CREW_DEATH, self.on_crew_death)
        event_bus.subscribe(EventType.TEST_RESULT, self.on_blood_test_result)
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_mutiny_turn_advance)

    def _load_gathering_location(self):
        """Load lynch mob gathering location from config, default to Rec Room."""
        import json
        import os
        try:
            config_path = os.path.join("config", "game_settings.json")
            with open(config_path, 'r') as f:
                settings = json.load(f)
            return settings.get("lynch_mob", {}).get("gathering_location", "Rec Room")
        except Exception:
            return "Rec Room"  # Fallback default

    def cleanup(self):
        event_bus.unsubscribe(EventType.LYNCH_MOB_TRIGGER, self.on_lynch_mob_trigger)
        event_bus.unsubscribe(EventType.CREW_DEATH, self.on_crew_death)
        event_bus.unsubscribe(EventType.TEST_RESULT, self.on_blood_test_result)
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_mutiny_turn_advance)
        
    def check_thresholds(self, crew, current_paranoia: Optional[int] = None):
        """Check if any crew member has fallen below the lynch threshold."""
        paranoia_blocked = (
            current_paranoia is not None
            and current_paranoia < self.thresholds.lynch_paranoia_trigger
        )

        if paranoia_blocked:
            return None

        if self.active_mob:
            if self.target and not self.target.is_alive:
                self.disband_mob()
            elif self.target:
                event_bus.emit(GameEvent(EventType.LYNCH_MOB_UPDATE, {
                    "target": self.target.name,
                    "location": self.target.location
                }))
            return None

        # Check for Mutiny against Player
        if self.check_player_mutiny(crew, current_paranoia):
            return None

        potential_target = self.trust_system.check_for_lynch_mob(
            crew, lynch_threshold=self.thresholds.lynch_average_threshold
        )
        if potential_target:
            self.form_mob(potential_target)
            return potential_target
        return None

    def check_player_mutiny(self, crew, current_paranoia: Optional[int] = None, game_state=None) -> bool:
        """Check if the crew mutinies against the player."""
        if current_paranoia is None or current_paranoia < 60:
            return False

        # Find player
        player = next((m for m in crew if m.name == "MacReady"), None)
        if not player:
            return False

        avg_trust = self.trust_system.get_average_trust("MacReady")
        innocent_kills = getattr(player, "innocent_kills", 0)
        refused_test = getattr(player, "refused_blood_test", False)
        
        # Count NPCs with trust < 20 toward player (for 3+ NPC condition)
        low_trust_count = sum(
            1 for m in crew 
            if m.name != "MacReady" and m.is_alive 
            and self.trust_system.get_trust(m.name, "MacReady") < 20
        )
        
        # Trigger conditions:
        # 1. Trust < 20 with 3+ NPCs
        # 2. Player killed 2+ innocents
        # 3. Player refused blood test
        should_trigger = (
            (low_trust_count >= 3) or
            (innocent_kills >= 2) or
            (refused_test and low_trust_count >= 2)
        )
        
        if should_trigger and self.mutiny_phase == MutinyPhase.NONE:
            self._enter_mutiny_phase(MutinyPhase.WARNING, player, game_state)
            return True
            
        return False
    
    def _enter_mutiny_phase(self, phase: MutinyPhase, target: 'CrewMember', game_state=None):
        """Transition to a new mutiny phase."""
        old_phase = self.mutiny_phase
        self.mutiny_phase = phase
        self.mutiny_turns_in_phase = 0
        self.mutiny_target = target
        
        from ui.message_reporter import emit_warning, emit_message
        
        if phase == MutinyPhase.WARNING:
            emit_warning("The crew is losing faith in you. They're starting to talk...")
            emit_message("NPCs gather in small groups, casting suspicious glances your way.", crawl=True)
            event_bus.emit(GameEvent(EventType.MUTINY_WARNING, {
                "target": target.name,
                "phase": "WARNING"
            }))
            
        elif phase == MutinyPhase.LOCKOUT:
            emit_warning("LOCKOUT: The crew no longer trusts your leadership!")
            emit_message("NPCs will refuse your orders. You need to regain their trust.", crawl=True)
            event_bus.emit(GameEvent(EventType.MUTINY_LOCKOUT, {
                "target": target.name,
                "phase": "LOCKOUT"
            }))
            
        elif phase == MutinyPhase.IMPRISONMENT:
            emit_warning("MUTINY! The crew drags you to the Generator Room!")
            emit_message("You've been locked in. Find a way to escape or wait for rescue.", crawl=True)
            # Move player to Generator Room
            if game_state:
                gen_room = game_state.station_map.rooms.get("Generator Room")
                if gen_room:
                    target.location = (gen_room[0], gen_room[1])
            event_bus.emit(GameEvent(EventType.MUTINY_IMPRISONMENT, {
                "target": target.name,
                "phase": "IMPRISONMENT",
                "location": "Generator Room"
            }))
            
        elif phase == MutinyPhase.EXECUTION:
            emit_warning("EXECUTION ORDER! The crew has decided you're too dangerous!")
            emit_message("All NPCs will attack you on sight. Run or fight!", crawl=True)
            event_bus.emit(GameEvent(EventType.MUTINY_TRIGGERED, {
                "target": target.name,
                "phase": "EXECUTION"
            }))
    
    def on_mutiny_turn_advance(self, event: GameEvent):
        """Progress mutiny phases over time."""
        if self.mutiny_phase == MutinyPhase.NONE:
            return
            
        game_state = event.payload.get("game_state")
        self.mutiny_turns_in_phase += 1
        
        # Phase progression based on turns
        if self.mutiny_phase == MutinyPhase.WARNING and self.mutiny_turns_in_phase >= 3:
            self._enter_mutiny_phase(MutinyPhase.LOCKOUT, self.mutiny_target, game_state)
        elif self.mutiny_phase == MutinyPhase.LOCKOUT and self.mutiny_turns_in_phase >= 2:
            self._enter_mutiny_phase(MutinyPhase.IMPRISONMENT, self.mutiny_target, game_state)
    
    def on_crew_death(self, event: GameEvent):
        """Track player innocent kills for mutiny trigger."""
        game_state = event.payload.get("game_state")
        if not game_state:
            return
            
        dead_name = event.payload.get("name")
        dead_member = next((m for m in game_state.crew if m.name == dead_name), None)
        
        # If the dead NPC was NOT infected, count as innocent kill
        if dead_member and not getattr(dead_member, "is_infected", False):
            player = game_state.player
            if player:
                player.innocent_kills = getattr(player, "innocent_kills", 0) + 1
                
                from ui.message_reporter import emit_warning
                if player.innocent_kills >= 2:
                    emit_warning(f"You've killed {player.innocent_kills} innocent crew members. The crew is getting suspicious...")
    
    def on_blood_test_result(self, event: GameEvent):
        """Track if player refuses blood test."""
        payload = event.payload
        if payload.get("refused") and payload.get("target") == "MacReady":
            game_state = payload.get("game_state")
            if game_state and game_state.player:
                game_state.player.refused_blood_test = True
                from ui.message_reporter import emit_warning
                emit_warning("You refused the blood test! The crew's suspicion of you grows...")
    
    def attempt_escape(self, player: 'CrewMember', method: str, game_state) -> bool:
        """
        Attempt to escape from imprisonment.
        Methods: 'lockpick', 'vent', 'force'
        """
        if self.mutiny_phase != MutinyPhase.IMPRISONMENT:
            return False
            
        rng = game_state.rng
        success = False
        
        event_bus.emit(GameEvent(EventType.ESCAPE_ATTEMPT, {
            "target": player.name,
            "method": method
        }))
        
        from ui.message_reporter import emit_message, emit_warning
        
        if method == "lockpick":
            # LOGIC + REPAIR skill check
            pool = player.attributes.get(Attribute.LOGIC, 2) + player.skills.get(Skill.REPAIR, 0)
            result = rng.calculate_success(pool)
            if result['success_count'] >= 2:
                success = True
                emit_message("You carefully pick the lock and slip out of the Generator Room.")
        
        elif method == "vent":
            # PROWESS + STEALTH skill check  
            pool = player.attributes.get(Attribute.PROWESS, 2) + player.skills.get(Skill.STEALTH, 0)
            result = rng.calculate_success(pool)
            if result['success_count'] >= 1:
                success = True
                player.in_vent = True
                emit_message("You squeeze into the ventilation system and begin crawling.")
        
        elif method == "force":
            # PROWESS check, but loud - alerts everyone
            pool = player.attributes.get(Attribute.PROWESS, 2)
            result = rng.calculate_success(pool)
            if result['success_count'] >= 3:
                success = True
                emit_warning("You break down the door! The noise alerts the entire station!")
                # Skip to execution phase if forced
                self._enter_mutiny_phase(MutinyPhase.EXECUTION, player, game_state)
                return True
        
        if success and self.mutiny_phase == MutinyPhase.IMPRISONMENT:
            # Successful silent escape - advance to execution if caught later
            self._enter_mutiny_phase(MutinyPhase.EXECUTION, player, game_state)
            return True
        elif not success:
            emit_message("Your escape attempt fails. You're still trapped in the Generator Room.")
            
        return success
    
    def is_order_blocked(self) -> bool:
        """Check if player orders should be blocked due to mutiny."""
        return self.mutiny_phase in (MutinyPhase.LOCKOUT, MutinyPhase.IMPRISONMENT, MutinyPhase.EXECUTION)
    
    def is_player_imprisoned(self) -> bool:
        """Check if player is currently imprisoned."""
        return self.mutiny_phase == MutinyPhase.IMPRISONMENT
    
    def reset_mutiny(self):
        """Reset mutiny state (e.g., if player regains trust)."""
        self.mutiny_phase = MutinyPhase.NONE
        self.mutiny_turns_in_phase = 0
        self.mutiny_target = None

    def on_lynch_mob_trigger(self, event: GameEvent):
        target_name = event.payload.get("target")
        self.active_mob = True
        
        from ui.message_reporter import emit_warning, emit_message
        emit_warning(f"EMERGENCY: THE CREW HAS TURNED ON {target_name.upper()}!")
        emit_message(f"They are dragging {target_name} to the Rec Room to be tied up.", crawl=True)

    def form_mob(self, target):
        self.active_mob = True
        self.target = target
        avg_trust = self.trust_system.get_average_trust(target.name)
        event_bus.emit(GameEvent(EventType.LYNCH_MOB_TRIGGER, {
            "target": target.name,
            "location": target.location,
            "average_trust": avg_trust,
            "threshold": self.thresholds.lynch_average_threshold
        }))

    def disband_mob(self):
        target_name = self.target.name if self.target else "Unknown"
        from ui.message_reporter import emit_message
        emit_message(f"[SOCIAL] Lynch mob against {target_name} disbanded.")
        self.active_mob = False
        self.target = None


class DialogueManager:
    """Manages branching dialogue based on game mode and trust levels."""
    def __init__(self):
        pass

    def get_response(self, speaker, listener_name, game_state):
        rng = game_state.rng
        trust = game_state.trust_system.get_trust(speaker.name, listener_name)
        
        tone = "NEUTRAL"
        if trust < 30:
            tone = "HOSTILE"
        elif trust > 70:
            tone = "FRIENDLY"
            
        mode = game_state.mode.value if hasattr(game_state.mode, 'value') else str(game_state.mode)
        
        if hasattr(speaker, 'knowledge_tags') and speaker.knowledge_tags:
            if rng.random_float() < 0.3:
                tag = rng.choose(speaker.knowledge_tags) if hasattr(rng, 'choose') else speaker.knowledge_tags[0]
                if "Protocol" in tag:
                    role = tag.split(": ")[1]
                    return f"I'm following {role} protocols exactly. You have nothing to worry about."
                elif "Memory" in tag:
                    interaction = tag.split(": ")[1]
                    return f"I remember the {interaction}. I'm still me."

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
        else:
            options = [
                "It's getting cold.",
                "Seen anything suspicious?",
                f"What do you think, {listener_name}?"
            ]
            
        if mode == "Emergency":
            options = [
                "WE NEED TO SECURE THE AREA!",
                "WHO DID THIS?!",
                "STAY CALM!"
            ]
            
        base_line = rng.choose(options) if hasattr(rng, 'choose') else options[0]
        return base_line


@dataclass
class ExplainResult:
    """Result of an explain away attempt."""
    success: bool
    critical: bool  # Critical success or failure
    player_successes: int
    observer_successes: int
    suspicion_change: int
    trust_change: int
    dialogue: str


class ExplainAwaySystem:
    """
    Handles the 'Explain Away' dialogue mechanic.

    When a player is detected sneaking, they can attempt to explain their behavior.
    Roll: INFLUENCE + DECEPTION vs LOGIC + EMPATHY of the observer.

    Success: Reduce suspicion by 3-5, emit forgiving dialogue
    Failure: Increase suspicion by 2, emit skeptical dialogue, trust penalty
    Critical Failure (0 successes): Immediate accusation trigger
    """

    # Dialogue options for different outcomes
    PLAYER_EXPLANATIONS = [
        "I thought I heard something suspicious over there.",
        "Just checking if this area is secure.",
        "I was looking for supplies, didn't want to wake anyone.",
        "Sorry, I was trying to be quiet - didn't mean to startle you.",
        "I was investigating a noise. False alarm, I think."
    ]

    OBSERVER_ACCEPTS = [
        "{observer} nods slowly. \"Alright, but be more careful.\"",
        "{observer} relaxes slightly. \"Fair enough. Stay safe.\"",
        "{observer} considers this. \"I suppose that makes sense.\"",
        "{observer} shrugs. \"Just announce yourself next time.\"",
        "{observer} seems satisfied. \"Okay, I believe you.\""
    ]

    OBSERVER_SKEPTICAL = [
        "{observer} narrows their eyes. \"That's what someone would say...\"",
        "{observer} doesn't look convinced. \"I'm watching you.\"",
        "{observer} frowns. \"That story doesn't add up.\"",
        "{observer} steps back warily. \"If you say so...\"",
        "{observer} seems doubtful. \"Just... keep your distance.\""
    ]

    OBSERVER_ACCUSES = [
        "{observer} points at you. \"THAT'S EXACTLY WHAT A THING WOULD SAY!\"",
        "{observer} backs away in horror. \"You can't fool me! Everyone, get over here!\"",
        "{observer} shouts. \"I KNEW IT! You're one of THEM!\"",
        "{observer}'s face twists with fear. \"Don't come any closer! HELP!\""
    ]

    def __init__(self):
        self._pending_explanations: Dict[str, 'CrewMember'] = {}
        event_bus.subscribe(EventType.PERCEPTION_EVENT, self.on_perception_event)

    def cleanup(self):
        event_bus.unsubscribe(EventType.PERCEPTION_EVENT, self.on_perception_event)

    def on_perception_event(self, event: GameEvent):
        """Track detection events that allow explain away attempts."""
        payload = event.payload
        if not payload:
            return

        outcome = payload.get("outcome")
        observer = payload.get("opponent_ref")
        player = payload.get("player_ref")
        game_state = payload.get("game_state")

        if outcome != "detected" or not observer or not player:
            return

        # Check if player was sneaking (not standing)
        from entities.crew_member import StealthPosture
        is_sneaking = getattr(player, "stealth_posture", StealthPosture.STANDING) != StealthPosture.STANDING

        if is_sneaking and observer.is_alive and not getattr(observer, 'is_revealed', False):
            # Player can attempt to explain
            self._pending_explanations[observer.name] = observer

            # Emit prompt to player
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"[!] {observer.name} caught you sneaking! Type EXPLAIN to try talking your way out."
            }))

    def can_explain_to(self, observer_name: str) -> bool:
        """Check if an explain away attempt is pending for this observer."""
        return observer_name in self._pending_explanations

    def get_pending_observers(self) -> List[str]:
        """Get list of observer names with pending explain opportunities."""
        return list(self._pending_explanations.keys())

    def clear_pending(self, observer_name: str = None):
        """Clear pending explanation opportunity."""
        if observer_name:
            self._pending_explanations.pop(observer_name, None)
        else:
            self._pending_explanations.clear()

    def attempt_explain(self, player: 'CrewMember', observer: 'CrewMember',
                        game_state: 'GameState') -> ExplainResult:
        """
        Attempt to explain away suspicious behavior.

        Roll: Player INFLUENCE + DECEPTION vs Observer LOGIC + EMPATHY
        """
        rng = game_state.rng

        # Calculate player pool: INFLUENCE + DECEPTION
        player_influence = player.attributes.get(Attribute.INFLUENCE, 1)
        player_deception = player.skills.get(Skill.DECEPTION, 0)
        player_pool = player_influence + player_deception

        # Calculate observer pool: LOGIC + EMPATHY
        observer_logic = observer.attributes.get(Attribute.LOGIC, 2)
        observer_empathy = observer.skills.get(Skill.EMPATHY, 0)
        observer_pool = observer_logic + observer_empathy

        # Roll both pools
        player_result = rng.calculate_success(player_pool)
        observer_result = rng.calculate_success(observer_pool)

        player_successes = player_result['success_count']
        observer_successes = observer_result['success_count']

        # Clear pending explanation
        self.clear_pending(observer.name)

        # Determine outcome
        if player_successes == 0 and observer_successes > 0:
            # Critical failure - accusation
            return self._critical_failure(player, observer, player_successes, observer_successes, game_state)
        elif player_successes > observer_successes:
            # Success - observer accepts explanation
            margin = player_successes - observer_successes
            return self._success(player, observer, player_successes, observer_successes, margin, game_state)
        else:
            # Failure - observer remains skeptical
            return self._failure(player, observer, player_successes, observer_successes, game_state)

    def _success(self, player: 'CrewMember', observer: 'CrewMember',
                 player_successes: int, observer_successes: int,
                 margin: int, game_state: 'GameState') -> ExplainResult:
        """Handle successful explanation."""
        rng = game_state.rng

        # Suspicion reduction: 3 base + margin (max 5)
        suspicion_reduction = min(5, 3 + margin)

        # Apply suspicion reduction
        if hasattr(observer, 'suspicion_level'):
            observer.suspicion_level = max(0, observer.suspicion_level - suspicion_reduction)
            if observer.suspicion_level == 0:
                observer.suspicion_state = "idle"

        # Small trust boost
        trust_change = 2
        if hasattr(game_state, 'trust_system'):
            game_state.trust_system.modify_trust(observer.name, player.name, trust_change)

        # Generate dialogue
        explanation = rng.choose(self.PLAYER_EXPLANATIONS)
        response = rng.choose(self.OBSERVER_ACCEPTS).format(observer=observer.name)
        dialogue = f'You say: "{explanation}"\n{response}'

        return ExplainResult(
            success=True,
            critical=False,
            player_successes=player_successes,
            observer_successes=observer_successes,
            suspicion_change=-suspicion_reduction,
            trust_change=trust_change,
            dialogue=dialogue
        )

    def _failure(self, player: 'CrewMember', observer: 'CrewMember',
                 player_successes: int, observer_successes: int,
                 game_state: 'GameState') -> ExplainResult:
        """Handle failed explanation."""
        rng = game_state.rng

        # Suspicion increase
        suspicion_increase = 2

        if hasattr(observer, 'increase_suspicion'):
            observer.increase_suspicion(suspicion_increase, turn=getattr(game_state, 'turn', 0))

        # Trust penalty
        trust_change = -5
        if hasattr(game_state, 'trust_system'):
            game_state.trust_system.modify_trust(observer.name, player.name, trust_change)

        # Generate dialogue
        explanation = rng.choose(self.PLAYER_EXPLANATIONS)
        response = rng.choose(self.OBSERVER_SKEPTICAL).format(observer=observer.name)
        dialogue = f'You say: "{explanation}"\n{response}'

        return ExplainResult(
            success=False,
            critical=False,
            player_successes=player_successes,
            observer_successes=observer_successes,
            suspicion_change=suspicion_increase,
            trust_change=trust_change,
            dialogue=dialogue
        )

    def _critical_failure(self, player: 'CrewMember', observer: 'CrewMember',
                          player_successes: int, observer_successes: int,
                          game_state: 'GameState') -> ExplainResult:
        """Handle critical failure - triggers accusation."""
        rng = game_state.rng

        # Major suspicion spike
        suspicion_increase = 5

        if hasattr(observer, 'increase_suspicion'):
            observer.increase_suspicion(suspicion_increase, turn=getattr(game_state, 'turn', 0))
            observer.suspicion_state = "follow"

        # Severe trust penalty
        trust_change = -15
        if hasattr(game_state, 'trust_system'):
            game_state.trust_system.modify_trust(observer.name, player.name, trust_change)

        # Generate dialogue
        response = rng.choose(self.OBSERVER_ACCUSES).format(observer=observer.name)
        dialogue = f"Your words stumble and fail.\n{response}"

        # Emit warning about impending trouble
        event_bus.emit(GameEvent(EventType.WARNING, {
            "text": f"{observer.name} is now convinced you're infected!"
        }))

        return ExplainResult(
            success=False,
            critical=True,
            player_successes=player_successes,
            observer_successes=observer_successes,
            suspicion_change=suspicion_increase,
            trust_change=trust_change,
            dialogue=dialogue
        )
