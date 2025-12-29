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

    def _hiding_spot_modifiers(self, station_map, actor):
        """Return hiding metadata and stealth modifiers for the actor's tile."""
        if not station_map or not hasattr(station_map, "get_hiding_spot"):
            return None, 0, False
        spot = station_map.get_hiding_spot(*actor.location)
        if not spot:
            return None, 0, False
        is_hiding = getattr(actor, "stealth_posture", StealthPosture.STANDING) == StealthPosture.HIDING
        if not is_hiding:
            return spot, 0, spot.get("blocks_los", False)
        cover_bonus = spot.get("cover_bonus", 0)
        blocks_los = spot.get("blocks_los", False)
        return spot, cover_bonus, blocks_los
    
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

        # Tile-based hiding modifiers
        hiding_spot, cover_bonus, blocks_los = self._hiding_spot_modifiers(station_map, player)
        if cover_bonus:
            subject_pool += cover_bonus
            observer_pool = max(1, observer_pool - cover_bonus)
        if blocks_los:
            observer_pool = max(1, observer_pool - 1)
        
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
            "observer_pool": observer_pool,
            "hiding_spot": hiding_spot
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

        # Apply hiding spot modifiers when present
        hiding_spot, cover_bonus, blocks_los = self._hiding_spot_modifiers(getattr(game_state, "station_map", None), subject)
        if cover_bonus and getattr(subject, "stealth_posture", StealthPosture.STANDING) == StealthPosture.HIDING:
            subject_pool += cover_bonus
            observer_result_penalty = cover_bonus + (1 if blocks_los else 0)
        else:
            observer_result_penalty = 0
        
        subject_result = res.roll_check(subject_pool, game_state.rng)
        
        if observer_result_penalty:
            observer_result['success_count'] = max(0, observer_result['success_count'] - observer_result_penalty)
        
        # Detected if observer wins
        return observer_result['success_count'] >= subject_result['success_count']
