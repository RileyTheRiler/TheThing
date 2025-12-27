from enum import Enum
import random
import pickle
import base64
from core.event_system import event_bus, EventType, GameEvent
from core.resolution import ResolutionSystem


class Difficulty(Enum):
    """Game difficulty levels affecting infection rates, mask decay, and starting conditions."""
    EASY = "Easy"
    NORMAL = "Normal"
    HARD = "Hard"


class DifficultySettings:
    """Configuration for each difficulty level."""

    SETTINGS = {
        Difficulty.EASY: {
            "base_infection_chance": 0.05,      # 5% base infection per turn
            "darkness_infection_chance": 0.30,  # 30% in darkness
            "mask_decay_rate": 1,               # 1 point per turn
            "starting_paranoia": 0,
            "initial_infected_min": 1,
            "initial_infected_max": 1,
            "description": "Forgiving mode for learning the mechanics"
        },
        Difficulty.NORMAL: {
            "base_infection_chance": 0.10,      # 10% base infection per turn
            "darkness_infection_chance": 0.50,  # 50% in darkness
            "mask_decay_rate": 2,               # 2 points per turn
            "starting_paranoia": 0,
            "initial_infected_min": 1,
            "initial_infected_max": 2,
            "description": "The standard experience as intended"
        },
        Difficulty.HARD: {
            "base_infection_chance": 0.15,      # 15% base infection per turn
            "darkness_infection_chance": 0.70,  # 70% in darkness
            "mask_decay_rate": 3,               # 3 points per turn
            "starting_paranoia": 20,
            "initial_infected_min": 2,
            "initial_infected_max": 3,
            "description": "Paranoia from the start, trust no one"
        }
    }

    @classmethod
    def get(cls, difficulty: Difficulty, key: str):
        """Get a setting value for the given difficulty."""
        return cls.SETTINGS[difficulty].get(key)

    @classmethod
    def get_all(cls, difficulty: Difficulty) -> dict:
        """Get all settings for the given difficulty."""
        return cls.SETTINGS[difficulty].copy()


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

    def random(self):
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
        """Calculate hour of day based on turn count (0-23). Start at 08:00."""
        # 1 turn = 1 hour (simplified for now as per legacy code)
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
