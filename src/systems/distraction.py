"""Distraction mechanics for The Thing game.

Allows players to throw items to create noise at target locations,
diverting NPC attention away from the player.
"""

from typing import Optional, Tuple, TYPE_CHECKING
from core.event_system import event_bus, EventType, GameEvent

if TYPE_CHECKING:
    from engine import GameState
    from entities.item import Item
    from entities.crew_member import CrewMember


class DistractionSystem:
    """Handles throwable item mechanics and NPC distraction behavior.

    When a throwable item is used:
    1. Calculate landing position based on direction/target
    2. Remove item from player inventory (if consumable)
    3. Emit PERCEPTION_EVENT at landing location
    4. Nearby NPCs interrupt current action and investigate
    """

    # How far items travel when thrown (in tiles)
    DEFAULT_THROW_DISTANCE = 4
    MIN_THROW_DISTANCE = 2
    MAX_THROW_DISTANCE = 6

    # Investigation duration for distraction sounds
    INVESTIGATION_TURNS = 3

    # Direction vectors
    DIRECTIONS = {
        "N": (0, -1), "NORTH": (0, -1),
        "S": (0, 1), "SOUTH": (0, 1),
        "E": (1, 0), "EAST": (1, 0),
        "W": (-1, 0), "WEST": (-1, 0),
        "NE": (1, -1), "NORTHEAST": (1, -1),
        "NW": (-1, -1), "NORTHWEST": (-1, -1),
        "SE": (1, 1), "SOUTHEAST": (1, 1),
        "SW": (-1, 1), "SOUTHWEST": (-1, 1),
    }

    def __init__(self):
        # Track active distractions for investigation behavior
        self.active_distractions = []  # List of (location, turns_remaining, item_name)
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        """Unsubscribe from events."""
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def on_turn_advance(self, event: GameEvent):
        """Decay active distractions each turn."""
        new_distractions = []
        for loc, turns, item_name in self.active_distractions:
            if turns > 1:
                new_distractions.append((loc, turns - 1, item_name))
        self.active_distractions = new_distractions

    def throw_item(self, player: 'CrewMember', item: 'Item', direction: str,
                   game_state: 'GameState') -> Tuple[bool, str]:
        """
        Throw an item in a direction to create a distraction.

        Args:
            player: The player throwing the item
            item: The throwable item
            direction: Direction to throw (N/S/E/W or room name)
            game_state: Current game state

        Returns:
            Tuple of (success, message)
        """
        if not getattr(item, 'throwable', False):
            return False, f"You can't throw the {item.name}."

        # Get direction vector
        direction = direction.upper()
        if direction not in self.DIRECTIONS:
            return False, f"Invalid direction: {direction}. Use N/S/E/W or NE/NW/SE/SW."

        dx, dy = self.DIRECTIONS[direction]

        # Calculate landing position
        landing_pos = self._calculate_landing(
            player.location, dx, dy, game_state.station_map
        )

        if not landing_pos:
            return False, "There's nowhere for the item to land in that direction."

        # Get noise level from item
        noise_level = getattr(item, 'noise_level', 4)
        creates_light = getattr(item, 'creates_light', False)

        # Consume item if it has limited uses
        if item.uses > 0:
            item.consume()
            if item.uses <= 0:
                player.inventory.remove(item)

        # Get room name for the landing position
        landing_room = game_state.station_map.get_room_name(*landing_pos)
        player_room = game_state.station_map.get_room_name(*player.location)

        # Track active distraction
        self.active_distractions.append(
            (landing_pos, self.INVESTIGATION_TURNS, item.name)
        )

        # Emit PERCEPTION_EVENT for the distraction
        event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, {
            "source": "distraction",
            "source_item": item.name,
            "location": landing_pos,
            "target_location": landing_pos,
            "room": landing_room,
            "noise_level": noise_level,
            "intensity": noise_level,
            "priority_override": 1,
            "linger_turns": self.INVESTIGATION_TURNS,
            "creates_light": creates_light,
            "game_state": game_state
        }))

        # Notify nearby NPCs about the distraction
        npcs_distracted = self._distract_nearby_npcs(
            landing_pos, noise_level, game_state
        )

        # Generate result message
        if creates_light:
            msg = f"You throw the {item.name} {direction}. It lands in {landing_room} with a bright flash!"
        else:
            msg = f"You throw the {item.name} {direction}. It clatters loudly in {landing_room}!"

        if npcs_distracted:
            npc_names = ", ".join(npcs_distracted[:3])
            if len(npcs_distracted) > 3:
                npc_names += f" and {len(npcs_distracted) - 3} others"
            msg += f" {npc_names} turns to investigate."

        # Drop item on ground if reusable
        if item.uses < 0 or item.uses > 0:  # -1 means infinite, >0 means still has uses
            game_state.station_map.add_item_to_room(item, *landing_pos, game_state.turn)

        return True, msg

    def _calculate_landing(self, start: Tuple[int, int], dx: int, dy: int,
                           station_map) -> Optional[Tuple[int, int]]:
        """Calculate where a thrown item lands."""
        x, y = start
        last_valid = None

        # Travel in direction until hitting a wall or max distance
        for distance in range(1, self.MAX_THROW_DISTANCE + 1):
            new_x = x + (dx * distance)
            new_y = y + (dy * distance)

            if station_map.is_walkable(new_x, new_y):
                last_valid = (new_x, new_y)
                if distance >= self.DEFAULT_THROW_DISTANCE:
                    break
            else:
                # Hit a wall, item lands at last valid position
                break

        return last_valid

    def _distract_nearby_npcs(self, location: Tuple[int, int], noise_level: int,
                              game_state: 'GameState') -> list:
        """
        Alert NPCs within hearing range of the distraction.

        NPCs will stop current action and investigate the noise source.
        """
        distracted_npcs = []
        station_map = game_state.station_map
        distraction_room = station_map.get_room_name(*location)

        # Hearing range based on noise level (higher noise = further hearing)
        hearing_range = noise_level + 2

        for npc in game_state.crew:
            if npc == game_state.player or not npc.is_alive:
                continue

            # Calculate distance to distraction
            dist = abs(npc.location[0] - location[0]) + abs(npc.location[1] - location[1])

            if dist <= hearing_range:
                # NPC hears the distraction
                self._set_investigation_target(npc, location, distraction_room, game_state)
                distracted_npcs.append(npc.name)

                # Emit dialogue for nearby NPCs
                npc_room = station_map.get_room_name(*npc.location)
                if npc_room == distraction_room:
                    event_bus.emit(GameEvent(EventType.DIALOGUE, {
                        "speaker": npc.name,
                        "text": "What was that noise?"
                    }))

        return distracted_npcs

    def _set_investigation_target(self, npc: 'CrewMember', location: Tuple[int, int],
                                   room: str, game_state: 'GameState'):
        """Set an NPC to investigate a distraction location."""
        # Override current activity with investigation
        npc.investigating = True

        # Set search targets for the distraction location
        if hasattr(npc, 'search_targets'):
            npc.search_targets = [location]
            npc.current_search_target = None
            npc.search_turns_remaining = self.INVESTIGATION_TURNS

        # Clear any player tracking temporarily
        if hasattr(npc, 'detected_player'):
            npc.detected_player = False

        # Emit investigation event
        event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
            "text": f"{npc.name} goes to investigate noise in {room}."
        }))

    def get_throwable_items(self, player: 'CrewMember') -> list:
        """Get list of throwable items in player's inventory."""
        return [item for item in player.inventory if getattr(item, 'throwable', False)]

    def has_active_distraction_at(self, location: Tuple[int, int]) -> bool:
        """Check if there's an active distraction at a location."""
        for loc, turns, _ in self.active_distractions:
            if loc == location and turns > 0:
                return True
        return False

    def get_active_distractions(self) -> list:
        """Get all active distraction locations for UI display."""
        return [(loc, item) for loc, turns, item in self.active_distractions if turns > 0]
