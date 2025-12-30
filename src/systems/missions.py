"""Mission and Objective System for The Thing game.

Provides clear goals and objectives for the player, tracking progress
through event subscriptions and providing feedback on mission status.
"""

from typing import Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum, auto
from core.event_system import event_bus, EventType, GameEvent

if TYPE_CHECKING:
    from engine import GameState


class MissionStatus(Enum):
    """Status of a mission objective."""
    LOCKED = auto()      # Not yet available
    AVAILABLE = auto()   # Can be started
    IN_PROGRESS = auto() # Currently active
    COMPLETED = auto()   # Successfully finished
    FAILED = auto()      # Cannot be completed


class MissionType(Enum):
    """Categories of missions."""
    PRIMARY = auto()    # Main story objectives
    SECONDARY = auto()  # Optional objectives
    SURVIVAL = auto()   # Stay alive goals


@dataclass
class Objective:
    """A single objective within a mission."""
    id: str
    description: str
    target_count: int = 1
    current_count: int = 0
    completed: bool = False

    @property
    def progress(self) -> float:
        """Get objective completion percentage."""
        if self.target_count <= 0:
            return 100.0 if self.completed else 0.0
        return min(100.0, (self.current_count / self.target_count) * 100)

    def increment(self, amount: int = 1) -> bool:
        """Increment progress. Returns True if just completed."""
        if self.completed:
            return False
        self.current_count = min(self.target_count, self.current_count + amount)
        if self.current_count >= self.target_count:
            self.completed = True
            return True
        return False


@dataclass
class Mission:
    """A mission containing one or more objectives."""
    id: str
    name: str
    description: str
    mission_type: MissionType
    objectives: List[Objective] = field(default_factory=list)
    status: MissionStatus = MissionStatus.AVAILABLE
    reward_description: str = ""

    @property
    def is_complete(self) -> bool:
        """Check if all objectives are completed."""
        return all(obj.completed for obj in self.objectives)

    @property
    def progress(self) -> float:
        """Get overall mission completion percentage."""
        if not self.objectives:
            return 0.0
        return sum(obj.progress for obj in self.objectives) / len(self.objectives)


class MissionSystem:
    """Manages player missions and objectives.

    Tracks progress through event subscriptions and provides
    feedback on mission status.
    """

    def __init__(self, game_state: Optional['GameState'] = None):
        self.game_state = game_state
        self.missions: Dict[str, Mission] = {}
        self.active_mission_id: Optional[str] = None

        # Initialize default missions
        self._create_default_missions()

        # Subscribe to relevant events
        event_bus.subscribe(EventType.CREW_DEATH, self.on_crew_death)
        event_bus.subscribe(EventType.TEST_RESULT, self.on_test_result)
        event_bus.subscribe(EventType.HELICOPTER_REPAIRED, self.on_helicopter_repaired)
        event_bus.subscribe(EventType.SOS_EMITTED, self.on_sos_emitted)
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        """Unsubscribe from events."""
        event_bus.unsubscribe(EventType.CREW_DEATH, self.on_crew_death)
        event_bus.unsubscribe(EventType.TEST_RESULT, self.on_test_result)
        event_bus.unsubscribe(EventType.HELICOPTER_REPAIRED, self.on_helicopter_repaired)
        event_bus.unsubscribe(EventType.SOS_EMITTED, self.on_sos_emitted)
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def _create_default_missions(self):
        """Create the default set of missions."""
        # Primary Mission: Identify the Thing
        self.add_mission(Mission(
            id="identify_thing",
            name="Identify the Threat",
            description="Use blood tests to identify infected crew members.",
            mission_type=MissionType.PRIMARY,
            objectives=[
                Objective("test_crew", "Perform blood tests on crew members", target_count=3),
                Objective("identify_infected", "Identify an infected crew member", target_count=1),
            ],
            reward_description="Gain insight into who can be trusted."
        ))

        # Primary Mission: Eliminate Infected
        self.add_mission(Mission(
            id="eliminate_threat",
            name="Eliminate the Threat",
            description="Remove all infected crew members from the station.",
            mission_type=MissionType.PRIMARY,
            objectives=[
                Objective("kill_infected", "Eliminate infected crew members", target_count=2),
            ],
            status=MissionStatus.LOCKED,
            reward_description="Secure the station for survivors."
        ))

        # Secondary Mission: Repair Systems
        self.add_mission(Mission(
            id="repair_systems",
            name="Restore Station Systems",
            description="Repair critical station equipment for escape options.",
            mission_type=MissionType.SECONDARY,
            objectives=[
                Objective("repair_radio", "Repair the radio for SOS", target_count=1),
                Objective("repair_helicopter", "Repair the helicopter", target_count=1),
            ],
            reward_description="Enable escape routes."
        ))

        # Secondary Mission: Gather Evidence
        self.add_mission(Mission(
            id="gather_evidence",
            name="Gather Evidence",
            description="Collect evidence about crew members' activities.",
            mission_type=MissionType.SECONDARY,
            objectives=[
                Objective("tag_evidence", "Tag suspicious items or locations", target_count=3),
                Objective("interrogate", "Interrogate crew members", target_count=2),
            ],
            reward_description="Build a case against suspects."
        ))

        # Survival Mission
        self.add_mission(Mission(
            id="survive",
            name="Survive the Night",
            description="Stay alive and maintain sanity until rescue arrives.",
            mission_type=MissionType.SURVIVAL,
            objectives=[
                Objective("survive_turns", "Survive turns", target_count=20),
                Objective("maintain_trust", "Keep crew trust above critical", target_count=1),
            ],
            reward_description="Live to see another day."
        ))

        # Set initial active mission
        self.active_mission_id = "identify_thing"

    def add_mission(self, mission: Mission):
        """Add a mission to the system."""
        self.missions[mission.id] = mission

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        """Get a mission by ID."""
        return self.missions.get(mission_id)

    def get_active_mission(self) -> Optional[Mission]:
        """Get the currently active mission."""
        if self.active_mission_id:
            return self.missions.get(self.active_mission_id)
        return None

    def set_active_mission(self, mission_id: str) -> bool:
        """Set the active mission."""
        if mission_id in self.missions:
            mission = self.missions[mission_id]
            if mission.status not in (MissionStatus.LOCKED, MissionStatus.FAILED):
                self.active_mission_id = mission_id
                mission.status = MissionStatus.IN_PROGRESS
                return True
        return False

    def update_objective(self, mission_id: str, objective_id: str, increment: int = 1) -> bool:
        """Update an objective's progress."""
        mission = self.missions.get(mission_id)
        if not mission:
            return False

        for obj in mission.objectives:
            if obj.id == objective_id:
                just_completed = obj.increment(increment)
                if just_completed:
                    event_bus.emit(GameEvent(EventType.MESSAGE, {
                        "text": f"[OBJECTIVE] Completed: {obj.description}"
                    }))

                # Check if mission is now complete
                if mission.is_complete:
                    mission.status = MissionStatus.COMPLETED
                    event_bus.emit(GameEvent(EventType.WARNING, {
                        "text": f"[MISSION COMPLETE] {mission.name}!"
                    }))
                    self._unlock_next_missions(mission_id)

                return True
        return False

    def _unlock_next_missions(self, completed_mission_id: str):
        """Unlock missions that depend on the completed mission."""
        if completed_mission_id == "identify_thing":
            if "eliminate_threat" in self.missions:
                self.missions["eliminate_threat"].status = MissionStatus.AVAILABLE
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": "[NEW MISSION] Eliminate the Threat is now available."
                }))

    # Event Handlers
    def on_crew_death(self, event: GameEvent):
        """Handle crew death - update elimination objectives."""
        payload = event.payload or {}
        victim_name = payload.get("name")
        was_infected = payload.get("was_infected", False)

        if was_infected:
            self.update_objective("eliminate_threat", "kill_infected")

    def on_test_result(self, event: GameEvent):
        """Handle blood test results."""
        payload = event.payload or {}

        # Increment test count
        self.update_objective("identify_thing", "test_crew")

        # Check if infected was identified
        if payload.get("result") == "infected" or payload.get("is_infected"):
            self.update_objective("identify_thing", "identify_infected")

    def on_helicopter_repaired(self, event: GameEvent):
        """Handle helicopter repair."""
        self.update_objective("repair_systems", "repair_helicopter")

    def on_sos_emitted(self, event: GameEvent):
        """Handle SOS signal sent."""
        self.update_objective("repair_systems", "repair_radio")

    def on_turn_advance(self, event: GameEvent):
        """Handle turn advance - update survival objectives."""
        game_state = event.payload.get("game_state")
        if game_state:
            self.update_objective("survive", "survive_turns")

            # Check trust levels
            if hasattr(game_state, 'trust_matrix'):
                # Maintain trust objective is "complete" while trust is OK
                player_trust = game_state.trust_matrix.get_average_trust_for("MacReady")
                if player_trust > 20:  # Above critical threshold
                    survive_mission = self.missions.get("survive")
                    if survive_mission:
                        for obj in survive_mission.objectives:
                            if obj.id == "maintain_trust" and not obj.completed:
                                obj.current_count = 1

    def get_mission_summary(self) -> str:
        """Get a summary of all missions for display."""
        lines = ["--- MISSION LOG ---"]

        for mission in self.missions.values():
            status_icon = {
                MissionStatus.LOCKED: "🔒",
                MissionStatus.AVAILABLE: "○",
                MissionStatus.IN_PROGRESS: "◐",
                MissionStatus.COMPLETED: "✓",
                MissionStatus.FAILED: "✗"
            }.get(mission.status, "?")

            active_marker = ">> " if mission.id == self.active_mission_id else "   "
            lines.append(f"{active_marker}{status_icon} {mission.name} ({int(mission.progress)}%)")

            # Show objectives for non-locked missions
            if mission.status != MissionStatus.LOCKED:
                for obj in mission.objectives:
                    obj_icon = "✓" if obj.completed else "○"
                    lines.append(f"       {obj_icon} {obj.description} ({obj.current_count}/{obj.target_count})")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize mission state for saving."""
        return {
            "active_mission_id": self.active_mission_id,
            "missions": {
                mid: {
                    "status": m.status.name,
                    "objectives": [
                        {"id": o.id, "current_count": o.current_count, "completed": o.completed}
                        for o in m.objectives
                    ]
                }
                for mid, m in self.missions.items()
            }
        }

    def from_dict(self, data: dict):
        """Restore mission state from saved data."""
        self.active_mission_id = data.get("active_mission_id")

        missions_data = data.get("missions", {})
        for mid, mdata in missions_data.items():
            if mid in self.missions:
                mission = self.missions[mid]
                mission.status = MissionStatus[mdata.get("status", "AVAILABLE")]

                obj_data = {o["id"]: o for o in mdata.get("objectives", [])}
                for obj in mission.objectives:
                    if obj.id in obj_data:
                        obj.current_count = obj_data[obj.id].get("current_count", 0)
                        obj.completed = obj_data[obj.id].get("completed", False)
