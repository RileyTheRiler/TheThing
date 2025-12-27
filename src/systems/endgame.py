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
        event_bus.subscribe(EventType.REPAIR_COMPLETE, self.on_repair_complete)
        event_bus.subscribe(EventType.SOS_SENT, self.on_sos_sent)
        event_bus.subscribe(EventType.POPULATION_STATUS, self.on_population_status)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.unsubscribe(EventType.CREW_DEATH, self.on_crew_death)
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

    def on_turn_advance(self, event: GameEvent):
        """Monitor rescue countdown and periodic checks."""
        if self.resolved:
            return

        game_state = event.payload.get("game_state")
        if not game_state:
            return

        # Check for Rescue Arrival
        if getattr(game_state, "rescue_signal_active", False) and getattr(game_state, "rescue_turns_remaining", None) is not None:
            if game_state.rescue_turns_remaining <= 0:
                # Custom check not in brief yet, or should be
                # We can try to finding it
                endings = self._endings_for_trigger("rescue_arrival")
                if endings:
                    self._emit_ending(endings[0], {"turn": game_state.turn})
                else:
                    # Fallback
                    self._emit_ending({
                        "id": "rescue",
                        "result": "win",
                        "message": "The rescue team has arrived!"
                    })
                return

        # Periodic check for Extermination or Consumption via population logic
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
             endings = self._endings_for_trigger("player_death")
             if endings:
                 self._emit_ending(endings[0])
             else:
                self._emit_ending({
                    "id": "death",
                    "result": "loss",
                    "message": "You have died."
                })
        else:
            self._check_population_endings(game_state)

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
            # Should have been caught by on_crew_death, but safe to check
            return

        for ending in self._endings_for_trigger("population_status"):
            # Simple logic matching brief conditions which usually specify human_count==1 etc
            # This is complex to match exactly without robust rule engine, 
            # assuming simplified check here:
            if ending.get("condition") == "sole_survivor" and living_crew == 1:
                 self._emit_ending(ending)
            elif ending.get("condition") == "extermination" and living_humans > 0 and living_crew == living_humans:
                 self._emit_ending(ending)
            elif ending.get("condition") == "all_dead" and living_humans == 0:
                 self._emit_ending(ending)

    def _check_population_endings(self, game_state):
        """Legacy check for endings if brief system misses."""
        if self.resolved: return
        
        living_crew = [m for m in game_state.crew if m.is_alive]
        living_humans = [m for m in living_crew if not m.is_infected]
        living_infected = [m for m in living_crew if m.is_infected and m != game_state.player]
        
        # Player is infected and revealed (Lose)
        if game_state.player.is_infected and getattr(game_state.player, "is_revealed", False):
            self._emit_ending({
                "id": "consumption",
                "result": "loss",
                "message": "You have been revealed as The Thing."
            })
            return

        # No humans left (Lose)
        if not living_humans:
             self._emit_ending({
                "id": "total_infection",
                "result": "loss",
                "message": "All humans have been assimilated."
            })
             return

        # Sole Survivor (Win)
        if len(living_crew) == 1 and living_crew[0] == game_state.player:
            self._emit_ending({
                "id": "sole_survivor",
                "result": "win",
                "message": "You are the only survivor."
            })
            return

        # Extermination (Win)
        if not living_infected and len(living_crew) > 0:
            # This is harder to verify without omniscience, but assuming check is allowed
            pass
