from typing import Dict, List, Optional
from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, ResolutionSystem, Skill
from core.perception import normalize_perception_payload
from systems.room_state import RoomState
from entities.crew_member import StealthPosture
from systems.dialogue import DialogueSystem

class StealthSystem:
    """
    Handles stealth encounters by reacting to TURN_ADVANCE events.
    Key mechanic: Subject Pool vs Observer Pool contest using ResolutionSystem.
    """

    def __init__(self, design_registry: Optional[DesignBriefRegistry] = None, room_states=None):
        self.design_registry = design_registry or DesignBriefRegistry()
        self.config = self.design_registry.get_brief("stealth")
        self.cooldown = 0
        self.room_states = room_states
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
        room_states = getattr(game_state, "room_states", None) or self.room_states
        
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

        # Quick detection chance gate before rolling dice
        detection_chance = 0.5
        if self.config:
            detection_chance = self.config.get("base_detection_chance", detection_chance)
        mods = None
        if room_states:
            mods = room_states.get_resolution_modifiers(room)
            stealth_mod = getattr(mods, "stealth_detection", 0.0) if mods else 0.0
            detection_chance = max(0.0, detection_chance + float(stealth_mod))

        roll = rng.random_float()
        if roll > detection_chance:
            noise_level = player.get_noise_level() if hasattr(player, "get_noise_level") else 0
            payload = {
                "room": room,
                "location": getattr(player, "location", None),
                "actor": getattr(player, "name", None),
                "opponent": opponent.name,
                "opponent_ref": opponent,
                "player_ref": player,
                "game_state": game_state,
                "outcome": "evaded",
                "player_successes": 0,
                "opponent_successes": 0,
                "subject_pool": 0,
                "observer_pool": 0,
                "noise_level": noise_level,
            }
            event_bus.emit(GameEvent(EventType.STEALTH_REPORT, payload))
            self.cooldown = self.config.get("cooldown_turns", 1) if self.config else 1
            return
        
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
        alert_bonus = 0
        if alert_system and alert_system.is_active:
            alert_bonus = alert_system.get_observation_bonus()
        elif getattr(game_state, "alert_status", "").upper() == "ALERT" and getattr(game_state, "alert_turns_remaining", 0) > 0:
            alert_bonus = 1
        observer_pool += alert_bonus

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
        
        # Enforce minimum pool (guard against mocked values)
        try:
            subject_pool = int(subject_pool)
        except Exception:
            subject_pool = 1

        try:
            observer_pool = int(observer_pool)
        except Exception:
            observer_pool = 1

        subject_pool = max(1, subject_pool)
        observer_pool = max(1, observer_pool)

        # 4. Resolution
        res = ResolutionSystem()
        
        subject_result = ResolutionSystem.roll_check(subject_pool, rng)
        observer_result = ResolutionSystem.roll_check(observer_pool, rng)
        
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
        
        noise_level = player.get_noise_level() if hasattr(player, "get_noise_level") else 0
        payload = {
            "room": room,
            "location": getattr(player, "location", None),
            "actor": getattr(player, "name", None),
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
            "suspicion_level": getattr(opponent, "suspicion_level", 0),
            "noise_level": noise_level,
        }
        event_bus.emit(GameEvent(EventType.STEALTH_REPORT, payload))

        # Emit Perception Event
        if hasattr(EventType, 'PERCEPTION_EVENT'):
             normalized = normalize_perception_payload(payload)
             event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, normalized))

        
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
            
            self._trigger_explain_away(opponent, player, game_state)
        else:
            opponent.detected_player = False
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"You remain unseen by {opponent.name}."
            }))

        self.cooldown = self.config.get("cooldown_turns", 1)

    def evaluate_detection(self, observer, subject, game_state, noise_level=None, alert_bonus: int = 0) -> bool:
        """
        Check if observer detects subject.
        Returns True if detected.
        """
        if noise_level is None:
            noise_level = subject.get_noise_level()

        ctx = self._prepare_detection_context(observer, subject, game_state, noise_level, alert_bonus)

        res = ResolutionSystem()
        subject_result = ResolutionSystem.roll_check(ctx["subject_pool"], game_state.rng)

        # Visual detection
        observer_result = ResolutionSystem.roll_check(ctx["observer_pool"], game_state.rng)
        observer_score = observer_result['success_count']
        if ctx["env_effects"]:
            observer_score = max(0, observer_score + ctx["env_effects"].stealth_detection_modifier)

        visual_detected = observer_score >= subject_result['success_count']

        # Heat-based detection when room is dark and not frozen
        thermal_detected = False
        thermal_bonus = 0
        thermal_context = ctx["env_effects"] or ctx.get("resolution_mods")
        if thermal_context and getattr(thermal_context, "heat_detection_enabled", False):
            thermal_bonus = getattr(thermal_context, "thermal_detection_bonus", 0)

        thermal_allowed = ctx["is_dark"] and not ctx["is_frozen"]

        if thermal_allowed:
            # Get observer's thermal detection pool (includes thermal goggles bonus)
            if hasattr(observer, 'get_thermal_detection_pool'):
                thermal_pool = observer.get_thermal_detection_pool()
            else:
                thermal_pool = observer.attributes.get(Attribute.THERMAL, 2)

            # Environmental/room thermal bonus (power off gives equipment bonus)
            thermal_pool += thermal_bonus

            # Subject's thermal signature (Things run hotter)
            if hasattr(subject, 'get_thermal_signature'):
                subject_thermal = subject.get_thermal_signature()
            else:
                subject_thermal = 2  # Default human thermal

            thermal_pool = max(1, thermal_pool)
            thermal_result = ResolutionSystem.roll_check(thermal_pool, game_state.rng)
            # Thermal detection is easier against higher thermal signatures
            thermal_threshold = max(0, subject_result['success_count'] - max(0, subject_thermal - 2))
            thermal_detected = thermal_result['success_count'] >= thermal_threshold

        if not (visual_detected or thermal_detected) and getattr(observer, "is_infected", False):
            thermal_detected = self.check_reverse_thermal_detection(observer, subject, game_state)

        return visual_detected or thermal_detected

    def _prepare_detection_context(self, observer, subject, game_state, noise_level: int, alert_bonus: int = 0):
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
        system_bonus = alert_system.get_observation_bonus() if alert_system and alert_system.is_active else 0
        status_bonus = 0
        if getattr(game_state, "alert_status", "").upper() == "ALERT" and getattr(game_state, "alert_turns_remaining", 0) > 0:
            status_bonus = max(status_bonus, 1)

        observer_pool += max(system_bonus, alert_bonus, status_bonus)

        prowess = subject.attributes.get(Attribute.PROWESS, 1)
        stealth = subject.skills.get(Skill.STEALTH, 0)
        subject_pool = prowess + stealth

        # Stealth progression perk: bonus dice at higher levels
        if hasattr(subject, "get_stealth_level_pool_bonus"):
            subject_pool += subject.get_stealth_level_pool_bonus()
        
        posture = getattr(subject, "stealth_posture", StealthPosture.STANDING)
        if posture == StealthPosture.CROUCHING:
            subject_pool += 1
        elif posture == StealthPosture.CRAWLING:
            subject_pool += 2
        elif posture == StealthPosture.HIDING:
            subject_pool += 4

        # Environmental modifiers sourced from coordinator (power, weather, room states)
        env_effects = None
        if env and room_name:
            env_effects = env.get_current_modifiers(room_name, game_state)
            observer_pool = ResolutionSystem.adjust_pool(observer_pool, env_effects.observation_pool_modifier)

        has_resolution_mods = hasattr(room_states, "get_resolution_modifiers")
        resolution_mods = room_states.get_resolution_modifiers(room_name) if has_resolution_mods and room_name else None

        # Darkness makes visual spotting harder
        if is_dark:
            subject_pool += 2
            observer_pool = max(1, observer_pool - 2)

        # Noise acts as penalty to subject pool (inverse of stealth) and a boon to observers
        noise_penalty = noise_level // 2
        subject_pool = max(1, subject_pool - noise_penalty)
        observer_pool = max(1, observer_pool + noise_level)

        # Apply hiding spot modifiers when present
        hiding_spot, cover_bonus, blocks_los = self._hiding_spot_modifiers(getattr(game_state, "station_map", None), subject)
        if cover_bonus and getattr(subject, "stealth_posture", StealthPosture.STANDING) == StealthPosture.HIDING:
            subject_pool += cover_bonus
            observer_result_penalty = cover_bonus + (1 if blocks_los else 0)
        else:
            observer_result_penalty = 0

        # Return context dict for use by detection methods
        return {
            "subject_pool": subject_pool,
            "observer_pool": observer_pool,
            "is_dark": is_dark,
            "is_frozen": is_frozen,
            "env_effects": env_effects,
            "resolution_mods": resolution_mods,
            "observer_result_penalty": observer_result_penalty,
            "room_name": room_name
        }

    # === VENT MECHANICS CONFIGURATION ===
    VENT_BASE_NOISE = 14        # Louder echoing noise in metal ducts
    VENT_ENCOUNTER_CHANCE = 0.20  # 20% chance to encounter Thing in vents (configurable)
    VENT_CRAWL_TURNS = 4        # Takes 4 turns per vent tile movement (slower, riskier)

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
        vent_noise_bonus = self.config.get("vent_noise_bonus", 5) if self.config else 5
        noise_level = max(actor.get_noise_level() + vent_noise_bonus, base_noise + vent_noise_bonus)

        # Broadcast perception event at current location
        vent_payload = normalize_perception_payload({
            "source": "vent",
            "room": room,
            "location": destination,
            "target_location": destination,
            "noise_level": noise_level,
            "intensity": noise_level,
            "priority_override": 3,
            "linger_turns": 3,
            "threat": "vent_close_quarters",
            "game_state": game_state,
            "actor_ref": actor,
            "actor": getattr(actor, "name", None),
        })
        event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, vent_payload))

        # Sound propagates to adjacent vent nodes (echoing effect)
        adjacent_vents = []
        if hasattr(station_map, "get_vent_neighbors_with_rooms"):
            adjacent_vents = station_map.get_vent_neighbors_with_rooms(*destination)
        else:
            adjacent_vents = [{"coord": coord, "room": station_map.get_room_name(*coord)} for coord in station_map.get_vent_neighbors(*destination)]

        for neighbor in adjacent_vents:
            adj_x, adj_y = neighbor["coord"]
            adj_room = neighbor["room"]
            # Reduced noise at adjacent nodes (echo falloff)
            echo_noise = max(noise_level - 3, base_noise)
            echo_noise = max(noise_level - 3, 5)
            echo_payload = normalize_perception_payload({
                "source": "vent_echo",
                "room": adj_room,
                "location": (adj_x, adj_y),
                "target_location": (adj_x, adj_y),
                "noise_level": echo_noise,
                "intensity": echo_noise,
                "priority_override": 1,
                "linger_turns": 2,
                "threat": "vent_close_quarters",
                "game_state": game_state,
                "actor_ref": actor,
                "actor": getattr(actor, "name", None),
            })
            event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, echo_payload))

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
                    "location": destination,
                    "actor": getattr(actor, "name", None),
                    "opponent": opponent.name,
                    "opponent_ref": opponent,
                    "player_ref": actor,
                    "game_state": game_state,
                    "outcome": "escaped" if encounter_result["escaped"] else "caught",
                    "vent_encounter": True,
                    "player_successes": player_result['success_count'],
                    "opponent_successes": thing_result['success_count'],
                    "subject_pool": player_pool,
                    "observer_pool": thing_pool,
                    "noise_level": noise_level,
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
        if ctx["is_dark"] and not ctx["is_frozen"]:
            thermal_bonus = 0
            thermal_context = ctx["env_effects"] or ctx.get("resolution_mods")
            if thermal_context and getattr(thermal_context, "heat_detection_enabled", False):
                thermal_bonus = getattr(thermal_context, "thermal_detection_bonus", 0)

            if hasattr(observer, 'get_thermal_detection_pool'):
                thermal_pool = observer.get_thermal_detection_pool()
            else:
                thermal_pool = observer.attributes.get(Attribute.THERMAL, 1)

            thermal_pool += thermal_bonus
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
        if hasattr(infected_npc, "get_thermal_detection_pool"):
            thing_thermal_pool = infected_npc.get_thermal_detection_pool()
        else:
            thing_thermal_pool = max(5, infected_npc.attributes.get(Attribute.THERMAL, 2))

        thermal_bonus = 0
        if room_states and hasattr(room_states, "get_resolution_modifiers"):
            mods = room_states.get_resolution_modifiers(room_name)
            if getattr(mods, "heat_detection_enabled", False):
                thermal_bonus = getattr(mods, "thermal_detection_bonus", 0)
        thing_thermal_pool += thermal_bonus

        # Check if player has thermal blanket equipped/in inventory
        thermal_blanket_penalty = self._get_thermal_blanket_bonus(player)
        if thermal_blanket_penalty > 0:
            thing_thermal_pool = max(1, thing_thermal_pool - thermal_blanket_penalty)

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

    def _get_thermal_blanket_bonus(self, player) -> int:
        """Check if player has a thermal blanket and return its masking bonus.

        Thermal blankets mask heat signatures, making thermal detection harder.
        Returns the effect_value of the thermal blanket (typically 3).
        """
        if not hasattr(player, 'inventory'):
            return 0

        for item in player.inventory:
            # Check for masks_heat effect (thermal blanket)
            effect = getattr(item, 'effect', None)
            if effect == 'masks_heat':
                # Check if item has uses remaining
                uses = getattr(item, 'uses', -1)
                if uses != 0:  # -1 means infinite, >0 means has uses
                    # Return the effect value (how much it masks heat)
                    return getattr(item, 'effect_value', 3)

        return 0
