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

    def __init__(self, rng):
        self.rng = rng
        self.events = self._define_events()
        self.event_history = []  # List of (turn, event_id)
        self.cooldowns = {}  # event_id -> turns until available

    def _define_events(self) -> List[RandomEvent]:
        """Define all possible random events."""
        return [
            # === WEATHER EVENTS ===
            RandomEvent(
                id="sudden_blizzard",
                name="Sudden Blizzard",
                description="A fierce blizzard strikes without warning! "
                           "Visibility drops to zero. All outdoor movement halted.",
                category=EventCategory.WEATHER,
                severity=EventSeverity.MODERATE,
                weight=8,
                cooldown=10,
                effect=self._effect_blizzard
            ),
            RandomEvent(
                id="temperature_plunge",
                name="Temperature Plunge",
                description="The temperature drops sharply. "
                           "Frost begins forming on the walls.",
                category=EventCategory.WEATHER,
                severity=EventSeverity.MINOR,
                weight=15,
                effect=self._effect_temp_drop
            ),
            RandomEvent(
                id="calm_weather",
                name="Brief Calm",
                description="The storm briefly subsides. "
                           "An eerie silence falls over the station.",
                category=EventCategory.WEATHER,
                severity=EventSeverity.MINOR,
                weight=10,
            ),

            # === EQUIPMENT EVENTS ===
            RandomEvent(
                id="lights_flicker",
                name="Lights Flicker",
                description="The lights flicker ominously for a moment. "
                           "Power fluctuation detected.",
                category=EventCategory.EQUIPMENT,
                severity=EventSeverity.MINOR,
                weight=20,
                requires_power=True,
            ),
            RandomEvent(
                id="generator_sputter",
                name="Generator Sputter",
                description="The generator sputters and coughs! "
                           "It stabilizes, but power output is reduced.",
                category=EventCategory.EQUIPMENT,
                severity=EventSeverity.MODERATE,
                weight=5,
                requires_power=True,
                cooldown=15,
                effect=self._effect_generator_trouble
            ),
            RandomEvent(
                id="radio_static",
                name="Radio Static",
                description="The radio crackles with unusual static. "
                           "For a moment, you think you hear voices...",
                category=EventCategory.EQUIPMENT,
                severity=EventSeverity.MINOR,
                weight=12,
            ),

            # === DISCOVERY EVENTS ===
            RandomEvent(
                id="hidden_supplies",
                name="Hidden Supplies",
                description="You notice a panel slightly ajar. "
                           "Behind it: emergency supplies!",
                category=EventCategory.DISCOVERY,
                severity=EventSeverity.MODERATE,
                weight=5,
                min_turn=5,
                effect=self._effect_find_supplies
            ),
            RandomEvent(
                id="old_journal",
                name="Old Journal Entry",
                description="A crumpled journal page falls from a shelf. "
                           "Previous crew notes about 'strange behavior'...",
                category=EventCategory.DISCOVERY,
                severity=EventSeverity.MINOR,
                weight=8,
                min_turn=3,
            ),

            # === ATMOSPHERE EVENTS ===
            RandomEvent(
                id="distant_scream",
                name="Distant Scream",
                description="A blood-curdling scream echoes through the station! "
                           "It came from... somewhere.",
                category=EventCategory.ATMOSPHERE,
                severity=EventSeverity.MODERATE,
                weight=6,
                min_turn=10,
                requires_infected=True,
                effect=self._effect_paranoia_spike
            ),
            RandomEvent(
                id="shadow_movement",
                name="Shadow Movement",
                description="You catch movement in your peripheral vision. "
                           "When you look, nothing is there.",
                category=EventCategory.ATMOSPHERE,
                severity=EventSeverity.MINOR,
                weight=15,
                min_turn=5,
                effect=self._effect_minor_paranoia
            ),
            RandomEvent(
                id="dogs_howl",
                name="Dogs Howling",
                description="The remaining dogs begin howling in unison. "
                           "Something has them spooked.",
                category=EventCategory.ATMOSPHERE,
                severity=EventSeverity.MINOR,
                weight=10,
                requires_infected=True,
            ),
            RandomEvent(
                id="power_outage_scare",
                name="Momentary Blackout",
                description="The lights go out completely for three seconds. "
                           "When they return, everyone looks around nervously.",
                category=EventCategory.ATMOSPHERE,
                severity=EventSeverity.MODERATE,
                weight=8,
                requires_power=True,
                effect=self._effect_blackout_scare
            ),

            # === CREATURE EVENTS (Thing-related) ===
            RandomEvent(
                id="strange_sounds",
                name="Inhuman Sounds",
                description="An unnatural gurgling sound comes from the walls. "
                           "It stops as suddenly as it started.",
                category=EventCategory.CREATURE,
                severity=EventSeverity.MODERATE,
                weight=4,
                min_turn=15,
                requires_infected=True,
                effect=self._effect_paranoia_spike
            ),
            RandomEvent(
                id="blood_trail",
                name="Blood Trail Discovered",
                description="Fresh blood droplets lead down the corridor... "
                           "They disappear around the corner.",
                category=EventCategory.CREATURE,
                severity=EventSeverity.MAJOR,
                weight=3,
                min_turn=10,
                requires_infected=True,
                effect=self._effect_blood_trail
            ),
        ]

    def check_for_event(self, game_state) -> Optional[RandomEvent]:
        """Check if a random event should trigger this turn.

        Args:
            game_state: Current game state

        Returns:
            A RandomEvent if one triggers, None otherwise
        """
        # Update cooldowns
        for event_id in list(self.cooldowns.keys()):
            self.cooldowns[event_id] -= 1
            if self.cooldowns[event_id] <= 0:
                del self.cooldowns[event_id]

        # Base chance of event (increases with paranoia)
        base_chance = 0.15 + (game_state.paranoia_level / 200)

        if self.rng.random() > base_chance:
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
        roll = self.rng.random() * total_weight

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
        """Execute a random event's effect.

        Args:
            event: The event to execute
            game_state: Current game state
        """
        # Emit message event
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            'text': f"\n[EVENT: {event.name}]",
            'crawl': False
        }))
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            'text': event.description,
            'crawl': True
        }))

        # Execute effect if present
        if event.effect:
            event.effect(game_state)

    # === EVENT EFFECTS ===

    def _effect_blizzard(self, game):
        """Blizzard effect: temperature drop, visibility issues."""
        game.weather.trigger_northeasterly()
        # Temperature is a property in GameState that reads from weather,
        # but we might want to affect the base temp in time_system?
        # GameState.temperature is a property: return self.weather.get_effective_temperature(self.time_system.temperature)
        # So we can't subtract from it directly.
        # We should modify time_system or let weather handle it.
        # The weather system handles temp modification via intensity.
        # But if we want an EXTRA drop:
        game.time_system.temperature -= 10

    def _effect_temp_drop(self, game):
        """Temperature drop effect."""
        game.time_system.temperature -= 5

    def _effect_generator_trouble(self, game):
        """Generator trouble: possible power issues next few turns."""
        # Increase chance of power failure
        if hasattr(game, 'sabotage'):
            game.sabotage.generator_stress += 20

    def _effect_find_supplies(self, game):
        """Find hidden supplies."""
        from entities.item import Item
        # Add a useful item to player's current room
        items = [
            Item("First Aid Kit", "Emergency medical supplies", healing=2),
            Item("Flare", "Emergency signal flare", weapon_skill=None, damage=1),
            Item("Batteries", "Fresh batteries for flashlight"),
        ]
        chosen = self.rng.choose(items)
        game.station_map.add_item_to_room(chosen, *game.player.location, game.turn)
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            'text': f"Found: {chosen.name}!"
        }))

    def _effect_paranoia_spike(self, game):
        """Major paranoia increase."""
        game.paranoia_level = min(100, game.paranoia_level + 15)

    def _effect_minor_paranoia(self, game):
        """Minor paranoia increase."""
        game.paranoia_level = min(100, game.paranoia_level + 5)

    def _effect_blackout_scare(self, game):
        """Momentary blackout: paranoia and glitch effect."""
        game.paranoia_level = min(100, game.paranoia_level + 10)
        game.crt.flicker(count=2, interval=0.15)

    def _effect_blood_trail(self, game):
        """Blood trail discovered: mark a random adjacent room as bloody."""
        player_room = game.station_map.get_room_name(*game.player.location)
        # Find adjacent rooms and mark one as bloody
        adjacent = game.station_map.get_adjacent_rooms(*game.player.location)
        if adjacent:
            target_room = self.rng.choose(adjacent)
            game.room_states.mark_bloody(target_room)
            game.paranoia_level = min(100, game.paranoia_level + 8)
