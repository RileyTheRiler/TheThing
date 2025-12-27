from enum import Enum
import random
import pickle
import base64
from src.core.event_system import event_bus, EventType, GameEvent
from src.core.resolution import ResolutionSystem

class GameMode(Enum):
    INVESTIGATIVE = "Investigative"
    EMERGENCY = "Emergency"
    STANDOFF = "Standoff"
    CINEMATIC = "Cinematic"

class RandomnessEngine:
    def __init__(self, seed=None):
        self.seed = seed
        if self.seed:
            random.seed(self.seed)
    
    def roll_2d6(self):
        """Standard 2d6 roll."""
        return random.randint(1, 6) + random.randint(1, 6)
    
    def roll_d6(self):
        return random.randint(1, 6)
        
    def calculate_success(self, pool_size):
        """
        Executes a dice pool check.
        Success = 6s.
        """
        dice = [self.roll_d6() for _ in range(pool_size)]
        successes = dice.count(6)
        return {
            "success": successes > 0,
            "success_count": successes,
            "dice": dice
        }

    def choose(self, collection):
        if not collection:
            return None
        return random.choice(collection)
        
    def random_float(self):
        return random.random()

    def to_dict(self):
        # Pickle the state and encode as base64 string
        state = random.getstate()
        pickled = pickle.dumps(state)
        b64_state = base64.b64encode(pickled).decode('utf-8')
        
        return {
            "seed": self.seed,
            "state_b64": b64_state
        }

    def from_dict(self, data):
        self.seed = data.get("seed")
        b64_state = data.get("state_b64")
        if b64_state:
            pickled = base64.b64decode(b64_state)
            state = pickle.loads(pickled)
            random.setstate(state)

class TimeSystem:
    def __init__(self, start_temp=-40):
        self.temperature = start_temp
        self.points_per_turn = 1
        self.turn_count = 0

    @property
    def hour(self):
        # Assuming 1 turn = 1 hour or some conversion.
        # Base hour 8:00 AM?
        return (8 + self.turn_count) % 24
        
    def tick(self):
        """Advance time by one turn."""
        self.turn_count += 1
        
    def update_environment(self, power_on):
        """
        Updates environmental factors based on power state.
        Returns: Tuple (temperature_change, new_temperature)
        """
        temp_change = 0
        if not power_on:
            # Thermal Decay
            temp_change = -5
            self.temperature += temp_change
        else:
            # Heating recovery (slow)
            if self.temperature < 20:
                temp_change = 2
                self.temperature += temp_change
                
        return temp_change, self.temperature

    def to_dict(self):
        return {
            "temperature": self.temperature,
            "turn_count": self.turn_count
        }

    @classmethod
    def from_dict(cls, data):
        ts = cls(data.get("temperature", -40))
        ts.turn_count = data.get("turn_count", 0)
        return ts
