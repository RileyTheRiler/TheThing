import json
from pathlib import Path
from typing import List, Dict, Optional

from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Skill
from entities.item import Item


class CraftingSystem:
    """
    Manages crafting queues using JSON-defined recipes.
    Responds to TURN_ADVANCE by progressing jobs and emitting reporting events.
    """

    def __init__(self, data_path: Optional[str] = None):
        if not data_path:
            base_path = Path(__file__).resolve().parents[2]
            data_path = base_path / "data" / "crafting.json"
        
        self.data_path = Path(data_path)
        self.recipes = {}
        self._load_recipes()
        self.active_jobs: List[Dict] = []
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def _load_recipes(self):
        if not self.data_path.exists():
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                recipes_list = data.get("recipes", [])
                self.recipes = {r["id"]: r for r in recipes_list}
        except Exception as e:
            print(f"Error loading crafting recipes: {e}")

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def validate_ingredients(self, crafter, recipe_id: str) -> bool:
        recipe = self.recipes.get(recipe_id)
        if not recipe:
            return False
        
        inventory = getattr(crafter, "inventory", [])
        inv_names = [item.name.lower() for item in inventory]
        
        for ingredient in recipe.get("ingredients", []):
            if ingredient.lower() not in inv_names:
                return False
        return True

    def queue_craft(self, crafter, recipe_id: str, game_state, target_inventory=None):
        recipe_key = recipe_id.lower()
        recipe = self.recipes.get(recipe_key)
        if not recipe:
            event_bus.emit(GameEvent(EventType.CRAFTING_REPORT, {
                "event": "error",
                "message": f"Unknown recipe: {recipe_id}",
                "actor": getattr(crafter, "name", "unknown")
            }))
            return False

        if not self.validate_ingredients(crafter, recipe_id):
            event_bus.emit(GameEvent(EventType.CRAFTING_REPORT, {
                "event": "error",
                "message": "Insufficient ingredients.",
                "actor": getattr(crafter, "name", "unknown")
            }))
            return False

        job = {
            "crafter": crafter,
            "recipe": recipe,
            "turns_remaining": recipe.get("craft_time", 1),
            "game_state": game_state,
            "inventory": target_inventory if target_inventory is not None else getattr(crafter, "inventory", []),
        }

        # Handle instant crafting (0 turns)
        if job["turns_remaining"] <= 0:
            self._consume_ingredients(job)
            crafted_item = self._craft_item(job)
            event_bus.emit(GameEvent(EventType.CRAFTING_REPORT, {
                "event": "completed",
                "recipe": recipe_id,
                "actor": getattr(crafter, "name", "unknown"),
                "item_name": crafted_item.name
            }))
            return True

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
            throwable=recipe.get("throwable", False),
            noise_level=recipe.get("noise_level", 0),
            creates_light=recipe.get("creates_light", False),
            deployable=recipe.get("deployable", False)
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
                "actor": getattr(job["crafter"], "name", "unknown"),
                "item_name": crafted_item.name
            }))

            event_bus.emit(GameEvent(EventType.ITEM_PICKUP, {
                "actor": actor,
                "item": crafted_item.name
            }))

    def to_dict(self):
        return {
            "active_jobs": [
                {
                    "crafter_name": getattr(job["crafter"], "name", "MacReady"),
                    "recipe_id": job["recipe"]["id"],
                    "turns_remaining": job["turns_remaining"]
                }
                for job in self.active_jobs
            ]
        }

    @classmethod
    def from_dict(cls, data, game_state=None):
        system = cls()
        if not data:
            return system
        
        if game_state:
            for job_data in data.get("active_jobs", []):
                crafter = next((m for m in game_state.crew if m.name == job_data["crafter_name"]), game_state.player)
                recipe = system.recipes.get(job_data["recipe_id"])
                if recipe:
                    system.active_jobs.append({
                        "crafter": crafter,
                        "recipe": recipe,
                        "turns_remaining": job_data["turns_remaining"],
                        "game_state": game_state,
                        "inventory": getattr(crafter, "inventory", [])
                    })
        return system
