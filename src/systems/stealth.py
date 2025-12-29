from typing import Dict, List, Optional
from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, ResolutionSystem, Skill
from systems.room_state import RoomState
from entities.crew_member import StealthPosture

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
        current_turn = event.payload.get("turn") or getattr(game_state, "turn", None)

        # Suspicion adjustments (toward the player)
        suspicion_delta = 0
        if not player_evaded:
            suspicion_delta = 3
        elif player_evaded and (subject_result['success_count'] - observer_result['success_count']) < 2:
            suspicion_delta = 1

        # Biological slip/location hint exposes player to extra scrutiny
        if getattr(player, "location_hint_active", False):
            suspicion_delta += 1

        if suspicion_delta and hasattr(opponent, "increase_suspicion"):
            opponent.increase_suspicion(suspicion_delta, turn=current_turn)
            opponent.suspicion_state = getattr(opponent, "suspicion_state", "idle")
        
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
            "observer_pool": observer_pool,
            "suspicion_delta": suspicion_delta,
            "suspicion_level": getattr(opponent, "suspicion_level", 0)
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
            
            # Contextual Dialogue
            dialogue = opponent.get_reaction_dialogue("STEALTH_DETECTED")
            event_bus.emit(GameEvent(EventType.DIALOGUE, {
                "speaker": opponent.name,
                "text": dialogue
            }))
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

        ctx = self._prepare_detection_context(observer, subject, game_state, noise_level)

        res = ResolutionSystem()
        subject_result = res.roll_check(ctx["subject_pool"], game_state.rng)

        # Visual detection
        observer_result = res.roll_check(ctx["observer_pool"], game_state.rng)
        observer_score = observer_result['success_count']
        if ctx["env_effects"]:
            observer_score = max(0, observer_score + ctx["env_effects"].stealth_detection_modifier)

        visual_detected = observer_score >= subject_result['success_count']

        # Heat-based detection when power is off and the room is not frozen
        thermal_detected = False
        if ctx["env_effects"] and ctx["env_effects"].heat_detection_enabled and not ctx["is_frozen"]:
            thermal_pool = observer.attributes.get(Attribute.THERMAL, 1) + ctx["env_effects"].thermal_detection_bonus
            thermal_pool = max(1, thermal_pool)
            thermal_result = res.roll_check(thermal_pool, game_state.rng)
            thermal_detected = thermal_result['success_count'] >= subject_result['success_count']

        return visual_detected or thermal_detected

    def _prepare_detection_context(self, observer, subject, game_state, noise_level: int):
        """Build detection pools and environmental context for repeated calculations."""
        station_map = getattr(game_state, "station_map", None)
        room_states = getattr(game_state, "room_states", None)
        env = getattr(game_state, "environmental_coordinator", None)
        room_name = None
        if station_map and hasattr(subject, "location"):
            room_name = station_map.get_room_name(*subject.location)

        is_dark = room_states.has_state(room_name, RoomState.DARK) if room_states and room_name else False
        is_frozen = room_states.has_state(room_name, RoomState.FROZEN) if room_states and room_name else False

        # Base visual pools
        logic = observer.attributes.get(Attribute.LOGIC, 1)
        observation = observer.skills.get(Skill.OBSERVATION, 0)
        observer_pool = logic + observation

        prowess = subject.attributes.get(Attribute.PROWESS, 1)
        stealth = subject.skills.get(Skill.STEALTH, 0)
        subject_pool = prowess + stealth
        
        posture = getattr(subject, "stealth_posture", StealthPosture.STANDING)
        if posture == StealthPosture.CROUCHING:
            subject_pool += 1
        elif posture == StealthPosture.CRAWLING:
            subject_pool += 2
        elif posture == StealthPosture.HIDING or posture == StealthPosture.HIDDEN:
            subject_pool += 4
        elif posture == StealthPosture.EXPOSED:
            subject_pool = max(1, subject_pool - 1)

        # Environmental modifiers sourced from coordinator (power, weather, room states)
        env_effects = None
        if env and room_name:
            env_effects = env.get_current_modifiers(room_name, game_state)
            observer_pool = ResolutionSystem.adjust_pool(observer_pool, env_effects.observation_pool_modifier)

        # Darkness makes visual spotting harder
        if is_dark:
            subject_pool += 2
            observer_pool = max(1, observer_pool - 2)

        # Noise acts as penalty to subject pool (inverse of stealth) and a boon to observers
        noise_penalty = noise_level // 2
        subject_pool = max(1, subject_pool - noise_penalty)
        observer_pool = ResolutionSystem.adjust_pool(observer_pool, noise_penalty)

        return {
            "observer_pool": observer_pool,
            "subject_pool": subject_pool,
            "env_effects": env_effects,
            "is_frozen": is_frozen,
            "room_name": room_name,
        }

    def get_detection_chance(self, observer, subject, game_state, noise_level=0) -> float:
        """Return an estimated probability of detection for diagnostics/tests."""
        ctx = self._prepare_detection_context(observer, subject, game_state, noise_level)

        # Simple contested-pool heuristic: chance proportional to pool sizes
        visual_ratio = ctx["observer_pool"] / (ctx["observer_pool"] + ctx["subject_pool"])

        thermal_ratio = 0.0
        if ctx["env_effects"] and ctx["env_effects"].heat_detection_enabled and not ctx["is_frozen"]:
            thermal_pool = observer.attributes.get(Attribute.THERMAL, 1) + ctx["env_effects"].thermal_detection_bonus
            thermal_ratio = thermal_pool / (thermal_pool + ctx["subject_pool"])

        # Combine independent visual and thermal chances
        combined = 1 - (1 - visual_ratio) * (1 - thermal_ratio)
        return max(0.0, min(1.0, combined))

    def set_posture(self, subject, posture: StealthPosture):
        """Helper to set stealth posture on a member without requiring imports in tests."""
        subject.stealth_posture = posture
