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

        # Player tracking / search memory
        self.last_seen_player_location = None
        self.last_seen_player_room = None
        self.last_seen_player_turn = None
        self.search_targets = []
        self.current_search_target = None
        self.search_turns_remaining = 0

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
        
        # Reset flag
        self.location_hint_active = False
        
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
            # Visual indicator flags for isometric renderer
            "detected_player": getattr(self, 'detected_player', False),
            "target_room": getattr(self, 'target_room', None),
            "in_lynch_mob": getattr(self, 'in_lynch_mob', False),
            "location_hint_active": getattr(self, 'location_hint_active', False)
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
        
        # Items hydration
        m.inventory = []
        for i_data in data.get("inventory", []):
            item = Item.from_dict(i_data)
            if item:
                m.inventory.append(item)
        
        m.stealth_posture = safe_enum(StealthPosture, "stealth_posture", StealthPosture.STANDING)
        
        return m

    def set_posture(self, posture: StealthPosture):
        """Set the character's stealth posture."""
        self.stealth_posture = posture

    def get_noise_level(self) -> int:
        """
        Calculate noise level generated by the character.
        Based on inventory weight, skill, and posture.
        """
        base_noise = 5
        weight = len(self.inventory)
        stealth_skill = self.skills.get(Skill.STEALTH, 0)
        
        posture_mod = 0
        if self.stealth_posture == StealthPosture.CROUCHING:
            posture_mod = -2
        elif self.stealth_posture == StealthPosture.CRAWLING:
            posture_mod = -4
            
        return max(1, base_noise + weight - stealth_skill + posture_mod)

    def get_reaction_dialogue(self, trigger_type: str) -> str:
        """
        Generate reactive dialogue based on behavior type/personality.
        
        trigger_type: "STEALTH_DETECTED", "SUSPICIOUS", etc.
        """
        # Default lines
        lines = ["Who's there?", "What was that?"]
        
        if trigger_type == "STEALTH_DETECTED":
            if self.behavior_type == "Aggressive":
                lines = ["Show yourself!", "I know you're there!", "Come out and fight!"]
            elif self.behavior_type == "Nervous":
                lines = ["Who's there?!", "Stay back!", "I... I hear you!"]
            elif self.behavior_type == "Analytical":
                lines = ["Identify yourself.", "Movement detected.", "Someone is lurking."]
            else:
                lines = ["Is someone there?", "Hello?", "Stop sneaking around."]

        # Simple deterministic choice based on name length for now to act as RNG
        # (Since we don't have easy access to RNG here without passing it in, 
        # and simple consistent variation is fine)
        idx = len(self.name) % len(lines)
        return lines[idx]
