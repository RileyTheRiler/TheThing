import json
from pathlib import Path
from typing import List, Dict, Optional

from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Skill
from entities.item import Item


class CraftingSystem:
    """
    Manages crafting queues using JSON-defined recipes.
    Responds to TURN_ADVANCE by progressing jobs and emitting reporting events.
    """

    def __init__(self, design_registry: Optional[DesignBriefRegistry] = None):
        base_path = Path(__file__).resolve().parents[2]
        self.design_registry = design_registry or DesignBriefRegistry()
        self.config = self.design_registry.get_brief("crafting")
        self.summary = self.config.get("summary")
        self.recipe_path = base_path / "data" / "crafting.json"
        self.recipes = self._load_recipes()
        self.active_jobs: List[Dict] = []
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def _load_recipes(self) -> Dict[str, Dict]:
        """Load recipes from data file, falling back to design briefs."""
        if self.recipe_path.exists():
            with self.recipe_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            recipes = data.get("recipes", []) if isinstance(data, dict) else []
            self.summary = data.get("summary", self.summary)
        else:
            recipes = self.config.get("recipes", [])

        return {r["id"].lower(): r for r in recipes if "id" in r}

    def _emit_invalid(self, crafter, recipe_id: str, missing: List[str]):
        actor = getattr(crafter, "name", "unknown")
        payload = {
            "event": "invalid",
            "recipe": recipe_id,
            "actor": actor,
            "missing": missing,
        }
        event_bus.emit(GameEvent(EventType.CRAFTING_REPORT, payload))
        if missing:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": f"Cannot craft {recipe_id}: missing {', '.join(missing)}."
            }))
        else:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": f"Cannot craft {recipe_id}: unknown recipe."
            }))

    def _validate_ingredients(self, recipe: Dict, inventory: List[Item]) -> List[str]:
        """Return a list of missing ingredients for the given inventory."""
        needed = [(i, i.lower()) for i in recipe.get("ingredients", [])]
        available = [getattr(item, "name", "").lower() for item in inventory]
        missing: List[str] = []

        for original, lowered in needed:
            if lowered in available:
                available.remove(lowered)
            else:
                missing.append(original)

        return missing

    def queue_craft(self, crafter, recipe_id: str, game_state, target_inventory=None):
        recipe_key = recipe_id.lower()
        recipe = self.recipes.get(recipe_key)
        if not recipe:
            self._emit_invalid(crafter, recipe_id, [])
            return False

        inventory = target_inventory or getattr(crafter, "inventory", [])
        missing = self._validate_ingredients(recipe, inventory)
        if missing:
            self._emit_invalid(crafter, recipe["id"], missing)
            return False

        job = {
            "crafter": crafter,
            "recipe": recipe,
            "turns_remaining": recipe.get("craft_time", 1),
            "game_state": game_state,
            "inventory": target_inventory or getattr(crafter, "inventory", []),
        }
        self.active_jobs.append(job)
        event_bus.emit(GameEvent(EventType.CRAFTING_REPORT, {
            "event": "queued",
            "recipe": recipe_id,
            "actor": getattr(crafter, "name", "unknown"),
            "turns": recipe.get("craft_time", 1),
        }))
        return True

    def _consume_ingredients(self, job) -> None:
        inventory = job["inventory"]
        ingredients = job["recipe"].get("ingredients", [])
        for ingredient in ingredients:
            for idx, item in enumerate(list(inventory)):
                if getattr(item, "name", "").lower() == ingredient.lower():
                    inventory.pop(idx)
                    break

    def _craft_item(self, job):
        recipe = job["recipe"]
        weapon_skill = recipe.get("weapon_skill")
        try:
            weapon_skill_enum = Skill[weapon_skill] if weapon_skill else None
        except KeyError:
            weapon_skill_enum = None

        crafted = Item(
            name=recipe["name"],
            description=recipe.get("description", ""),
            category=recipe.get("category", "misc"),
            weapon_skill=weapon_skill_enum,
            damage=recipe.get("damage", 0),
            uses=recipe.get("uses", -1),
            effect=recipe.get("effect"),
            effect_value=recipe.get("effect_value", 0),
        )
        crafted.add_history(
            getattr(job["game_state"], "turn", 0),
            f"Crafted by {getattr(job['crafter'], 'name', 'unknown')}"
        )
        job["inventory"].append(crafted)
        return crafted

    def on_turn_advance(self, event: GameEvent):
        if not self.active_jobs:
            return

        for job in list(self.active_jobs):
            job["turns_remaining"] -= 1
            if job["turns_remaining"] > 0:
                continue

            self._consume_ingredients(job)
            crafted_item = self._craft_item(job)
            self.active_jobs.remove(job)

            actor = getattr(job["crafter"], "name", "unknown")
            event_bus.emit(GameEvent(EventType.CRAFTING_REPORT, {
                "event": "completed",
                "recipe": job["recipe"]["id"],
                "actor": actor,
                "item_name": crafted_item.name,
                "brief": self.summary
            }))

            event_bus.emit(GameEvent(EventType.ITEM_PICKUP, {
                "actor": actor,
                "item": crafted_item.name
            }))
