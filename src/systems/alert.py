"""Station-wide alert system for The Thing game.

When a human NPC detects the player acting suspiciously, a station-wide
alert is triggered that makes all NPCs more vigilant for a set duration.
"""

from typing import Optional, TYPE_CHECKING
from core.event_system import event_bus, EventType, GameEvent

if TYPE_CHECKING:
    from engine import GameState


class AlertSystem:
    """Manages station-wide alert status.

    When triggered:
    - All NPC observation pools receive +2 bonus
    - Alert message displayed to player
    - Alert decays by 1 each turn until reaching 0
    """

    # Configuration
    DEFAULT_ALERT_DURATION = 10  # Turns of heightened vigilance
    OBSERVATION_BONUS = 2        # Bonus to all NPC observation pools during alert

    def __init__(self, game_state: Optional['GameState'] = None):
        self.game_state = game_state
        self._alert_active = False
        self._alert_turns_remaining = 0
        self._triggering_observer = None  # Who triggered the alert

        if self.game_state:
            # Ensure the game exposes alert fields for other systems even before a trigger
            if not hasattr(self.game_state, "alert_status"):
                self.game_state.alert_status = "CALM"
            if not hasattr(self.game_state, "alert_turns_remaining"):
                self.game_state.alert_turns_remaining = 0

        # Subscribe to relevant events
        event_bus.subscribe(EventType.PERCEPTION_EVENT, self.on_perception_event)
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        """Unsubscribe from events."""
        event_bus.unsubscribe(EventType.PERCEPTION_EVENT, self.on_perception_event)
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    @property
    def is_active(self) -> bool:
        """Check if station alert is currently active."""
        return self._alert_active and self._alert_turns_remaining > 0

    @property
    def turns_remaining(self) -> int:
        """Get remaining turns of alert status."""
        return self._alert_turns_remaining

    def on_perception_event(self, event: GameEvent):
        """Handle perception events to trigger alerts when player is detected."""
        payload = event.payload
        if not payload:
            return

        outcome = payload.get("outcome")
        if outcome != "detected":
            return

        # Get the observer who detected the player
        observer_ref = payload.get("opponent_ref")
        if not observer_ref:
            return

        # Only human NPCs trigger station-wide alerts
        # Infected NPCs coordinate privately instead
        if getattr(observer_ref, "is_infected", False):
            return

        # Don't re-trigger if already on high alert
        if self._alert_turns_remaining >= self.DEFAULT_ALERT_DURATION // 2:
            return

        # Trigger station alert
        self._trigger_alert(observer_ref, payload.get("game_state") or self.game_state)

    def _trigger_alert(self, observer, game_state: Optional['GameState']):
        """Activate station-wide alert."""
        gs = game_state or self.game_state
        game_state = game_state or self.game_state
        self._alert_active = True
        self._alert_turns_remaining = self.DEFAULT_ALERT_DURATION
        self._triggering_observer = observer.name if observer else "Unknown"
        self._sync_game_state(gs, status="alert")

        # Mirror state on the game for UI/AI access
        if game_state:
            game_state.alert_status = "ALERT"
            game_state.alert_turns_remaining = self._alert_turns_remaining

        # Emit warning to player
        event_bus.emit(GameEvent(EventType.WARNING, {
            "text": f"ALERT: {self._triggering_observer} has raised the alarm! All crew are now on high alert."
        }))

        if game_state and getattr(game_state, "audio", None):
            game_state.audio.trigger_event('alert')

        # Emit station alert event for other systems
        event_bus.emit(GameEvent(EventType.STATION_ALERT, {
            "triggered_by": self._triggering_observer,
            "duration": self._alert_turns_remaining,
            "active": True,
            "game_state": gs
        }))

        # Log to game journal if available
        if gs and hasattr(gs, 'journal'):
            game_state.journal.append(
                f"[Turn {getattr(gs, 'turn', '?')}] STATION ALERT triggered by {self._triggering_observer}"
            )

    def on_turn_advance(self, event: GameEvent):
        """Decay alert status each turn."""
        if not self._alert_active:
            return

        self._alert_turns_remaining = max(0, self._alert_turns_remaining - 1)

        game_state = event.payload.get("game_state") or self.game_state
        self._sync_game_state(game_state)
        game_state = event.payload.get("game_state") if event.payload else None
        if not game_state:
            game_state = self.game_state
        if game_state:
            game_state.alert_turns_remaining = max(0, self._alert_turns_remaining)

        if self._alert_turns_remaining <= 0:
            self._deactivate_alert(game_state)
        elif self._alert_turns_remaining == 5:
            # Halfway warning
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": "The station is calming down. Alert level decreasing."
            }))
        elif self._alert_turns_remaining == 2:
            # Almost over
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": "Crew vigilance returning to normal levels."
            }))

    def _deactivate_alert(self, game_state: Optional['GameState']):
        """End the station alert."""
        game_state = game_state or self.game_state
        self._alert_active = False
        self._alert_turns_remaining = 0
        self._sync_game_state(game_state or self.game_state, status="calm")

        if game_state:
            game_state.alert_status = "CALM"
            game_state.alert_turns_remaining = 0

        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": "Station alert has ended. Crew returning to normal routines."
        }))

        # Emit event for other systems
        event_bus.emit(GameEvent(EventType.STATION_ALERT, {
            "triggered_by": None,
            "duration": 0,
            "active": False,
            "game_state": game_state
        }))

    def get_observation_bonus(self) -> int:
        """Get the observation pool bonus during alert.

        This should be added to all NPC observation checks while alert is active.
        Bonus decays as the timer winds down to represent crews calming.
        """
        if self.is_active:
            # Scale bonus slightly as alert winds down
            decay_ratio = self._alert_turns_remaining / self.DEFAULT_ALERT_DURATION
            return max(1, int(self.OBSERVATION_BONUS * max(0.5, decay_ratio)))
        return 0

    def get_speed_bonus(self) -> int:
        """Provide extra movement steps for AI pathfinding during alert."""
        if self.is_active:
            return 1  # One extra step while alert is active
        return 0
        if not self.is_active:
            return 0

        if self._alert_turns_remaining <= 2:
            return max(1, self.OBSERVATION_BONUS - 1)
        return self.OBSERVATION_BONUS

    def get_speed_multiplier(self) -> int:
        """Movement speed multiplier for AI while alert is active."""
        if not self.is_active:
            return 1
        # Early alert turns are more frantic
        if self._alert_turns_remaining > self.DEFAULT_ALERT_DURATION // 2:
            return 2
        return 1

    def force_trigger(self, duration: int = None):
        """Manually trigger an alert (for testing or special events)."""
        self._alert_active = True
        self._alert_turns_remaining = duration or self.DEFAULT_ALERT_DURATION
        self._triggering_observer = "Emergency"
        self._sync_game_state(self.game_state, status="alert")

        if self.game_state:
            self.game_state.alert_status = "ALERT"
            self.game_state.alert_turns_remaining = self._alert_turns_remaining

        event_bus.emit(GameEvent(EventType.WARNING, {
            "text": "EMERGENCY ALERT: All crew are now on high alert!"
        }))

    def to_dict(self) -> dict:
        """Serialize alert state for saving."""
        return {
            "alert_active": self._alert_active,
            "alert_turns_remaining": self._alert_turns_remaining,
            "triggering_observer": self._triggering_observer
        }

    @classmethod
    def from_dict(cls, data: dict, game_state: Optional['GameState'] = None) -> 'AlertSystem':
        """Deserialize alert state from save data."""
        system = cls(game_state)
        if data:
            system._alert_active = data.get("alert_active", False)
            system._alert_turns_remaining = data.get("alert_turns_remaining", 0)
            system._triggering_observer = data.get("triggering_observer")
            system._sync_game_state(game_state)
            if game_state:
                game_state.alert_status = "ALERT" if system._alert_active else "CALM"
                game_state.alert_turns_remaining = system._alert_turns_remaining
        return system

    def _sync_game_state(self, game_state: Optional['GameState'], status: Optional[str] = None):
        """Mirror alert status/turns to the owning GameState for UI/save visibility."""
        if not game_state:
            return
        self.game_state = game_state
        game_state.alert_status = status or ("alert" if self._alert_active else "calm")
        game_state.alert_turns_remaining = self._alert_turns_remaining
