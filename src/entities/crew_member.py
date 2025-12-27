"""CrewMember entity class for The Thing game."""

import random

from core.resolution import Attribute, Skill, ResolutionSystem
from systems.forensics import BiologicalSlipGenerator
from systems.pathfinding import pathfinder
from entities.item import Item


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

    def add_knowledge_tag(self, tag):
        """Add a knowledge tag/memory log if it doesn't already exist."""
        if tag not in self.knowledge_tags:
            self.knowledge_tags.append(tag)

    def take_damage(self, amount):
        """Apply damage to crew member. Returns True if they died."""
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.is_alive = False
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

    def update_ai(self, game_state):
        """
        Agent 2/8: NPC AI Logic.
        Priority: Thing AI > Lynch Mob > Schedule > Wander
        """
        if not self.is_alive:
            return

        current_turn = game_state.turn

        # THING AI: Revealed Things actively hunt humans
        if self.is_revealed:
            self._update_thing_ai(game_state, current_turn)
            return

        # 0. PRIORITY: Lynch Mob Hunting (Agent 2)
        if game_state.lynch_mob.active_mob and game_state.lynch_mob.target:
            target = game_state.lynch_mob.target
            if target != self and target.is_alive:
                # Move toward the lynch target
                tx, ty = target.location
                self._pathfind_step(tx, ty, game_state.station_map, current_turn, game_state)
                return

        # 1. Check Schedule
        # Schedule entries: {"start": 8, "end": 20, "room": "Rec Room"}
        current_hour = game_state.time_system.hour
        destination = None
        for entry in self.schedule:
            start = entry.get("start", 0)
            end = entry.get("end", 24)
            room = entry.get("room")

            # Handle wrap-around schedules (e.g., 20:00 to 08:00)
            if start < end:
                if start <= current_hour < end:
                    destination = room
                    break
            else:  # Wrap around midnight
                if current_hour >= start or current_hour < end:
                    destination = room
                    break

        if destination:
            # Move towards destination room
            target_pos = game_state.station_map.rooms.get(destination)
            if target_pos:
                tx, ty, _, _ = target_pos
                self._pathfind_step(tx, ty, game_state.station_map, current_turn, game_state)
                return

        # 2. Idling / Wandering
        if game_state.rng.random_float() < 0.3:
            dx = game_state.rng.choose([-1, 0, 1])
            dy = game_state.rng.choose([-1, 0, 1])
            self.move(dx, dy, game_state.station_map)

    def _update_thing_ai(self, game_state, current_turn):
        """AI behavior for revealed Things - actively hunt and attack humans."""
        rng = game_state.rng

        # Find nearest living human
        humans = [m for m in game_state.crew
                  if m.is_alive and not m.is_infected and m != self]

        if not humans:
            # No humans left, wander aimlessly
            dx = rng.choose([-1, 0, 1])
            dy = rng.choose([-1, 0, 1])
            self.move(dx, dy, game_state.station_map)
            return

        # Find closest human
        closest = min(humans, key=lambda h: abs(h.location[0] - self.location[0]) +
                                            abs(h.location[1] - self.location[1]))

        # Check if in same location - ATTACK!
        if closest.location == self.location:
            self._thing_attack(closest, game_state)
            return

        # Move toward closest human
        tx, ty = closest.location
        self._pathfind_step(tx, ty, game_state.station_map, current_turn, game_state)

    def _thing_attack(self, target, game_state):
        """The Thing attacks a human target."""
        rng = game_state.rng

        # Thing gets bonus attack dice (representing its alien nature)
        thing_attack_bonus = 3
        attack_pool = self.attributes.get(Attribute.PROWESS, 2) + thing_attack_bonus
        attack_result = rng.calculate_success(attack_pool)

        # Target defends
        defense_pool = target.attributes.get(Attribute.PROWESS, 1) + target.skills.get(Skill.MELEE, 0)
        defense_result = rng.calculate_success(defense_pool)

        thing_name = f"The-Thing-That-Was-{self.name}"

        if attack_result['success_count'] > defense_result['success_count']:
            # Hit! Deal damage
            net_hits = attack_result['success_count'] - defense_result['success_count']
            damage = 2 + net_hits  # Base Thing damage + net hits
            died = target.take_damage(damage)

            print(f"\n[COMBAT] {thing_name} ATTACKS {target.name}!")
            print(f"[COMBAT] Attack: {attack_result['success_count']} vs Defense: {defense_result['success_count']}")
            print(f"[COMBAT] HIT! {target.name} takes {damage} damage!")

            if died:
                print(f"[COMBAT] *** {target.name} HAS BEEN KILLED BY THE THING! ***")

            # Chance to infect on hit (grapple attack)
            if not died and rng.random_float() < 0.3:
                target.is_infected = True
                print(f"[COMBAT] {target.name} has been INFECTED during the attack!")
        else:
            print(f"\n[COMBAT] {thing_name} lunges at {target.name} but MISSES!")

    def _pathfind_step(self, target_x, target_y, station_map, current_turn=0, game_state=None):
        """Take one step toward target using A* pathfinding.

        Falls back to greedy movement if pathfinding fails.
        Handles barricades - Things can break through, NPCs respect them.
        """
        goal = (target_x, target_y)

        # Try A* pathfinding first
        dx, dy = pathfinder.get_move_delta(self.location, goal, station_map, current_turn)

        # If pathfinding returns no movement, fall back to greedy
        if dx == 0 and dy == 0 and self.location != goal:
            dx = 1 if target_x > self.location[0] else -1 if target_x < self.location[0] else 0
            dy = 1 if target_y > self.location[1] else -1 if target_y < self.location[1] else 0

        # Check for barricades at destination
        new_x = self.location[0] + dx
        new_y = self.location[1] + dy

        if game_state and station_map.is_walkable(new_x, new_y):
            target_room = station_map.get_room_name(new_x, new_y)
            current_room = station_map.get_room_name(*self.location)

            if game_state.room_states.is_entry_blocked(target_room) and target_room != current_room:
                if self.is_revealed:
                    # Revealed Things try to break barricades
                    success, msg, _ = game_state.room_states.attempt_break_barricade(
                        target_room, self, game_state.rng, is_thing=True
                    )
                    if not success:
                        print(f"[BARRICADE] Something pounds on the {target_room} barricade!")
                        return  # Can't move this turn
                    else:
                        print(f"[BARRICADE] {msg}")
                        # Fall through to move
                else:
                    # Regular NPCs respect barricades
                    return

        self.move(dx, dy, station_map)

    def get_dialogue(self, game_state):
        """Generate dialogue for the crew member with potential speech tells."""
        rng = game_state.rng

        # Dialogue Invariants
        dialogue_invariants = [i for i in self.invariants if i.get('type') == 'dialogue']
        if dialogue_invariants:
            inv = rng.choose(dialogue_invariants) if hasattr(rng, 'choose') else random.choice(dialogue_invariants)
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
            "knowledge_tags": self.knowledge_tags
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize crew member from dictionary."""
        attrs = {Attribute[k]: v for k, v in data.get("attributes", {}).items()}
        skills = {Skill[k]: v for k, v in data.get("skills", {}).items()}

        m = cls(
            name=data["name"],
            role=data["role"],
            behavior_type=data["behavior_type"],
            attributes=attrs,
            skills=skills
        )
        m.is_infected = data["is_infected"]
        m.trust_score = data["trust_score"]
        m.location = tuple(data["location"])
        m.is_alive = data["is_alive"]
        m.health = data["health"]
        m.stress = data["stress"]
        m.mask_integrity = data.get("mask_integrity", 100.0)
        m.is_revealed = data.get("is_revealed", False)
        m.schedule = data.get("schedule", [])
        m.invariants = data.get("invariants", [])
        m.inventory = [Item.from_dict(i) for i in data.get("inventory", [])]
        m.knowledge_tags = data.get("knowledge_tags", [])
        return m
