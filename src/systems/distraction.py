"""Distraction mechanics for throwable items.

Allows players to throw items toward a target location (room or coordinates) to create
high-noise PERCEPTION_EVENTs that pull NPC investigation.
"""

from typing import Tuple, TYPE_CHECKING, List
from typing import Optional, Tuple, TYPE_CHECKING, List
from core.event_system import event_bus, EventType, GameEvent

if TYPE_CHECKING:
    from engine import GameState
    from entities.item import Item
    from entities.crew_member import CrewMember


class DistractionSystem:
    """Compute landing tiles for thrown items and broadcast distraction events."""

    MIN_DISTANCE = 3
    MAX_DISTANCE = 5
    INVESTIGATION_TURNS = 2

    def __init__(self):
        self.active_distractions: List[Tuple[Tuple[int, int], int, str]] = []
    """Handles throwable item mechanics and NPC distraction behavior.

    When a throwable item is used:
    1. Calculate landing position based on direction/target
    2. Remove item from player inventory (if consumable)
    3. Emit PERCEPTION_EVENT at landing location
    4. Nearby NPCs interrupt current action and investigate
    """

    # How far items travel when thrown (in tiles)
    MIN_THROW_DISTANCE = 3
    MAX_THROW_DISTANCE = 5

    # Investigation duration for distraction sounds
    INVESTIGATION_TURNS = 3
    INVESTIGATION_LINGER = 2
    HIGH_NOISE_FLOOR = 5

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
        self.active_distractions = []  # List of (location, turns_remaining, item_name, noise_level)
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def on_turn_advance(self, event: GameEvent):
        """Decay active distractions each turn."""
        remaining = []
        for loc, turns, name in self.active_distractions:
            if turns > 1:
                remaining.append((loc, turns - 1, name))
        self.active_distractions = remaining

    def throw_toward(self, player: "CrewMember", item: "Item", target: Tuple[int, int],
                     game_state: "GameState") -> Tuple[bool, str]:
        """Throw ``item`` toward ``target`` coordinates."""
        if not getattr(item, "throwable", False):
            return False, f"You can't throw the {item.name}."

        landing = game_state.station_map.project_toward(
            player.location, target, min_distance=self.MIN_DISTANCE, max_distance=self.MAX_DISTANCE
        new_distractions = []
        for loc, turns, item_name, noise in self.active_distractions:
            if turns > 1:
                new_distractions.append((loc, turns - 1, item_name, noise))
        self.active_distractions = new_distractions

    def throw_item(self, player: 'CrewMember', item: 'Item', target: str,
                   game_state: 'GameState') -> Tuple[bool, str]:
        """
        Throw an item in a direction to create a distraction.

        Args:
            player: The player throwing the item
            item: The throwable item
            target: Direction to throw (N/S/E/W) or coordinates string
            game_state: Current game state

        Returns:
            Tuple of (success, message)
        """
        if not getattr(item, 'throwable', False):
            return False, f"You can't throw the {item.name}."

        # Get direction vector
        direction_vec = self._parse_target_vector(target, player.location, game_state.station_map)
        if not direction_vec:
            return False, f"Invalid throw target: {target}. Use N/S/E/W/NE/NW/SE/SW or coordinates like 10,12."

        # Calculate landing position
        landing_pos = self._calculate_landing(
            player.location, direction_vec, game_state.station_map, game_state
        )
        if not landing:
            return False, "The throw has nowhere valid to land in that direction."

        noise_level = max(getattr(item, "noise_level", 4), 5)  # force high noise for distraction pulls
        creates_light = getattr(item, "creates_light", False)

        if item.uses > 0:
            item.consume()
            if item.uses <= 0 and item in player.inventory:
                player.inventory.remove(item)

        landing_room = game_state.station_map.get_room_name(*landing)

        self.active_distractions.append((landing, self.INVESTIGATION_TURNS, item.name))
        if not landing_pos:
            return False, "There's nowhere for the item to land in that direction."

        # Get noise level from item
        noise_level = max(getattr(item, 'noise_level', 4), self.HIGH_NOISE_FLOOR)
        creates_light = getattr(item, 'creates_light', False)

        # Remove from inventory first so the thrown item leaves the player's hands
        if item in player.inventory:
            player.inventory.remove(item)

        # Consume item if it has limited uses
        consumed = False
        if item.uses > 0:
            item.consume()
            consumed = item.uses <= 0

        # Get room name for the landing position
        landing_room = game_state.station_map.get_room_name(*landing_pos)
        player_room = game_state.station_map.get_room_name(*player.location)
        item.add_history(game_state.turn, f"Thrown from {player_room} to {landing_room}")

        # Track active distraction
        self.active_distractions.append(
            (landing_pos, self.INVESTIGATION_TURNS, item.name, noise_level)
        )

        event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, {
            "source": "distraction",
            "source_item": item.name,
            "target_location": landing,
            "room": landing_room,
            "noise_level": noise_level,
            "creates_light": creates_light,
            "priority_override": 3,
            "linger_turns": self.INVESTIGATION_TURNS,
            "game_state": game_state,
            "intensity": noise_level
            "target_location": landing_pos,
            "location": landing_pos,
            "room": landing_room,
            "noise_level": noise_level,
            "creates_light": creates_light,
            "priority_override": 2,
            "intensity": noise_level,
            "linger_turns": self.INVESTIGATION_LINGER,
            "investigation_turns": self.INVESTIGATION_TURNS,
            "game_state": game_state
        }))

        heard = self._distract_nearby_npcs(landing, noise_level, game_state)

        message = f"You hurl the {item.name} toward {landing_room} (tile {landing[0]},{landing[1]})."
        if creates_light:
            message += " A flare erupts in a wash of light!"
        else:
            message += " It hits with a loud clatter."

        if heard:
            preview = ", ".join(heard[:3])
            if len(heard) > 3:
                preview += f" (+{len(heard)-3} more)"
            message += f" {preview} react to the noise."

        if item.uses < 0 or item.uses > 0:
            game_state.station_map.add_item_to_room(item, *landing, game_state.turn)

        return True, message
            msg = f"You throw the {item.name} toward {landing_room}. It lands with a bright flash!"
        else:
            msg = f"You throw the {item.name} toward {landing_room}. It clatters loudly!"

        if npcs_distracted:
            npc_names = ", ".join(npcs_distracted[:3])
            if len(npcs_distracted) > 3:
                npc_names += f" and {len(npcs_distracted) - 3} others"
            msg += f" {npc_names} turns to investigate."

        # Drop item on ground if reusable
        if item.uses < 0 or (item.uses > 0 and not consumed):  # -1 means infinite, >0 means still has uses
            game_state.station_map.add_item_to_room(item, *landing_pos, game_state.turn)

        return True, msg

    def _parse_target_vector(self, target: str, origin: Tuple[int, int], station_map) -> Optional[Tuple[int, int]]:
        """Convert a target string into a normalized direction vector."""
        if not target:
            return None
        target = target.upper()
        if target in self.DIRECTIONS:
            return self.DIRECTIONS[target]

        # Coordinates style input: "10,12" or "10 12"
        cleaned = target.replace(",", " ")
        parts = [p for p in cleaned.split() if p]
        if len(parts) == 2 and all(p.lstrip("+-").isdigit() for p in parts):
            tx, ty = int(parts[0]), int(parts[1])
            if not station_map.is_walkable(tx, ty):
                return None
            dx = tx - origin[0]
            dy = ty - origin[1]
            if dx == 0 and dy == 0:
                return None
            return (self._normalize(dx), self._normalize(dy))
        return None

    def _normalize(self, delta: int) -> int:
        """Normalize delta to -1, 0, or 1 for direction vectors."""
        if delta > 0:
            return 1
        if delta < 0:
            return -1
        return 0

    def _calculate_landing(self, start: Tuple[int, int], direction: Tuple[int, int],
                           station_map, game_state: 'GameState') -> Optional[Tuple[int, int]]:
        """Calculate where a thrown item lands using StationMap helper."""
        candidate_tiles: List[Tuple[int, int]] = station_map.get_throw_landing_tiles(
            start, direction, min_distance=self.MIN_THROW_DISTANCE, max_distance=self.MAX_THROW_DISTANCE
        )
        if not candidate_tiles:
            return None
        # Favor further tiles but introduce a touch of randomness
        if len(candidate_tiles) == 1:
            return candidate_tiles[0]
        return game_state.rng.choose(candidate_tiles[-2:]) if hasattr(game_state, "rng") else candidate_tiles[-1]

    def _distract_nearby_npcs(self, location: Tuple[int, int], noise_level: int,
                              game_state: "GameState") -> List[str]:
        """Mark nearby NPCs to investigate the distraction source."""
        heard: List[str] = []
        station_map = game_state.station_map
        hearing_range = noise_level + 2
        room = station_map.get_room_name(*location)

        for npc in game_state.crew:
            if npc == game_state.player or not npc.is_alive:
                continue
            dist = abs(npc.location[0] - location[0]) + abs(npc.location[1] - location[1])
            if dist > hearing_range:
                continue
            heard.append(npc.name)
            self._flag_investigation(npc, location, room, game_state)
            npc_room = station_map.get_room_name(*npc.location)
            if npc_room == room:
                event_bus.emit(GameEvent(EventType.DIALOGUE, {
                    "speaker": npc.name,
                    "text": "What was that noise?"
                }))

        return heard

    def _flag_investigation(self, npc: "CrewMember", location: Tuple[int, int],
                            room: str, game_state: "GameState"):
        npc.investigating = True
        npc.investigation_goal = location
        npc.investigation_priority = max(getattr(npc, "investigation_priority", 0), 3)
        npc.investigation_expires = game_state.turn + self.INVESTIGATION_TURNS
        npc.investigation_loops = self.INVESTIGATION_TURNS
        npc.investigation_source = "distraction"
        if hasattr(npc, "detected_player"):
            npc.detected_player = False
        if hasattr(npc, "search_targets"):
        npc.investigation_priority = max(getattr(npc, "investigation_priority", 0), 2)
        npc.investigation_source = "distraction"
        npc.investigation_expires = game_state.turn + self.INVESTIGATION_TURNS

        # Set search targets for the distraction location
        if hasattr(npc, 'search_targets'):
            npc.search_targets = [location]
            npc.current_search_target = None
            npc.search_turns_remaining = self.INVESTIGATION_TURNS

        event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
            "text": f"{npc.name} peels off to investigate a noise in {room}."
        }))

    def get_throwable_items(self, player: "CrewMember") -> list:
        return [i for i in player.inventory if getattr(i, "throwable", False)]

    def has_active_distraction_at(self, location: Tuple[int, int]) -> bool:
        for loc, turns, _ in self.active_distractions:
        """Check if there's an active distraction at a location."""
        for loc, turns, *_ in self.active_distractions:
            if loc == location and turns > 0:
                return True
        return False

    def get_active_distractions(self) -> list:
        return [(loc, item) for loc, turns, item in self.active_distractions if turns > 0]
        """Get all active distraction locations for UI display."""
        return [(loc, item) for loc, turns, item, _ in self.active_distractions if turns > 0]
