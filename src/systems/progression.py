"""Progression system for skill advancement in The Thing game.

Handles XP awards and level-up mechanics for stealth and other skills.
Successful evasions grant Stealth XP, eventually providing noise reduction
and stealth pool bonuses.
"""

from typing import Dict, List, Optional, TYPE_CHECKING
from core.event_system import event_bus, EventType, GameEvent

if TYPE_CHECKING:
    from engine import GameState


class ProgressionSystem:
    """Manages skill progression through XP gain and level advancement.

    Stealth XP is awarded when successfully evading detection.
    Higher difficulty evasions (larger observer pool) grant more XP.
    """

    # XP thresholds for each stealth level (cumulative)
    STEALTH_LEVEL_THRESHOLDS = [100, 300, 600, 1000]

    # Level benefit descriptions for feedback
    LEVEL_BENEFITS = {
        1: "Base noise reduced by 1",
        2: "Stealth pool increased by 1",
        3: "Base noise reduced by 1 (cumulative)",
        4: "Stealth pool increased by 1, Silent Takedown unlocked"
    }

    def __init__(self, game_state: Optional['GameState'] = None):
        self.game_state = game_state

        # Subscribe to stealth events
        event_bus.subscribe(EventType.STEALTH_REPORT, self.on_stealth_report)

    def cleanup(self):
        """Unsubscribe from events."""
        event_bus.unsubscribe(EventType.STEALTH_REPORT, self.on_stealth_report)

    def on_stealth_report(self, event: GameEvent):
        """Handle stealth report events and award XP for successful evasions."""
        payload = event.payload
        if not payload:
            return

        outcome = payload.get("outcome")
        if outcome != "evaded":
            return  # Only award XP for successful evasions

        player_ref = payload.get("player_ref")
        if not player_ref:
            return

        # Calculate XP based on difficulty
        observer_pool = payload.get("observer_pool", 0)
        player_successes = payload.get("player_successes", 0)

        # XP formula: (observer_pool - player_successes) * 10, minimum 10 XP
        xp_gained = max(10, (observer_pool - player_successes) * 10)

        # Award XP and check for level up
        self.award_stealth_xp(player_ref, xp_gained)

    def award_stealth_xp(self, character, xp_amount: int):
        """Award stealth XP to a character and check for level advancement.

        Args:
            character: The character to award XP to
            xp_amount: Amount of XP to award
        """
        if not hasattr(character, 'stealth_xp'):
            character.stealth_xp = 0
        if not hasattr(character, 'stealth_level'):
            character.stealth_level = 0

        old_level = character.stealth_level
        character.stealth_xp += xp_amount

        # Check for level up
        new_level = self.calculate_stealth_level(character.stealth_xp)

        if new_level > old_level:
            character.stealth_level = new_level
            self._handle_level_up(character, old_level, new_level)

        # Emit XP gain message
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"[Stealth +{xp_amount} XP] ({character.stealth_xp}/{self._get_next_threshold(new_level)})"
        }))

    def calculate_stealth_level(self, xp: int) -> int:
        """Calculate stealth level based on total XP."""
        level = 0
        for threshold in self.STEALTH_LEVEL_THRESHOLDS:
            if xp >= threshold:
                level += 1
            else:
                break
        return level

    def _get_next_threshold(self, current_level: int) -> int:
        """Get XP threshold for next level."""
        if current_level >= len(self.STEALTH_LEVEL_THRESHOLDS):
            return self.STEALTH_LEVEL_THRESHOLDS[-1]  # Max level
        return self.STEALTH_LEVEL_THRESHOLDS[current_level]

    def _handle_level_up(self, character, old_level: int, new_level: int):
        """Handle level up events and apply benefits."""
        for level in range(old_level + 1, new_level + 1):
            benefit = self.LEVEL_BENEFITS.get(level, "Unknown benefit")

            # Apply special unlocks
            if level == 4:
                character.silent_takedown_unlocked = True

            # Emit level up event
            event_bus.emit(GameEvent(EventType.SKILL_LEVEL_UP, {
                "character": character.name,
                "skill": "Stealth",
                "new_level": level,
                "benefit": benefit
            }))

            # Also emit a prominent message
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"*** STEALTH LEVEL {level}! *** {benefit}"
            }))

    def get_stealth_progress(self, character) -> Dict:
        """Get stealth progression status for a character.

        Returns:
            Dict with xp, level, next_threshold, and progress percentage
        """
        xp = getattr(character, 'stealth_xp', 0)
        level = getattr(character, 'stealth_level', 0)

        if level >= len(self.STEALTH_LEVEL_THRESHOLDS):
            # Max level
            return {
                "xp": xp,
                "level": level,
                "next_threshold": None,
                "progress": 100.0,
                "max_level": True
            }

        next_threshold = self.STEALTH_LEVEL_THRESHOLDS[level]
        prev_threshold = self.STEALTH_LEVEL_THRESHOLDS[level - 1] if level > 0 else 0

        xp_in_level = xp - prev_threshold
        xp_needed = next_threshold - prev_threshold
        progress = (xp_in_level / xp_needed) * 100 if xp_needed > 0 else 0

        return {
            "xp": xp,
            "level": level,
            "next_threshold": next_threshold,
            "progress": progress,
            "max_level": False,
            "xp_to_next": next_threshold - xp
        }

    def get_level_benefits_summary(self, level: int) -> List[str]:
        """Get a list of all benefits at or below the given level."""
        benefits = []
        for lvl in range(1, level + 1):
            if lvl in self.LEVEL_BENEFITS:
                benefits.append(f"Level {lvl}: {self.LEVEL_BENEFITS[lvl]}")
        return benefits

    def to_dict(self) -> Dict:
        """Serialize progression system state for saving."""
        # Progression data is stored on characters, not here
        return {}

    @classmethod
    def from_dict(cls, data: Dict, game_state: Optional['GameState'] = None) -> 'ProgressionSystem':
        """Deserialize progression system from save data."""
        return cls(game_state)
