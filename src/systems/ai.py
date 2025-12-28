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
        from core.event_system import event_bus, EventType
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        from core.event_system import event_bus, EventType
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def on_turn_advance(self, event):
        game_state = event.payload.get("game_state")
        if game_state:
            self.update(game_state)

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

        # Passive perception hook: if an NPC spots the player, move toward them
        if self._perceive_player(member, game_state):
            self._pursue_player(member, game_state)
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

    def _perceive_player(self, member: 'CrewMember', game_state: 'GameState') -> bool:
        """Use the StealthSystem detection logic as an AI hook."""
        stealth = getattr(game_state, "stealth_system", None)
        player = getattr(game_state, "player", None)
        station_map = getattr(game_state, "station_map", None)
        if not stealth or not player or not station_map:
            return False
        if member == player or not player.is_alive:
            return False

        member_room = station_map.get_room_name(*member.location)
        player_room = station_map.get_room_name(*player.location)
        if member_room != player_room:
            return False

        noise = stealth.get_noise_level(player)
        detected = stealth.evaluate_detection(member, player, game_state, noise_level=noise)
        if detected and hasattr(member, "add_knowledge_tag"):
            member.add_knowledge_tag(f"Spotted {player.name} in {player_room}")
        return detected

    def _pathfind_step(self, member: 'CrewMember', target_x: int, target_y: int, station_map: 'StationMap'):
        """Simple greedy step towards target."""
        dx = 1 if target_x > member.location[0] else -1 if target_x < member.location[0] else 0
        dy = 1 if target_y > member.location[1] else -1 if target_y < member.location[1] else 0
        member.move(dx, dy, station_map)

    def _pursue_player(self, member: 'CrewMember', game_state: 'GameState'):
        """Move one step toward the player when detected via perception."""
        player = getattr(game_state, "player", None)
        if not player:
            return
        tx, ty = player.location
        self._pathfind_step(member, tx, ty, game_state.station_map)
