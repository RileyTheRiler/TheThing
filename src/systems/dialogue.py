from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from core.resolution import Attribute, ResolutionSystem, Skill


@dataclass
class DialogueNodeResult:
    """Structured result for dialogue nodes.

    lines: list of {"speaker": str, "text": str} dictionaries rendered by the UI.
    success: optional boolean to indicate resolution outcome (for branching effects).
    outcome: short tag describing the branch that fired.
    """

    lines: List[Dict[str, str]]
    success: Optional[bool] = None
    outcome: str = "neutral"


class DialogueSystem:
    """Simple dialogue graph executor.

    Each node is a callable that accepts (speaker, listener, game_state, context)
    and returns a DialogueNodeResult. Nodes are registered by name.
    """

    def __init__(self, rng=None):
        self.rng = rng
        self.nodes: Dict[str, Callable] = {
            "EXPLAIN_AWAY": self._handle_explain_away,
        }

    def run_node(self, node_name: str, speaker, listener, game_state, context: Optional[Dict] = None) -> Optional[DialogueNodeResult]:
        """Execute a named dialogue node."""

        handler = self.nodes.get(node_name.upper())
        if not handler:
            return None
        return handler(speaker, listener, game_state, context or {})

    def _behavioral_reaction(self, speaker, trigger_type: str) -> str:
        """Baseline line derived from the speaker's behavior type."""

        lines = ["Who's there?", "What was that?"]

        if trigger_type == "STEALTH_DETECTED":
            if speaker.behavior_type == "Aggressive":
                lines = ["Show yourself!", "I know you're there!", "Come out and fight!"]
            elif speaker.behavior_type == "Nervous":
                lines = ["Who's there?!", "Stay back!", "I... I hear you!"]
            elif speaker.behavior_type == "Analytical":
                lines = ["Identify yourself.", "Movement detected.", "Someone is lurking."]
            else:
                lines = ["Is someone there?", "Hello?", "Stop sneaking around."]

        idx = len(speaker.name) % len(lines)
        return lines[idx]

    def _handle_explain_away(self, observer, intruder, game_state, context: Dict) -> DialogueNodeResult:
        """Branch where the intruder tries to talk their way out of being spotted."""

        rng = getattr(game_state, "rng", None) or self.rng
        res = ResolutionSystem()

        charisma = intruder.attributes.get(Attribute.INFLUENCE, 1)
        deception = intruder.skills.get(Skill.DECEPTION, 0)
        actor_pool = max(1, charisma + deception)

        scrutiny = observer.attributes.get(Attribute.LOGIC, 1)
        observation = observer.skills.get(Skill.OBSERVATION, 0)
        opposed_pool = max(1, scrutiny + observation)

        actor_result = res.roll_check(actor_pool, rng)
        opposed_result = res.roll_check(opposed_pool, rng)
        success = actor_result["success_count"] >= opposed_result["success_count"]

        opener = self._behavioral_reaction(observer, context.get("trigger_type", "STEALTH_DETECTED"))
        lines = [{"speaker": observer.name, "text": opener}]

        if success:
            prior_suspicion = getattr(observer, "suspicion_level", 0)
            observer.suspicion_level = max(0, prior_suspicion - 4)
            observer.detected_player = False
            observer.investigating = False
            observer.last_known_player_location = None
            observer.alerted_to_player = False

            if hasattr(game_state, "trust_system"):
                game_state.trust_system.update_trust(observer.name, intruder.name, 3)

            lines.append({
                "speaker": intruder.name,
                "text": "Easy, I was checking the vents for a leak. Didn't mean to startle you.",
            })
            lines.append({
                "speaker": observer.name,
                "text": "Fine. Just call it out next time.",
            })

            outcome = "calmed"
        else:
            observer.suspicion_level = min(10, getattr(observer, "suspicion_level", 0) + 5)
            observer.detected_player = True
            observer.investigating = True
            observer.last_known_player_location = getattr(intruder, "location", None)
            observer.alerted_to_player = True

            if hasattr(game_state, "trust_system"):
                game_state.trust_system.update_trust(observer.name, intruder.name, -8)

            lines.append({
                "speaker": intruder.name,
                "text": "I was just passing through...",  # faltering attempt
            })
            lines.append({
                "speaker": observer.name,
                "text": "I don't buy it. You're up to something!",
            })

            outcome = "hostile"

        return DialogueNodeResult(lines=lines, success=success, outcome=outcome)
