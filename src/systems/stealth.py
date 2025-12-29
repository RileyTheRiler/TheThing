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

        # Stealth level progression bonus (levels 2 and 4 add +1 each)
        if hasattr(player, 'get_stealth_level_pool_bonus'):
            subject_pool += player.get_stealth_level_pool_bonus()

        # 2. Observer Pool (Infected NPC Perception)
        logic = opponent.attributes.get(Attribute.LOGIC, 1)
        observation = opponent.skills.get(Skill.OBSERVATION, 0)
        observer_pool = logic + observation

        # Station Alert Bonus (all NPCs more vigilant during alert)
        alert_system = getattr(game_state, 'alert_system', None)
        if alert_system and alert_system.is_active:
            observer_pool += alert_system.get_observation_bonus()

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
            "hiding_spot": hiding_spot,
            "suspicion_delta": suspicion_delta,
            "suspicion_level": getattr(opponent, "suspicion_level", 0)
        }
        event_bus.emit(GameEvent(EventType.STEALTH_REPORT, payload))
        
        # Emit Perception Event
        if hasattr(EventType, 'PERCEPTION_EVENT'):
             event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, payload))

        
        # Check for reverse thermal detection (Thing sensing player heat in darkness)
        if player_evaded:
            # Even if visually evaded, Thing might detect by heat
            if self.check_reverse_thermal_detection(opponent, player, game_state):
                player_evaded = False  # Override evasion
                payload["outcome"] = "thermal_detected"
                payload["thermal_detection"] = True

        if not player_evaded:
            # If detected, opponent might attack or reveal
            opponent.detected_player = True  # Set for visual indicator
            thermal_msg = " by heat signature" if payload.get("thermal_detection") else ""
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"{opponent.name} spots you{thermal_msg} in {room}!"
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

        # Heat-based detection when room is dark and not frozen
        thermal_detected = False
        if ctx["is_dark"] and not ctx["is_frozen"]:
            # Get observer's thermal detection pool (includes thermal goggles bonus)
            if hasattr(observer, 'get_thermal_detection_pool'):
                thermal_pool = observer.get_thermal_detection_pool()
            else:
                thermal_pool = observer.attributes.get(Attribute.THERMAL, 2)

            # Environmental thermal bonus (power off gives equipment bonus)
            if ctx["env_effects"] and ctx["env_effects"].heat_detection_enabled:
                thermal_pool += ctx["env_effects"].thermal_detection_bonus

            # Subject's thermal signature (Things run hotter)
            if hasattr(subject, 'get_thermal_signature'):
                subject_thermal = subject.get_thermal_signature()
            else:
                subject_thermal = 2  # Default human thermal

            thermal_pool = max(1, thermal_pool)
            thermal_result = res.roll_check(thermal_pool, game_state.rng)
            # Thermal detection is easier against higher thermal signatures
            thermal_threshold = max(0, subject_result['success_count'] - (subject_thermal - 2))
            thermal_detected = thermal_result['success_count'] >= thermal_threshold

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

        # Station Alert Bonus (all NPCs more vigilant during alert)
        alert_system = getattr(game_state, 'alert_system', None)
        if alert_system and alert_system.is_active:
            observer_pool += alert_system.get_observation_bonus()

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

        # Apply hiding spot modifiers when present
        hiding_spot, cover_bonus, blocks_los = self._hiding_spot_modifiers(getattr(game_state, "station_map", None), subject)
        if cover_bonus and getattr(subject, "stealth_posture", StealthPosture.STANDING) == StealthPosture.HIDING:
            subject_pool += cover_bonus

        # Noise acts as penalty to observer pool as well (harder to spot in loud environments)
        noise_penalty = noise_level // 3
        observer_pool = ResolutionSystem.adjust_pool(observer_pool, -noise_penalty)

        return {
            "observer_pool": max(1, observer_pool),
            "subject_pool": max(1, subject_pool),
            "env_effects": env_effects,
            "is_dark": is_dark,
            "is_frozen": is_frozen,
            "room_name": room_name,
            "cover_bonus": cover_bonus,
            "blocks_los": blocks_los,
        }

    # === VENT MECHANICS CONFIGURATION ===
    VENT_BASE_NOISE = 10        # Echoing noise in metal ducts
    VENT_ENCOUNTER_CHANCE = 0.20  # 20% chance to encounter Thing in vents
    VENT_CRAWL_TURNS = 2        # Takes 2 turns per vent tile movement

    def handle_vent_movement(self, game_state, actor, destination):
        """Enhanced vent crawling with echoing noise, Thing encounters, and danger.

        Features:
        - High base noise (echoes in metal ducts)
        - Sound propagates to adjacent vent nodes
        - Chance to encounter The Thing in confined space
        - Limited escape options when encountered
        """
        rng = getattr(game_state, "rng", None)
        station_map = getattr(game_state, "station_map", None)
        crew = getattr(game_state, "crew", [])
        if not rng or not station_map or not actor:
            return {"encounter": False}

        room = station_map.get_room_name(*destination)

        # Vent noise is louder due to echoing in metal ducts
        base_noise = self.config.get("vent_base_noise", self.VENT_BASE_NOISE) if self.config else self.VENT_BASE_NOISE
        noise_level = max(actor.get_noise_level(), base_noise)

        # Broadcast perception event at current location
        event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, {
            "source": "vent",
            "room": room,
            "location": destination,
            "noise_level": noise_level,
            "game_state": game_state
        }))

        # Sound propagates to adjacent vent nodes (echoing effect)
        adjacent_vents = station_map.get_vent_neighbors(*destination)
        for adj_x, adj_y in adjacent_vents:
            adj_room = station_map.get_room_name(adj_x, adj_y)
            # Reduced noise at adjacent nodes (echo falloff)
            echo_noise = max(noise_level - 3, 5)
            event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, {
                "source": "vent_echo",
                "room": adj_room,
                "location": (adj_x, adj_y),
                "noise_level": echo_noise,
                "game_state": game_state
            }))

        # Check for Thing encounter in the vents
        encounter_chance = self.config.get("vent_encounter_chance", self.VENT_ENCOUNTER_CHANCE) if self.config else self.VENT_ENCOUNTER_CHANCE
        encounter_result = {"encounter": False, "escaped": False, "damage": 0}

        if rng.random_float() < encounter_chance:
            candidates = self._detect_candidates(crew)
            if candidates:
                opponent = rng.choose(candidates)
                encounter_result["encounter"] = True
                encounter_result["opponent"] = opponent

                # Vent encounter is extremely dangerous - limited escape options
                event_bus.emit(GameEvent(EventType.WARNING, {
                    "text": f"DANGER! You come face-to-face with {opponent.name} in the cramped vent!"
                }))

                # Contested roll: Player tries to escape, Thing tries to grab
                res = ResolutionSystem()
                prowess = actor.attributes.get(Attribute.PROWESS, 1) if hasattr(actor, "attributes") else 2
                player_pool = max(1, prowess - 1)  # Cramped space penalty

                thing_prowess = opponent.attributes.get(Attribute.PROWESS, 3) if hasattr(opponent, "attributes") else 3
                thing_pool = thing_prowess + 2  # Advantage in confined space

                player_result = res.roll_check(player_pool, rng)
                thing_result = res.roll_check(thing_pool, rng)

                if player_result['success_count'] > thing_result['success_count']:
                    # Escaped but injured
                    encounter_result["escaped"] = True
                    encounter_result["damage"] = 1
                    event_bus.emit(GameEvent(EventType.MESSAGE, {
                        "text": "You scramble backward, scraping yourself on the duct walls!"
                    }))
                    if hasattr(actor, "take_damage"):
                        actor.take_damage(1)
                else:
                    # Caught - serious damage
                    encounter_result["escaped"] = False
                    encounter_result["damage"] = 3
                    event_bus.emit(GameEvent(EventType.WARNING, {
                        "text": f"{opponent.name} grabs you in the confined space! You take serious wounds!"
                    }))
                    if hasattr(actor, "take_damage"):
                        actor.take_damage(3, game_state=game_state)

                # Emit stealth report for encounter
                payload = {
                    "room": room,
                    "opponent": opponent.name,
                    "opponent_ref": opponent,
                    "player_ref": actor,
                    "game_state": game_state,
                    "outcome": "escaped" if encounter_result["escaped"] else "caught",
                    "vent_encounter": True,
                    "player_successes": player_result['success_count'],
                    "opponent_successes": thing_result['success_count'],
                    "subject_pool": player_pool,
                    "observer_pool": thing_pool
                }
                event_bus.emit(GameEvent(EventType.STEALTH_REPORT, payload))
            else:
                # No infected nearby, just eerie sounds
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": "You hear something skittering in a distant duct..."
                }))

        return encounter_result

    def get_vent_crawl_turns(self) -> int:
        """Return the number of turns required per vent tile movement."""
        return self.config.get("vent_crawl_turns", self.VENT_CRAWL_TURNS) if self.config else self.VENT_CRAWL_TURNS

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

    def check_reverse_thermal_detection(self, infected_npc, player, game_state) -> bool:
        """Check if an infected NPC (The Thing) can detect the player by heat.

        Reverse thermal detection: Things have heightened thermal senses and can
        detect human heat signatures in darkness. Frozen rooms block this.

        Args:
            infected_npc: The infected NPC doing the detecting
            player: The player being detected
            game_state: Current game state

        Returns:
            True if the Thing detects the player's heat signature
        """
        if not getattr(infected_npc, 'is_infected', False):
            return False

        station_map = getattr(game_state, 'station_map', None)
        room_states = getattr(game_state, 'room_states', None)

        if not station_map or not player:
            return False

        # Must be in same location
        if getattr(infected_npc, 'location', None) != getattr(player, 'location', None):
            return False

        room_name = station_map.get_room_name(*player.location)

        # Check room states
        is_dark = room_states.has_state(room_name, RoomState.DARK) if room_states and room_name else False
        is_frozen = room_states.has_state(room_name, RoomState.FROZEN) if room_states and room_name else False

        # Thermal detection only works in darkness, NOT in frozen rooms
        if not is_dark or is_frozen:
            return False

        # The Thing has enhanced thermal senses (+2 base, +3 from infection)
        thing_thermal_pool = 5  # Enhanced Thing senses

        # Human's thermal signature (standard human warmth)
        if hasattr(player, 'get_thermal_signature'):
            human_thermal = player.get_thermal_signature()
        else:
            human_thermal = 2

        # Roll detection
        res = ResolutionSystem()
        rng = getattr(game_state, 'rng', None)
        if not rng:
            return False

        # Player's stealth provides defense
        prowess = player.attributes.get(Attribute.PROWESS, 1) if hasattr(player, 'attributes') else 2
        stealth = player.skills.get(Skill.STEALTH, 0) if hasattr(player, 'skills') else 0
        defense_pool = max(1, prowess + stealth)

        thing_result = res.roll_check(thing_thermal_pool, rng)
        player_result = res.roll_check(defense_pool, rng)

        # Thing needs more successes to detect by heat
        detected = thing_result['success_count'] > player_result['success_count']

        if detected:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"{infected_npc.name} senses your body heat in the darkness!"
            }))

        return detected
