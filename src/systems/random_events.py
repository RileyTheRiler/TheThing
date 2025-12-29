"""
Random Events System (Tier 6.2)
Generates dynamic events during gameplay: blizzards, equipment failures,
supply discoveries, and atmospheric occurrences.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional, Callable
from core.event_system import event_bus, EventType, GameEvent


class EventCategory(Enum):
    """Categories of random events."""
    WEATHER = auto()      # Blizzards, temperature drops
    EQUIPMENT = auto()    # Failures, malfunctions
    DISCOVERY = auto()    # Finding items, clues
    ATMOSPHERE = auto()   # Creepy sounds, paranoia triggers
    CREATURE = auto()     # Thing-related events
    SABOTAGE = auto()     # Discovered sabotage
    NPC = auto()          # NPC-triggered events


class EventSeverity(Enum):
    """How impactful the event is."""
    MINOR = 1       # Flavor text only
    MODERATE = 2    # Small gameplay effect
    MAJOR = 3       # Significant gameplay change
    CRITICAL = 4    # Game-changing event


@dataclass
class RandomEvent:
    """Definition of a random event."""
    id: str
    name: str
    description: str
    category: EventCategory
    severity: EventSeverity
    weight: int = 10  # Higher = more likely
    min_turn: int = 1  # Earliest turn this can trigger
    max_turn: int = 999  # Latest turn this can trigger
    cooldown: int = 0  # Turns before this can trigger again
    requires_power: Optional[bool] = None  # None = either
    requires_infected: Optional[bool] = None  # Requires infected crew
    effect: Optional[Callable] = None  # Function to execute


class RandomEventSystem:
    """Manages random event generation and execution."""

    def __init__(self, rng, config_registry=None):
        self.rng = rng
        self.config_registry = config_registry
        self.events = self._load_events()
        self.event_history = []  # List of (turn, event_id)
        self.cooldowns = {}  # event_id -> turns until available
        
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def _load_events(self) -> List[RandomEvent]:
        """Load events from config or fallback to definitions."""
        events = []
        
        if self.config_registry:
            brief = self.config_registry.get_brief("random_events")
            if brief and "events" in brief:
                for event_data in brief["events"]:
                    try:
                        # Map string category to Enum
                        category_str = event_data.get("category", "ATMOSPHERE")
                        category = getattr(EventCategory, category_str, EventCategory.ATMOSPHERE)
                        
                        severity_str = event_data.get("severity", "MINOR")
                        severity = getattr(EventSeverity, severity_str, EventSeverity.MINOR)
                        
                        # Create closure for effect execution
                        effects_list = event_data.get("effects", [])
                        
                        # We need to capture effects_list in the lambda correctly
                        def create_effect_runner(effects_data):
                            return lambda game: self._execute_effects(game, effects_data)
                        
                        event_effect = create_effect_runner(effects_list) if effects_list else None

                        event = RandomEvent(
                            id=event_data["id"],
                            name=event_data["name"],
                            description=event_data["description"],
                            category=category,
                            severity=severity,
                            weight=event_data.get("weight", 10),
                            min_turn=event_data.get("min_turn", 1),
                            max_turn=event_data.get("max_turn", 999),
                            cooldown=event_data.get("cooldown", 0),
                            requires_power=event_data.get("requires_power"),
                            requires_infected=event_data.get("requires_infected"),
                            effect=event_effect
                        )
                        events.append(event)
                    except Exception as e:
                        print(f"Error loading event {event_data.get('id')}: {e}")
        
        return events

    def on_turn_advance(self, event):
        game_state = event.payload.get("game_state")
        if game_state:
            res_event = self.check_for_event(game_state)
            if res_event:
                self.execute_event(res_event, game_state)

    def check_for_event(self, game_state) -> Optional[RandomEvent]:
        """Check if a random event should trigger this turn."""
        # Update cooldowns
        for event_id in list(self.cooldowns.keys()):
            self.cooldowns[event_id] -= 1
            if self.cooldowns[event_id] <= 0:
                del self.cooldowns[event_id]

        # Base chance from config
        base_chance = 0.15
        if self.config_registry:
            brief = self.config_registry.get_brief("random_events")
            if brief:
                base_chance = brief.get("base_chance", 0.15)
                # Increase chance with paranoia
                base_chance += (game_state.paranoia_level * brief.get("paranoia_multiplier", 0.005))

        val = self.rng.random_float()
        
        if val > base_chance:
            return None

        # Filter eligible events
        eligible = []
        for event in self.events:
            # Check turn range
            if game_state.turn < event.min_turn:
                continue
            if game_state.turn > event.max_turn:
                continue

            # Check cooldown
            if event.id in self.cooldowns:
                continue

            # Check power requirement
            if event.requires_power is not None:
                if event.requires_power != game_state.power_on:
                    continue

            # Check infection requirement
            if event.requires_infected:
                has_infected = any(m.is_infected for m in game_state.crew if m.is_alive)
                if not has_infected:
                    continue

            eligible.append(event)

        if not eligible:
            return None

        # Weighted random selection
        total_weight = sum(e.weight for e in eligible)
        roll = self.rng.random_float() * total_weight

        cumulative = 0
        for event in eligible:
            cumulative += event.weight
            if roll <= cumulative:
                # Apply cooldown
                if event.cooldown > 0:
                    self.cooldowns[event.id] = event.cooldown

                # Record in history
                self.event_history.append((game_state.turn, event.id))

                return event

        return None

    def execute_event(self, event: RandomEvent, game_state):
        """Execute a random event's effect."""
        # Process description templates
        description = event.description
        
        # Replace template placeholders if any
        if "{{npc_name}}" in description or "{{target_name}}" in description:
            # Pick valid agents for template
            candidates = [m for m in game_state.crew if m.is_alive and m != game_state.player]
            if candidates:
                actor = self.rng.choose(candidates)
                description = description.replace("{{npc_name}}", actor.name)
                
                targets = [m for m in game_state.crew if m.is_alive and m != actor]
                if targets:
                    target = self.rng.choose(targets)
                    description = description.replace("{{target_name}}", target.name)
        
        # Emit message event
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            'text': f"\\n[EVENT: {event.name}]",
            'crawl': False
        }))
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            'text': description,
            'crawl': True
        }))

        # Execute effect if present
        if event.effect:
            event.effect(game_state)

    def _execute_effects(self, game_state, effects_data: List[dict]):
        """Execute a list of effect definitions."""
        for effect in effects_data:
            eff_type = effect.get("type")
            
            if eff_type == "power_off":
                game_state.power_on = False
                event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "The hum of the generator dies. Silence falls."}))
                
            elif eff_type == "all_rooms_dark":
                if hasattr(game_state, 'room_states') and hasattr(game_state, 'station_map'):
                    rooms = list(game_state.station_map.rooms.keys())
                    for room in rooms:
                        game_state.room_states.add_state(room, "DARK")
                
            elif eff_type == "random_rooms_dark":
                count = effect.get("count", 1)
                # This would require accessing RoomStateManager to set DARK state
                if hasattr(game_state, 'room_states') and hasattr(game_state, 'station_map'):
                    rooms = list(game_state.station_map.rooms.keys())
                    targets = self.rng.choose_many(rooms, count)
                    for room in targets:
                        game_state.room_states.add_state(room, "DARK")
                    target_str = ", ".join(targets)
                    event_bus.emit(GameEvent(EventType.MESSAGE, {"text": f"Power lost in: {target_str}."}))

            elif eff_type == "paranoia":
                amount = effect.get("amount", 5)
                game_state.paranoia_level = min(100, game_state.paranoia_level + amount)
                
            elif eff_type == "require_repair":
                target = effect.get("target")
                if hasattr(game_state, 'sabotage'):
                    if target == "generator":
                        game_state.sabotage.generator_stress = 100 # Max stress/broken
                        
            elif eff_type == "destroy_equipment":
                target = effect.get("target")
                if target == "radio" and hasattr(game_state, 'sabotage'):
                    game_state.sabotage.radio_working = False
                    
            elif eff_type == "sabotage_helicopter":
                if hasattr(game_state, 'sabotage'):
                    game_state.sabotage.helicopter_working = False

            elif eff_type == "emit_event":
                evt_type_str = effect.get("event_type")
                target = effect.get("target")
                if evt_type_str and hasattr(EventType, evt_type_str):
                    evt_type = getattr(EventType, evt_type_str)
                    event_bus.emit(GameEvent(evt_type, {"target": target}))

            elif eff_type == "weather_intensity":
                amount = effect.get("amount", 1)
                if hasattr(game_state, 'weather'):
                    game_state.weather.storm_intensity = min(100, game_state.weather.storm_intensity + (amount * 10))
                    
            elif eff_type == "temperature_drop":
                amount = effect.get("amount", 5)
                if hasattr(game_state, 'time_system'):
                    game_state.time_system.temperature -= amount

            elif eff_type == "flicker_lights":
                if hasattr(game_state, 'crt'):
                    game_state.crt.flicker(count=3, interval=0.1)

            elif eff_type == "npc_action":
                action = effect.get("action")
                # Flavor logic for NPC actions
                pass
            
            elif eff_type == "trust_change":
                 # Simple trust hit to everyone or specific target
                 amount = effect.get("amount", -5)
                 if hasattr(game_state, 'trust_system'):
                     # We'd need to know WHO caused it to lower trust specifically
                     # For now, maybe lower global trust average or just player trust in random
                     pass

            elif eff_type == "force_move_player":
                # Forcing player to a random adjacent room
                if hasattr(game_state, "player") and hasattr(game_state, "station_map"):
                    current_room = game_state.station_map.get_room_name(*game_state.player.location)
                    connections = game_state.station_map.get_connections(current_room)
                    if connections:
                        target_room = self.rng.choose(connections)
                        
                        # Calculate center of new room
                        room_coords = game_state.station_map.rooms[target_room]
                        cx = (room_coords[0] + room_coords[2]) // 2
                        cy = (room_coords[1] + room_coords[3]) // 2
                        
                        game_state.player.location = (cx, cy)
                        event_bus.emit(GameEvent(EventType.MOVEMENT, {
                            "character": game_state.player.name,
                            "from_room": current_room,
                            "to_room": target_room,
                            "forced": True
                        }))
                        event_bus.emit(GameEvent(EventType.MESSAGE, {
                            "text": f"You scramble into the {target_room} to escape the burst!"
                        }))

            elif eff_type == "spawn_item":
                # Spawn an item in the player's current room or a random room
                category = effect.get("category", "resource")
                count = effect.get("count", 1)
                
                from entities.item import Item
                
                items_to_spawn = []
                if category == "resource":
                    items_to_spawn = [Item("Canned Food", "Emergency rations", category="resource"), Item("Fuel Canister", "Fuel for generator", category="resource")]
                elif category == "weapon":
                    items_to_spawn = [Item("Scalpel", "Medical tool, can be used as weapon", category="weapon")]
                
                if items_to_spawn:
                    item_template = self.rng.choose(items_to_spawn)
                    
                    if hasattr(game_state, "station_map"):
                        target_room_name = None
                        if effect.get("location") == "player_room" and game_state.player:
                            target_room_name = game_state.station_map.get_room_name(*game_state.player.location)
                        else:
                            target_room_name = self.rng.choose(list(game_state.station_map.rooms.keys()))
                            
                        if target_room_name:
                             # Add to room inventory
                             item_coords = game_state.station_map.rooms[target_room_name]
                             item_x = (item_coords[0] + item_coords[2]) // 2
                             item_y = (item_coords[1] + item_coords[3]) // 2
                             game_state.station_map.add_item_to_room(item_template, item_x, item_y, game_state.turn)
                             
                             event_bus.emit(GameEvent(EventType.MESSAGE, {
                                "text": f"You spot a {item_template.name} in the {target_room_name}."
                            }))
            
            elif eff_type == "weather_clear":
                amount = effect.get("amount", 1)
                if hasattr(game_state, 'weather'):
                    game_state.weather.storm_intensity = max(0, game_state.weather.storm_intensity - (amount * 10))
                    event_bus.emit(GameEvent(EventType.MESSAGE, {
                        "text": "The weather seems to be clearing up."
                    }))
