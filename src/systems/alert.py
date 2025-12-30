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
        self._trigger_alert(observer_ref, payload.get("game_state"))

    def _trigger_alert(self, observer, game_state: Optional['GameState']):
        """Activate station-wide alert."""
        self._alert_active = True
        self._alert_turns_remaining = self.DEFAULT_ALERT_DURATION
        self._triggering_observer = observer.name if observer else "Unknown"

        # Emit warning to player
        event_bus.emit(GameEvent(EventType.WARNING, {
            "text": f"ALERT: {self._triggering_observer} has raised the alarm! All crew are now on high alert."
        }))

        # Emit station alert event for other systems
        event_bus.emit(GameEvent(EventType.STATION_ALERT, {
            "triggered_by": self._triggering_observer,
            "duration": self._alert_turns_remaining,
            "active": True,
            "game_state": game_state
        }))

        # Log to game journal if available
        if game_state and hasattr(game_state, 'journal'):
            game_state.journal.append(
                f"[Turn {getattr(game_state, 'turn', '?')}] STATION ALERT triggered by {self._triggering_observer}"
            )

    def on_turn_advance(self, event: GameEvent):
        """Decay alert status each turn."""
        if not self._alert_active:
            return

        self._alert_turns_remaining -= 1

        game_state = event.payload.get("game_state")

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
        self._alert_active = False
        self._alert_turns_remaining = 0

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
        """
        if self.is_active:
            return self.OBSERVATION_BONUS
        return 0

    def force_trigger(self, duration: int = None):
        """Manually trigger an alert (for testing or special events)."""
        self._alert_active = True
        self._alert_turns_remaining = duration or self.DEFAULT_ALERT_DURATION
        self._triggering_observer = "Emergency"

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
        return system
