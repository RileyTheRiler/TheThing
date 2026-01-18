from typing import TYPE_CHECKING, Tuple, Optional, List, Dict, Any
from core.resolution import Attribute, Skill
from core.event_system import event_bus, EventType, GameEvent
from core.perception import normalize_perception_payload
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
    SEARCH_TURNS = 12  # Extended duration for broader sweeps
    SEARCH_SPIRAL_RADIUS = 3  # Maximum tiles to expand search radius
    SECURITY_CHECK_INTERVAL = 6
    SECURITY_INVESTIGATION_WINDOW = 12

    def __init__(self):
        self.cache: Optional[AICache] = None
        self.budget_limit = 0
        self.budget_spent = 0
        self.exhaustion_count = 0  # Track how many times budget was denied
        self.alert_speed_bonus = 0
        self.alert_context: Dict[str, Any] = {"active": False, "observation_bonus": 0, "speed_multiplier": 1}
        self.alert_speed_bonus = 0
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.subscribe(EventType.PERCEPTION_EVENT, self.on_perception_event)
        self.security_roles = {"commander", "radio op"}

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.unsubscribe(EventType.PERCEPTION_EVENT, self.on_perception_event)

    def on_turn_advance(self, event):
        game_state = event.payload.get("game_state")
        if game_state:
            self.update(game_state)

    def on_perception_event(self, event):
        """React to PERCEPTION_EVENT emissions from StealthSystem."""
        payload = normalize_perception_payload(event.payload)
        if not payload:
            return
        if self._handle_vent_noise_ping(payload):
            return

        # Noise/distraction payloads (no player reference, direct coordinates)
        if payload.get("target_location") and not payload.get("player_ref"):
            self._handle_investigation_ping(payload)
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
            "location": payload.get("location"),
            "observer": observer.name if hasattr(observer, 'name') else "Unknown",
            "actor": payload.get("actor"),
            "outcome": outcome,
            "severity": payload.get("severity"),
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
        room = self._record_last_seen(observer, player.location, game_state)
        self._enter_search_mode(observer, player.location, room, game_state)
        
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
        observer.investigation_goal = player.location
        observer.investigation_priority = max(getattr(observer, "investigation_priority", 0), 2)
        observer.investigation_expires = game_state.turn + 3
        observer.investigation_source = "suspicion"
        self._record_last_seen(observer, player.location, game_state)
        observer.suspicion_level = 5 # Moderate suspicion
        self._apply_suspicion(observer, 2, game_state, reason="near_detection")
        
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"{observer.name} pauses, looking suspicious... \"What was that?\""
        }))

    def _react_to_evasion(self, observer: 'CrewMember', player: 'CrewMember', game_state: 'GameState'):
        """NPC reacts to player evading detection completely."""
        # Increase suspicion slightly
        self._apply_suspicion(observer, 1, game_state, reason="evasion")

    def _is_security_officer(self, member: 'CrewMember') -> bool:
        """Return True if this NPC should respond to security console alerts."""
        role = getattr(member, "role", "").lower()
        return role in self.security_roles

    def _apply_suspicion(self, observer: 'CrewMember', amount: int, game_state: 'GameState', reason: str = ""):
        """Adjust suspicion and update state transitions."""
        if not hasattr(observer, "increase_suspicion"):
            return
        current_turn = getattr(game_state, "turn", 0)
        observer.increase_suspicion(amount, turn=current_turn)
        self._update_suspicion_state(observer, game_state.player, game_state, reason=reason)

    def _update_suspicion_state(self, observer: 'CrewMember', player: 'CrewMember', game_state: 'GameState', reason: str = ""):
        """Evaluate suspicion thresholds and trigger dialogue prompts."""
        # Coordinating infected remain locked to that behavior until cleared.
        if getattr(observer, "suspicion_state", "idle") == "coordinating":
            return
        # Coordination overrides standard suspicion transitions to keep focus on the ambush
        if getattr(observer, "coordinating_ambush", False) and getattr(observer, "is_infected", False):
            observer.suspicion_state = "coordinating"
            return

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

        # If alerter is infected, also broadcast to other infected for coordination
        if getattr(alerter, 'is_infected', False) and not getattr(alerter, 'is_revealed', False):
            self._broadcast_infected_alert(alerter, player_location, game_state)

    def _broadcast_infected_alert(self, alerter: 'CrewMember', player_location: Tuple[int, int], game_state: 'GameState'):
        """Broadcast coordination signal to other infected NPCs for pincer movement."""
        station_map = game_state.station_map
        alerter_room = station_map.get_room_name(*alerter.location)

        # Find other infected NPCs that can coordinate
        infected_allies = []
        for npc in game_state.crew:
            if npc == alerter or npc == game_state.player or not npc.is_alive:
                continue
            if not getattr(npc, 'is_infected', False):
                continue
            if getattr(npc, 'is_revealed', False):
                continue  # Revealed Things act independently

            # Check proximity - must be in same room or adjacent rooms
            npc_room = station_map.get_room_name(*npc.location)
            adjacent_rooms = station_map.get_connections(alerter_room)

            if npc_room == alerter_room or npc_room in adjacent_rooms:
                infected_allies.append(npc)

        if not infected_allies:
            return  # No allies to coordinate with

        # Calculate flanking positions for each ally using the pathfinder to ensure opposite approach vectors
        flank_positions = self._calculate_flanking_positions(
            player_location, alerter.location, infected_allies, station_map, current_turn=getattr(game_state, "turn", 0)
        )

        # Assign flanking positions to allies
        for i, ally in enumerate(infected_allies):
            flank_pos = flank_positions[i] if i < len(flank_positions) else player_location
            ally.coordinating_ambush = True
            ally.ambush_target_location = player_location
            ally.flank_position = flank_pos
            ally.coordination_leader = alerter.name
            ally.coordination_turns_remaining = 5  # Coordination expires after 5 turns
            ally.suspicion_state = "coordinating"

        # Alerter also enters coordination mode (approaches directly)
        alerter.coordinating_ambush = True
        alerter.ambush_target_location = player_location
        alerter.flank_position = None  # Leader approaches directly
        alerter.coordination_leader = alerter.name
        alerter.coordination_turns_remaining = 5
        alerter.suspicion_state = "coordinating"

        # Emit coordination event
        event_bus.emit(GameEvent(EventType.INFECTED_COORDINATION, {
            "leader": alerter.name,
            "allies": [a.name for a in infected_allies],
            "target_location": player_location,
            "room": alerter_room
        }))

        # Subtle hint to player (something feels wrong)
        if len(infected_allies) >= 1:
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": "You sense movement in the shadows... multiple presences converging."
            }))

    def _calculate_flanking_positions(self, target: Tuple[int, int], leader_pos: Tuple[int, int],
                                       allies: List['CrewMember'], station_map: 'StationMap', current_turn: int = 0) -> List[Tuple[int, int]]:
        """Calculate optimal flanking positions around a target for pincer movement.

        Positions allies on opposite sides of the target from the leader while using the pathfinder
        to prefer routes that actually connect to the destination.
        """
        tx, ty = target
        lx, ly = leader_pos

        # Calculate normalized direction from leader to target
        dx = tx - lx
        dy = ty - ly

        # Flanking positions are perpendicular and opposite to leader's approach
        flank_offsets = [
            (-dy, dx),   # 90 degrees left
            (dy, -dx),   # 90 degrees right
            (-dx, -dy),  # Opposite (behind target from leader's perspective)
            (-dy - 1, dx + 1),
            (dy + 1, -dx - 1),
        ]

        # Normalize offsets to reasonable distance (2-4 tiles from target)
        normalized_offsets = []
        for offset_x, offset_y in flank_offsets:
            if offset_x != 0:
                offset_x = 3 if offset_x > 0 else -3
            if offset_y != 0:
                offset_y = 3 if offset_y > 0 else -3
            normalized_offsets.append((offset_x, offset_y))

        used_positions = set()
        positions: List[Tuple[int, int]] = []
        for ally in allies:
            best_pos = None
            best_len = None

            for offset_x, offset_y in normalized_offsets:
                flank_x = tx + offset_x
                flank_y = ty + offset_y

                if not station_map.is_walkable(flank_x, flank_y):
                    continue
                if (flank_x, flank_y) in used_positions:
                    continue

                path = pathfinder.find_path(ally.location, (flank_x, flank_y), station_map, current_turn)
                if not path:
                    continue

                path_len = len(path)
                if best_pos is None or path_len < best_len:
                    best_pos = (flank_x, flank_y)
                    best_len = path_len

            if best_pos:
                used_positions.add(best_pos)
                positions.append(best_pos)
            else:
                # Fallback: converge directly on target if no flank is reachable
                positions.append(target)
        def _normalize(val: int) -> int:
            if val > 0:
                return 1
            if val < 0:
                return -1
            return 0

        dir_x = _normalize(dx)
        dir_y = _normalize(dy)

        # Primary offsets: opposite side first, then perpendicular lanes
        base_offsets = [
            (-dir_x * 3, -dir_y * 3),  # Directly opposite the leader's approach
            (-dir_y * 3, dir_x * 3),   # Perpendicular left
            (dir_y * 3, -dir_x * 3),   # Perpendicular right
            (-dir_x * 2, -dir_y * 2),  # Closer opposite position
            (-dir_y * 2, dir_x * 2),   # Closer perpendicular
            (dir_y * 2, -dir_x * 2),
        ]

        positions: List[Tuple[int, int]] = []
        tested_positions = set()
        for ally in allies:
            if len(positions) >= len(allies):
                break

            # Try offsets in priority order until we find a reachable flank for this ally
            for offset_x, offset_y in base_offsets:
                flank_x = tx + offset_x
                flank_y = ty + offset_y
                candidate = (flank_x, flank_y)

                if candidate in tested_positions:
                    continue
                if candidate == target:
                    continue
                tested_positions.add(candidate)

                # Ensure position is walkable and reachable from this ally
                if not station_map.is_walkable(flank_x, flank_y):
                    continue

                path = pathfinder.find_path(ally.location, candidate, station_map, current_turn)
                if path:
                    positions.append(candidate)
                    break

                # Try nearby adjustments if primary spot is not reachable
                for adj_x, adj_y in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    alt_x, alt_y = flank_x + adj_x, flank_y + adj_y
                    if not station_map.is_walkable(alt_x, alt_y):
                        continue
                    alt_candidate = (alt_x, alt_y)
                    if alt_candidate in tested_positions:
                        continue
                    tested_positions.add(alt_candidate)
                    path = pathfinder.find_path(ally.location, alt_candidate, station_map, current_turn)
                    if path:
                        positions.append(alt_candidate)
                        break

                if len(positions) >= len(allies):
                    break

        return positions

    def _execute_coordinated_ambush(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """Execute coordinated pincer movement for infected NPCs.

        Returns True if the NPC took a coordination action this turn.
        """
        if getattr(member, "suspicion_state", "idle") != "coordinating":
            member.suspicion_state = "coordinating"
        member.suspicion_state = "coordinating"

        # Decay coordination timer
        if member.coordination_turns_remaining > 0:
            member.coordination_turns_remaining -= 1

        # Check if coordination has expired
        if member.coordination_turns_remaining <= 0:
            self._clear_coordination(member)
            return False

        player = game_state.player
        player_loc = player.location

        # Update target location if player has moved significantly
        if member.ambush_target_location:
            old_target = member.ambush_target_location
            dist_to_old = abs(player_loc[0] - old_target[0]) + abs(player_loc[1] - old_target[1])
            if dist_to_old > 3:
                # Player moved too far, update ambush target
                member.ambush_target_location = player_loc
                # Recalculate flank position if this is not the leader
                if member.flank_position and member.coordination_leader != member.name:
                    leader = None
                    for npc in game_state.crew:
                        if npc.name == member.coordination_leader and npc.is_alive:
                            leader = npc
                            break
                    if leader:
                        flank_positions = self._calculate_flanking_positions(
                            player_loc, leader.location, [member], game_state.station_map, current_turn=getattr(game_state, "turn", 0)
                        )
                        if flank_positions:
                            member.flank_position = flank_positions[0]

        # Determine movement target
        if member.flank_position:
            # Move to flanking position first
            target_pos = member.flank_position
            dist_to_flank = abs(member.location[0] - target_pos[0]) + abs(member.location[1] - target_pos[1])

            if dist_to_flank <= 1:
                # Reached flank position, now approach player
                target_pos = player_loc
        else:
            # Leader approaches directly
            target_pos = player_loc

        # Check if in position to attack (same location as player)
        if member.location == player_loc:
            # Close enough - coordination complete, attack!
            self._clear_coordination(member)
            # Trigger a stealth detection (the infected has cornered the player)
            event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, normalize_perception_payload({
                "room": game_state.station_map.get_room_name(*player_loc),
                "location": player_loc,
                "opponent": member.name,
                "opponent_ref": member,
                "player_ref": player,
                "actor": getattr(player, "name", None),
                "game_state": game_state,
                "outcome": "detected",
                "player_successes": 0,
                "opponent_successes": 3,
                "subject_pool": 0,
                "observer_pool": 3,
            })))
            return True

        # Move toward target
        self._pathfind_step(member, target_pos[0], target_pos[1], game_state, steps=self._get_alert_steps())
        return True

    def _clear_coordination(self, member: 'CrewMember'):
        """Clear coordination state from a crew member."""
        member.coordinating_ambush = False
        member.ambush_target_location = None
        member.flank_position = None
        member.coordination_leader = None
        member.coordination_turns_remaining = 0
        if getattr(member, "suspicion_state", None) == "coordinating":
            member.suspicion_state = "idle"

    def _build_alert_context(self, game_state: 'GameState') -> Dict[str, Any]:
        """Capture alert modifiers for this turn."""
        alert_system = getattr(game_state, "alert_system", None)
        alert_active = False
        observation_bonus = 0
        speed_multiplier = 1

        if alert_system and alert_system.is_active:
            alert_active = True
            observation_bonus = alert_system.get_observation_bonus()
            speed_multiplier = alert_system.get_speed_multiplier()
        elif getattr(game_state, "alert_status", "").upper() == "ALERT":
            alert_active = True
            observation_bonus = max(observation_bonus, 1 if getattr(game_state, "alert_turns_remaining", 0) > 0 else 0)

        return {
            "active": alert_active,
            "observation_bonus": observation_bonus,
            "speed_multiplier": max(1, speed_multiplier)
        }

    def _handle_security_console_duties(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """Route security-role NPCs to the console to review alerts and investigate."""
        if not getattr(member, "security_role", False):
            return False

        security_sys = getattr(game_state, "security_system", None)
        if not security_sys:
            return False

        # Throttle checks unless new alerts arrive
        next_check = getattr(member, "next_security_check_turn", 0)
        has_unread = security_sys.has_unread_alerts()
        if getattr(member, "investigating", False) and not has_unread:
            return False
        if not has_unread and game_state.turn < next_check:
            return False

        # Identify top alerts within the recent window
        prioritized = security_sys.security_log.get_prioritized(count=5)
        recent_entries = [
            e for e in prioritized
            if game_state.turn - e.get("turn", game_state.turn) <= self.SECURITY_INVESTIGATION_WINDOW
        ]
        if not has_unread and not recent_entries:
            return False

        console_room = "Radio Room"
        station_map = game_state.station_map
        console_pos = station_map.rooms.get(console_room)
        if not console_pos:
            return False

        target_x, target_y, _, _ = console_pos
        member_room = station_map.get_room_name(*member.location)

        # Move toward the console if not already there
        if member_room != console_room:
            member.target_room = console_room
            self._pathfind_step(member, target_x, target_y, game_state)
            return True

        # At the console: read alerts and choose an investigation target
        unread = security_sys.check_console(npc=member)
        entries_to_consider = unread if unread else recent_entries
        if entries_to_consider:
            entries_sorted = sorted(
                entries_to_consider,
                key=lambda e: (e.get("severity", 1), e.get("turn", 0)),
                reverse=True
            )
            for entry in entries_sorted:
                if self._start_security_investigation_from_entry(member, entry, game_state):
                    break

        member.next_security_check_turn = game_state.turn + self.SECURITY_CHECK_INTERVAL
        return True

    def _start_security_investigation_from_entry(self, member: 'CrewMember', entry: Dict, game_state: 'GameState') -> bool:
        """Configure investigation state based on a security log entry."""
        target_pos = entry.get("position")
        if not target_pos:
            return False

        severity = entry.get("severity", 1)
        member.investigating = True
        member.investigation_goal = target_pos
        member.investigation_priority = max(severity, getattr(member, "investigation_priority", 0))
        member.investigation_expires = game_state.turn + self.SEARCH_TURNS
        member.investigation_source = "security_log"
        member.last_known_player_location = target_pos
        member.last_seen_player_turn = entry.get("turn", game_state.turn)
        member.last_seen_player_room = game_state.station_map.get_room_name(*target_pos)

        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"{member.name} responds to security alert near {member.last_seen_player_room}."
        }))
        return True

    def update(self, game_state: 'GameState'):
        """Updates AI for all crew members with per-turn caching and action budget."""
        # Initialize turn-level cache and budget
        self.cache = AICache(game_state)
        self.budget_limit = 15 + (5 * len(game_state.crew))
        self.budget_spent = 0
        self.exhaustion_count = 0
        self.alert_speed_bonus = 0
        alert_system = getattr(game_state, "alert_system", None)
        if alert_system and alert_system.is_active:
            self.alert_speed_bonus = alert_system.get_speed_bonus()
        self.alert_context = self._build_alert_context(game_state)
        
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

    def _get_alert_steps(self) -> int:
        """Return movement steps NPCs can take this turn, factoring alert state."""
        return 1 + max(0, self.alert_speed_bonus)

    def update_member_ai(self, member: 'CrewMember', game_state: 'GameState'):
        """
        Agent 2/8: NPC AI Logic.
        Priority: Thing AI > Lynch Mob > Investigation > Schedule > Wander
        """
        if not member.is_alive:
            return
        if not self.alert_context.get("active") and getattr(member, "alerted_to_player", False):
            member.alerted_to_player = False
        self._expire_investigation(member, game_state)
        current_turn = getattr(game_state, "turn", 0)
        if hasattr(member, "decay_suspicion"):
            member.decay_suspicion(current_turn)
        if hasattr(member, "suspicion_state"):
            self._update_suspicion_state(member, game_state.player, game_state)
        alert_system = getattr(game_state, "alert_system", None)
        if alert_system and not alert_system.is_active:
            member.alerted_to_player = False

        # 0. PRIORITY: Thing AI (Agent 3) - Revealed Things actively hunt
        if getattr(member, 'is_revealed', False):
            self._update_thing_ai(member, game_state)
            return

        # 0.5. PRIORITY: Infected Coordination - Hidden infected executing pincer movement
        if getattr(member, 'coordinating_ambush', False) and getattr(member, 'is_infected', False):
            if self._execute_coordinated_ambush(member, game_state):
                return
        
        # Tier 8: MIMICRY BEHAVIOR (Hidden Infected)
        if getattr(member, 'is_infected', False) and not getattr(member, 'is_revealed', False):
            if self._update_mimicry_ai(member, game_state):
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

        # Security-role duty: check console and dispatch investigations
        if self._handle_security_console_duties(member, game_state):
            return
                
        # 1. PRIORITY: Investigation (Suspicious/Almost Detected)
        if getattr(member, 'investigating', False) and hasattr(member, 'last_known_player_location'):
            target_loc = getattr(member, "investigation_goal", None) or member.last_known_player_location
            if member.location == target_loc:
                linger = getattr(member, "investigation_loops", 0)
                if linger > 0:
                    member.investigation_loops = linger - 1
                    event_bus.emit(GameEvent(EventType.MESSAGE, {
                        "text": f"{member.name} scans the area for clues..."
                    }))
                else:
                    member.investigating = False
                    member.investigation_goal = None
                    member.investigation_priority = 0
                    member.investigation_source = None
                    event_bus.emit(GameEvent(EventType.MESSAGE, {
                        "text": f"{member.name} checks the area but finds nothing."
                    }))
                linger_turns = getattr(member, "investigation_linger_turns", 0)
                arrival_announced = getattr(member, "investigation_arrival_reported", False)
                if linger_turns > 0:
                    if not arrival_announced:
                        event_bus.emit(GameEvent(EventType.MESSAGE, {
                            "text": f"{member.name} reaches the noise and starts looking around."
                        }))
                        member.investigation_arrival_reported = True
                    neighbors = game_state.station_map.get_walkable_neighbors(*target_loc)
                    if neighbors:
                        patrol_target = game_state.rng.choose(neighbors) if hasattr(game_state, "rng") else neighbors[0]
                        if patrol_target != member.location:
                            self._pathfind_step(member, patrol_target[0], patrol_target[1], game_state)
                            member.investigation_linger_turns = max(0, linger_turns - 1)
                            return
                    member.investigation_linger_turns = max(0, linger_turns - 1)
                    return
                # Arrived and finished lingering
                member.investigating = False
                member.investigation_goal = None
                member.investigation_priority = 0
                member.investigation_source = None
                member.investigation_linger_turns = 0
                member.investigation_arrival_reported = False
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": f"{member.name} checks the area but finds nothing."
                }))
            else:
                # Move toward investigation spot
                self._pathfind_step(member, target_loc[0], target_loc[1], game_state, steps=self._get_alert_steps())
                member.investigation_arrival_reported = False
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
                self._pathfind_step(member, tx, ty, game_state, steps=self._get_alert_steps())
                return
        else:
            member.in_lynch_mob = False

        # Search mode: sweep around last seen room/corridors
        if getattr(member, "search_turns_remaining", 0) > 0:
            if self._execute_search(member, game_state):
                return

        # 2.5 SECURITY: Console checks for roles tasked with monitoring cameras
        if self._is_security_officer(member):
            if self._handle_security_console(member, game_state):
                return

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
                self._pathfind_step(member, tx, ty, game_state, steps=self._get_alert_steps())
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

        # Vent interceptions take priority over general hunting
        vent_goal = getattr(member, "vent_intercept_goal", None)
        vent_expires = getattr(member, "vent_intercept_expires", 0)
        if vent_goal:
            if vent_expires and game_state.turn > vent_expires:
                member.vent_intercept_goal = None
                member.vent_intercept_expires = 0
            elif member.location == vent_goal:
                member.vent_intercept_goal = None
                member.vent_intercept_expires = 0
            else:
                self._pathfind_step(member, vent_goal[0], vent_goal[1], game_state)
                return

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
        self._pathfind_step(member, tx, ty, game_state, steps=self._get_alert_steps())

    def _update_mimicry_ai(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """
        AI behavior for HIDDEN Things to mimic human roles.
        Tier 8 Enhanced: Opportunistic attacks, false accusations, sabotage.
        Returns True if an action was taken (overriding normal behavior).
        """
        rng = game_state.rng
        mode = getattr(member, "mimicry_mode", "blend_in")
        
        # 1. TRANSFORMATION CHECK (highest priority)
        if self._should_transform(member, game_state):
            self._trigger_transformation(member, game_state)
            return True
        
        # 2. OPPORTUNISTIC ATTACK (alone with 1-2 targets)
        if self._should_opportunistic_attack(member, game_state):
            self._execute_opportunistic_attack(member, game_state)
            return True
        
        # 3. FALSE ACCUSATION (15% chance when conditions met)
        if rng.random_float() < 0.15 and self._can_make_false_accusation(member, game_state):
            self._make_false_accusation(member, game_state)
            return True
        
        # 4. SABOTAGE (20% chance when unobserved near equipment)
        if rng.random_float() < 0.20 and self._can_sabotage(member, game_state):
            self._execute_sabotage(member, game_state)
            return True
        
        # 5. ROLE-BASED MIMICRY (blend in behavior)
        role = getattr(member, "mimicry_role", None)
        
        if role == "dog_handler":
            # Clark/Dog Handler: Obsessively stays near dogs (Kennel)
            current_room = game_state.station_map.get_room_name(*member.location)
            if current_room != "Kennel" and rng.random_float() < 0.7:
                kennel_pos = game_state.station_map.rooms.get("Kennel")
                if kennel_pos:
                    tx, ty, _, _ = kennel_pos
                    self._pathfind_step(member, tx, ty, game_state)
                    if rng.random_float() < 0.1:
                        event_bus.emit(GameEvent(EventType.MESSAGE, {
                            "text": f"{member.name} mutters about the dogs being restless."
                        }))
                    return True

        elif role == "loner":
            # Avoids rooms with other people
            current_room = game_state.station_map.get_room_name(*member.location)
            people_in_room = [m for m in game_state.crew if m.is_alive and 
                            game_state.station_map.get_room_name(*m.location) == current_room]
            
            if len(people_in_room) > 2:
                neighbors = game_state.station_map.get_walkable_neighbors(*member.location)
                if neighbors:
                    target = rng.choose(neighbors)
                    self._pathfind_step(member, target[0], target[1], game_state)
                    return True
        
        elif role == "social_butterfly":
            # Seeks out the Rec Room or Mess Hall
            current_room = game_state.station_map.get_room_name(*member.location)
            if current_room not in ["Rec Room", "Mess Hall"] and rng.random_float() < 0.5:
                target_room = rng.choose(["Rec Room", "Mess Hall"])
                target_pos = game_state.station_map.rooms.get(target_room)
                if target_pos:
                    tx, ty, _, _ = target_pos
                    self._pathfind_step(member, tx, ty, game_state)
                    return True

        # 80% of the time, let normal AI schedule take over (blend in)
        return False
    
    def _should_transform(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """Check if Thing should reveal itself (transformation triggers)."""
        # Low health (< 30%)
        if member.health <= 1:  # Assuming 3 max health, 1 = ~30%
            return True
        
        # Cornered: In barricaded room with hostile NPCs
        current_room = game_state.station_map.get_room_name(*member.location)
        if hasattr(game_state, 'room_states') and game_state.room_states.is_barricaded(current_room):
            hostile_npcs = [
                m for m in game_state.crew
                if m.is_alive and not getattr(m, 'is_infected', False)
                and m != member and game_state.station_map.get_room_name(*m.location) == current_room
            ]
            if len(hostile_npcs) >= 2:
                # Surrounded and cornered - fight or flight
                return True
        
        return False
    
    def _trigger_transformation(self, member: 'CrewMember', game_state: 'GameState'):
        """Reveal the Thing - transform and become hostile."""
        member.is_revealed = True
        member.revealed_name = f"The-Thing-That-Was-{member.name}"
        
        event_bus.emit(GameEvent(EventType.WARNING, {
            "text": f"HORROR! {member.name}'s body TWISTS and CONTORTS! They're a THING!"
        }))
        
        event_bus.emit(GameEvent(EventType.BIOLOGICAL_SLIP, {
            "name": member.name,
            "type": "transformation",
            "room": game_state.station_map.get_room_name(*member.location)
        }))
    
    def _should_opportunistic_attack(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """Check if conditions are right for opportunistic attack."""
        current_room = game_state.station_map.get_room_name(*member.location)
        
        # Find humans in the same room (excluding other Things)
        humans_in_room = [
            m for m in game_state.crew
            if m.is_alive and not getattr(m, 'is_infected', False)
            and game_state.station_map.get_room_name(*m.location) == current_room
        ]
        
        # Attack only when alone with 1-2 targets
        if not (1 <= len(humans_in_room) <= 2):
            return False
        
        # Check for witnesses in adjacent rooms
        connected_rooms = getattr(game_state.station_map, 'get_adjacent_rooms', lambda r: [])(current_room)
        for adj_room in connected_rooms:
            witnesses = [
                m for m in game_state.crew
                if m.is_alive and not getattr(m, 'is_infected', False)
                and game_state.station_map.get_room_name(*m.location) == adj_room
            ]
            if witnesses:
                return False  # Too risky
        
        # Check if target is vulnerable (low health or distracted)
        target = humans_in_room[0]
        is_vulnerable = (
            target.health <= 1 or
            getattr(target, 'stress', 0) > 3 or
            getattr(target, 'suspicion_state', 'idle') == 'idle'  # Not alert
        )
        
        return is_vulnerable
    
    def _execute_opportunistic_attack(self, member: 'CrewMember', game_state: 'GameState'):
        """Execute a sneak attack on an isolated target."""
        current_room = game_state.station_map.get_room_name(*member.location)
        
        humans_in_room = [
            m for m in game_state.crew
            if m.is_alive and not getattr(m, 'is_infected', False)
            and game_state.station_map.get_room_name(*m.location) == current_room
        ]
        
        if not humans_in_room:
            return
        
        target = humans_in_room[0]
        
        # Reveal and attack
        member.is_revealed = True
        member.revealed_name = f"The-Thing-That-Was-{member.name}"
        
        event_bus.emit(GameEvent(EventType.WARNING, {
            "text": f"{member.name}'s face SPLITS OPEN! They lunge at {target.name}!"
        }))
        
        # Use existing attack logic
        self._thing_attack(member, target, game_state)
    
    def _can_make_false_accusation(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """Check if conditions allow false accusation."""
        # Need high paranoia and multiple people present
        if game_state.paranoia_level < 40:
            return False
        
        current_room = game_state.station_map.get_room_name(*member.location)
        people_in_room = [
            m for m in game_state.crew
            if m.is_alive and m != member
            and game_state.station_map.get_room_name(*m.location) == current_room
        ]
        
        # Need at least 2 others (one to accuse, one to witness)
        if len(people_in_room) < 2:
            return False
        
        # Find a clean NPC to falsely accuse
        clean_npcs = [m for m in people_in_room if not getattr(m, 'is_infected', False)]
        return len(clean_npcs) > 0
    
    def _make_false_accusation(self, member: 'CrewMember', game_state: 'GameState'):
        """Infected NPC makes false accusation against a clean crew member."""
        current_room = game_state.station_map.get_room_name(*member.location)
        
        clean_npcs = [
            m for m in game_state.crew
            if m.is_alive and m != member and not getattr(m, 'is_infected', False)
            and game_state.station_map.get_room_name(*m.location) == current_room
        ]
        
        if not clean_npcs:
            return
        
        # Pick a random clean target
        target = game_state.rng.choose(clean_npcs)
        
        # Generate accusation dialogue
        accusations = [
            f"I saw {target.name}'s eyes go BLACK for a second!",
            f"{target.name} was moving strange earlier... inhuman-like.",
            f"There's something OFF about {target.name}. We should test them!",
            f"Why won't {target.name} look anyone in the eye? Guilty conscience?",
            f"{target.name} has been sneaking around at night. I don't trust them."
        ]
        
        accusation = game_state.rng.choose(accusations)
        
        event_bus.emit(GameEvent(EventType.DIALOGUE, {
            "speaker": member.name,
            "text": accusation
        }))
        
        # Lower trust in the target
        if hasattr(game_state, 'trust_system'):
            # Other NPCs in room reduce trust in target
            for witness in clean_npcs:
                if witness != target:
                    game_state.trust_system.modify_trust(witness.name, target.name, -5)
        
        event_bus.emit(GameEvent(EventType.ACCUSATION_RESULT, {
            "accuser": member.name,
            "accused": target.name,
            "false_accusation": True,
            "room": current_room
        }))
    
    def _can_sabotage(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """Check if conditions allow sabotage."""
        current_room = game_state.station_map.get_room_name(*member.location)
        
        # Must be alone (or only with other infected)
        others_in_room = [
            m for m in game_state.crew
            if m.is_alive and m != member and not getattr(m, 'is_infected', False)
            and game_state.station_map.get_room_name(*m.location) == current_room
        ]
        
        if others_in_room:
            return False
        
        # Check if room has sabotage targets
        sabotage_rooms = ["Generator Room", "Radio Room", "Infirmary", "Lab"]
        return current_room in sabotage_rooms
    
    def _execute_sabotage(self, member: 'CrewMember', game_state: 'GameState'):
        """Infected NPC sabotages equipment."""
        current_room = game_state.station_map.get_room_name(*member.location)
        
        sabotage_effects = {
            "Generator Room": ("generator", "The lights flicker ominously..."),
            "Radio Room": ("radio", "Static crackles from the radio..."),
            "Infirmary": ("medical", "Medical supplies have been tampered with..."),
            "Lab": ("lab", "Test samples have been contaminated...")
        }
        
        if current_room not in sabotage_effects:
            return
        
        target, effect_msg = sabotage_effects[current_room]
        
        # Emit subtle hint (player can investigate)
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"[AMBIENT] {effect_msg}"
        }))
        
        # Add sabotage evidence to room
        if hasattr(game_state, 'room_states'):
            game_state.room_states.add_state(current_room, "SABOTAGED")
        
        # Mark member as having sabotaged (for forensics)
        member.add_knowledge_tag(f"Sabotaged:{current_room}")
        
        event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
            "text": f"DEBUG: Infected {member.name} sabotaged {target} in {current_room}"
        }))

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
        in_vent = getattr(player, "in_vent", False)
        
        if member_room != player_room:
            # Vent noise can carry into rooms that share an entry grate
            if not (in_vent and game_state.station_map.is_vent_entry(*member.location)):
                return False

        noise = self.cache.player_noise if self.cache else player.get_noise_level()
        if in_vent:
            noise += 3  # Vents amplify scraping sounds
        alert_system = getattr(game_state, "alert_system", None)
        if alert_system and alert_system.is_active:
            noise += max(0, alert_system.get_observation_bonus() // 2)
        # Use cached visibility modifier if available
        vis_mod = self.cache.get_visibility_modifier(player_room, game_state) if self.cache else None
        
        # We need a small update to StealthSystem to accept vis_mod, or just pass normal
        alert_bonus = self.alert_context.get("observation_bonus", 0) if self.alert_context else 0
        detected = stealth.evaluate_detection(member, player, game_state, noise_level=noise, alert_bonus=alert_bonus)
        if detected and hasattr(member, "add_knowledge_tag"):
            member.add_knowledge_tag(f"Spotted {player.name} in {player_room}")
            room = self._record_last_seen(member, player.location, game_state, player_room)
            self._enter_search_mode(member, player.location, room, game_state)
        return detected

    def _pathfind_step(self, member: 'CrewMember', target_x: int, target_y: int, game_state: 'GameState', steps: int = 1):
        """Take one or more steps toward target using A* pathfinding with cache and budget."""
        goal = (target_x, target_y)
        station_map = game_state.station_map
        current_turn = game_state.turn

        # 1. Budget check for pathfinding
        # Check cache first to determine cost
        steps = max(1, self.alert_context.get("speed_multiplier", 1) if self.alert_context else 1)

        path = None
        current_path_index = 0

        # Calculate path once if budget allows
        cache_key = (member.location, goal)
        use_astar = True
        if hasattr(pathfinder, '_path_cache') and cache_key in pathfinder._path_cache:
            use_astar = False

        cost = self.COST_ASTAR if use_astar else self.COST_PATH_CACHE
        
        path = None
        path_found = False

        # Optimize: Compute path once, then iterate steps
        if self._request_budget(cost):
            path = pathfinder.find_path(member.location, goal, station_map, current_turn)
            path_found = True

        for i in range(steps):
            dx, dy = 0, 0

            # Use path if available
            target_next = None
            if path_found and path and current_path_index + 1 < len(path):
                target_next = path[current_path_index + 1]
                # Ensure next node is reachable (adjacent)
                if abs(target_next[0] - member.location[0]) <= 1 and abs(target_next[1] - member.location[1]) <= 1:
                    dx = target_next[0] - member.location[0]
                    dy = target_next[1] - member.location[1]
                else:
                    # Path desync
                    path = None

            # Fallback to greedy if no path or path exhausted
            if dx == 0 and dy == 0:
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

            # If we successfully moved to the target node of the path, advance index
            if target_next and member.location == target_next:
                current_path_index += 1
            elif target_next and member.location != target_next:
                # Move failed or was redirected
                path = None

            # Check for tripwire triggers at new location
            self._check_tripwire_trigger(member, game_state)

            # Early exit if already at goal
            if member.location == goal:
                break

    def _check_tripwire_trigger(self, member: 'CrewMember', game_state: 'GameState'):
        """Check if NPC stepped on a deployed tripwire and trigger it."""
        if not hasattr(game_state, 'deployed_items'):
            return

        member_pos = member.location
        if member_pos not in game_state.deployed_items:
            return

        deployed = game_state.deployed_items[member_pos]
        if deployed.get('triggered', False):
            return  # Already triggered

        # Trigger the tripwire!
        deployed['triggered'] = True
        deployed['triggered_by'] = member.name
        deployed['triggered_turn'] = game_state.turn

        item_name = deployed['item_name']
        room = deployed['room']
        noise_level = deployed.get('noise_level', 6)

        # Emit alert to player
        event_bus.emit(GameEvent(EventType.WARNING, {
            "text": f"ALERT: Your {item_name} in {room} was triggered by {member.name}!"
        }))

        # Emit perception event so other systems know
        event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, {
            "source": "tripwire",
            "item": item_name,
            "triggered_by": member.name,
            "location": member_pos,
            "target_location": member_pos,
            "room": room,
            "noise_level": noise_level,  # Tripwires are loud
            "intensity": noise_level,
            "priority_override": 2,
            "linger_turns": 2,
            "game_state": game_state
        }))

        # Remove the used tripwire
        del game_state.deployed_items[member_pos]

        event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
            "text": f"Tripwire triggered and consumed in {room}."
        }))

    def _pursue_player(self, member: 'CrewMember', game_state: 'GameState'):
        """Move one step toward the player when detected via perception."""
        player_loc = self.cache.player_location if self.cache else game_state.player.location
        self._pathfind_step(member, player_loc[0], player_loc[1], game_state, steps=self._get_alert_steps())

    def _handle_security_console(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """Send security-focused NPCs to the console and react to alerts."""
        if getattr(member, "investigating", False) or getattr(member, "search_turns_remaining", 0) > 0:
            return False

        security_sys = getattr(game_state, "security_system", None)
        if not security_sys or not security_sys.has_unread_alerts():
            return False

        console_room = getattr(security_sys, "console_room", "Radio Room")
        member_room = game_state.station_map.get_room_name(*member.location)

        # Move toward the console if not present
        if member_room != console_room:
            target_pos = game_state.station_map.rooms.get(console_room)
            if target_pos:
                tx, ty, _, _ = target_pos
                self._pathfind_step(member, tx, ty, game_state)
                return True
            return False

        # At console: read alerts and set investigation target
        alerts = security_sys.check_console(npc=member)
        if not alerts:
            return True

        latest = alerts[-1]
        target_pos = latest.get("position") or latest.get("location")
        if isinstance(target_pos, (list, tuple)) and len(target_pos) >= 2:
            member.investigating = True
            member.investigation_goal = (target_pos[0], target_pos[1])
            member.investigation_priority = max(getattr(member, "investigation_priority", 0), 3)
            member.investigation_expires = game_state.turn + 4
            member.investigation_source = "security_console"
            member.last_known_player_location = member.investigation_goal
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"{member.name} leaves the console to investigate a security alert in {game_state.station_map.get_room_name(*member.investigation_goal)}."
            }))
        return True

    def _handle_vent_noise_ping(self, payload: Dict) -> bool:
        """Direct infected (Thing) AI toward loud vent noises for interception."""
        source = payload.get("source", "")
        if source not in ("vent", "vent_echo"):
            return False

        game_state = payload.get("game_state")
        vent_loc = payload.get("location")
        station_map = game_state.station_map if game_state else None
        if not game_state or not vent_loc or not station_map:
            return False

        vent_nodes = []
        if station_map.is_at_vent(*vent_loc):
            vent_nodes.append(vent_loc)
        vent_nodes.extend(getattr(station_map, "get_vent_entry_nodes", lambda: [])())
        if not vent_nodes:
            return False

        priority = max(3, payload.get("priority_override", 0) or 0)
        duration = max(3, payload.get("linger_turns", 3))
        noise_level = payload.get("noise_level", 0)
        for npc in game_state.crew:
            if npc == game_state.player or not npc.is_alive:
                continue
            if not getattr(npc, "is_infected", False):
                continue
            intercept = self._get_closest_position(npc.location, vent_nodes)
            npc.investigating = True
            npc.investigation_goal = intercept
            npc.last_known_player_location = vent_loc
            npc.investigation_priority = max(getattr(npc, "investigation_priority", 0), priority)
            npc.investigation_expires = game_state.turn + duration
            npc.investigation_source = "vent_noise"
            npc.vent_intercept_goal = intercept
            npc.vent_intercept_expires = game_state.turn + duration

        event_bus.emit(GameEvent(EventType.DIAGNOSTIC, {
            "type": "AI_VENT_NOISE_TARGET",
            "source": source,
            "noise_level": noise_level,
            "room": station_map.get_room_name(*vent_loc),
            "vent_location": vent_loc
        }))
        return True

    def _handle_investigation_ping(self, payload: Dict):
        """Handle PERCEPTION_EVENT payloads that mark a noisy distraction."""
        game_state = payload.get("game_state")
        target_loc = payload.get("target_location")
        if not game_state or not target_loc:
            return

        station_map = game_state.station_map
        target_room = station_map.get_room_name(*target_loc)
        priority = payload.get("priority_override", 1)
        duration = max(3, payload.get("investigation_turns", 4))
        source = payload.get("source", "noise")
        intensity = payload.get("intensity", 1)
        is_vent_noise = str(source).startswith("vent")
        linger_turns = payload.get("linger_turns", 2)

        for npc in game_state.crew:
            if npc == game_state.player or not npc.is_alive:
                continue
            npc_room = station_map.get_room_name(*npc.location)
            if target_room == npc_room or target_room in station_map.get_connections(npc_room):
                npc.investigating = True
                npc.investigation_goal = target_loc
                npc.last_known_player_location = target_loc
                npc.investigation_priority = max(getattr(npc, "investigation_priority", 0), priority)
                npc.investigation_expires = game_state.turn + duration
                npc.investigation_loops = duration
                npc.investigation_source = source
                if getattr(npc, "coordinating_ambush", False):
                    self._clear_coordination(npc)
                npc.suspicion_state = getattr(npc, "suspicion_state", "idle")
                npc.investigation_linger_turns = max(getattr(npc, "investigation_linger_turns", 0), linger_turns)
                npc.investigation_arrival_reported = False
                npc.search_turns_remaining = 0
                npc.current_search_target = None

        if is_vent_noise:
            self._handle_vent_threat(game_state, target_loc, intensity, priority, source)

        event_bus.emit(GameEvent(EventType.DIAGNOSTIC, {
            "type": "AI_INVESTIGATION_PING",
            "room": target_room,
            "source": source,
            "intensity": intensity,
            "priority": priority
        }))

    def _handle_vent_threat(self, game_state: 'GameState', target_loc: Tuple[int, int], intensity: int, priority: int, source: str):
        """Escalate close-quarters vent noise into high-priority infected responses."""
        station_map = getattr(game_state, "station_map", None)
        if not station_map:
            return
        vent_neighbors = station_map.get_vent_neighbors(*target_loc) if hasattr(station_map, "get_vent_neighbors") else []
        vent_node = station_map.get_vent_node(*target_loc) if hasattr(station_map, "get_vent_node") else None
        expires_after = max(3, min(6, (intensity // 3) + 2))

        for npc in game_state.crew:
            if npc == game_state.player or not npc.is_alive or not getattr(npc, "is_infected", False):
                continue

            # Manhattan proximity plus vent graph adjacency gives "close-quarters" classification
            distance = abs(npc.location[0] - target_loc[0]) + abs(npc.location[1] - target_loc[1])
            shares_vent_branch = False
            if hasattr(station_map, "is_at_vent") and station_map.is_at_vent(*npc.location):
                shares_vent_branch = npc.location == target_loc or npc.location in vent_neighbors

            if distance <= 1 or shares_vent_branch:
                npc.investigating = True
                npc.investigation_goal = target_loc
                npc.last_known_player_location = target_loc
                npc.investigation_priority = max(getattr(npc, "investigation_priority", 0), max(priority, 3))
                npc.investigation_source = "vent_threat"
                npc.investigation_expires = max(getattr(npc, "investigation_expires", 0), game_state.turn + expires_after)
                npc.vent_close_quarters_alert = True
                npc.vent_alert_turn = game_state.turn
                if hasattr(npc, "suspicion_level"):
                    npc.suspicion_level = max(getattr(npc, "suspicion_level", 0), 4)
                self._apply_suspicion(npc, 1, game_state, reason="vent_noise")

                event_bus.emit(GameEvent(EventType.DIAGNOSTIC, {
                    "type": "AI_VENT_THREAT",
                    "npc": npc.name,
                    "source": source,
                    "target": target_loc,
                    "room": station_map.get_room_name(*target_loc),
                    "close_quarters": True,
                    "vent_room": vent_node.get("room") if vent_node else station_map.get_room_name(*target_loc)
                }))

    def _expire_investigation(self, member: 'CrewMember', game_state: 'GameState'):
        """Clear investigation goals once their timer elapses."""
        expires = getattr(member, "investigation_expires", 0)
        if expires and game_state.turn > expires:
            member.investigating = False
            member.investigation_goal = None
            member.investigation_priority = 0
            member.investigation_source = None
            member.investigation_expires = 0
            member.investigation_loops = 0
            member.last_known_player_location = None
        vent_goal = getattr(member, "vent_intercept_goal", None)
        vent_expires = getattr(member, "vent_intercept_expires", 0)
        if vent_goal and vent_expires and game_state.turn > vent_expires:
            member.vent_intercept_goal = None
            member.vent_intercept_expires = 0
            member.investigation_linger_turns = 0
            member.investigation_arrival_reported = False
    def _record_last_seen(self, member: 'CrewMember', location: Tuple[int, int], game_state: 'GameState', room_name: Optional[str] = None) -> str:
        """Store last-seen player data on the NPC for later search behavior."""
        room = room_name or game_state.station_map.get_room_name(*location)
        member.last_seen_player_location = location
        member.last_seen_player_room = room
        member.last_seen_player_turn = game_state.turn
        return room

    def _enter_search_mode(self, member: 'CrewMember', anchor_location: Tuple[int, int], anchor_room: str, game_state: 'GameState'):
        """Initialize search mode around the last seen position with spiral-out pattern.

        Enhanced search includes:
        - Adjacent rooms (not just corridors)
        - Spiral-out pattern expanding radius each turn
        - Search history to avoid rechecking areas
        """
        if not hasattr(member, "search_turns_remaining"):
            return

        station_map = game_state.station_map
        member.clear_search_history()
        member.search_anchor = anchor_location
        member.search_spiral_radius = 1  # Start at radius 1, expand each turn

        member.search_targets = self._build_search_targets(
            anchor_location, anchor_room, station_map
        )
        member.current_search_target = None
        member.search_turns_remaining = self.SEARCH_TURNS

        event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
            "text": f"{member.name} is searching around {anchor_room} (Last seen at turn {game_state.turn})."
        }))
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"{member.name} starts a thorough sweep of {anchor_room} and adjacent areas!"
        }))

    def _execute_search(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """Advance the search pattern; returns True if a search action occurred.

        Enhanced search behavior:
        - Tracks search_history to avoid rechecking locations
        - Spiral-out pattern expands radius over time
        - Resets search timer if player is re-detected during search
        """
        if member.search_turns_remaining <= 0 or not member.search_targets:
            self._complete_search(member)
            return False

        # Initialize search_history if not present
        if not hasattr(member, 'search_history'):
            member.search_history = set()

        if member.current_search_target is None:
            member.current_search_target = self._get_next_unchecked_target(member)

        if member.current_search_target is None:
            self._complete_search(member)
            return False

        # If we've reached the current target, mark as checked and find next
        if member.location == member.current_search_target:
            member.record_search_checkpoint(member.location, game_state.station_map)
            member.current_search_target = self._get_next_unchecked_target(member)

        if member.current_search_target is None:
            self._complete_search(member)
            return False

        if member.current_search_target:
            tx, ty = member.current_search_target
            self._pathfind_step(member, tx, ty, game_state, steps=self._get_alert_steps())
            member.search_turns_remaining -= 1
            if member.search_turns_remaining <= 0:
                self._complete_search(member)
            return True

        self._complete_search(member)
        return False

    def _get_next_unchecked_target(self, member: 'CrewMember') -> Optional[Tuple[int, int]]:
        """Get the next search target that hasn't been checked yet."""
        search_history = getattr(member, 'search_history', set())

        for target in member.search_targets:
            if target not in search_history:
                return target

        # All targets checked
        return None

    @staticmethod
    def _get_closest_position(origin: Tuple[int, int], targets: List[Tuple[int, int]]) -> Tuple[int, int]:
        """Return the target position closest to origin using Manhattan distance."""
        return min(targets, key=lambda pos: abs(origin[0] - pos[0]) + abs(origin[1] - pos[1]))

    def reset_search_on_detection(self, member: 'CrewMember', new_location: Tuple[int, int], game_state: 'GameState'):
        """Reset search timer and update anchor when player is re-detected during active search.

        Called when an NPC spots the player while already in search mode.
        """
        if member.search_turns_remaining > 0:
            # Player spotted during search - reset timer and update anchor
            anchor_room = game_state.station_map.get_room_name(*new_location)
            member.search_anchor = new_location
            member.search_turns_remaining = self.SEARCH_TURNS  # Full reset
            if hasattr(member, "clear_search_history"):
                member.clear_search_history()
            else:
                member.search_history = set()  # Clear history for fresh search

            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                "text": f"{member.name} re-acquired target! Search reset around {anchor_room}."
            }))

            # Re-initialize search targets around new location
            self._enter_search_mode(member, new_location, anchor_room, game_state)

    def _complete_search(self, member: 'CrewMember'):
        """Reset search state so patrol/schedule logic can resume."""
        member.search_turns_remaining = 0
        member.current_search_target = None
        member.search_targets = []
        member.search_anchor = None
        member.search_spiral_radius = 1
        if hasattr(member, "clear_search_history"):
            member.clear_search_history()

    def _build_search_targets(self, anchor_location: Tuple[int, int], anchor_room: str, station_map: 'StationMap') -> List[Tuple[int, int]]:
        """Create an ordered list of search targets using room sweeps and a spiral-out pattern."""
        targets: List[Tuple[int, int]] = [anchor_location]

        # Sweep anchor room center first, then connected rooms
        targets.extend(self._get_room_sweep_targets(anchor_room, station_map))

        # Spiral rings radiating outward from anchor
        for radius in range(1, self.SEARCH_SPIRAL_RADIUS + 1):
            targets.extend(self._generate_spiral_ring(anchor_location, radius, station_map))

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for pos in targets:
            if pos in seen:
                continue
            seen.add(pos)
            deduped.append(pos)
        return deduped

    def _get_room_sweep_targets(self, anchor_room: str, station_map: 'StationMap') -> List[Tuple[int, int]]:
        """Return centers for the anchor room and its adjacent rooms."""
        room_targets: List[Tuple[int, int]] = []
        anchor_center = self._get_room_center(anchor_room, station_map)
        if anchor_center and station_map.is_walkable(*anchor_center):
            room_targets.append(anchor_center)

        connections = station_map.get_connections(anchor_room) if hasattr(station_map, "get_connections") else []
        for room in connections:
            center = self._get_room_center(room, station_map)
            if center and station_map.is_walkable(*center):
                room_targets.append(center)
        return room_targets

    def _get_room_center(self, room_name: str, station_map: 'StationMap') -> Optional[Tuple[int, int]]:
        """Compute the central tile of a named room if defined."""
        if not room_name or not hasattr(station_map, "rooms") or room_name not in station_map.rooms:
            return None
        x1, y1, x2, y2 = station_map.rooms[room_name]
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _generate_spiral_ring(self, anchor_location: Tuple[int, int], radius: int, station_map: 'StationMap') -> List[Tuple[int, int]]:
        """Generate perimeter coordinates for the given radius around the anchor."""
        x0, y0 = anchor_location
        x_min, x_max = x0 - radius, x0 + radius
        y_min, y_max = y0 - radius, y0 + radius

        ring: List[Tuple[int, int]] = []

        # Top edge left->right
        for x in range(x_min, x_max + 1):
            pos = (x, y_min)
            if station_map.is_walkable(*pos):
                ring.append(pos)

        # Right edge top->bottom (skip corner)
        for y in range(y_min + 1, y_max + 1):
            pos = (x_max, y)
            if station_map.is_walkable(*pos):
                ring.append(pos)

        # Bottom edge right->left (skip corner)
        for x in range(x_max - 1, x_min - 1, -1):
            pos = (x, y_max)
            if station_map.is_walkable(*pos):
                ring.append(pos)

        # Left edge bottom->top (skip both corners)
        for y in range(y_max - 1, y_min, -1):
            pos = (x_min, y)
            if station_map.is_walkable(*pos):
                ring.append(pos)

        return ring
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
