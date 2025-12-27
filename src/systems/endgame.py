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
        }
        event_bus.emit(GameEvent(EventType.ENDING_REPORT, payload))
        self.resolved = True
