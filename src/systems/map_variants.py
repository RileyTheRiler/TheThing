import random
from core.event_system import event_bus, EventType, GameEvent
from systems.room_state import RoomState

class MapVariantSystem:
    """
    Randomizes starting conditions of the station map to increase replayability.
    """
    def __init__(self, rng=None):
        self.rng = rng or random

    def apply_variants(self, game_state):
        """
        Roll for random map quirks and apply them to the game state.
        
        Possible Quirk Types:
        - BROKEN_GENERATOR: Generator starts with damage or offline.
        - FROZEN_SECTOR: A specific room starts frozen.
        - SUPPLY_SHORTAGE: Reduced items in storage.
        - LOCKED_DOORS: Some rooms start barricaded.
        """
        # 30% chance of a variant
        if self.rng.random() > 0.3:
            return

        variants = [
            self._variant_broken_generator,
            self._variant_frozen_kennel,
            self._variant_supply_shortage,
            self._variant_locked_storage
        ]
        
        if hasattr(self.rng, "choose"):
            chosen_variant = self.rng.choose(variants)
        else:
            chosen_variant = self.rng.choice(variants)
        chosen_variant(game_state)

    def _variant_broken_generator(self, game_state):
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": "[MAP VARIANT] The generator is sputtering. It seems damaged from the start."
        }))
        # We don't have a direct "health" on generator yet, but we can simulate it
        # by triggering a minor sabotage-like effect or just alerting the player.
        # Ideally, we'd set require_repair = True.
        # For now, let's just turn it off so they have to restart it.
        game_state.power_on = False
        game_state.room_states.on_power_failure(None)

    def _variant_frozen_kennel(self, game_state):
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": "[MAP VARIANT] The heating in the Kennel has failed."
        }))
        game_state.room_states.add_state("Kennel", RoomState.FROZEN)

    def _variant_supply_shortage(self, game_state):
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": "[MAP VARIANT] Supplies are running low in Storage."
        }))
        # Remove some items from Storage
        storage_items = game_state.station_map.get_items_in_room(17, 2) # Rough coord for Storage center
        # Actually better to target by room name
        if "Storage" in game_state.station_map.room_items:
            # removing half items
            items = game_state.station_map.room_items["Storage"]
            keep_count = len(items) // 2
            game_state.station_map.room_items["Storage"] = items[:keep_count]

    def _variant_locked_storage(self, game_state):
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": "[MAP VARIANT] The Storage door is jammed."
        }))
        game_state.room_states.barricade_room("Storage", actor="System")
