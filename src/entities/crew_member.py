"""CrewMember entity class for The Thing game."""

from core.resolution import Attribute, Skill, ResolutionSystem
from core.event_system import event_bus, EventType, GameEvent
from systems.forensics import BiologicalSlipGenerator
from systems.pathfinding import pathfinder
from entities.item import Item
from enum import Enum, auto


class StealthPosture(Enum):
    STANDING = auto()
    CROUCHING = auto()
    CRAWLING = auto()
    HIDING = auto()
    # Aliases for external callers/tests
    EXPOSED = STANDING  # Alias for clarity in tests/UI
    HIDDEN = HIDING


class CrewMember:
    """Represents an NPC or player character in the game.

    Crew members have attributes, skills, inventory, and hidden infection state.
    They follow schedules, respond to lynch mobs, and can reveal biological tells.
    """

    def __init__(self, name, role, behavior_type, attributes=None, skills=None, schedule=None, invariants=None):
        self.name = name
        self.original_name = name
        self.revealed_name = None
        self.role = role
        self.behavior_type = behavior_type
        self.is_infected = False  # The "Truth" hidden from the player
        self.trust_score = 50      # 0 to 100
        self.location = (0, 0)
        self.is_alive = True

        # Stats
        self.attributes = attributes if attributes else {}
        self.skills = skills if skills else {}
        self.schedule = schedule if schedule else []
        self.invariants = invariants if invariants else []
        self.forbidden_rooms = []  # Hydrated from JSON
        self.stress = 0
        self.inventory = []
        self.health = 3  # Base health
        self.mask_integrity = 100.0  # Agent 3: Mask Tracking
        self.is_revealed = False    # Agent 3: Violent Reveal
        self.slipped_vapor = False  # Hook: Biological Slip flag
        self.knowledge_tags = []    # Agent 3: Searchlight Harvest
        self.stealth_posture = StealthPosture.STANDING
        self.schedule_slip_flag = False  # Flagged when off expected schedule
        self.schedule_slip_reason = None
        self.location_hint_active = False
        self.investigating = False
        self.investigation_goal = None
        self.investigation_priority = 0
        self.investigation_expires = 0
        self.investigation_source = None
        self.in_vent = False        # Whether the character is moving through vents
        # Thermal sense/resistance baseline for heat-based detection
        # Base thermal signature (human body heat)
        self.attributes.setdefault(Attribute.THERMAL, 2)
        # Suspicion tracking toward the player
        self.suspicion_level = 0
        self.suspicion_thresholds = {"question": 4, "follow": 8}
        self.suspicion_decay_delay = 3  # turns before suspicion decays
        self.suspicion_last_raised = None
        self.suspicion_state = "idle"
        # Suspicion tracking toward the player
        self.suspicion_level = 0
        self.suspicion_thresholds = {"question": 4, "follow": 8}
        self.suspicion_decay_delay = 3  # turns before suspicion decays
        self.suspicion_last_raised = None
        self.suspicion_state = "idle"

        # Player tracking / search memory
        self.last_seen_player_location = None
        self.last_seen_player_room = None
        self.last_seen_player_turn = None
        self.search_targets = []
        self.current_search_target = None
        self.search_turns_remaining = 0
        self.search_history = set()  # Tracks checked locations during search
        self.search_anchor = None  # Center point of current search pattern
        self.search_spiral_radius = 1  # Current expansion radius for spiral search
        self.last_location_hint_turn = -1  # Cooldown for ambient warnings

        # Infected coordination (pincer movement)
        self.coordinating_ambush = False
        self.ambush_target_location = None
        self.flank_position = None
        self.coordination_leader = None  # Name of NPC who initiated coordination
        self.coordination_turns_remaining = 0

        # Stealth skill progression
        self.stealth_xp = 0
        self.stealth_level = 0
        self.silent_takedown_unlocked = False  # Unlocked at level 4

    def add_knowledge_tag(self, tag):
        """Add a knowledge tag/memory log if it doesn't already exist."""
        if tag not in self.knowledge_tags:
            self.knowledge_tags.append(tag)

    def take_damage(self, amount, game_state=None):
        """Apply damage to crew member. Returns True if they died."""
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.is_alive = False
            
            # Emit Crew Death Event
            if game_state:
                event_bus.emit(GameEvent(EventType.CREW_DEATH, {
                    "name": self.name,
                    "game_state": game_state
                }))
            
            return True  # Died
        return False

    def add_item(self, item, turn=0):
        """Add an item to inventory and record in item history."""
        self.inventory.append(item)
        item.add_history(turn, f"Picked up by {self.name}")

    def remove_item(self, item_name):
        """Remove and return an item from inventory by name."""
        for i, item in enumerate(self.inventory):
            if item.name.upper() == item_name.upper():
                return self.inventory.pop(i)
        return None

    def roll_check(self, attribute, skill=None, rng=None):
        """Perform an attribute+skill check using the resolution system."""
        attr_val = self.attributes.get(attribute, 1)
        skill_val = self.skills.get(skill, 0)
        pool_size = attr_val + skill_val

        # Use a temporary ResolutionSystem if one isn't provided
        res = ResolutionSystem()
        return res.roll_check(pool_size, rng=rng)

    def move(self, dx, dy, station_map):
        """Attempt to move by delta. Returns True if successful."""
        new_x = self.location[0] + dx
        new_y = self.location[1] + dy
        if station_map.is_walkable(new_x, new_y):
            self.location = (new_x, new_y)
            return True
        return False

    def get_description(self, game_state):
        """Generate a description of the crew member with potential biological tells."""
        rng = game_state.rng
        desc = [f"This is {self.name}, the {self.role}."]

        # 1. Spatial Slip Check
        current_room = game_state.station_map.get_room_name(*self.location)
        if hasattr(self, 'forbidden_rooms') and current_room in self.forbidden_rooms:
            desc.append(f"Something is wrong. {self.name} shouldn't be in the {current_room}. They look out of place, almost defensive.")

        # 2. Invariant Visual Slips (Base Behavioral Patterns)
        for inv in [i for i in self.invariants if i.get('type') == 'visual']:
            if self.is_infected and rng.random_float() < inv.get('slip_chance', 0.5):
                desc.append(inv['slip_desc'])
            else:
                desc.append(inv['baseline'])

        # 3. Agent 3/4 biological slips and sensory tells
        if self.is_infected and not self.is_revealed:
            # Chance to show a sensory tell increases as mask integrity drops
            if self.mask_integrity < 80:
                slip_chance = (80 - self.mask_integrity) / 80.0
                if rng.random_float() < slip_chance:
                    slip = BiologicalSlipGenerator.get_visual_slip(rng)
                    desc.append(f"You notice they are {slip}.")

            # Specific hint for infected NPCs
            if self.mask_integrity < 50 and rng.random_float() < 0.3:
                desc.append("Their eyes seem strange... almost like lusterless black spheres.")

        # 4. State based on stress and environment
        state = "shivering in the cold"
        if self.stress > 3:
            state = "visibly shaking and hyperventilating"
        elif self.is_infected and self.mask_integrity < 40:
            state = "unnaturally still, staring through you"

        desc.append(f"State: {state.capitalize()}.")

        return " ".join(desc)

    def check_location_hints(self, game_state):
        """Check if character is deviating from expected location patterns.
        
        Returns a list of location hint slips that should be displayed.
        """
        hints = []
        current_room = game_state.station_map.get_room_name(*self.location)
        current_hour = game_state.time_system.hour
        rng = game_state.rng
        current_turn = game_state.turn
        
        # Reset flag
        self.location_hint_active = False
        
        # Only check once per turn to avoid spamming the same hint
        if current_turn <= self.last_location_hint_turn:
            return hints
            
        # Check location_hint invariants
        for inv in [i for i in self.invariants if i.get('type') == 'location_hint']:
            expected_room = inv.get('expected_room')
            time_range = inv.get('time_range', [0, 24])
            slip_chance = inv.get('slip_chance', 0.5)
            slip_desc = inv.get('slip_desc', f"{self.name} is not where they should be.")
            
            # Check if we're in the time range
            if time_range[0] <= current_hour < time_range[1]:
                # If infected and NOT in expected room, chance to generate hint
                if self.is_infected and current_room != expected_room:
                    if rng.random_float() < slip_chance:
                        hints.append(slip_desc)
                        self.location_hint_active = True  # Set for visual indicator
                        self.last_location_hint_turn = current_turn
        
        return hints

    def get_dialogue(self, game_state):
        """Generate dialogue for the crew member with potential speech tells."""
        rng = game_state.rng

        # Dialogue Invariants
        dialogue_invariants = [i for i in self.invariants if i.get('type') == 'dialogue']
        if dialogue_invariants:
            inv = rng.choose(dialogue_invariants)
            if self.is_infected and rng.random_float() < inv.get('slip_chance', 0.5):
                base_dialogue = f"Speaking {inv['slip_desc']}."
            else:
                base_dialogue = f"Wait, {inv['baseline']}."  # Simple flavor
        else:
            base_dialogue = f"I'm {self.behavior_type}."

        if game_state.time_system.temperature < 0:
            show_vapor = True
            # BIOLOGICAL SLIP HOOK
            if self.is_infected and self.slipped_vapor:
                show_vapor = False

            if show_vapor:
                base_dialogue += " [VAPOR]"
            else:
                base_dialogue += " [NO VAPOR]"
        return base_dialogue

    def to_dict(self):
        """Serialize crew member to dictionary for save/load."""
        return {
            "name": self.name,
            "role": self.role,
            "behavior_type": self.behavior_type,
            "is_infected": self.is_infected,
            "trust_score": self.trust_score,
            "location": self.location,
            "is_alive": self.is_alive,
            "health": self.health,
            "stress": self.stress,
            "mask_integrity": self.mask_integrity,
            "is_revealed": self.is_revealed,
            "attributes": {k.name: v for k, v in self.attributes.items()},
            "skills": {k.name: v for k, v in self.skills.items()},
            "inventory": [i.to_dict() for i in self.inventory],
            "schedule": self.schedule,
            "invariants": self.invariants,
            "knowledge_tags": self.knowledge_tags,
            "stealth_posture": self.stealth_posture.name,
            "in_vent": self.in_vent,
            "suspicion_level": getattr(self, 'suspicion_level', 0),
            "suspicion_thresholds": getattr(self, 'suspicion_thresholds', {"question": 4, "follow": 8}),
            "suspicion_decay_delay": getattr(self, 'suspicion_decay_delay', 3),
            "suspicion_last_raised": getattr(self, 'suspicion_last_raised', None),
            "suspicion_state": getattr(self, 'suspicion_state', "idle"),
            # Visual indicator flags for isometric renderer
            "detected_player": getattr(self, 'detected_player', False),
            "target_room": getattr(self, 'target_room', None),
            "in_lynch_mob": getattr(self, 'in_lynch_mob', False),
            "location_hint_active": getattr(self, 'location_hint_active', False),
            # Infected coordination state
            "coordinating_ambush": getattr(self, 'coordinating_ambush', False),
            "ambush_target_location": getattr(self, 'ambush_target_location', None),
            "flank_position": getattr(self, 'flank_position', None),
            "coordination_leader": getattr(self, 'coordination_leader', None),
            "coordination_turns_remaining": getattr(self, 'coordination_turns_remaining', 0),
            # Stealth skill progression
            "stealth_xp": getattr(self, 'stealth_xp', 0),
            "stealth_level": getattr(self, 'stealth_level', 0),
            "silent_takedown_unlocked": getattr(self, 'silent_takedown_unlocked', False),
            "schedule_slip_flag": getattr(self, 'schedule_slip_flag', False),
            "schedule_slip_reason": getattr(self, 'schedule_slip_reason', None),
            # Enhanced search memory
            "search_history": list(getattr(self, 'search_history', set())),
            "search_anchor": getattr(self, 'search_anchor', None),
            "search_spiral_radius": getattr(self, 'search_spiral_radius', 1),
            "search_targets": getattr(self, 'search_targets', []),
            "search_turns_remaining": getattr(self, 'search_turns_remaining', 0)
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize crew member from dictionary."""
        if not data:
            return None
        if not isinstance(data, dict):
             raise ValueError("Crew member data must be a dictionary.")

        name = data.get("name")
        role = data.get("role")
        behavior_type = data.get("behavior_type")
        if not all([name, role, behavior_type]):
             raise ValueError("Crew member data missing required fields 'name', 'role', or 'behavior_type'.")

        # Helper for Enum mapping
        def safe_enum(enum_class, key, default):
            val = data.get(key)
            if val is None:
                return default
            try:
                return enum_class[val]
            except (KeyError, ValueError):
                return default

        attrs = {}
        for key, value in data.get("attributes", {}).items():
            try:
                attrs[Attribute[key]] = value
            except KeyError:
                continue

        skills = {}
        for key, value in data.get("skills", {}).items():
            try:
                skills[Skill[key]] = value
            except KeyError:
                continue

        m = cls(
            name=name,
            role=role,
            behavior_type=behavior_type,
            attributes=attrs,
            skills=skills,
            schedule=data.get("schedule", []),
            invariants=data.get("invariants", [])
        )

        m.is_infected = data.get("is_infected", False)
        m.trust_score = data.get("trust_score", 50)
        m.location = tuple(data.get("location", (0, 0)))
        m.is_alive = data.get("is_alive", True)
        m.health = data.get("health", 3)
        m.stress = data.get("stress", 0)
        m.mask_integrity = data.get("mask_integrity", 100.0)
        m.is_revealed = data.get("is_revealed", False)
        m.knowledge_tags = data.get("knowledge_tags", [])
        m.schedule_slip_flag = data.get("schedule_slip_flag", False)
        m.schedule_slip_reason = data.get("schedule_slip_reason")
        m.location_hint_active = data.get("location_hint_active", False)
        m.in_vent = data.get("in_vent", False)
        m.suspicion_level = data.get("suspicion_level", 0)
        m.suspicion_thresholds = data.get("suspicion_thresholds", {"question": 4, "follow": 8})
        m.suspicion_decay_delay = data.get("suspicion_decay_delay", 3)
        m.suspicion_last_raised = data.get("suspicion_last_raised")
        m.suspicion_state = data.get("suspicion_state", "idle")

        # Infected coordination state
        m.coordinating_ambush = data.get("coordinating_ambush", False)
        ambush_loc = data.get("ambush_target_location")
        m.ambush_target_location = tuple(ambush_loc) if ambush_loc else None
        flank_pos = data.get("flank_position")
        m.flank_position = tuple(flank_pos) if flank_pos else None
        m.coordination_leader = data.get("coordination_leader")
        m.coordination_turns_remaining = data.get("coordination_turns_remaining", 0)

        # Stealth skill progression
        m.stealth_xp = data.get("stealth_xp", 0)
        m.stealth_level = data.get("stealth_level", 0)
        m.silent_takedown_unlocked = data.get("silent_takedown_unlocked", False)

        # Enhanced search memory
        m.search_history = set(data.get("search_history", []))
        search_anchor = data.get("search_anchor")
        m.search_anchor = tuple(search_anchor) if search_anchor else None
        m.search_spiral_radius = data.get("search_spiral_radius", 1)
        m.search_targets = [tuple(t) if isinstance(t, list) else t for t in data.get("search_targets", [])]
        m.search_turns_remaining = data.get("search_turns_remaining", 0)

        if m.search_history is None:
            m.search_history = set()

        # Items hydration
        m.inventory = []
        for i_data in data.get("inventory", []):
            item = Item.from_dict(i_data)
            if item:
                m.inventory.append(item)
        
        m.stealth_posture = safe_enum(StealthPosture, "stealth_posture", StealthPosture.STANDING)
        
        return m

    # --- Search utilities -------------------------------------------------

    def clear_search_history(self):
        """Reset stored search locations/rooms so a new sweep can begin fresh."""
        self.search_history = set()

    def record_search_checkpoint(self, location, station_map):
        """Add a visited coordinate (and its room) to search history to avoid repeats."""
        if not hasattr(self, "search_history") or self.search_history is None:
            self.search_history = set()

        self.search_history.add(tuple(location))
        if station_map:
            room_name = station_map.get_room_name(*location)
            self.search_history.add(room_name)

    def set_posture(self, posture: StealthPosture):
        """Set the character's stealth posture."""
        self.stealth_posture = posture

    def get_noise_level(self) -> int:
        """
        Calculate noise level generated by the character.
        Based on inventory weight, skill, posture, and stealth level progression.
        """
        base_noise = 5
        weight = len(self.inventory)
        stealth_skill = self.skills.get(Skill.STEALTH, 0)

        posture_mod = 0
        if self.stealth_posture == StealthPosture.CROUCHING:
            posture_mod = -2
        elif self.stealth_posture == StealthPosture.CRAWLING:
            posture_mod = -4
        elif self.stealth_posture == StealthPosture.HIDING:
            posture_mod = -1

        vent_penalty = 4 if getattr(self, "in_vent", False) else 0

        # Stealth level progression bonus: levels 1 and 3 reduce noise by 1 each
        level_noise_reduction = self.get_stealth_level_noise_bonus()

        return max(1, base_noise + weight - stealth_skill + posture_mod + vent_penalty - level_noise_reduction)

    def get_stealth_level_noise_bonus(self) -> int:
        """Return noise reduction from stealth level progression."""
        level = getattr(self, 'stealth_level', 0)
        # Level 1: -1 noise, Level 3: -1 noise (cumulative)
        bonus = 0
        if level >= 1:
            bonus += 1
        if level >= 3:
            bonus += 1
        return bonus

    def get_stealth_level_pool_bonus(self) -> int:
        """Return stealth pool bonus from stealth level progression."""
        level = getattr(self, 'stealth_level', 0)
        # Level 2: +1 pool, Level 4: +1 pool (cumulative)
        bonus = 0
        if level >= 2:
            bonus += 1
        if level >= 4:
            bonus += 1
        return bonus

    def get_thermal_signature(self) -> int:
        """Return thermal signature for heat-based detection.

        The Thing runs hotter than humans - infected characters have
        a higher thermal signature, making them detectable via thermal sensing.
        """
        base_thermal = self.attributes.get(Attribute.THERMAL, 2)

        # Infected creatures run hotter (+3 thermal signature)
        if getattr(self, 'is_infected', False):
            return base_thermal + 3

        return base_thermal

    def get_thermal_detection_pool(self) -> int:
        """Return thermal detection pool for detecting heat signatures.

        Checks if character has thermal goggles equipped for bonus.
        """
        base_pool = self.attributes.get(Attribute.THERMAL, 2)

        # Check for thermal goggles in inventory
        for item in getattr(self, 'inventory', []):
            if hasattr(item, 'effect') and item.effect == 'thermal_detection':
                base_pool += getattr(item, 'effect_value', 0)

        return base_pool

    def is_out_of_schedule(self, game_state) -> bool:
        """
        Check if this character is not in their expected location based on schedule.

        Returns True if the character is in a location that doesn't match their
        current schedule entry, making them suspicious and easier to interrogate.
        """
        if not hasattr(self, 'schedule') or not self.schedule:
            return False

        current_hour = game_state.time_system.hour
        current_room = game_state.station_map.get_room_name(*self.location)

        # Find the scheduled room for the current hour
        expected_room = None
        for entry in self.schedule:
            start = entry.get("start", 0)
            end = entry.get("end", 24)
            room = entry.get("room")

            # Handle wrap-around schedules (e.g., 20:00 to 08:00)
            if start < end:
                if start <= current_hour < end:
                    expected_room = room
                    break
            else:  # Wrap around midnight
                if current_hour >= start or current_hour < end:
                    expected_room = room
                    break

        if not expected_room:
            return False  # No schedule entry for this time

        # Check if current room matches expected (allow partial matches for flexibility)
        # e.g., "Corridor near Lab" should match if expected is "Lab"
        if expected_room in current_room or current_room in expected_room:
            return False

        # Corridors are neutral - NPCs can be in corridors without being "out of schedule"
        if current_room.startswith("Corridor"):
            return False

        return True

    def get_schedule_info(self, game_state) -> dict:
        """
        Get information about the character's schedule status.

        Returns a dict with:
        - expected_room: Where they should be
        - current_room: Where they are
        - out_of_schedule: Boolean
        """
        current_room = game_state.station_map.get_room_name(*self.location)
        current_hour = game_state.time_system.hour

        expected_room = None
        for entry in self.schedule:
            start = entry.get("start", 0)
            end = entry.get("end", 24)
            room = entry.get("room")

            if start < end:
                if start <= current_hour < end:
                    expected_room = room
                    break
            else:
                if current_hour >= start or current_hour < end:
                    expected_room = room
                    break

        return {
            "expected_room": expected_room,
            "current_room": current_room,
            "current_hour": current_hour,
            "out_of_schedule": self.is_out_of_schedule(game_state)
        }

    def get_reaction_dialogue(self, trigger_type: str) -> str:
        """
        Legacy helper retained for compatibility.

        Delegates to DialogueSystem via game systems; kept as a fallback string.
        """
        from systems.dialogue import DialogueSystem

        system = DialogueSystem()
        result = system._behavioral_reaction(self, trigger_type)
        return result
        # Simple deterministic choice based on name length for now to act as RNG
        # (Since we don't have easy access to RNG here without passing it in, 
        # and simple consistent variation is fine)
        idx = len(self.name) % len(lines)
        return lines[idx]

    # === Suspicion helpers ===
    def increase_suspicion(self, amount: int, turn: int = None):
        """Increase suspicion toward the player and track last raise turn."""
        self.suspicion_level = min(100, max(0, getattr(self, "suspicion_level", 0) + amount))
        self.suspicion_last_raised = turn

    def decay_suspicion(self, current_turn: int):
        """
        Reduce suspicion if enough turns have passed since the last raise.
        Returns True if decay occurred.
        """
        decay_delay = getattr(self, "suspicion_decay_delay", 3)
        if self.suspicion_level <= 0:
            self.suspicion_state = "idle"
            return False

        last_raise = getattr(self, "suspicion_last_raised", None)
        if last_raise is None:
            # No record? Decay slowly to avoid being stuck.
            last_raise = current_turn - decay_delay

        if current_turn - last_raise >= decay_delay:
            self.suspicion_level = max(0, self.suspicion_level - 1)
            if self.suspicion_level == 0:
                self.suspicion_state = "idle"
            return True
        return False

    def clear_suspicion(self):
        """Immediately clear suspicion state."""
        self.suspicion_level = 0
        self.suspicion_state = "idle"
        self.suspicion_last_raised = None
