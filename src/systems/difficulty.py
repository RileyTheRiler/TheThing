"""
Difficulty Scaling System (Tier 10.2)
Manages difficulty scaling for Survivor Mode where each run increases challenge.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SurvivorModeState:
    """Tracks state across survivor mode runs."""
    active: bool = False
    current_run: int = 0
    carryover_items: list = None
    carryover_skills: dict = None
    carryover_crew_member: Optional[str] = None
    total_wins: int = 0
    
    def __post_init__(self):
        if self.carryover_items is None:
            self.carryover_items = []
        if self.carryover_skills is None:
            self.carryover_skills = {}


class SurvivorDifficultyScaler:
    """
    Scales difficulty for survivor mode based on run number.
    
    Each successful run increases the challenge:
    - More starting infected NPCs
    - Lower starting temperature
    - Higher chance of damaged equipment
    """
    
    # Maximum scaling caps to prevent impossible difficulty
    MAX_ADDITIONAL_INFECTED = 4  # Cap at +4 extra infected
    MIN_TEMPERATURE_MODIFIER = -30  # Cap at -30°C from base
    MAX_EQUIPMENT_DAMAGE_CHANCE = 0.5  # Cap at 50% chance
    
    @staticmethod
    def get_starting_infected_count(run: int) -> int:
        """
        Get number of additional infected NPCs for this run.
        
        Args:
            run: Current run number (0-indexed)
            
        Returns:
            Number of additional infected NPCs (on top of base 1)
        """
        additional = min(run, SurvivorDifficultyScaler.MAX_ADDITIONAL_INFECTED)
        return 1 + additional  # Base 1 + scaled additions
    
    @staticmethod
    def get_temperature_modifier(run: int) -> int:
        """
        Get temperature modifier for this run.
        
        Args:
            run: Current run number (0-indexed)
            
        Returns:
            Temperature modifier in degrees C (negative = colder)
        """
        modifier = -5 * run
        return max(modifier, SurvivorDifficultyScaler.MIN_TEMPERATURE_MODIFIER)
    
    @staticmethod
    def get_equipment_damage_chance(run: int) -> float:
        """
        Get chance that each piece of equipment starts damaged.
        
        Args:
            run: Current run number (0-indexed)
            
        Returns:
            Damage probability (0.0 to 0.5)
        """
        chance = 0.1 * run  # 10% per run
        return min(chance, SurvivorDifficultyScaler.MAX_EQUIPMENT_DAMAGE_CHANCE)
    
    @staticmethod
    def get_difficulty_summary(run: int) -> str:
        """Get a human-readable summary of difficulty modifiers."""
        infected = SurvivorDifficultyScaler.get_starting_infected_count(run)
        temp_mod = SurvivorDifficultyScaler.get_temperature_modifier(run)
        damage_chance = SurvivorDifficultyScaler.get_equipment_damage_chance(run)
        
        lines = [
            f"=== SURVIVOR MODE RUN {run + 1} ===",
            f"Starting Infected: {infected}",
            f"Temperature Modifier: {temp_mod:+d}°C",
            f"Equipment Damage Risk: {damage_chance * 100:.0f}%"
        ]
        
        if run > 0:
            lines.append("")
            lines.append("Previous run bonuses applied:")
            lines.append("- Up to 3 items carried over")
            lines.append("- Skill levels preserved")
        
        return "\n".join(lines)


class CarryoverManager:
    """
    Manages item and skill carryover between survivor mode runs.
    """
    
    MAX_CARRYOVER_ITEMS = 3
    
    @staticmethod
    def select_carryover_items(inventory: list, max_items: int = 3) -> list:
        """
        Select items to carry over to next run.
        
        Args:
            inventory: Full inventory from completed run
            max_items: Maximum items allowed (default 3)
            
        Returns:
            List of selected item names (up to max_items)
        """
        # Prioritize key items, then weapons, then tools
        priority_order = [
            "Flamethrower", "Test Kit", "Radio Parts", "Medical Kit",
            "Shotgun", "Pistol", "Axe", "Knife",
            "Flashlight", "Rope", "Fuel", "Wire Cutters"
        ]
        
        selected = []
        remaining = list(inventory)
        
        # First pass: priority items
        for item_name in priority_order:
            if len(selected) >= max_items:
                break
            if item_name in remaining:
                selected.append(item_name)
                remaining.remove(item_name)
        
        # Second pass: any remaining items
        while len(selected) < max_items and remaining:
            selected.append(remaining.pop(0))
        
        return selected[:max_items]
    
    @staticmethod
    def preserve_skills(player) -> dict:
        """
        Extract skill levels from player to carry over.
        
        Args:
            player: Player entity with skill attributes
            
        Returns:
            Dictionary of skill name -> level
        """
        skills = {}
        
        # Common skill attributes
        skill_attrs = [
            'stealth_level', 'combat_skill', 'repair_skill',
            'medical_skill', 'investigation_skill'
        ]
        
        for attr in skill_attrs:
            if hasattr(player, attr):
                skills[attr] = getattr(player, attr)
        
        # Also preserve XP if tracked
        xp_attrs = ['stealth_xp', 'combat_xp', 'repair_xp']
        for attr in xp_attrs:
            if hasattr(player, attr):
                skills[attr] = getattr(player, attr)
        
        return skills
    
    @staticmethod
    def apply_skill_carryover(player, skills: dict):
        """
        Apply carried-over skills to player.
        
        Args:
            player: Player entity to modify
            skills: Dictionary of skill name -> level from previous run
        """
        for attr, value in skills.items():
            if hasattr(player, attr):
                setattr(player, attr, value)
    
    @staticmethod
    def select_survivor_crew_member(crew: list) -> Optional[str]:
        """
        Select a surviving crew member to carry over.
        
        Args:
            crew: List of surviving crew members at end of run
            
        Returns:
            Name of selected crew member, or None if no survivors
        """
        if not crew:
            return None
        
        # Prioritize by trust/relationship, then randomly
        # For simplicity, just pick the first non-infected survivor
        for member in crew:
            if hasattr(member, 'is_thing') and not member.is_thing:
                if hasattr(member, 'is_alive') and member.is_alive:
                    return member.name
        
        return None
