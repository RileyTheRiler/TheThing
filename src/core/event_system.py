from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any
import time

class EventType(Enum):
    # Core Game Events
    TURN_ADVANCE = auto()
    CREW_DEATH = auto()
    HELICOPTER_REPAIRED = auto()
    SOS_EMITTED = auto()
    ESCAPE_SUCCESS = auto()
    POPULATION_STATUS = auto()

    # "Biological Slip" Hook (Missionary -> Terminal)
    BIOLOGICAL_SLIP = auto()

    # "Lynch Mob" Hook (Psychologist -> Architect)
    LYNCH_MOB_TRIGGER = auto()
    LYNCH_MOB_UPDATE = auto()
    LYNCH_MOB_VOTE = auto()
    TRUST_THRESHOLD_CROSSED = auto()
    PARANOIA_THRESHOLD_CROSSED = auto()

    # "Searchlight" Hook (Missionary -> Psychologist)
    SEARCHLIGHT_HARVEST = auto()
    COMMUNION_SUCCESS = auto()

    # Forensic / Terminal
    EVIDENCE_TAGGED = auto()

    # Sabotage
    POWER_FAILURE = auto()

    # Environmental (Weather/Temperature/Power interplay)
    TEMPERATURE_THRESHOLD_CROSSED = auto()
    ENVIRONMENTAL_STATE_CHANGE = auto()

    # Social thresholds
    # TRUST_THRESHOLD_CROSSED and PARANOIA_THRESHOLD_CROSSED defined above

    # === REPORTING PATTERN (Tier 2.6) ===
    # Systems emit these instead of returning strings

    # Message display events
    MESSAGE = auto()          # General message to display
    WARNING = auto()          # Warning message (high visibility)
    ERROR = auto()            # Error message
    COMBAT_LOG = auto()       # Combat action results
    DIALOGUE = auto()         # NPC dialogue
    SYSTEM_LOG = auto()       # System/mechanical info

    # Action result events
    MOVEMENT = auto()         # Player/NPC movement
    ITEM_PICKUP = auto()      # Item picked up
    ITEM_DROP = auto()        # Item dropped
    ATTACK_RESULT = auto()    # Attack outcome
    TEST_RESULT = auto()      # Blood test result
    BARRICADE_ACTION = auto() # Barricade built/broken
    STEALTH_REPORT = auto()   # Stealth encounter updates
    CRAFTING_REPORT = auto()  # Crafting queue/status updates
    REPAIR_COMPLETE = auto()  # Helicopter repair/escape status updates
    SOS_SENT = auto()         # Radio rescue signal/arrival
    ENDING_REPORT = auto()    # Ending triggers/results
    INTERROGATION_RESULT = auto() # Questioning results
    ACCUSATION_RESULT = auto()    # Formal accusation results
    PERCEPTION_EVENT = auto()     # AI perception results (stealth)
    DIAGNOSTIC = auto()           # System diagnostics (performance, budget)

@dataclass
class GameEvent:
    type: EventType
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

class EventBus:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._subscribers = {}
        return cls._instance

    def __init__(self):
        # Initialized in __new__ to ensure singleton safety if re-instantiated, 
        # but standard singleton pattern usually relies on module imports. 
        # We will keep it simple.
        if not hasattr(self, '_subscribers'):
            self._subscribers: Dict[EventType, List[Callable[[GameEvent], None]]] = {}

    def subscribe(self, event_type: EventType, callback: Callable[[GameEvent], None]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[GameEvent], None]):
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    def emit(self, event: GameEvent):
        """
        Pushes an event to all subscribers.
        """
        if event.type in self._subscribers:
            for callback in self._subscribers[event.type]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"ERROR processing event {event.type}: {e}")

    def clear(self):
        self._subscribers = {}

# Global global accessor
event_bus = EventBus()
