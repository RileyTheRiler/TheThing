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
        event_bus.subscribe(EventType.REPAIR_COMPLETE, self.on_repair_complete)
        event_bus.subscribe(EventType.SOS_SENT, self.on_sos_sent)
        event_bus.subscribe(EventType.POPULATION_STATUS, self.on_population_status)

    def cleanup(self):
        event_bus.unsubscribe(EventType.REPAIR_COMPLETE, self.on_repair_complete)
        event_bus.unsubscribe(EventType.SOS_SENT, self.on_sos_sent)
        event_bus.unsubscribe(EventType.POPULATION_STATUS, self.on_population_status)

    def _endings_for_trigger(self, trigger: str):
        return [e for e in self.config.get("endings", []) if e.get("trigger") == trigger]

    def _emit_ending(self, ending: dict, extra_payload: dict | None = None):
        if self.resolved:
            return

        payload = {
            "result": ending.get("result", "win"),
            "message": ending.get("message"),
            "brief": self.config.get("summary"),
            "ending_id": ending.get("id"),
        }
        if extra_payload:
            payload.update(extra_payload)

        event_bus.emit(GameEvent(EventType.ENDING_REPORT, payload))
        self.resolved = True

    def on_repair_complete(self, event: GameEvent):
        if self.resolved:
            return

        status = event.payload.get("status")
        turn = event.payload.get("turn")
        for ending in self._endings_for_trigger("repair_complete"):
            expected_status = ending.get("status")
            if expected_status and expected_status != status:
                continue
            self._emit_ending(ending, {"status": status, "turn": turn})
            break

    def on_sos_sent(self, event: GameEvent):
        if self.resolved:
            return

        arrived = event.payload.get("arrived")
        turn = event.payload.get("turn")
        for ending in self._endings_for_trigger("sos_sent"):
            required_arrival = ending.get("arrived", True)
            if required_arrival and not arrived:
                continue
            self._emit_ending(ending, {"arrived": arrived, "turn": turn})
            break

    def on_population_status(self, event: GameEvent):
        if self.resolved:
            return

        living_humans = event.payload.get("living_humans")
        living_crew = event.payload.get("living_crew", living_humans)
        player_alive = event.payload.get("player_alive", False)
        if not player_alive:
            return

        for ending in self._endings_for_trigger("population_status"):
            if living_crew == 1 or living_humans == 1:
                self._emit_ending(ending, {
                    "living_humans": living_humans,
                    "living_crew": living_crew
                })
                break
