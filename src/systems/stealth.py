from typing import List, Optional

from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent


class StealthSystem:
    """
    Handles stealth encounters by reacting to TURN_ADVANCE events.
    Emits reporting events so the UI can surface outcomes without direct calls.
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

    def on_turn_advance(self, event: GameEvent):
        if self.cooldown > 0:
            self.cooldown -= 1

        game_state = event.payload.get("game_state")
        rng = event.payload.get("rng")
        if not game_state or rng is None:
            return

        player = getattr(game_state, "player", None)
        crew = getattr(game_state, "crew", [])
        station_map = getattr(game_state, "station_map", None)
        if not player or not station_map:
            return

        room = station_map.get_room_name(*player.location)
        nearby_infected = [
            m for m in self._detect_candidates(crew)
            if getattr(m, "location", None) == player.location
        ]

        if not nearby_infected or self.cooldown > 0:
            return

        detection_chance = self.config.get("base_detection_chance", 0.35)
        detected = rng.random_float() < detection_chance
        opponent = nearby_infected[0]
        payload = {
            "brief": self.config.get("summary"),
            "room": room,
            "opponent": opponent.name,
            "outcome": "detected" if detected else "evaded",
        }
        event_bus.emit(GameEvent(EventType.STEALTH_REPORT, payload))

        if detected:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"{opponent.name} corners you in the {room}!"
            }))
        else:
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"You stay hidden from {opponent.name} in the {room}."
            }))

        self.cooldown = self.config.get("cooldown_turns", 1)
