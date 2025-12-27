from typing import Optional, Dict, Any

from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent


class EndgameSystem:
    """
    Handles multiple ending scenarios by subscribing to game events.
    Emits ENDING_REPORT when a win or loss condition is met.
    """

    def __init__(self, design_registry: Optional[DesignBriefRegistry] = None):
        self.design_registry = design_registry or DesignBriefRegistry()
        self.config = self.design_registry.get_brief("endings")
        self.states = self.config.get("states", {})
        self.resolved = False
<<<<<<< HEAD
        
        # Subscribe to triggers
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.subscribe(EventType.CREW_DEATH, self.on_crew_death)
        event_bus.subscribe(EventType.HELICOPTER_REPAIRED, self.on_helicopter_repaired)
        event_bus.subscribe(EventType.SOS_EMITTED, self.on_sos_emitted)
        event_bus.subscribe(EventType.ESCAPE_SUCCESS, self.on_escape_success)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.unsubscribe(EventType.CREW_DEATH, self.on_crew_death)
        event_bus.unsubscribe(EventType.HELICOPTER_REPAIRED, self.on_helicopter_repaired)
        event_bus.unsubscribe(EventType.SOS_EMITTED, self.on_sos_emitted)
        event_bus.unsubscribe(EventType.ESCAPE_SUCCESS, self.on_escape_success)

    def on_turn_advance(self, event: GameEvent):
        """Monitor rescue countdown and periodic checks."""
        if self.resolved:
            return

        game_state = event.payload.get("game_state")
        if not game_state:
            return

        # Check for Rescue Arrival
        if game_state.rescue_signal_active and game_state.rescue_turns_remaining is not None:
            if game_state.rescue_turns_remaining <= 0:
                self._resolve_ending("RESCUE", game_state)
                return

        # Periodic check for Extermination or Consumption
        self._check_population_endings(game_state)

    def on_crew_death(self, event: GameEvent):
        """Triggered when any crew member dies."""
        if self.resolved:
            return
        
        game_state = event.payload.get("game_state")
        if not game_state:
            return

        # Check if it was the player
        victim_name = event.payload.get("name")
        if victim_name == "MacReady":
            self._resolve_ending("DEATH", game_state)
            return

        self._check_population_endings(game_state)

    def on_helicopter_repaired(self, event: GameEvent):
        """Track helicopter status if needed (mainly for future complex logic)."""
        pass

    def on_sos_emitted(self, event: GameEvent):
        """Track SOS activation."""
        pass

    def on_escape_success(self, event: GameEvent):
        """Triggered when player successfully flies away."""
        if self.resolved:
            return
        
        game_state = event.payload.get("game_state")
        self._resolve_ending("ESCAPE", game_state)

    def _check_population_endings(self, game_state):
        """Check for Sole Survivor, Extermination, or Consumption."""
        living_crew = [m for m in game_state.crew if m.is_alive]
        living_humans = [m for m in living_crew if not m.is_infected]
        living_infected = [m for m in living_crew if m.is_infected and m != game_state.player]

        # Player is infected and revealed (Lose)
        if game_state.player.is_infected and game_state.player.is_revealed:
            self._resolve_ending("CONSUMPTION", game_state)
            return

        # No humans left (Lose)
        if not living_humans:
            self._resolve_ending("CONSUMPTION", game_state)
            return

        # Sole Survivor (Win)
        if len(living_crew) == 1 and living_crew[0] == game_state.player:
            self._resolve_ending("SOLE_SURVIVOR", game_state)
            return

        # Extermination (Win)
        if not living_infected:
            # Only win if at least one human is left (already checked by living_humans)
            self._resolve_ending("EXTERMINATION", game_state)

    def _resolve_ending(self, ending_key: str, game_state):
        """Emit the ending report and mark as resolved."""
        state_data = self.states.get(ending_key, {})
        
        payload = {
            "result": "win" if ending_key in ["ESCAPE", "RESCUE", "EXTERMINATION", "SOLE_SURVIVOR"] else "loss",
            "ending_type": ending_key,
            "name": state_data.get("name", ending_key),
            "message": state_data.get("message", "Game Over"),
            "turn": getattr(game_state, "turn", None),
=======
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
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503
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
