from enum import Enum
import random
import json
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
        # Save state as JSON-serializable structure instead of pickle
        # random.getstate() returns (version, internal_state_tuple, gaussian_state)
        state = random.getstate()

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
                random.setstate(state)
            except (TypeError, ValueError, IndexError) as e:
                print(f"Warning: Failed to restore RNG state: {e}")
                if self.seed:
                    random.seed(self.seed)

class TimeSystem:
    def __init__(self, start_temp=-40):
        self.temperature = start_temp
        self.points_per_turn = 1
        self.turn_count = 0
        
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
