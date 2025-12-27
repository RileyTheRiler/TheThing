import random
import time
from core.event_system import event_bus, EventType, GameEvent

class BiologicalSlipGenerator:
    """
    Generates subtle "tells" and anomalies for infected characters.
    """
    
    VISUAL_TELLS = [
        "sweating profusely despite the cold",
        "staring unblinkingly for too long",
        "a slight, unnatural tic in the left eye",
        "fingers twitching rhythmically",
        "skin looking waxy and artificial"
    ]
    
    AUDIO_TELLS = [
        "voice slightly distorted, like a bad radio",
        "pausing too long before answering",
        "a strange, clicking sound in the throat",
        "repeating the last word of a sentence",
        "having zero emotional inflection"
    ]
    
    @staticmethod
    def get_visual_slip(random_engine=None):
        if random_engine:
            return random_engine.choose(BiologicalSlipGenerator.VISUAL_TELLS)
        return random.choice(BiologicalSlipGenerator.VISUAL_TELLS)
        
    @staticmethod
    def get_audio_slip(random_engine=None):
        if random_engine:
            return random_engine.choose(BiologicalSlipGenerator.AUDIO_TELLS)
        return random.choice(BiologicalSlipGenerator.AUDIO_TELLS)


class ForensicDatabase:
    """
    Structured storage for player-defined tags and sightings.
    """
    def __init__(self):
        self.tags = {} # character_name -> list of tags
        
    def add_tag(self, character_name, category, note, turn):
        if character_name not in self.tags:
            self.tags[character_name] = []
        
        entry = {
            "turn": turn,
            "category": category.upper(),
            "note": note,
            "timestamp": time.time()
        }
        self.tags[character_name].append(entry)
        return entry

    def get_report(self, character_name):
        if character_name not in self.tags:
            return f"No forensic data for {character_name}."
        
        report = [f"--- FORENSIC DOSSIER: {character_name.upper()} ---"]
        for tag in self.tags[character_name]:
            report.append(f"[TURN {tag['turn']}] {tag['category']}: {tag['note']}")
        return "\n".join(report)


class EvidenceLog:
    """
    Physical Persistence Log tracking "Chain of Custody" for key items.
    """
    def __init__(self):
        self.log = {} # item_name -> list of events

    def record_event(self, item_name, action, actor_name, location, turn):
        if item_name not in self.log:
            self.log[item_name] = []
            
        event = {
            "turn": turn,
            "action": action.upper(),
            "actor": actor_name,
            "location": location,
            "timestamp": time.time()
        }
        self.log[item_name].append(event)

    def get_history(self, item_name):
        if item_name not in self.log:
            return f"No history found for '{item_name}'."
        
        history = [f"--- CHAIN OF CUSTODY: {item_name.upper()} ---"]
        for event in self.log[item_name]:
            history.append(f"[TURN {event['turn']}] {event['action']} by {event['actor']} in {event['location']}")
        return "\n".join(history)



class BloodTestSim:
    """
    Manages the heated wire blood test state machine.
    """
    
    ROOM_TEMP = 20
    TARGET_TEMP = 100
    READY_THRESHOLD = 90
    COOLING_RATE = 10

    def __init__(self):
        self.active = False
        self.wire_temp = self.ROOM_TEMP
        self.target_temp = self.TARGET_TEMP # Hot enough to burn
        self.wire_temp = 20 # Room temp (approx)
        self.target_temp = 90 # Hot enough to burn (lowered for gameplay reliability)
        self.current_sample = None # Name of crew member
        self.state = "IDLE" # IDLE, HEATING, READY, REACTION
        
    def start_test(self, crew_name):
        self.active = True
        self.current_sample = crew_name
        self.wire_temp = self.ROOM_TEMP
        self.state = "HEATING"
        return f"Prepared blood sample from {crew_name}. Wire is cold ({self.wire_temp}C)."
        
    def heat_wire(self):
        if not self.active:
            return "No test in progress."
            
        increase = random.randint(20, 30)
        self.wire_temp += increase
        
        if self.wire_temp >= self.READY_THRESHOLD: # Lowered from 100 for gameplay reliability
            self.state = "READY"
            return f"Wire is GLOWING HOT ({self.wire_temp}C). Ready to apply."
        else:
            return f"Heating wire... ({self.wire_temp}C)"

    def cool_down(self):
        """
        Simulates the wire cooling down over time.
        """
        if not self.active:
            return

        if self.wire_temp > 20:
            # Cool down by 15 degrees, but don't go below 20
            cooling_amount = 15
            self.wire_temp = max(20, self.wire_temp - cooling_amount)

            # If it was READY but cooled down too much, revert state
            if self.state == "READY" and self.wire_temp < 90:
                self.state = "HEATING"
            
    def cool_down(self):
        """
        Simulate thermal decay of the wire over time.
        """
        if not self.active:
            return

        # Cooling rate (degrees per turn)
        cooling_rate = 15
        self.wire_temp = max(20, self.wire_temp - cooling_rate)

        # Check state regression if temp drops below threshold
        if self.state == "READY" and self.wire_temp < self.target_temp:
            self.state = "HEATING"

    def apply_wire(self, is_infected):
        if not self.active:
            return "No test in progress."
            
        # Fix logic: Use 90 as threshold since heat_wire considers 90 as READY
        threshold = 90 if hasattr(self, 'state') and self.state == "READY" else self.target_temp

        if self.wire_temp < threshold:
            return f"Wire not hot enough ({self.wire_temp}C). It just feels warm."
            
        self.active = False # End test after application
        
        if is_infected:
            return self._infected_reaction()
        else:
            return self._human_reaction()
            
    def _human_reaction(self):
        return "The blood HISSES and smokes. Just a normal burn reaction. HUMAN."
        
    def _infected_reaction(self):
        reactions = [
            "The blood SCREAMS and leaps away from the wire!",
            "The sample violently expands, trying to attack the wire!",
            "Eerie silence... then the petri dish shatters as the blood flees."
        ]
        return f"*** TEST RESULT: {random.choice(reactions)} ***"

    def cancel(self):
        self.active = False
        self.state = "IDLE"
        return "Test cancelled."

    def cool_down(self):
        """
        Simulate natural cooling of the wire over time.
        """
        if not self.active:
            return

        # Simple linear cooling
        if self.wire_temp > self.ROOM_TEMP:
            self.wire_temp = max(self.ROOM_TEMP, self.wire_temp - self.COOLING_RATE)

        # State transition: if we lose heat, we might no longer be READY
        if self.state == "READY" and self.wire_temp < self.READY_THRESHOLD:
            self.state = "HEATING"

class ForensicsSystem:
    """
    Agent 4: Forensics System.
    Manages blood tests and evidence tracking.
    """
    def __init__(self):
        self.blood_test = BloodTestSim()
        # Register for turn advance if we want things to happen over time
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def on_turn_advance(self, event: GameEvent):
        """
        Handle turn advancement.
        The wire cools down if left unattended.
        The wire cools down over time.
        """
        if self.blood_test.active:
            self.blood_test.cool_down()

    def get_status(self):
        if self.blood_test.active:
            return f"[TEST: {self.blood_test.state}] Wire: {self.blood_test.wire_temp}C"
        return None
