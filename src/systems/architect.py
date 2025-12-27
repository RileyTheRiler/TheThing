"""Systems architecture utilities and helpers.

Imports follow the project-level absolute pattern (`from core...`) so modules stay
importable without sys.path tweaks or `src.` prefixes.
"""

import random
import json
from core.event_system import event_bus, EventType, GameEvent
from core.resolution import ResolutionSystem
from enum import Enum


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
        self._random = random.Random(self.seed)
    
    def roll_2d6(self):
        """Standard 2d6 roll."""
        return self._random.randint(1, 6) + self._random.randint(1, 6)
    
    def roll_d6(self):
        return self._random.randint(1, 6)

    def randint(self, a, b):
        return self._random.randint(a, b)

    def sample(self, population, k):
        return self._random.sample(population, k)
        
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
        return self._random.choice(collection)
        
    def random_float(self):
        return self._random.random()

    def random(self):
        return self._random.random()

    def to_dict(self):
        # Save state as JSON-serializable structure instead of pickle
        # random.getstate() returns (version, internal_state_tuple, gaussian_state)
        state = self._random.getstate()

        # Convert tuple to list for JSON serialization
        # internal_state_tuple is a tuple of 624 ints, so it converts cleanly
        serializable_state = [state[0], list(state[1]), state[2]]
        
        return {
            "seed": self.seed,
            "rng_state": serializable_state
        }

    def from_dict(self, data):
        self.seed = data.get("seed")
        # Reinitialize the local RNG with the stored seed so state restoration is deterministic
        self._random = random.Random(self.seed)
        if not data:
            return
        self.seed = data.get("seed", self.seed)
        rng_state = data.get("rng_state")

        if rng_state:
            try:
                state = (
                    rng_state[0],
                    tuple(rng_state[1]),
                    rng_state[2]
                )
                self._random.setstate(state)
            except (TypeError, ValueError, IndexError) as e:
                print(f"Warning: Failed to restore RNG state: {e}")
                if self.seed is not None:
                    self._random.seed(self.seed)
                random.setstate(state)
                return
            except (TypeError, ValueError, IndexError) as e:
                print(f"Warning: Failed to restore RNG state: {e}")
        if self.seed is not None:
            random.seed(self.seed)

class TimeSystem:
    def __init__(self, start_temp=-40, start_hour=19):
        self.temperature = start_temp
        self.points_per_turn = 1
        self.turn_count = 0
        self._start_hour = start_hour  # Reference hour for turn-based progression
        
        # Subscribe to Turn Advance
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def on_turn_advance(self, event: GameEvent):
        """Handle turn advance event."""
        self.tick()
        game_state = event.payload.get("game_state")
        power_on = game_state.power_on if game_state else True
        self.update_environment(power_on)

    @property
    def hour(self):
        # Start at 19:00 (7 PM), 1 turn = 1 hour
        return (19 + self.turn_count) % 24
        self.start_hour = start_hour

    @property
    def hour(self):
        """Current in-game hour (0-23)."""
        return (self.start_hour + self.turn_count) % 24
        self.start_hour = start_hour  # Start at 7 PM by default
        self._start_hour = start_hour
        self._hour = start_hour

    @property
    def hour(self):
        """Current in-game hour (0-23)."""
        return self._hour

    @hour.setter
    def hour(self, value):
        # Allow safe assignment from load/state restoration while normalizing range.
        self._hour = int(value) % 24

    def tick(self):
        """Advance time by one turn."""
        self.turn_count += 1

        self._hour = (self._start_hour + self.turn_count) % 24

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
            "turn_count": self.turn_count,
            "hour": self.hour
        }

    @classmethod
    def from_dict(cls, data):
        if not data:
            return cls()

        turn_count = data.get("turn_count", 0)
        saved_hour = data.get("hour", 19)
        start_hour = (saved_hour - turn_count) % 24
        ts = cls(data.get("temperature", -40), start_hour)
        ts.turn_count = turn_count
        temp = data.get("temperature", -40)
        turn_count = data.get("turn_count", 0)
        saved_hour = data.get("hour", 19)

        start_hour = (saved_hour - turn_count) % 24

        ts = cls(temp, start_hour=start_hour)
        ts.turn_count = turn_count
        # Recompute hour from stored value to keep normalization consistent.
        ts.hour = saved_hour
        return ts
