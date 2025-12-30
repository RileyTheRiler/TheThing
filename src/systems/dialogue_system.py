from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING
import random

from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, Skill, ResolutionSystem

if TYPE_CHECKING:
    from engine import GameState, CrewMember


@dataclass
class ExplainResult:
    """Outcome data for an explain-away attempt."""

    success: bool
    critical: bool
    player_successes: int
    observer_successes: int
    suspicion_change: int
    trust_change: int
    dialogue: str


class DialogueBranchingSystem:
    """Handles dialogue branches that rely on contested social rolls."""

    PLAYER_EXPLANATIONS = [
        "I thought I heard something suspicious over there.",
        "Just checking if this area is secure.",
        "I was looking for supplies, didn't want to wake anyone.",
        "Sorry, I was trying to be quiet - didn't mean to startle you.",
        "I was investigating a noise. False alarm, I think."
    ]

    OBSERVER_ACCEPTS = [
        "{observer} nods slowly. \"Alright, but be more careful.\"",
        "{observer} relaxes slightly. \"Fair enough. Stay safe.\"",
        "{observer} considers this. \"I suppose that makes sense.\"",
        "{observer} shrugs. \"Just announce yourself next time.\"",
        "{observer} seems satisfied. \"Okay, I believe you.\""
    ]

    OBSERVER_SKEPTICAL = [
        "{observer} narrows their eyes. \"That's what someone would say...\"",
        "{observer} doesn't look convinced. \"I'm watching you.\"",
        "{observer} frowns. \"That story doesn't add up.\"",
        "{observer} steps back warily. \"If you say so...\"",
        "{observer} seems doubtful. \"Just... keep your distance.\""
    ]

    OBSERVER_ACCUSES = [
        "{observer} points at you. \"THAT'S EXACTLY WHAT A THING WOULD SAY!\"",
        "{observer} backs away in horror. \"You can't fool me! Everyone, get over here!\"",
        "{observer} shouts. \"I KNEW IT! You're one of THEM!\"",
        "{observer}'s face twists with fear. \"Don't come any closer! HELP!\""
    ]

    def __init__(self, rng=None):
        self.rng = rng
        self._pending_explanations: Dict[str, 'CrewMember'] = {}
        event_bus.subscribe(EventType.PERCEPTION_EVENT, self.on_perception_event)

    def cleanup(self):
        event_bus.unsubscribe(EventType.PERCEPTION_EVENT, self.on_perception_event)

    def _choose(self, options: List[str], rng):
        if rng and hasattr(rng, "choose"):
            return rng.choose(options)
        return random.choice(options)

    def on_perception_event(self, event: GameEvent):
        """Track detections that unlock explain-away opportunities."""
        payload = event.payload or {}
        outcome = payload.get("outcome")
        observer = payload.get("opponent_ref")
        player = payload.get("player_ref")

        if outcome != "detected" or not observer or not player:
            return

        from entities.crew_member import StealthPosture

        is_sneaking = getattr(player, "stealth_posture", StealthPosture.STANDING) != StealthPosture.STANDING
        if not is_sneaking or getattr(observer, "is_revealed", False) or not getattr(observer, "is_alive", True):
            return

        self._pending_explanations[observer.name] = observer

        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"[!] {observer.name} caught you sneaking! Type EXPLAIN_AWAY to talk your way out."
        }))

    def can_explain_to(self, observer_name: str) -> bool:
        return observer_name in self._pending_explanations

    def get_pending_observers(self) -> List[str]:
        return list(self._pending_explanations.keys())

    def clear_pending(self, observer_name: Optional[str] = None):
        if observer_name:
            self._pending_explanations.pop(observer_name, None)
        else:
            self._pending_explanations.clear()

    def _pool(self, actor: 'CrewMember', attribute: Attribute, skill: Skill, default_attr: int = 1,
              default_skill: int = 0) -> int:
        attr_val = 0
        skill_val = 0
        if hasattr(actor, "attributes"):
            attr_val = actor.attributes.get(attribute, default_attr)
        if hasattr(actor, "skills"):
            skill_val = actor.skills.get(skill, default_skill)
        return max(1, attr_val + skill_val)

    def explain_away(self, player: 'CrewMember', observer: 'CrewMember', game_state: 'GameState') -> ExplainResult:
        rng = getattr(game_state, "rng", None) or self.rng
        resolver = ResolutionSystem()

        player_pool = self._pool(player, Attribute.INFLUENCE, Skill.DECEPTION)
        observer_pool = self._pool(observer, Attribute.LOGIC, Skill.EMPATHY, default_attr=2)

        player_roll = resolver.roll_check(player_pool, rng)
        observer_roll = resolver.roll_check(observer_pool, rng)

        player_successes = player_roll.get("success_count", 0)
        observer_successes = observer_roll.get("success_count", 0)

        self.clear_pending(observer.name)

        if player_successes == 0 and observer_successes > 0:
            return self._critical_failure(player, observer, player_successes, observer_successes, game_state)
        if player_successes > observer_successes:
            margin = player_successes - observer_successes
            return self._success(player, observer, player_successes, observer_successes, margin, game_state)
        return self._failure(player, observer, player_successes, observer_successes, game_state)

    def attempt_explain(self, player: 'CrewMember', observer: 'CrewMember', game_state: 'GameState') -> ExplainResult:
        """Backward compatible alias for explain_away."""
        return self.explain_away(player, observer, game_state)

    def _success(self, player: 'CrewMember', observer: 'CrewMember', player_successes: int,
                 observer_successes: int, margin: int, game_state: 'GameState') -> ExplainResult:
        rng = getattr(game_state, "rng", None) or self.rng
        suspicion_reduction = min(5, 3 + margin)

        if hasattr(observer, "suspicion_level"):
            observer.suspicion_level = max(0, observer.suspicion_level - suspicion_reduction)
            if observer.suspicion_level == 0:
                observer.suspicion_state = "idle"

        trust_change = 2
        if hasattr(game_state, "trust_system"):
            game_state.trust_system.modify_trust(observer.name, player.name, trust_change)

        explanation = self._choose(self.PLAYER_EXPLANATIONS, rng)
        response = self._choose(self.OBSERVER_ACCEPTS, rng).format(observer=observer.name)
        dialogue = f'You say: "{explanation}"\n{response}'

        return ExplainResult(
            success=True,
            critical=False,
            player_successes=player_successes,
            observer_successes=observer_successes,
            suspicion_change=-suspicion_reduction,
            trust_change=trust_change,
            dialogue=dialogue
        )

    def _failure(self, player: 'CrewMember', observer: 'CrewMember', player_successes: int,
                 observer_successes: int, game_state: 'GameState') -> ExplainResult:
        rng = getattr(game_state, "rng", None) or self.rng
        suspicion_increase = 2

        if hasattr(observer, "increase_suspicion"):
            observer.increase_suspicion(suspicion_increase, turn=getattr(game_state, "turn", 0))

        trust_change = -5
        if hasattr(game_state, "trust_system"):
            game_state.trust_system.modify_trust(observer.name, player.name, trust_change)

        explanation = self._choose(self.PLAYER_EXPLANATIONS, rng)
        response = self._choose(self.OBSERVER_SKEPTICAL, rng).format(observer=observer.name)
        dialogue = f'You say: "{explanation}"\n{response}'

        return ExplainResult(
            success=False,
            critical=False,
            player_successes=player_successes,
            observer_successes=observer_successes,
            suspicion_change=suspicion_increase,
            trust_change=trust_change,
            dialogue=dialogue
        )

    def _critical_failure(self, player: 'CrewMember', observer: 'CrewMember', player_successes: int,
                          observer_successes: int, game_state: 'GameState') -> ExplainResult:
        rng = getattr(game_state, "rng", None) or self.rng
        suspicion_increase = 5

        if hasattr(observer, "increase_suspicion"):
            observer.increase_suspicion(suspicion_increase, turn=getattr(game_state, "turn", 0))
            observer.suspicion_state = "follow"

        trust_change = -15
        if hasattr(game_state, "trust_system"):
            game_state.trust_system.modify_trust(observer.name, player.name, trust_change)

        response = self._choose(self.OBSERVER_ACCUSES, rng).format(observer=observer.name)
        dialogue = f"Your words stumble and fail.\n{response}"

        event_bus.emit(GameEvent(EventType.WARNING, {
            "text": f"{observer.name} is now convinced you're infected!"
        }))

        event_bus.emit(GameEvent(EventType.ACCUSATION_RESULT, {
            "target": player.name,
            "outcome": f"{observer.name} loudly accuses you of being The Thing!",
            "accuser": observer.name,
            "supporters": [],
            "opposers": []
        }))

        return ExplainResult(
            success=False,
            critical=True,
            player_successes=player_successes,
            observer_successes=observer_successes,
            suspicion_change=suspicion_increase,
            trust_change=trust_change,
            dialogue=dialogue
        )
