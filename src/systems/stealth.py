from typing import Dict, List, Optional
from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, ResolutionSystem, Skill
from systems.room_state import RoomState
from entities.crew_member import StealthPosture
from systems.dialogue import DialogueSystem

class StealthSystem:
    """
    Handles stealth encounters by reacting to TURN_ADVANCE events.
    Key mechanic: Subject Pool vs Observer Pool contest using ResolutionSystem.
    """

    def __init__(self, design_registry: Optional[DesignBriefRegistry] = None):
        self.design_registry = design_registry or DesignBriefRegistry()
        self.config = self.design_registry.get_brief("stealth")
        self.cooldown = 0
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def _detect_candidates(self, crew) -> List:
        """Return infected crew sharing a room with the player."""
        return [m for m in crew if getattr(m, "is_infected", False) and getattr(m, "is_alive", True)]
    
    def can_hide_in_room(self, room_name, room_states):
        """Check if room has hiding spots (darkness or default cover)."""
        if not room_states:
            return True # Default to yes if system missing
        is_dark = room_states.has_state(room_name, RoomState.DARK)
        # Assuming most rooms have some furniture, but darkness guarantees it
        return True # Simplified: Can always TRY to hide, but darkness helps

    def set_posture(self, subject, posture: StealthPosture):
        """Assign a stealth posture to a subject."""
        if hasattr(subject, "set_posture"):
            subject.set_posture(posture)
        else:
            subject.stealth_posture = posture

    def get_detection_chance(self, observer, subject, game_state, noise_level: int = 0) -> float:
        """
        Estimate probability that observer detects subject based on current modifiers.
        Used by tests to ensure darkness/noise/posture affect detection odds.
        """
        observer_pool = observer.attributes.get(Attribute.LOGIC, 1) + observer.skills.get(Skill.OBSERVATION, 0)
        subject_pool = subject.attributes.get(Attribute.PROWESS, 1) + subject.skills.get(Skill.STEALTH, 0)

        posture = getattr(subject, "stealth_posture", StealthPosture.STANDING)
        if posture == StealthPosture.CROUCHING:
            subject_pool += 1
        elif posture in (StealthPosture.CRAWLING,):
            subject_pool += 2
        elif posture in (StealthPosture.HIDING, StealthPosture.HIDDEN):
            subject_pool += 4
        elif posture in (StealthPosture.EXPOSED,):
            subject_pool = max(1, subject_pool - 1)

        room_name = game_state.station_map.get_room_name(*subject.location)
        is_dark = not getattr(game_state, "power_on", True) or (game_state.room_states and game_state.room_states.has_state(room_name, RoomState.DARK))
        if is_dark:
            subject_pool += 2
            observer_pool = max(1, observer_pool - 2)

        noise_penalty = noise_level // 2
        noise_bonus = noise_level
        subject_pool = max(1, subject_pool - noise_penalty)
        observer_pool = max(1, observer_pool + noise_bonus)

        # Simple opposed-pool probability estimate: observer chance relative to combined pools
        return min(1.0, max(0.0, observer_pool / (observer_pool + subject_pool)))

    def on_turn_advance(self, event: GameEvent):
        if self.cooldown > 0:
            self.cooldown -= 1

        game_state = event.payload.get("game_state")
        # Ensure rng is available
        rng = event.payload.get("rng")
        if not rng and game_state:
            rng = game_state.rng
            
        if not game_state or not rng:
            return

        player = getattr(game_state, "player", None)
        crew = getattr(game_state, "crew", [])
        station_map = getattr(game_state, "station_map", None)
        room_states = getattr(game_state, "room_states", None)
        
        if not player or not station_map:
            return

        room = station_map.get_room_name(*player.location)
        nearby_infected = [
            m for m in self._detect_candidates(crew)
            if getattr(m, "location", None) == player.location and m != player
        ]

        if not nearby_infected or self.cooldown > 0:
            return

        # Opponent is the first infected person found
        opponent = nearby_infected[0]
        
        # 1. Subject Pool (Player Stealth)
        prowess = player.attributes.get(Attribute.PROWESS, 1) if hasattr(player, "attributes") else 2
        stealth = player.skills.get(Skill.STEALTH, 0) if hasattr(player, "skills") else 0
        subject_pool = prowess + stealth

        # 2. Observer Pool (Infected NPC Perception)
        logic = opponent.attributes.get(Attribute.LOGIC, 1)
        observation = opponent.skills.get(Skill.OBSERVATION, 0)
        observer_pool = logic + observation

        # 3. Modifiers (Posture and Environment)
        posture = getattr(player, "stealth_posture", StealthPosture.STANDING)
        
        # Posture Modifiers
        if posture == StealthPosture.CROUCHING:
            subject_pool += 1
        elif posture == StealthPosture.CRAWLING:
            subject_pool += 2
        elif posture == StealthPosture.HIDING:
            subject_pool += 4
            # Hiding requires skipping turn actions, handled by game loop not here
            # But effectively boosts defense

        # Environmental Modifiers
        is_dark = room_states.has_state(room, RoomState.DARK) if room_states else False
        if is_dark:
            subject_pool += 2
            observer_pool = max(1, observer_pool - 2)
        
        # Enforce minimum pool
        subject_pool = max(1, subject_pool)
        observer_pool = max(1, observer_pool)

        # 4. Resolution
        res = ResolutionSystem()
        
        subject_result = res.roll_check(subject_pool, rng)
        observer_result = res.roll_check(observer_pool, rng)
        
        player_evaded = subject_result['success_count'] > observer_result['success_count']
        
        payload = {
            "room": room,
            "opponent": opponent.name,
            "opponent_ref": opponent,  # Reference to actual NPC object
            "player_ref": player,      # Reference to player object
            "game_state": game_state,  # Full game state for AI reactions
            "outcome": "evaded" if player_evaded else "detected",
            "player_successes": subject_result['success_count'],
            "opponent_successes": observer_result['success_count'],
            "subject_pool": subject_pool,
            "observer_pool": observer_pool
        }
        event_bus.emit(GameEvent(EventType.STEALTH_REPORT, payload))
        
        # Emit Perception Event
        if hasattr(EventType, 'PERCEPTION_EVENT'):
             event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, payload))

        
        if not player_evaded:
            # If detected, opponent might attack or reveal
            opponent.detected_player = True  # Set for visual indicator
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"{opponent.name} spots you in {room}!"
            }))
            
            self._trigger_explain_away(opponent, player, game_state)
        else:
            opponent.detected_player = False
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"You remain unseen by {opponent.name}."
            }))

        self.cooldown = self.config.get("cooldown_turns", 1)

    def evaluate_detection(self, observer, subject, game_state, noise_level=None) -> bool:
        """
        Check if observer detects subject.
        Returns True if detected.
        """
        if noise_level is None:
            noise_level = subject.get_noise_level()
            
        logic = observer.attributes.get(Attribute.LOGIC, 1)
        observation = observer.skills.get(Skill.OBSERVATION, 0)
        pool = logic + observation
        
        res = ResolutionSystem()
        observer_result = res.roll_check(pool, game_state.rng)
        
        prowess = subject.attributes.get(Attribute.PROWESS, 1)
        stealth = subject.skills.get(Skill.STEALTH, 0)
        subject_pool = prowess + stealth
        
        # Noise acts as penalty to subject pool (inverse of stealth)
        # Higher noise -> Lower effective stealth result? 
        # Or easier for observer?
        # Let's say Noise adds directly to Observer successes needed, or reduces subject pool?
        # Specification was "Link noise levels to AudioManager".
        # For mechanic: Let's subtract Noise/2 from Subject Pool to make noisy movement harder to hide.
        
        noise_penalty = noise_level // 2
        subject_pool = max(1, subject_pool - noise_penalty)
        
        subject_result = res.roll_check(subject_pool, game_state.rng)
        
        # Detected if observer wins
        return observer_result['success_count'] >= subject_result['success_count']

    def _trigger_explain_away(self, observer, intruder, game_state):
        """Route detection into the Explain Away dialogue node."""
        dialogue_system = getattr(game_state, "dialogue_system", None) or DialogueSystem(rng=getattr(game_state, "rng", None))
        result = dialogue_system.run_node("EXPLAIN_AWAY", observer, intruder, game_state, {"trigger_type": "STEALTH_DETECTED"}) if dialogue_system else None

        if not result:
            # Fallback to legacy single-line reaction
            dialogue = observer.get_reaction_dialogue("STEALTH_DETECTED")
            event_bus.emit(GameEvent(EventType.DIALOGUE, {
                "speaker": observer.name,
                "text": dialogue
            }))
            return

        for line in result.lines:
            event_bus.emit(GameEvent(EventType.DIALOGUE, {
                "speaker": line.get("speaker", observer.name),
                "text": line.get("text", "...")
            }))

        if result.success:
            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                "text": f"{observer.name}'s suspicion drops after your explanation."
            }))
        elif result.success is False:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"{observer.name} grows hostile and keeps eyes on you!"
            }))
