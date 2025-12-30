"""Distraction mechanics for throwable items.

Allows players to throw items toward a target location (room or coordinates) to create
high-noise PERCEPTION_EVENTs that pull NPC investigation.
"""

from typing import Tuple, TYPE_CHECKING, List
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
            if loc == location and turns > 0:
                return True
        return False

    def get_active_distractions(self) -> list:
        return [(loc, item) for loc, turns, item in self.active_distractions if turns > 0]
