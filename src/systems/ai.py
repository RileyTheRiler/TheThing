from typing import TYPE_CHECKING, Tuple, Optional, List, Dict
from core.resolution import Attribute, Skill
from core.event_system import event_bus, EventType, GameEvent
from systems.pathfinding import pathfinder
from systems.ai_cache import AICache

if TYPE_CHECKING:
    from engine import GameState, CrewMember, StationMap

class AISystem:
    """
    Handles AI logic for CrewMembers.
    Decouples logic from the CrewMember data class.
    """
    
    # Action costs (complexity units)
    COST_ASTAR = 5
    COST_PATH_CACHE = 1
    COST_PERCEPTION = 2

    def __init__(self):
        self.cache: Optional[AICache] = None
        self.budget_limit = 0
        self.budget_spent = 0
        self.exhaustion_count = 0  # Track how many times budget was denied
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.subscribe(EventType.PERCEPTION_EVENT, self.on_perception_event)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.unsubscribe(EventType.PERCEPTION_EVENT, self.on_perception_event)

    def on_turn_advance(self, event):
        game_state = event.payload.get("game_state")
        if game_state:
            self.update(game_state)

    def on_perception_event(self, event):
        """React to PERCEPTION_EVENT emissions from StealthSystem."""
        payload = event.payload
        if not payload:
            return
        
        # Extract perception data
        game_state = payload.get("game_state")
        observer = payload.get("opponent_ref")
        player = payload.get("player_ref")
        outcome = payload.get("outcome") # "detected" or "evaded"
        player_successes = payload.get("player_successes", 0)
        opponent_successes = payload.get("opponent_successes", 0)
        suspicion_delta = payload.get("suspicion_delta", 0)
        
        # Diagnostics
        event_bus.emit(GameEvent(EventType.DIAGNOSTIC, {
            "type": "AI_PERCEPTION_HOOK",
            "room": payload.get("room"),
            "observer": observer.name if hasattr(observer, 'name') else "Unknown",
            "outcome": outcome,
            "margin": abs(player_successes - opponent_successes)
        }))
        
        # If we have full context, trigger reactions
        if game_state and observer and player:
            # Apply suspicion raised by the stealth resolution
            if suspicion_delta:
                self._apply_suspicion(observer, suspicion_delta, game_state, reason="stealth_check")
            if getattr(player, "location_hint_active", False):
                self._apply_suspicion(observer, 1, game_state, reason="location_hint")

            if outcome == "detected":
                self._react_to_detection(observer, player, game_state)
            elif outcome == "evaded":
                # Check for "Almost Detected" (Margin < 2)
                margin = player_successes - opponent_successes
                if margin < 2:
                    self._react_to_suspicion(observer, player, game_state)
                else:
                    self._react_to_evasion(observer, player, game_state)
    
    def _react_to_detection(self, observer: 'CrewMember', player: 'CrewMember', game_state: 'GameState'):
        """NPC reacts to detecting the player."""
        # Set alert state
        observer.detected_player = True
        observer.investigating = False # Already found
        
        # Broadcast alert to nearby NPCs
        self._broadcast_alert(observer, player.location, game_state)
        self._apply_suspicion(observer, 2, game_state, reason="direct_detection")
        
        # Emit reaction event
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"{observer.name} is now actively searching for you!"
        }))

    def _react_to_suspicion(self, observer: 'CrewMember', player: 'CrewMember', game_state: 'GameState'):
        """NPC reacts to almost detecting the player - investigates location."""
        observer.investigating = True
        observer.last_known_player_location = player.location
        self._apply_suspicion(observer, 2, game_state, reason="near_detection")
        
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"{observer.name} pauses, looking suspicious... \"What was that?\""
        }))

    def _react_to_evasion(self, observer: 'CrewMember', player: 'CrewMember', game_state: 'GameState'):
        """NPC reacts to player evading detection completely."""
        # Increase suspicion slightly
        self._apply_suspicion(observer, 1, game_state, reason="evasion")

    def _apply_suspicion(self, observer: 'CrewMember', amount: int, game_state: 'GameState', reason: str = ""):
        """Adjust suspicion and update state transitions."""
        if not hasattr(observer, "increase_suspicion"):
            return
        current_turn = getattr(game_state, "turn", 0)
        observer.increase_suspicion(amount, turn=current_turn)
        self._update_suspicion_state(observer, game_state.player, game_state, reason=reason)

    def _update_suspicion_state(self, observer: 'CrewMember', player: 'CrewMember', game_state: 'GameState', reason: str = ""):
        """Evaluate suspicion thresholds and trigger dialogue prompts."""
        thresholds = getattr(observer, "suspicion_thresholds", {"question": 4, "follow": 8})
        prev_state = getattr(observer, "suspicion_state", "idle")
        level = getattr(observer, "suspicion_level", 0)

        new_state = "idle"
        if level >= thresholds.get("follow", 8):
            new_state = "follow"
        elif level >= thresholds.get("question", 4):
            new_state = "question"

        observer.suspicion_state = new_state

        if new_state == prev_state:
            return

        dialogue_payload = {
            "speaker": observer.name,
            "text": "",
            "prompt": "FOLLOW_UP",
            "target": player.name
        }

        if new_state == "question":
            dialogue_payload["text"] = f"{player.name}, what are you doing here?"
            dialogue_payload["prompt"] = "QUESTION_PLAYER"
            event_bus.emit(GameEvent(EventType.DIALOGUE, dialogue_payload))
        elif new_state == "follow":
            dialogue_payload["text"] = f"{observer.name} starts shadowing you closely."
            dialogue_payload["prompt"] = "FOLLOW_PLAYER"
            event_bus.emit(GameEvent(EventType.DIALOGUE, dialogue_payload))
        elif prev_state in ["question", "follow"] and new_state == "idle":
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"{observer.name} seems less focused on you now."
            }))

    def _broadcast_alert(self, alerter: 'CrewMember', player_location: Tuple[int, int], game_state: 'GameState'):
        """Broadcast alert to nearby NPCs about player location."""
        alerter_room = game_state.station_map.get_room_name(*alerter.location)
        
        # Find NPCs in same or adjacent rooms
        for npc in game_state.crew:
            if npc == alerter or npc == game_state.player or not npc.is_alive:
                continue
            
            npc_room = game_state.station_map.get_room_name(*npc.location)
            
            # Alert NPCs in same room
            if npc_room == alerter_room:
                npc.alerted_to_player = True
                npc.last_known_player_location = player_location

    def update(self, game_state: 'GameState'):
        """Updates AI for all crew members with per-turn caching and action budget."""
        # Initialize turn-level cache and budget
        self.cache = AICache(game_state)
        self.budget_limit = 15 + (5 * len(game_state.crew))
        self.budget_spent = 0
        self.exhaustion_count = 0
        
        for member in game_state.crew:
            if member != game_state.player:
                self.update_member_ai(member, game_state)
        
        if self.exhaustion_count > 0:
            from core.event_system import GameEvent, EventType, event_bus
            event_bus.emit(GameEvent(EventType.DIAGNOSTIC, {
                "type": "AI_BUDGET_EXHAUSTED",
                "exhaustion_count": self.exhaustion_count,
                "total_budget": self.budget_limit,
                "turn": game_state.turn
            }))

    def _request_budget(self, amount: int) -> bool:
        """Check if action is within budget. Returns True if allowed."""
        if self.budget_spent + amount <= self.budget_limit:
            self.budget_spent += amount
            return True
        self.exhaustion_count += 1
        return False

    def update_member_ai(self, member: 'CrewMember', game_state: 'GameState'):
        """
        Agent 2/8: NPC AI Logic.
        Priority: Thing AI > Lynch Mob > Investigation > Schedule > Wander
        """
        if not member.is_alive:
            return
        current_turn = getattr(game_state, "turn", 0)
        if hasattr(member, "decay_suspicion"):
            member.decay_suspicion(current_turn)
        if hasattr(member, "suspicion_state"):
            self._update_suspicion_state(member, game_state.player, game_state)

        # 0. PRIORITY: Thing AI (Agent 3) - Revealed Things actively hunt
        if getattr(member, 'is_revealed', False):
            self._update_thing_ai(member, game_state)
            return

        # Suspicion-driven behaviors (question or follow the player)
        if getattr(member, "suspicion_state", "idle") == "follow":
            member.last_known_player_location = game_state.player.location
            self._pursue_player(member, game_state)
            return
        elif getattr(member, "suspicion_state", "idle") == "question":
            if self._request_budget(self.COST_PERCEPTION):
                self._question_player(member, game_state)
            # still allow other logic if questioning but not blocked

        # Passive perception hook: if an NPC spots the player, move toward them
        if self._request_budget(self.COST_PERCEPTION):
            if self._perceive_player(member, game_state):
                self._pursue_player(member, game_state)
                return
                
        # 1. PRIORITY: Investigation (Suspicious/Almost Detected)
        if getattr(member, 'investigating', False) and hasattr(member, 'last_known_player_location'):
            target_loc = member.last_known_player_location
            if member.location == target_loc:
                # Arrived at investigation spot
                member.investigating = False
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": f"{member.name} checks the area but finds nothing."
                }))
            else:
                # Move toward investigation spot
                self._pathfind_step(member, target_loc[0], target_loc[1], game_state)
                return

        # 2. PRIORITY: Lynch Mob Hunting (Agent 2)
        if game_state.lynch_mob.active_mob and game_state.lynch_mob.target:
            target = game_state.lynch_mob.target
            if target != member and target.is_alive:
                # Mark as part of lynch mob for visual indicator
                member.in_lynch_mob = True
                member.target_room = game_state.station_map.get_room_name(*target.location)
                # Move toward the lynch target
                tx, ty = target.location
                self._pathfind_step(member, tx, ty, game_state)
                return
        else:
            member.in_lynch_mob = False

        # 3. Check Schedule
        # Schedule entries: {"start": 8, "end": 20, "room": "Rec Room"}
        current_hour = game_state.time_system.hour
        destination = None
        for entry in member.schedule:
            start = entry.get("start", 0)
            end = entry.get("end", 24)
            room = entry.get("room")

            # Handle wrap-around schedules (e.g., 20:00 to 08:00)
            if start < end:
                if start <= current_hour < end:
                    destination = room
                    break
            else: # Wrap around midnight
                if current_hour >= start or current_hour < end:
                    destination = room
                    break

        if destination:
            # Move towards destination room
            target_pos = game_state.station_map.rooms.get(destination)
            if target_pos:
                tx, ty, _, _ = target_pos
                self._pathfind_step(member, tx, ty, game_state)
                return

        # 4. Idling / Wandering
        if game_state.rng.random_float() < 0.3:
            dx = game_state.rng.choose([-1, 0, 1])
            dy = game_state.rng.choose([-1, 0, 1])
            member.move(dx, dy, game_state.station_map)

    def _update_thing_ai(self, member: 'CrewMember', game_state: 'GameState'):
        """
        AI behavior for revealed Things.
        - Actively hunt humans.
        - Ambush in vents/dark rooms if player is nearby but not visible.
        """
        rng = game_state.rng

        # Find nearest living human
        humans = [m for m in game_state.crew
                  if m.is_alive and not getattr(m, 'is_infected', False) and m != member]

        if not humans:
            # No humans left, wander aimlessly
            dx = rng.choose([-1, 0, 1])
            dy = rng.choose([-1, 0, 1])
            member.move(dx, dy, game_state.station_map)
            return

        # Find closest human
        closest = min(humans, key=lambda h: abs(h.location[0] - member.location[0]) +
                                            abs(h.location[1] - member.location[1]))
        dist_to_human = abs(closest.location[0] - member.location[0]) + abs(closest.location[1] - member.location[1])

        # Check if in same location - ATTACK!
        if closest.location == member.location:
            self._thing_attack(member, closest, game_state)
            return

        # AMBUSH BEHAVIOR
        # If human is somewhat close (distance < 5) but not adjacent (distance > 1), try to ambush
        can_see_human = dist_to_human < 3 # Simplified LOS
        
        if 1 < dist_to_human < 5 and not can_see_human:
             # Look for ambush spot (Dark room or Vent)
             current_room = game_state.station_map.get_room_name(*member.location)
             is_ambush_spot = False
             
             # Check if current room is suitable (Dark or has a Vent)
             if hasattr(game_state, 'room_states'):
                  if game_state.room_states.has_state(current_room, "DARK"):
                      is_ambush_spot = True
             
             if not is_ambush_spot and hasattr(game_state.station_map, "is_at_vent"):
                  if game_state.station_map.is_at_vent(*member.location):
                      is_ambush_spot = True
             
             if is_ambush_spot:
                 # WAIT/AMBUSH
                 if rng.random_float() < 0.7:
                     # 70% chance to hold position and wait for player to come closer
                     return 

        # Default: Move toward closest human
        tx, ty = closest.location
        self._pathfind_step(member, tx, ty, game_state)

    def _thing_attack(self, attacker: 'CrewMember', target: 'CrewMember', game_state: 'GameState'):
        """The Thing attacks a human target."""
        rng = game_state.rng

        # Thing gets bonus attack dice (representing its alien nature)
        thing_attack_bonus = 3
        attack_pool = attacker.attributes.get(Attribute.PROWESS, 2) + thing_attack_bonus
        attack_result = rng.calculate_success(attack_pool)

        # Target defends
        defense_pool = target.attributes.get(Attribute.PROWESS, 1) + target.skills.get(Skill.MELEE, 0)
        defense_result = rng.calculate_success(defense_pool)

        thing_name = f"The-Thing-That-Was-{attacker.name}"

        if attack_result['success_count'] > defense_result['success_count']:
            # Hit! Deal damage
            net_hits = attack_result['success_count'] - defense_result['success_count']
            damage = 2 + net_hits  # Base Thing damage + net hits
            died = target.take_damage(damage, game_state=game_state)

            event_bus.emit(GameEvent(EventType.COMBAT_LOG, {
                "attacker": thing_name,
                "target": target.name,
                "action": "ATTACKS",
                "damage": damage,
                "result": "KILLED" if died else "HIT"
            }))

            # Chance to infect on hit (grapple attack)
            if not died and rng.random_float() < 0.3:
                target.is_infected = True
                event_bus.emit(GameEvent(EventType.WARNING, {
                    "text": f"{target.name} has been INFECTED during the attack!"
                }))
        else:
            event_bus.emit(GameEvent(EventType.COMBAT_LOG, {
                "attacker": thing_name,
                "target": target.name,
                "action": "lunges at",
                "result": "MISSES"
            }))

    def _perceive_player(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """Use the StealthSystem detection logic as an AI hook."""
        stealth = getattr(game_state, "stealth_system", None)
        player = getattr(game_state, "player", None)
        station_map = getattr(game_state, "station_map", None)
        if not stealth or not player or not station_map:
            return False
        if member == player or not player.is_alive:
            return False

        member_room = game_state.station_map.get_room_name(*member.location)
        player_room = self.cache.player_room if self.cache else game_state.station_map.get_room_name(*player.location)
        
        if member_room != player_room:
            return False

        noise = self.cache.player_noise if self.cache else player.get_noise_level()
        # Use cached visibility modifier if available
        vis_mod = self.cache.get_visibility_modifier(player_room, game_state) if self.cache else None
        
        # We need a small update to StealthSystem to accept vis_mod, or just pass normal
        detected = stealth.evaluate_detection(member, player, game_state, noise_level=noise)
        if detected and hasattr(member, "add_knowledge_tag"):
            member.add_knowledge_tag(f"Spotted {player.name} in {player_room}")
        return detected

    def _pathfind_step(self, member: 'CrewMember', target_x: int, target_y: int, game_state: 'GameState'):
        """Take one step toward target using A* pathfinding with cache and budget."""
        goal = (target_x, target_y)
        station_map = game_state.station_map
        current_turn = game_state.turn

        # 1. Budget check for pathfinding
        # Check cache first to determine cost
        cache_key = (member.location, goal)
        use_astar = True
        if hasattr(pathfinder, '_path_cache') and cache_key in pathfinder._path_cache:
            use_astar = False

        cost = self.COST_ASTAR if use_astar else self.COST_PATH_CACHE
        
        dx, dy = 0, 0
        if self._request_budget(cost):
            # Try A* pathfinding
            dx, dy = pathfinder.get_move_delta(member.location, goal, station_map, current_turn)
        else:
            # Budget exhausted - fall back to greedy movement (0 cost)
            dx = 1 if target_x > member.location[0] else -1 if target_x < member.location[0] else 0
            dy = 1 if target_y > member.location[1] else -1 if target_y < member.location[1] else 0

        # Check for barricades at destination
        new_x = member.location[0] + dx
        new_y = member.location[1] + dy

        if station_map.is_walkable(new_x, new_y):
            target_room = station_map.get_room_name(new_x, new_y)
            current_room = station_map.get_room_name(*member.location)

            if hasattr(game_state, 'room_states') and game_state.room_states.is_entry_blocked(target_room) and target_room != current_room:
                if getattr(member, 'is_revealed', False):
                    # Revealed Things try to break barricades
                    success, msg, _ = game_state.room_states.attempt_break_barricade(
                        target_room, member, game_state.rng, is_thing=True
                    )
                    if not success:
                        return  # Can't move this turn
                    # else fall through to move
                else:
                    # Regular NPCs respect barricades
                    return

        member.move(dx, dy, station_map)

    def _pursue_player(self, member: 'CrewMember', game_state: 'GameState'):
        """Move one step toward the player when detected via perception."""
        player_loc = self.cache.player_location if self.cache else game_state.player.location
        self._pathfind_step(member, player_loc[0], player_loc[1], game_state)

    def _question_player(self, member: 'CrewMember', game_state: 'GameState'):
        """
        Move toward the player and issue a questioning dialogue when nearby.
        """
        player = game_state.player
        member_room = game_state.station_map.get_room_name(*member.location)
        player_room = game_state.station_map.get_room_name(*player.location)

        if member_room == player_room:
            event_bus.emit(GameEvent(EventType.DIALOGUE, {
                "speaker": member.name,
                "target": player.name,
                "text": f"{player.name}, I have some questions for you.",
                "prompt": "QUESTION_PLAYER"
            }))
            member.last_known_player_location = player.location
        else:
            self._pursue_player(member, game_state)
