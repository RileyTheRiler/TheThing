"""
RelationshipMatrix: Tracks pairwise NPC-to-NPC relationships for Tier 8 Paranoia.

Separate from TrustMatrix (0-100 trust score), this tracks friendship/rivalry
on a -10 to +10 scale based on shared experiences.

Thresholds:
  +5 or higher = Friends (cooperative behaviors)
  -5 or lower = Rivals (antagonistic behaviors)

Modifiers:
  - Shared attacks (surviving together): +2
  - Accusations (accuser vs accused): -3
  - Blood tests (both clean): +1
  - Proximity (same room 5+ turns): +1
"""

from typing import Dict, List, Optional, TYPE_CHECKING
from core.event_system import event_bus, EventType, GameEvent

if TYPE_CHECKING:
    from engine import GameState, CrewMember

__all__ = ['RelationshipMatrix', 'FRIENDSHIP_THRESHOLD', 'RIVALRY_THRESHOLD']

FRIENDSHIP_THRESHOLD = 5
RIVALRY_THRESHOLD = -5


class RelationshipMatrix:
    """
    Tracks pairwise relationships between all crew members.
    Scale: -10 (bitter rivals) to +10 (close friends)
    """

    def __init__(self, crew: List['CrewMember']):
        # Dictionary of dictionaries: self.matrix[member_a][member_b] = relationship_score
        # Start at 0 (neutral)
        self.matrix: Dict[str, Dict[str, int]] = {
            m.name: {other.name: 0 for other in crew if other.name != m.name}
            for m in crew
        }
        self.crew_ref = {m.name: m for m in crew}
        
        # Proximity tracking: how many consecutive turns two members shared a room
        self.proximity_turns: Dict[str, Dict[str, int]] = {
            m.name: {other.name: 0 for other in crew if other.name != m.name}
            for m in crew
        }
        
        # Track last known locations for proximity calculation
        self._last_locations: Dict[str, tuple] = {}
        
        # Subscribe to events
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.subscribe(EventType.ATTACK_RESULT, self.on_attack_result)
        event_bus.subscribe(EventType.ACCUSATION_RESULT, self.on_accusation)
        event_bus.subscribe(EventType.TEST_RESULT, self.on_blood_test)

    def cleanup(self):
        """Unsubscribe from events."""
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        event_bus.unsubscribe(EventType.ATTACK_RESULT, self.on_attack_result)
        event_bus.unsubscribe(EventType.ACCUSATION_RESULT, self.on_accusation)
        event_bus.unsubscribe(EventType.TEST_RESULT, self.on_blood_test)

    def get_relationship(self, member_a: str, member_b: str) -> int:
        """Get the relationship score between two members."""
        if member_a in self.matrix and member_b in self.matrix[member_a]:
            return self.matrix[member_a][member_b]
        return 0  # Default neutral

    def modify_relationship(self, member_a: str, member_b: str, amount: int, reason: str = ""):
        """
        Modify relationship between two members symmetrically.
        Clamps to -10 to +10 range.
        """
        if member_a not in self.matrix or member_b not in self.matrix:
            return
        if member_a == member_b:
            return

        # Get current values
        old_a_to_b = self.matrix[member_a].get(member_b, 0)
        old_b_to_a = self.matrix[member_b].get(member_a, 0)

        # Apply change symmetrically
        new_a_to_b = max(-10, min(10, old_a_to_b + amount))
        new_b_to_a = max(-10, min(10, old_b_to_a + amount))

        self.matrix[member_a][member_b] = new_a_to_b
        self.matrix[member_b][member_a] = new_b_to_a

        # Check for threshold crossings
        self._check_threshold_crossing(member_a, member_b, old_a_to_b, new_a_to_b, reason)
        self._check_threshold_crossing(member_b, member_a, old_b_to_a, new_b_to_a, reason)

    def _check_threshold_crossing(self, observer: str, subject: str,
                                   old_value: int, new_value: int, reason: str):
        """Emit event if relationship crosses friendship or rivalry threshold."""
        crossed_friendship = old_value < FRIENDSHIP_THRESHOLD <= new_value
        left_friendship = old_value >= FRIENDSHIP_THRESHOLD > new_value
        crossed_rivalry = old_value > RIVALRY_THRESHOLD >= new_value
        left_rivalry = old_value <= RIVALRY_THRESHOLD < new_value

        if crossed_friendship or left_friendship or crossed_rivalry or left_rivalry:
            status = "neutral"
            if new_value >= FRIENDSHIP_THRESHOLD:
                status = "friends"
            elif new_value <= RIVALRY_THRESHOLD:
                status = "rivals"

            event_bus.emit(GameEvent(EventType.RELATIONSHIP_CHANGE, {
                "observer": observer,
                "subject": subject,
                "old_value": old_value,
                "new_value": new_value,
                "status": status,
                "reason": reason
            }))

            # Update crew member tags for AI behavior
            crew_member = self.crew_ref.get(observer)
            if crew_member:
                # Remove old relationship tags for this subject
                crew_member.relationship_tags = [
                    t for t in crew_member.relationship_tags
                    if not (t.startswith("Friend:") and t.endswith(subject)) and
                       not (t.startswith("Rival:") and t.endswith(subject))
                ]
                # Add new tag
                if status == "friends":
                    crew_member.relationship_tags.append(f"Friend:{subject}")
                elif status == "rivals":
                    crew_member.relationship_tags.append(f"Rival:{subject}")

    def are_friends(self, member_a: str, member_b: str) -> bool:
        """Check if two members are friends (relationship >= +5)."""
        return self.get_relationship(member_a, member_b) >= FRIENDSHIP_THRESHOLD

    def are_rivals(self, member_a: str, member_b: str) -> bool:
        """Check if two members are rivals (relationship <= -5)."""
        return self.get_relationship(member_a, member_b) <= RIVALRY_THRESHOLD

    def get_friends(self, member_name: str) -> List[str]:
        """Get list of all friends for a member."""
        if member_name not in self.matrix:
            return []
        return [
            other for other, score in self.matrix[member_name].items()
            if score >= FRIENDSHIP_THRESHOLD
        ]

    def get_rivals(self, member_name: str) -> List[str]:
        """Get list of all rivals for a member."""
        if member_name not in self.matrix:
            return []
        return [
            other for other, score in self.matrix[member_name].items()
            if score <= RIVALRY_THRESHOLD
        ]

    # === Event Handlers ===

    def on_turn_advance(self, event: GameEvent):
        """Track proximity and apply +1 bonus for 5+ turns in same room."""
        game_state = event.payload.get("game_state")
        if not game_state:
            return

        # Group living crew by room
        room_groups: Dict[str, List[str]] = {}
        for member in game_state.crew:
            if not member.is_alive:
                continue
            room = game_state.station_map.get_room_name(*member.location)
            if room not in room_groups:
                room_groups[room] = []
            room_groups[room].append(member.name)

        # Update proximity counters
        for room, members in room_groups.items():
            for i, member_a in enumerate(members):
                for member_b in members[i + 1:]:
                    # Increment proximity
                    if member_a in self.proximity_turns and member_b in self.proximity_turns[member_a]:
                        self.proximity_turns[member_a][member_b] += 1
                        self.proximity_turns[member_b][member_a] += 1

                        # Apply bonus at exactly 5 turns together
                        if self.proximity_turns[member_a][member_b] == 5:
                            self.modify_relationship(member_a, member_b, 1, "proximity")
                            from ui.message_reporter import emit_message
                            emit_message(f"[SOCIAL] {member_a} and {member_b} have been spending time together.")

        # Reset proximity for members in different rooms
        for member_a in self.proximity_turns:
            for member_b in self.proximity_turns[member_a]:
                # Find rooms for each
                room_a = None
                room_b = None
                for room, members in room_groups.items():
                    if member_a in members:
                        room_a = room
                    if member_b in members:
                        room_b = room
                if room_a != room_b:
                    self.proximity_turns[member_a][member_b] = 0

    def on_attack_result(self, event: GameEvent):
        """
        When crew members survive an attack together, boost their relationship.
        +2 for surviving the same combat encounter.
        """
        payload = event.payload
        attacker = payload.get("attacker", "")
        target = payload.get("target", "")
        result = payload.get("result", "")

        # If this was a Thing attack and both survived
        if "Thing" in attacker and result not in ("KILLED", "DEAD"):
            # Find all crew in the same room as target who witnessed this
            game_state = payload.get("game_state")
            if game_state:
                target_member = next((m for m in game_state.crew if m.name == target), None)
                if target_member:
                    room = game_state.station_map.get_room_name(*target_member.location)
                    witnesses = [
                        m.name for m in game_state.crew
                        if m.is_alive and m.name != target and
                        game_state.station_map.get_room_name(*m.location) == room
                    ]
                    for witness in witnesses:
                        self.modify_relationship(target, witness, 2, "shared_attack")

    def on_accusation(self, event: GameEvent):
        """
        When an accusation is made, decrease relationship between accuser and accused.
        -3 relationship penalty.
        """
        payload = event.payload
        accuser = payload.get("accuser", "")
        accused = payload.get("accused", payload.get("target", ""))

        if accuser and accused and accuser != accused:
            self.modify_relationship(accuser, accused, -3, "accusation")
            from ui.message_reporter import emit_message
            emit_message(f"[SOCIAL] The accusation has damaged the relationship between {accuser} and {accused}.")

    def on_blood_test(self, event: GameEvent):
        """
        When two crew members pass a blood test together (both clean), +1 relationship.
        """
        payload = event.payload
        tested = payload.get("tested", "")
        result = payload.get("result", "")
        witnesses = payload.get("witnesses", [])

        if result == "clean" and tested and witnesses:
            for witness in witnesses:
                # Both must be clean for the bonus
                witness_member = self.crew_ref.get(witness)
                if witness_member and not getattr(witness_member, 'is_infected', False):
                    self.modify_relationship(tested, witness, 1, "blood_test_clean")

    # === Serialization ===

    def to_dict(self) -> dict:
        """Serialize for save/load."""
        return {
            "matrix": self.matrix,
            "proximity_turns": self.proximity_turns
        }

    @classmethod
    def from_dict(cls, data: dict, crew: List['CrewMember']) -> 'RelationshipMatrix':
        """Deserialize from saved data."""
        instance = cls(crew)
        if "matrix" in data:
            instance.matrix = data["matrix"]
        if "proximity_turns" in data:
            instance.proximity_turns = data["proximity_turns"]
        return instance
