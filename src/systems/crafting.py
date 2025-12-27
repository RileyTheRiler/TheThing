from typing import List, Dict, Optional

from core.design_briefs import DesignBriefRegistry
from core.event_system import event_bus, EventType, GameEvent
from entities.item import Item


class CraftingSystem:
    """
    Manages crafting queues using JSON-defined recipes.
    Responds to TURN_ADVANCE by progressing jobs and emitting reporting events.
    """

    def __init__(self, design_registry: Optional[DesignBriefRegistry] = None):
        self.design_registry = design_registry or DesignBriefRegistry()
        self.config = self.design_registry.get_brief("crafting")
        self.recipes = {r["id"]: r for r in self.config.get("recipes", [])}
        self.active_jobs: List[Dict] = []
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def queue_craft(self, crafter, recipe_id: str, game_state, target_inventory=None):
        recipe = self.recipes.get(recipe_id)
        if not recipe:
            return

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
            "actor": getattr(crafter, "name", "unknown")
        }))

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
        crafted = Item(
            name=recipe["name"],
            description=recipe.get("description", ""),
            category=recipe.get("category", "misc")
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

            event_bus.emit(GameEvent(EventType.CRAFTING_REPORT, {
                "event": "completed",
                "recipe": job["recipe"]["id"],
                "actor": getattr(job["crafter"], "name", "unknown"),
                "item_name": crafted_item.name,
                "brief": self.config.get("summary")
            }))

            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"{getattr(job['crafter'], 'name', 'You')} crafted {crafted_item.name}."
            }))
