from typing import Optional

from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent


class EndgameSystem:
    """
    Surfaces ending triggers over the event bus so presentation layers
    can react without directly coupling to win/lose checks.
    """

    def __init__(self, design_registry: Optional[DesignBriefRegistry] = None):
        self.design_registry = design_registry or DesignBriefRegistry()
        self.config = self.design_registry.get_brief("endings")
        self.resolved = False
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def on_turn_advance(self, event: GameEvent):
        if self.resolved:
            return

        game_state = event.payload.get("game_state")
        if not game_state or not hasattr(game_state, "check_game_over"):
            return

        game_over, won, message = game_state.check_game_over()
        if not game_over:
            return

        payload = {
            "result": "win" if won else "loss",
            "message": message,
            "turn": getattr(game_state, "turn", None),
            "brief": self.config.get("summary"),
        }
        event_bus.emit(GameEvent(EventType.ENDING_REPORT, payload))
        self.resolved = True
