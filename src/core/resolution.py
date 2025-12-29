import math
from dataclasses import dataclass
from enum import Enum


@dataclass
class ResolutionModifiers:
    """Environmental modifiers that adjust roll math."""

    attack_pool: int = 0
    observation_pool: int = 0
    stealth_detection: float = 0.0

class Attribute(Enum):
    PROWESS = "Prowess"
    LOGIC = "Logic"
    INFLUENCE = "Influence"
    RESOLVE = "Resolve"
    THERMAL = "Thermal"

class Skill(Enum):
    MELEE = "Melee"
    FIREARMS = "Firearms"
    PILOT = "Pilot"
    REPAIR = "Repair"
    MEDICINE = "Medicine"
    PERSUASION = "Persuasion"
    EMPATHY = "Empathy"
    OBSERVATION = "Observation"
    GEOLOGY = "Geology"
    MECHANICS = "Mechanics"
    SCIENCE = "Science"
    METEOROLOGY = "Meteorology"
    HANDLING = "Handling"
    COMMS = "Comms"
    DECEPTION = "Deception"
    STEALTH = "Stealth"

    @staticmethod
    def get_attribute(skill):
        mapping = {
            Skill.MELEE: Attribute.PROWESS,
            Skill.FIREARMS: Attribute.PROWESS,
            Skill.PILOT: Attribute.PROWESS,
            Skill.REPAIR: Attribute.PROWESS,     # "Mechanical skill"
            Skill.MECHANICS: Attribute.PROWESS,
            Skill.HANDLING: Attribute.PROWESS,   
            Skill.STEALTH: Attribute.PROWESS,
            
            Skill.MEDICINE: Attribute.LOGIC,
            Skill.OBSERVATION: Attribute.LOGIC,  
            Skill.GEOLOGY: Attribute.LOGIC,
            Skill.SCIENCE: Attribute.LOGIC,
            Skill.METEOROLOGY: Attribute.LOGIC,
            Skill.COMMS: Attribute.LOGIC,        # "Technical understanding"

            Skill.PERSUASION: Attribute.INFLUENCE,
            Skill.EMPATHY: Attribute.INFLUENCE,  # Social standing/understanding
            Skill.DECEPTION: Attribute.INFLUENCE,

            # Resolve serves as a defense/resistance stat primarily
        }
        return mapping.get(skill)

class ResolutionSystem:
    @staticmethod
    def adjust_pool(base_pool: int, modifier: int) -> int:
        """
        Safely adjust a dice pool by an integer modifier without going negative.
        """
        return max(0, base_pool + modifier)

    @staticmethod
    def roll_check(pool_size, rng):
        """
        Executes a dice pool check using the provided RandomnessEngine.
        
        This method requires an explicit RandomnessEngine to ensure deterministic 
        behavior across game sessions and save/load cycles.
        
        Success = 6s.
        """
        pool_size = max(1, pool_size)
        
        if rng and hasattr(rng, "calculate_success"):
            return rng.calculate_success(pool_size)

        raise ValueError("RandomnessEngine (rng) must be provided for roll_check to ensure determinism.")

    @staticmethod
    def resolve_pool(base_pool, skills_attributes, modifiers):
        """
        Calculates final pool size by applying modifiers.
        
        Args:
            base_pool (int): Starting pool size.
            skills_attributes (list): Skills/Attributes involved in the roll.
            modifiers (dict): Active environmental modifiers.
            
        Returns:
            int: Modified pool size (minimum 1).
        """
        if not modifiers:
            return max(1, base_pool)
            
        final_pool = base_pool
        for sa in skills_attributes:
            if sa in modifiers:
                final_pool += modifiers[sa]
                
        return max(1, final_pool)

    @staticmethod
    def success_probability(pool_size: int) -> float:
        """Probability of at least one success (6) in the pool."""
        if pool_size <= 0:
            return 0.0
        return 1 - math.pow(5 / 6, pool_size)

    def calculate_infection_risk(self, lighting_condition: str, mask_integrity: float, paranoia_level: int) -> float:
        """
        Calculates P(Infection) based on the formula:
        P(I) = BaseChance * (1.0 - Mask_Integrity) * (1 + (Paranoia / 100))
        
        lighting_condition: "LIGHT" or "DARK"
        """
        base_chance = 0.05
        if lighting_condition.upper() == "DARK":
            base_chance = 0.40
            
        probability = base_chance * (1.0 - mask_integrity) * (1.0 + (paranoia_level / 100.0))
        return min(1.0, max(0.0, probability))

    def calculate_thermal_decay(self, current_temp: float, power_on: bool) -> float:
        """
        Calculates new temperature based on:
        Delta_T = -k * (Current_Temp - Target_Temp)
        Target is -50 if power off, +10 if power on.
        """
        target_temp = 10.0 if power_on else -60.0 # Deep freeze target
        k = 0.1 # Decay constant
        
        # Newton's Law of Cooling approximation for a game turn
        # T_new = T + k(T_target - T)
        # But the formula in the spec was a bit abstract, let's stick to a robust cooling curve
        # or the simple linear approximation implied by the user's prompt "Delta T = ..."
        
        # User prompt said: Delta T = -k * (Current_Temp - Ambient_Exterior) where k=0.5 if power off
        # Let's align with that specific instruction if possible, but the user actually gave:
        # Delta T = -k * (Current_Temp - (-60)) if power off. k=0.2 (arbitrary game balance choice)
        # UPDATE: Tuning to align with user prompt (k=0.5) for rapid freezing mechanic.
        
        k_val = 0.05 if power_on else 0.5
        ambient_exterior = -60.0
        
        # If power is on, we are heating UP towards 10C, or maintaining 10C.
        if power_on:
            # Heating logic: Moves towards 15C
            target = 15.0
            delta = k_val * (target - current_temp)
        else:
            # Cooling logic: Moves towards -60C
            delta = -k_val * (current_temp - ambient_exterior)

        return current_temp + delta
