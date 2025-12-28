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

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def on_turn_advance(self, event):
        game_state = event.payload.get("game_state")
        if game_state:
            self.update(game_state)

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
        Priority: Thing AI > Lynch Mob > Schedule > Wander
        """
        if not member.is_alive:
            return

        # 0. PRIORITY: Thing AI (Agent 3) - Revealed Things actively hunt
        if getattr(member, 'is_revealed', False):
            self._update_thing_ai(member, game_state)
            return

        # Passive perception hook: if an NPC spots the player, move toward them
        if self._request_budget(self.COST_PERCEPTION):
            if self._perceive_player(member, game_state):
                self._pursue_player(member, game_state)
                return

        # 0. PRIORITY: Lynch Mob Hunting (Agent 2)
        if game_state.lynch_mob.active_mob and game_state.lynch_mob.target:
            target = game_state.lynch_mob.target
            if target != member and target.is_alive:
                # Move toward the lynch target
                tx, ty = target.location
                self._pathfind_step(member, tx, ty, game_state)
                return

        # 1. Check Schedule
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

        # 2. Idling / Wandering
        if game_state.rng.random_float() < 0.3:
            dx = game_state.rng.choose([-1, 0, 1])
            dy = game_state.rng.choose([-1, 0, 1])
            member.move(dx, dy, game_state.station_map)

    def _update_thing_ai(self, member: 'CrewMember', game_state: 'GameState'):
        """AI behavior for revealed Things - actively hunt and attack humans."""
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

        # Check if in same location - ATTACK!
        if closest.location == member.location:
            self._thing_attack(member, closest, game_state)
            return

        # Move toward closest human
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

        noise = self.cache.player_noise if self.cache else stealth.get_noise_level(player)
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
