"""Item entity class for The Thing game."""

from core.resolution import Skill


class Item:
    """Represents a physical item in the game world.

    Items can be weapons, tools, evidence, or consumables. They track
    their own history for chain-of-custody forensic purposes.
    """

    def __init__(self, name, description, is_evidence=False, weapon_skill=None, damage=0,
                 uses=-1, effect=None, effect_value=0, category="misc"):
        self.name = name
        self.description = description
        self.is_evidence = is_evidence
        self.weapon_skill = weapon_skill
        self.damage = damage
        self.uses = uses
        self.effect = effect
        self.effect_value = effect_value
        self.category = category
        self.history = []

    def add_history(self, turn, location):
        """Record an event in the item's chain of custody."""
        self.history.append(f"[Turn {turn}] {location}")

    def is_consumable(self):
        """Check if item has limited uses."""
        return self.uses > 0

    def consume(self):
        """Use one charge of a consumable item."""
        if self.uses > 0:
            self.uses -= 1
            return self.uses >= 0
        return True

    def __str__(self):
        if self.damage > 0:
            return f"{self.name} (DMG: {self.damage})"
        elif self.uses > 0:
            return f"{self.name} ({self.uses} uses)"
        return self.name

    def to_dict(self):
        """Serialize item to dictionary for save/load."""
        return {
            "name": self.name,
            "description": self.description,
            "is_evidence": self.is_evidence,
            "weapon_skill": self.weapon_skill.name if self.weapon_skill else None,
            "damage": self.damage,
            "uses": self.uses,
            "effect": self.effect,
            "effect_value": self.effect_value,
            "category": self.category,
            "history": self.history
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize item from dictionary."""
        if not data or not isinstance(data, dict):
            # Return None or empty item instead of raising to prevent save corruption?
            # Raising seems safer for now to catch bad saves early.
            # But let's follow the pattern of being slightly robust?
            # Actually, `engine.py` might expect an Item.
            # Let's stick to the stricter validation for now.
            if not data:
                return None
            if not isinstance(data, dict):
                 raise ValueError("Item data must be a dictionary.")

        name = data.get("name")
        description = data.get("description")
        if not name or not description:
            # Fallback for old saves or partial data?
             name = name or "Unknown Item"
             description = description or "A mysterious object."

        skill = None
        skill_name = data.get("weapon_skill")
        if skill_name:
            try:
                skill = Skill[skill_name]
            except (KeyError, ValueError):
                skill = None

        item = cls(
            name=name,
            description=description,
            is_evidence=data.get("is_evidence", False),
            weapon_skill=skill,
            damage=data.get("damage", 0),
            uses=data.get("uses", -1),
            effect=data.get("effect"),
            effect_value=data.get("effect_value", 0),
            category=data.get("category", "misc")
        )
        item.history = data.get("history", [])
        return item
