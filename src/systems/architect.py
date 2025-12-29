"""Systems architecture utilities and helpers.

Imports follow the project-level absolute pattern (`from core...`) so modules stay
importable without sys.path tweaks or `src.` prefixes.
"""

import random
from enum import Enum

from core.event_system import event_bus, EventType, GameEvent
from core.resolution import ResolutionSystem


class Verbosity(Enum):
    """Logging verbosity levels."""
    MINIMAL = 0
    STANDARD = 1
    VERBOSE = 2
    DEBUG = 3


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


class Verbosity(Enum):
    STANDARD = "Standard"
    VERBOSE = "Verbose"
    MINIMAL = "Minimal"


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
            "dice": dice,
            "dice_count": pool_size
        }

    def choose(self, collection):
        if not collection:
            return None
        return self._random.choice(list(collection))

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
        rng_state = data.get("rng_state")

        # Handle legacy pickle format (for backward compatibility if needed,
        # but for security we should probably drop it or strictly validate.
        # Given the instruction to fix security, we will NOT support the vulnerable format.)
        if rng_state:
            # Reconstruct tuple structure required by random.setstate
            # (version, internal_state_tuple, gaussian_state)
            try:
                state = (
                    rng_state[0],
                    tuple(rng_state[1]),
                    rng_state[2]
                )
                self._random.setstate(state)
            except (TypeError, ValueError, IndexError) as e:
                print(f"Warning: Failed to restore RNG state: {e}")
                if self.seed:
                    self._random.seed(self.seed)


class Verbosity(Enum):
    MINIMAL = "Minimal"
    STANDARD = "Standard"
    VERBOSE = "Verbose"
    DEBUG = "Debug"



class TimeSystem:
    def __init__(self, start_temp=-40, start_hour=19):
        self.temperature = start_temp
        self.points_per_turn = 1
        self.turn_count = 0

    @property
    def hour(self):
        """Returns the current hour (0-23) based on turn count.
           Assuming game starts at 08:00 and each turn is 1 hour."""
        return (8 + self.turn_count) % 24
        self.start_hour = start_hour
        
    @property
    def hour(self):
        """Calculates current hour based on turn count."""
        return self.turn_count % 24
        # Subscribe to turn advances
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

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
        """Current in-game hour (0-23)."""
        return (self.start_hour + self.turn_count) % 24

    @hour.setter
    def hour(self, value: int):
        """
        Set the current in-game hour by adjusting the start offset.

        The TimeSystem tracks time as an offset from the initial hour plus
        turn_count. Updating the hour recalculates start_hour so that future
        ticks continue from the requested time.
        """
        # Normalize to 0-23 to keep representation consistent
        normalized = value % 24
        self.start_hour = (normalized - self.turn_count) % 24

    def tick(self):
        """Advance time by one turn."""
        self.turn_count += 1

    def on_turn_advance(self, event: GameEvent):
        """Advance time and update environment on turn."""
        self.tick()
        game_state = event.payload.get("game_state")
        if game_state:
            self.update_environment(game_state.power_on)
    @property
    def hour(self):
        """Returns the current hour of the day (0-23)."""
        # Assuming 1 turn = 1 hour for now based on usage
        return self.turn_count % 24
        
    def update_environment(self, power_on):
        """
        Updates environmental factors based on power state.
        Returns: Tuple (temperature_change, new_temperature)
        """
        old_temp = self.temperature

        # Delegate to ResolutionSystem for consistent thermal decay physics
        res = ResolutionSystem()
        self.temperature = res.calculate_thermal_decay(self.temperature, power_on)

        temp_change = self.temperature - old_temp
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
        temp = data.get("temperature", -40)
        turn_count = data.get("turn_count", 0)
        saved_hour = data.get("hour", 19)

        # Recalculate start hour so property math remains consistent
        start_hour = (saved_hour - turn_count) % 24

        ts = cls(temp, start_hour=start_hour)
        ts.turn_count = turn_count
        return ts
