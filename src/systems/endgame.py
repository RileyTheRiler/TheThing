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
        self.ending_definitions = {e.get("id"): e for e in self.config.get("endings", []) if e.get("id")}
        self.resolved = False
        
        # Subscribe to triggers
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.subscribe(EventType.CREW_DEATH, self.on_crew_death)
        event_bus.subscribe(EventType.HELICOPTER_REPAIRED, self.on_helicopter_repaired)
        event_bus.subscribe(EventType.SOS_EMITTED, self.on_sos_emitted)
        event_bus.subscribe(EventType.SOS_SENT, self.on_rescue_arrival)
        event_bus.subscribe(EventType.ESCAPE_SUCCESS, self.on_escape_success)
        # Tier 9 endings
        event_bus.subscribe(EventType.GENERATOR_DESTROYED, self.on_generator_destroyed)
        event_bus.subscribe(EventType.UFO_CONSTRUCTED, self.on_ufo_constructed)
        # Tier 8: Mutiny
        event_bus.subscribe(EventType.MUTINY_TRIGGERED, self.on_mutiny_execution)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.unsubscribe(EventType.CREW_DEATH, self.on_crew_death)
        event_bus.unsubscribe(EventType.HELICOPTER_REPAIRED, self.on_helicopter_repaired)
        event_bus.unsubscribe(EventType.SOS_EMITTED, self.on_sos_emitted)
        event_bus.unsubscribe(EventType.SOS_SENT, self.on_rescue_arrival)
        event_bus.unsubscribe(EventType.ESCAPE_SUCCESS, self.on_escape_success)
        event_bus.unsubscribe(EventType.GENERATOR_DESTROYED, self.on_generator_destroyed)
        event_bus.unsubscribe(EventType.UFO_CONSTRUCTED, self.on_ufo_constructed)
        event_bus.unsubscribe(EventType.MUTINY_TRIGGERED, self.on_mutiny_execution)

    def on_turn_advance(self, event: GameEvent):
        """Monitor rescue countdown and periodic checks."""
        if self.resolved:
            return

        game_state = event.payload.get("game_state")
        if not game_state:
            return

        self._check_escape_routes(game_state)
        if getattr(game_state, "escape_route", None) == "overland" and getattr(game_state, "overland_escape_turns", 1) == 0:
            self._resolve_ending("PYRRHIC_VICTORY", game_state, ending_id="pyrrhic_victory")
            return

        # Check for Rescue Arrival
        if getattr(game_state, "rescue_signal_active", False) and getattr(game_state, "rescue_turns_remaining", None) is not None:
            if game_state.rescue_turns_remaining <= 0:
                self._resolve_ending("RESCUE", game_state, ending_id="radio_rescue")
                return

        # Periodic check for Extermination or Consumption
        self._check_population_endings(game_state)
        
        # Check for Freeze Out ending (Tier 9)
        self._check_freeze_out(game_state)

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
            self._resolve_ending("DEATH", game_state, ending_id="death")
            self._resolve_ending("DEATH", game_state, ending_id="macready_death")
            return

        self._check_population_endings(game_state)

    def on_helicopter_repaired(self, event: GameEvent):
        """Track helicopter status."""
        game_state = event.payload.get("game_state")
        if game_state:
            game_state.helicopter_status = "FIXED"
            game_state.helicopter_operational = True
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": "The helicopter engine roars to life! It's ready for takeoff."
            }))

    def on_sos_emitted(self, event: GameEvent):
        """Track SOS activation."""
        game_state = event.payload.get("game_state")
        if game_state:
            game_state.rescue_signal_active = True
            eta = getattr(game_state, "rescue_eta_turns", 20)
            game_state.rescue_turns_remaining = eta  # 20 turns until rescue
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"SOS signal verified. Rescue team ETA: {eta} hours."
            }))

    def on_rescue_arrival(self, event: GameEvent):
        """Triggered when the rescue team actually arrives."""
        if self.resolved:
            return

        if not event.payload.get("arrived"):
            return

        game_state = event.payload.get("game_state")
        if game_state:
            self._resolve_ending("RESCUE", game_state, ending_id="radio_rescue")

    def on_escape_success(self, event: GameEvent):
        """Triggered when player successfully flies away."""
        if self.resolved:
            return
        
        game_state = event.payload.get("game_state")
        if game_state:
            game_state.helicopter_status = "ESCAPED"
            self._resolve_escape(game_state)
            # Check if player is infected?
            if game_state.player.is_infected:
                 # It's a win for the Thing, but technically an "Escape" ending structure
                 # depending on how we want to flavor it. The config separates them?
                 # Config has ESCAPE.
                 pass
            
            route = event.payload.get("route") or getattr(game_state, "escape_route", None)
            if route:
                game_state.escape_route = route
            game_state.helicopter_status = "ESCAPED"
            ending_key = "ESCAPE"
            ending_id = "helicopter_escape"
            if route == "overland" or getattr(game_state, "escape_route", None) == "overland":
                ending_key = "PYRRHIC_VICTORY" if not getattr(game_state, "power_on", True) else "ESCAPE"
                ending_id = "pyrrhic_victory" if ending_key == "PYRRHIC_VICTORY" else "overland_escape"
            self._resolve_ending(ending_key, game_state, ending_id=ending_id)

    def _check_population_endings(self, game_state):
        """Check for Sole Survivor, Extermination, or Consumption."""
        living_crew = [m for m in game_state.crew if m.is_alive]
        living_humans = [m for m in living_crew if not m.is_infected]
        living_infected = [m for m in living_crew if m.is_infected and m != game_state.player]

        # Player is infected and revealed (Lose)
        if game_state.player.is_infected and getattr(game_state.player, "is_revealed", False):
            self._resolve_ending("CONSUMPTION", game_state, ending_id="consumption")
            return

        # No humans left (Lose)
        if not living_humans:
            self._resolve_ending("CONSUMPTION", game_state, ending_id="consumption")
            return

        # Sole Survivor (Win)
        if len(living_crew) == 1 and living_crew[0] == game_state.player:
            self._resolve_ending("SOLE_SURVIVOR", game_state, ending_id="sole_survivor")
            return

        # Extermination (Win)
        # Note: This is simplified. True logic might require "Test" on all corpses or something.
        if not living_infected:
            # Only win if at least one human is left (checked above)
            self._resolve_ending("EXTERMINATION", game_state, ending_id="extermination")

    def _check_escape_routes(self, game_state):
        """Check helicopter and rescue timers for win/loss outcomes."""
        if getattr(game_state, "helicopter_status", None) == "ESCAPED":
            self._resolve_escape(game_state)
            return

        if getattr(game_state, "rescue_signal_active", False) and getattr(game_state, "rescue_turns_remaining", None) is not None:
            if game_state.rescue_turns_remaining <= 0:
                self._resolve_rescue(game_state)

    def _resolve_escape(self, game_state):
        pyro = self._is_pyrrhic(game_state)
        key = "PYRRHIC" if pyro else "ESCAPE"
        ending_id = "pyrrhic_victory" if pyro else "helicopter_escape"
        self._resolve_ending(key, game_state, ending_id=ending_id)

    def _resolve_rescue(self, game_state):
        pyro = self._is_pyrrhic(game_state)
        key = "PYRRHIC" if pyro else "RESCUE"
        ending_id = "pyrrhic_victory" if pyro else "radio_rescue"
        self._resolve_ending(key, game_state, ending_id=ending_id)

    def _is_pyrrhic(self, game_state) -> bool:
        """Determine if the station is effectively lost while you escape."""
        power_ruined = not getattr(game_state, "power_on", True) and getattr(getattr(game_state, "sabotage", None), "power_sabotaged", False)
        return bool(power_ruined)

    def _resolve_ending(self, ending_key: str, game_state, ending_id: Optional[str] = None):
        """Emit the ending report and mark as resolved."""
        state_data = self.states.get(ending_key, {})
        ending_meta = self.ending_definitions.get(ending_id)
        
        payload = {
            "result": "win" if ending_key in ["ESCAPE", "RESCUE", "EXTERMINATION", "SOLE_SURVIVOR", "PYRRHIC"] else "loss",
            "result": "win" if ending_key in ["ESCAPE", "RESCUE", "EXTERMINATION", "SOLE_SURVIVOR", "PYRRHIC_VICTORY"] else "loss",
            "ending_type": ending_key,
            "ending_id": ending_id or ending_key.lower(),
            "name": state_data.get("name", ending_key),
            "message": (ending_meta.get("message") if ending_meta else None) or state_data.get("message", "Game Over"),
            "turn": getattr(game_state, "turn", None),
            "ending_id": ending_id or state_data.get("id") or ending_key.lower(),
        }
        event_bus.emit(GameEvent(EventType.ENDING_REPORT, payload))
        if hasattr(game_state, "game_over"):
            game_state.game_over = True
            game_state.last_ending_payload = payload
        self.resolved = True

    def on_generator_destroyed(self, event: GameEvent):
        """Triggered when the generator is destroyed (Tier 9)."""
        if self.resolved:
            return
        
        game_state = event.payload.get("game_state")
        if game_state:
            # Mark generator as destroyed for freeze out check
            game_state.generator_destroyed = True

    def on_ufo_constructed(self, event: GameEvent):
        """Triggered when an infected NPC completes UFO construction (Tier 9)."""
        if self.resolved:
            return
        
        game_state = event.payload.get("game_state")
        if game_state:
            self._resolve_ending("BLAIR_THING", game_state, ending_id="blair_thing")

    def on_mutiny_execution(self, event: GameEvent):
        """Triggered when mutiny reaches EXECUTION phase - player caught after escape."""
        if self.resolved:
            return
        
        phase = event.payload.get("phase")
        target = event.payload.get("target")
        
        # Only trigger game over on EXECUTION phase
        if phase == "EXECUTION" and target == "MacReady":
            game_state = event.payload.get("game_state")
            if game_state:
                self._resolve_ending("MUTINY", game_state, ending_id="mutiny_execution")

    def _check_freeze_out(self, game_state):
        """Check if conditions are met for the Freeze Out ending."""
        generator_destroyed = getattr(game_state, "generator_destroyed", False)
        if not generator_destroyed:
            return
            
        temperature = getattr(game_state, "temperature", -40)
        
        # At -60°C: Things become dormant (cannot act)
        if temperature <= -60:
            for crew in game_state.crew:
                if getattr(crew, 'is_infected', False) and crew.is_alive:
                    if not getattr(crew, 'is_dormant', False):
                        crew.is_dormant = True
                        event_bus.emit(GameEvent(EventType.MESSAGE, {
                            "text": f"{crew.name} has frozen stiff, unable to move..."
                        }))
        
        # At -80°C: Things die, check for victory
        if temperature <= -80:
            living_things = [c for c in game_state.crew 
                            if getattr(c, 'is_infected', False) and c.is_alive]
            
            # Kill all Things
            for thing in living_things:
                thing.is_alive = False
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": f"The alien cells in {thing.name} have crystallized and died."
                }))
                event_bus.emit(GameEvent(EventType.CREW_DEATH, {
                    "game_state": game_state,
                    "name": thing.name,
                    "cause": "frozen"
                }))
            
            # Kill crew without cold weather gear (except player for now)
            for crew in game_state.crew:
                if crew.is_alive and not getattr(crew, 'is_infected', False) and crew != game_state.player:
                    has_gear = any(
                        "PARKA" in i.name.upper() or "COAT" in i.name.upper() or 
                        "COLD" in i.name.upper() or "THERMAL" in i.name.upper()
                        for i in getattr(crew, 'inventory', [])
                    )
                    if not has_gear:
                        crew.is_alive = False
                        event_bus.emit(GameEvent(EventType.MESSAGE, {
                            "text": f"{crew.name} succumbs to the cold..."
                        }))
                        event_bus.emit(GameEvent(EventType.CREW_DEATH, {
                            "game_state": game_state,
                            "name": crew.name,
                            "cause": "frozen"
                        }))
            
            # Check victory: player alive, all Things frozen/dead
            if game_state.player.is_alive:
                all_things_dead = not any(
                    getattr(c, 'is_infected', False) and c.is_alive 
                    for c in game_state.crew
                )
                if all_things_dead:
                    self._resolve_ending("FREEZE_OUT", game_state, ending_id="freeze_out")

