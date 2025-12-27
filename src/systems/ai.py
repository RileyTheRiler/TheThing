from typing import TYPE_CHECKING, Tuple
from core.resolution import ResolutionSystem

if TYPE_CHECKING:
    from engine import GameState, CrewMember, StationMap

class AISystem:
    """
    Handles AI logic for CrewMembers.
    Decouples logic from the CrewMember data class.
    """

    def __init__(self):
        pass

    def update(self, game_state: 'GameState'):
        """Updates AI for all crew members."""
        for member in game_state.crew:
            if member != game_state.player:
                self.update_member_ai(member, game_state)

    def update_member_ai(self, member: 'CrewMember', game_state: 'GameState'):
        """
        Agent 2/8: NPC AI Logic.
        Priority: Lynch Mob > Schedule > Wander
        """
        if not member.is_alive or member.is_revealed:
            return

        # 0. PRIORITY: Lynch Mob Hunting (Agent 2)
        if game_state.lynch_mob.active_mob and game_state.lynch_mob.target:
            target = game_state.lynch_mob.target
            if target != member and target.is_alive:
                # Move toward the lynch target
                tx, ty = target.location
                self._pathfind_step(member, tx, ty, game_state.station_map)
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
                self._pathfind_step(member, tx, ty, game_state.station_map)
                return

        # 2. Idling / Wandering
        if game_state.rng.random_float() < 0.3:
            dx = game_state.rng.choose([-1, 0, 1])
            dy = game_state.rng.choose([-1, 0, 1])
            member.move(dx, dy, game_state.station_map)

    def _pathfind_step(self, member: 'CrewMember', target_x: int, target_y: int, station_map: 'StationMap'):
        """Simple greedy step towards target."""
        dx = 1 if target_x > member.location[0] else -1 if target_x < member.location[0] else 0
        dy = 1 if target_y > member.location[1] else -1 if target_y < member.location[1] else 0
        member.move(dx, dy, station_map)
