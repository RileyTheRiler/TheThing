from src.systems.missionary import MissionarySystem
from src.systems.psychology import PsychologySystem
from src.core.resolution import Attribute, Skill, ResolutionSystem
from src.systems.social import TrustMatrix, LynchMobSystem, DialogueManager
from src.systems.architect import RandomnessEngine, GameMode, TimeSystem
from src.systems.persistence import SaveManager
from src.core.event_system import event_bus, EventType, GameEvent

# Agent 6: Dungeon Master Systems
from src.systems.weather import WeatherSystem
from src.systems.sabotage import SabotageManager
from src.systems.room_state import RoomStateManager, RoomState

# Agent 4: Forensics
from src.systems.forensics import BiologicalSlipGenerator, BloodTestSim, ForensicDatabase, EvidenceLog

# Terminal Designer Systems (Agent 5)
from src.ui.renderer import TerminalRenderer
from src.ui.crt_effects import CRTOutput
from src.ui.command_parser import CommandParser
from src.audio.audio_manager import AudioManager, Sound

import json
import os
import sys
import random
import time

class Item:
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
        self.history.append(f"[Turn {turn}] {location}")

    def is_consumable(self):
        return self.uses > 0

    def consume(self):
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
        skill = None
        if data.get("weapon_skill"):
             try:
                 skill = Skill[data["weapon_skill"]]
             except KeyError:
                 skill = None
                 
        item = cls(
            name=data["name"],
            description=data["description"],
            is_evidence=data["is_evidence"],
            weapon_skill=skill,
            damage=data["damage"],
            uses=data.get("uses", -1),
            effect=data.get("effect"),
            effect_value=data.get("effect_value", 0),
            category=data.get("category", "misc")
        )
        item.history = data.get("history", [])
        return item

class CrewMember:
    def __init__(self, name, role, behavior_type, attributes=None, skills=None, schedule=None, invariants=None):
        self.name = name
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
        self.forbidden_rooms = [] # Hydrated from JSON
        self.stress = 0
        self.inventory = []
        self.health = 3 # Base health
        self.mask_integrity = 100.0 # Agent 3: Mask Tracking
        self.is_revealed = False    # Agent 3: Violent Reveal
        self.slipped_vapor = False  # Hook: Biological Slip flag

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.is_alive = False
            return True # Died
        return False

    def add_item(self, item, turn=0):
        self.inventory.append(item)
        item.add_history(turn, f"Picked up by {self.name}")
    
    def remove_item(self, item_name):
        for i, item in enumerate(self.inventory):
            if item.name.upper() == item_name.upper():
                return self.inventory.pop(i)
        return None

    def roll_check(self, attribute, skill=None, rng=None):
        attr_val = self.attributes.get(attribute, 1) 
        skill_val = self.skills.get(skill, 0)
        pool_size = attr_val + skill_val
        
        # Use a temporary ResolutionSystem if one isn't provided (usually from GameState)
        res = ResolutionSystem()
        return res.roll_check(pool_size)

    def move(self, dx, dy, station_map):
        new_x = self.location[0] + dx
        new_y = self.location[1] + dy
        if station_map.is_walkable(new_x, new_y):
            self.location = (new_x, new_y)
            return True
        return False

    def get_description(self, game_state):
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
        Priority: Lynch Mob > Schedule > Wander
        """
        if not self.is_alive or self.is_revealed:
            return

        # 0. PRIORITY: Lynch Mob Hunting (Agent 2)
        if game_state.lynch_mob.active_mob and game_state.lynch_mob.target:
            target = game_state.lynch_mob.target
            if target != self and target.is_alive:
                # Move toward the lynch target
                tx, ty = target.location
                self._pathfind_step(tx, ty, game_state.station_map)
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
            else: # Wrap around midnight
                if current_hour >= start or current_hour < end:
                    destination = room
                    break
        
        if destination:
            # Move towards destination room
            target_pos = game_state.station_map.rooms.get(destination)
            if target_pos:
                tx, ty, _, _ = target_pos
                self._pathfind_step(tx, ty, game_state.station_map)
                return

        # 2. Idling / Wandering
        if game_state.rng.random_float() < 0.3:
            dx = game_state.rng.choose([-1, 0, 1])
            dy = game_state.rng.choose([-1, 0, 1])
            self.move(dx, dy, game_state.station_map)

    def _pathfind_step(self, target_x, target_y, station_map):
        """Simple greedy step towards target."""
        dx = 1 if target_x > self.location[0] else -1 if target_x < self.location[0] else 0
        dy = 1 if target_y > self.location[1] else -1 if target_y < self.location[1] else 0
        self.move(dx, dy, station_map)

    def get_dialogue(self, game_state):
        rng = game_state.rng
        
        # Dialogue Invariants
        dialogue_invariants = [i for i in self.invariants if i.get('type') == 'dialogue']
        if dialogue_invariants:
            inv = rng.choose(dialogue_invariants) if hasattr(rng, 'choose') else random.choice(dialogue_invariants)
            if self.is_infected and rng.random_float() < inv.get('slip_chance', 0.5):
                base_dialogue = f"Speaking {inv['slip_desc']}."
            else:
                base_dialogue = f"Wait, {inv['baseline']}." # Simple flavor
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
            "invariants": self.invariants
        }
    
    @classmethod
    def from_dict(cls, data):
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
        return m

class StationMap:
    def __init__(self, width=20, height=20):
        self.width = width
        self.height = height
        self.grid = [['.' for _ in range(width)] for _ in range(height)]
        self.rooms = {
            "Rec Room": (5, 5, 10, 10),
            "Infirmary": (0, 0, 4, 4),
            "Generator": (15, 15, 19, 19),
            "Kennel": (0, 15, 4, 19)
        }
        self.room_items = {} 

    def add_item_to_room(self, item, x, y, turn=0):
        room_name = self.get_room_name(x, y)
        if room_name not in self.room_items:
            self.room_items[room_name] = []
        self.room_items[room_name].append(item)
        item.add_history(turn, f"Dropped in {room_name}")

    def get_items_in_room(self, x, y):
        room_name = self.get_room_name(x, y)
        return self.room_items.get(room_name, [])

    def remove_item_from_room(self, item_name, x, y):
        room_name = self.get_room_name(x, y)
        if room_name in self.room_items:
            for i, item in enumerate(self.room_items[room_name]):
                if item.name.upper() == item_name.upper():
                    return self.room_items[room_name].pop(i)
        return None

    def is_walkable(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def get_room_name(self, x, y):
        for name, (x1, y1, x2, y2) in self.rooms.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return name
        return "Corridor (Sector {},{})".format(x, y)

    def render(self, crew):
        display_grid = [row[:] for row in self.grid]
        for member in crew:
            if member.is_alive:
                x, y = member.location
                if 0 <= x < self.width and 0 <= y < self.height:
                    display_grid[y][x] = member.name[0] 
        output = []
        for row in display_grid:
            output.append(" ".join(row))
        return "\n".join(output)
    
    def to_dict(self):
        # Serialize room_items
        # room_items is Dict[RoomName, List[Item]]
        items_dict = {}
        for room, items in self.room_items.items():
            items_dict[room] = [i.to_dict() for i in items]
            
        return {
            "width": self.width,
            "height": self.height,
            "room_items": items_dict
            # rooms and grid are static/derived for now, so we don't save grid unless it changes
        }

    @classmethod
    def from_dict(cls, data):
        sm = cls(data["width"], data["height"])
        items_dict = data.get("room_items", {})
        for room, items_data in items_dict.items():
            sm.room_items[room] = [Item.from_dict(i) for i in items_data]
        return sm

class GameState:
    def __init__(self, seed=None):
        self.rng = RandomnessEngine(seed)
        self.time_system = TimeSystem()
        self.save_manager = SaveManager(game_state_factory=GameState.from_dict)
        
        self.turn = 1
        self.power_on = True
        self.blood_bank_destroyed = False
        self.paranoia_level = 0
        self.mode = GameMode.INVESTIGATIVE

        self.station_map = StationMap()
        self.crew = self._initialize_crew()
        self.journal = []

        self.player = next((m for m in self.crew if m.name == "MacReady"), None)
        self._initialize_items()
        
        self.trust_system = TrustMatrix(self.crew)
        
        # Agent 2: Social Psychologist
        self.lynch_mob = LynchMobSystem(self.trust_system)
        self.dialogue_manager = DialogueManager()
        
        # Agent 3: Missionary System
        self.missionary_system = MissionarySystem()
        
        # Agent 7: Psychology System
        self.psychology_system = PsychologySystem()
        
        # Agent 4: Forensics
        self.forensic_db = ForensicDatabase()
        self.evidence_log = EvidenceLog()
        self.blood_test_sim = BloodTestSim()
        
        # Terminal Designer Systems (Agent 5)
        self.renderer = TerminalRenderer(self.station_map)
        self.crt = CRTOutput(palette="amber", crawl_speed=0.015)
        self.parser = CommandParser(known_names=[m.name for m in self.crew])
        self.audio = AudioManager(enabled=True)
        
        # Agent 6: DM Systems (Now Event-Driven)
        self.weather = WeatherSystem()
        self.sabotage = SabotageManager()
        self.room_states = RoomStateManager(list(self.station_map.rooms.keys()))

        # Integration helper
        self.resolution = ResolutionSystem()
        
        # Hook Listeners
        event_bus.subscribe(EventType.BIOLOGICAL_SLIP, self.on_biological_slip)
        event_bus.subscribe(EventType.LYNCH_MOB_TRIGGER, self.on_lynch_mob_trigger)

    def cleanup(self):
        """Cleanup resources before destruction."""
        if hasattr(self, 'audio'):
            self.audio.shutdown()

    def on_biological_slip(self, event: GameEvent):
        char_name = event.payload.get("character_name")
        slip_type = event.payload.get("type")
        if slip_type == "VAPOR":
            member = next((m for m in self.crew if m.name == char_name), None)
            if member:
                member.slipped_vapor = True

    def on_lynch_mob_trigger(self, event: GameEvent):
        target_name = event.payload.get("target")
        location = event.payload.get("location")
        print(f"\n[EVENT] LYNCH MOB TRIGGERED for {target_name} at {location}!")
        # Move all NPCs to location
        target_member = next((m for m in self.crew if m.name == target_name), None)
        if target_member:
            for m in self.crew:
                if m != target_member and m.is_alive and not m.is_revealed:
                    m.location = target_member.location
                    print(f"[SOCIAL] {m.name} moves to confront {target_name}.")

    @property
    def temperature(self):
        # Effective temperature includes wind chill
        return self.weather.get_effective_temperature(self.time_system.temperature)

    def _initialize_items(self):
        # Only called if new game
        items = [
            ("Whiskey", "J&B Scotch Bottle.", "Rec Room", None, 0),
            ("Flamethrower", "Standard issue M2A1.", "Rec Room", Skill.FIREARMS, 3),
            ("Scalpel", "Surgical steel.", "Infirmary", Skill.MELEE, 1),
            ("Wire", "Copper wire roll.", "Generator", None, 0)
        ]
        for name, desc, room, skill, dmg in items:
            target_room = self.station_map.rooms.get(room)
            if target_room:
                 x1, y1, x2, y2 = target_room
                 self.station_map.add_item_to_room(Item(name, desc, weapon_skill=skill, damage=dmg), x1, y1)

    def _initialize_crew(self):
        # Normally loads from file, here simplified
        # Retained logic from before...
        # For hydration, we handle in from_dict
        # If new game, we load defaults
        if hasattr(self, 'crew') and self.crew: 
             return self.crew

        config_path = os.path.join("config", "characters.json")
        crew = []
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            for char_data in data:
                # Use Attribute and Skill names directly from JSON as per standards
                attrs = {}
                for k, v in char_data.get("attributes", {}).items():
                    try:
                        attrs[Attribute(k)] = v
                    except ValueError:
                        # Fallback for legacy keys if necessary, but preferred to be standard
                        pass

                skills = {}
                for k, v in char_data.get("skills", {}).items():
                    try:
                        skills[Skill(k)] = v
                    except ValueError:
                        pass
                
                m = CrewMember(
                    name=char_data["name"],
                    role=char_data["role"],
                    behavior_type=char_data["behavior"],
                    attributes=attrs,
                    skills=skills,
                    schedule=char_data.get("schedule", []),
                    invariants=char_data.get("invariants", [])
                )
                m.forbidden_rooms = char_data.get("forbidden_rooms", [])
                m.location = (self.rng.roll_d6() + 4, self.rng.roll_d6() + 4)
                crew.append(m)
        except Exception as e:
            m = CrewMember("MacReady", "Pilot", "Cynical")
            m.location = (5, 5)
            crew.append(m)
        return crew

    def advance_turn(self):
        self.turn += 1
        
        # Reset per-turn flags
        for member in self.crew:
            member.slipped_vapor = False
        
        self.paranoia_level = min(100, self.paranoia_level + 1)
        
        # 1. Emit TURN_ADVANCE Event (Triggers TimeSystem, WeatherSystem, InfectionSystem, etc.)
        event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {
            "game_state": self,
            "rng": self.rng
        }))
        
        # 3. Process Local Environment Effects
        player_room = self.station_map.get_room_name(*self.player.location)
        paranoia_mod = self.room_states.get_paranoia_modifier(player_room)
        if paranoia_mod > 0:
            self.paranoia_level = min(100, self.paranoia_level + paranoia_mod)
        
        # 4. Lynch Mob Check (Agent 2)
        lynch_target = self.lynch_mob.check_thresholds(self.crew)
        if lynch_target:
            # Mob is active, NPCs will converge via event handler
            pass
        
        # 5. NPC AI Update
        for member in self.crew:
            if member != self.player:
                member.update_ai(self)

    def to_dict(self):
        return {
            "turn": self.turn,
            "power_on": self.power_on,
            "paranoia_level": self.paranoia_level,
            "mode": self.mode.value,
            "temperature": self.time_system.temperature,
            "rng": self.rng.to_dict(),
            "time_system": self.time_system.to_dict(),
            "station_map": self.station_map.to_dict(),
            "crew": [m.to_dict() for m in self.crew],
            "journal": self.journal,
            "trust": self.trust_system.matrix # Assuming dict
        }

    @classmethod
    def from_dict(cls, data):
        game = cls() # Init with defaults
        # Overwrite content
        game.turn = data["turn"]
        game.power_on = data["power_on"]
        game.paranoia_level = data["paranoia_level"]
        game.mode = GameMode(data["mode"])

        game.rng.from_dict(data["rng"])
        game.time_system = TimeSystem.from_dict(data["time_system"])

        game.station_map = StationMap.from_dict(data["station_map"])

        game.crew = [CrewMember.from_dict(m) for m in data["crew"]]
        # Re-link player
        game.player = next((m for m in game.crew if m.name == "MacReady"), None)

        game.journal = data["journal"]
        game.trust_system.matrix = data.get("trust", {})
        
        return game

# --- Game Loop ---
def main():
    """Main game loop - can be called from launcher or run directly"""
    game = GameState(seed=None)
    
    # Agent 5 Boot Sequence
    game.crt.boot_sequence()
    game.audio.ambient_loop(Sound.THRUM)

    while True:
        # Update CRT glitch based on paranoia
        game.crt.set_glitch_level(game.paranoia_level)
        
        player_room = game.station_map.get_room_name(*game.player.location)
        weather_status = game.weather.get_status()
        room_icons = game.room_states.get_status_icons(player_room)
        
        game.crt.output(f"\n[TURN {game.turn}] MODE: {game.mode.value} | TIME: {game.time_system.hour:02}:00 | TEMP: {game.temperature:.1f}C | POWER: {'ON' if game.power_on else 'OFF'}")
        game.crt.output(f"[LOC: {player_room}] {room_icons}")
        game.crt.output(f"[{weather_status}]")
        
        # Sabotage status
        if not game.sabotage.radio_operational or not game.sabotage.chopper_operational:
            game.crt.warning(game.sabotage.get_status())
            
        # Room modifiers
        room_desc = game.room_states.get_room_description_modifiers(player_room)
        if room_desc:
            game.crt.output(f">>> {room_desc}", crawl=True)

        room_items = game.station_map.get_items_in_room(*game.player.location)
        if room_items:
            item_list = ", ".join([str(i) for i in room_items])
            game.crt.output(f"[VISIBLE ITEMS]: {item_list}")
            
        # Agent 5 Map Rendering
        game.crt.output(game.renderer.render(game, game.player))
        
        try:
            prompt = game.crt.prompt("CMD")
            user_input = input(prompt).strip()
            if not user_input:
                continue
            
            # Use CommandParser
            parsed = game.parser.parse(user_input)
            if not parsed:
                # Fallback to legacy
                cmd = user_input.upper().split()
            else:
                action = parsed['action']
                target = parsed.get('target')
                cmd = [action]
                if target: cmd.append(target)
                if parsed.get('args'):
                    cmd.extend(parsed['args'])
                
            game.audio.trigger_event('success')
        except EOFError:
            break
            
        action = cmd[0]
        
        if action == "EXIT":
            break
        elif action == "ADVANCE":
            game.advance_turn()
        elif action == "SAVE":
            slot = cmd[1] if len(cmd) > 1 else "auto"
            game.save_manager.save_game(game, slot)
        elif action == "LOAD":
            slot = cmd[1] if len(cmd) > 1 else "auto"
            loaded_game = game.save_manager.load_game(slot)
            if loaded_game and isinstance(loaded_game, GameState):
                game.cleanup()
                game = loaded_game
                game.audio.ambient_loop(Sound.THRUM)
                print("*** GAME LOADED ***")
        elif action == "STATUS":
            for m in game.crew:
                status = "Alive" if m.is_alive else "DEAD"
                msg = f"{m.name} ({m.role}): Loc {m.location} | HP: {m.health} | {status}"
                avg_trust = game.trust_system.get_average_trust(m.name)
                msg += f" | Trust: {avg_trust:.1f}"
                print(msg)
        # ... REST OF COMMANDS SAME AS BEFORE ...
        elif action == "TRUST":
            if len(cmd) < 2:
                print("Usage: TRUST <NAME>")
            else:
                target_name = cmd[1]
                print(f"--- TRUST MATRIX FOR {target_name.upper()} ---")
                for m in game.crew:
                    if m.name in game.trust_system.matrix:
                        val = game.trust_system.matrix[m.name].get(target_name.title(), 50)
                        print(f"{m.name} -> {target_name.title()}: {val}")
        
        # --- FORENSIC COMMANDS ---
        elif action == "HEAT":
            print(game.forensics.blood_test.heat_wire())
            
        elif action == "TEST":
            if len(cmd) < 2:
                print("Usage: TEST <NAME>")
            else:
                target_name = cmd[1]
                # Check if we have wire? For now assume yes or check inventory later
                target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
                if target:
                    if game.station_map.get_room_name(*target.location) == player_room:
                        print(game.forensics.blood_test.start_test(target.name))
                    else:
                        print(f"{target.name} is not here.")
                else:
                    print(f"Unknown target: {target_name}")

        elif action == "APPLY":
            if not game.forensics.blood_test.active:
                print("No test in progress.")
            else:
                # Find the sample owner to check infection status
                sample_name = game.forensics.blood_test.current_sample
                subject = next((m for m in game.crew if m.name == sample_name), None)
                if subject:
                    print(game.forensics.blood_test.apply_wire(subject.is_infected))
                    
        elif action == "CANCEL":
             print(game.forensics.blood_test.cancel())
             
        elif action == "TAG":
            if len(cmd) < 3:
                print("Usage: TAG <NAME> <CATEGORY> <NOTE...>")
            else:
                target_name = cmd[1]
                category = cmd[2]
                note = " ".join(cmd[3:])
                target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
                if target:
                    game.forensic_db.add_tag(target.name, category, note, game.turn)
                    print(f"Logged forensic tag for {target.name}.")
                else:
                    print(f"Unknown target: {target_name}")
                    
        elif action == "LOG":
            if len(cmd) < 2:
                print("Usage: LOG <ITEM NAME>")
            else:
                item_name = " ".join(cmd[1:])
                print(game.evidence_log.get_history(item_name))

        elif action == "DOSSIER":
            if len(cmd) < 2:
                print("Usage: DOSSIER <NAME>")
            else:
                target_name = cmd[1]
                print(game.forensic_db.get_report(target_name))
        # -------------------------

        elif action == "TALK":
             for m in game.crew:
                room = game.station_map.get_room_name(*m.location)
                if room == player_room: # Only talk to people in the same room
                    print(f"{m.name}: {m.get_dialogue(game)}")
        elif action == "LOOK":
            if len(cmd) < 2:
                print("Usage: LOOK <NAME>")
            else:
                target_name = cmd[1]
                target = next((m for m in game.crew if m.name.upper() == target_name), None)
                if target:
                    if game.station_map.get_room_name(*target.location) == player_room:
                        print(target.get_description(game))
                    else:
                        print(f"There is no {target_name} here.")
                else:
                    print(f"Unknown crew member: {target_name}")
        elif action == "TAG":
            if len(cmd) < 3:
                print("Usage: TAG <NAME> <CATEGORY> <NOTE...>")
                print("Categories: IDENTITY, TRUST, SUSPICION, BEHAVIOR")
            else:
                target_name = cmd[1]
                category = cmd[2]
                note = " ".join(cmd[3:])
                target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
                if target:
                    game.forensic_db.add_tag(target.name, category, note, game.turn)
                    # Emit Event for Social System to lower trust
                    event_bus.emit(GameEvent(EventType.EVIDENCE_TAGGED, {"target": target.name, "game_state": game}))
                    print(f"Logged forensic tag for {target.name} [{category}].")
                else:
                    print(f"Unknown target: {target_name}")

        elif action == "LOG":
            if len(cmd) < 2:
                print("Usage: LOG <ITEM NAME>")
            else:
                item_name = " ".join(cmd[1:])
                print(game.evidence_log.get_history(item_name))

        elif action == "DOSSIER":
            if len(cmd) < 2:
                print("Usage: DOSSIER <NAME>")
            else:
                target_name = cmd[1]
                print(game.forensic_db.get_report(target_name))

        elif action == "JOURNAL":
            print("\n--- MACREADY'S JOURNAL ---")
            if not game.journal:
                print("(No direct diary entries - use DOSSIER for tags)")
            for entry in game.journal:
                print(entry)
            print("--------------------------")
        elif action == "CHECK":
            if len(cmd) < 2:
                print("Usage: CHECK <SKILL> (e.g., CHECK MELEE)")
            else:
                skill_name = cmd[1].title()
                try:
                    skill_enum = next((s for s in Skill if s.value.upper() == skill_name.upper()), None)
                    if skill_enum:
                        assoc_attr = Skill.get_attribute(skill_enum)
                        result = game.player.roll_check(assoc_attr, skill_enum, game.rng)
                        outcome = "SUCCESS" if result['success'] else "FAILURE"
                        print(f"Checking {skill_name} ({assoc_attr.value} + Skill)...")
                        print(f"Pool: {len(result['dice'])} dice -> {result['dice']}")
                        print(f"[{outcome}] ({result['success_count']} successes)")
                    else:
                        print(f"Unknown skill: {skill_name}")
                        print("Available: " + ", ".join([s.value for s in Skill]))
                except Exception as e:
                    print(f"Error resolving check: {e}")
        elif action == "INVENTORY" or action == "INV":
            print(f"\n--- {game.player.name}'s INVENTORY ---")
            if not game.player.inventory:
                print("(Empty)")
            for item in game.player.inventory:
                print(f"- {item.name}: {item.description}")
        elif action == "GET":
            if len(cmd) < 2:
                print("Usage: GET <ITEM NAME>")
            else:
                item_name = " ".join(cmd[1:])
                found_item = game.station_map.remove_item_from_room(item_name, *game.player.location)
                if found_item:
                    game.player.add_item(found_item, game.turn)
                    game.evidence_log.record_event(found_item.name, "GET", game.player.name, player_room, game.turn)
                    print(f"You picked up {found_item.name}.")
                else:
                    print(f"You don't see '{item_name}' here.")
        elif action == "DROP":
            if len(cmd) < 2:
                print("Usage: DROP <ITEM NAME>")
            else:
                item_name = " ".join(cmd[1:])
                dropped_item = game.player.remove_item(item_name)
                if dropped_item:
                    game.station_map.add_item_to_room(dropped_item, *game.player.location, game.turn)
                    game.evidence_log.record_event(dropped_item.name, "DROP", game.player.name, player_room, game.turn)
                    print(f"You dropped {dropped_item.name}.")
                else:
                    print(f"You don't have '{item_name}'.")
        elif action == "ATTACK":
            if len(cmd) < 2:
                print("Usage: ATTACK <NAME>")
            else:
                target_name = cmd[1]
                target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
                if not target:
                    print(f"Unknown target: {target_name}")
                elif game.station_map.get_room_name(*target.location) != player_room:
                    print(f"{target.name} is not here.")
                elif not target.is_alive:
                    print(f"{target.name} is already dead.")
                else:
                    weapon = next((i for i in game.player.inventory if i.damage > 0), None)
                    w_name = weapon.name if weapon else "Fists"
                    w_skill = weapon.weapon_skill if weapon else Skill.MELEE
                    w_dmg = weapon.damage if weapon else 0
                    
                    print(f"Attacking {target.name} with {w_name}...")
                    att_attr = Skill.get_attribute(w_skill)
                    att_res = game.player.roll_check(att_attr, w_skill, game.rng)
                    
                    def_skill = Skill.MELEE
                    def_attr = Attribute.PROWESS 

                    def_res = target.roll_check(def_attr, def_skill, game.rng)
                    
                    print(f"Attack: {att_res['success_count']} vs Defense: {def_res['success_count']}")
                    
                    if att_res['success_count'] > def_res['success_count']:
                        net_hits = att_res['success_count'] - def_res['success_count']
                        total_dmg = w_dmg + net_hits
                        died = target.take_damage(total_dmg)
                        print(f"HIT! Dealt {total_dmg} damage.")
                        if died:
                            print(f"*** {target.name} HAS DIED ***")
                    else:
                        print("MISS/BLOCKED!")
        elif action == "MOVE":
            if len(cmd) < 2:
                print("Usage: MOVE <NORTH/SOUTH/EAST/WEST>")
            else:
                direction = cmd[1]
                dx, dy = 0, 0
                if direction in ["NORTH", "N"]: dy = -1
                elif direction in ["SOUTH", "S"]: dy = 1
                elif direction in ["EAST", "E"]: dx = 1
                elif direction in ["WEST", "W"]: dx = -1
                
                if game.player.move(dx, dy, game.station_map):
                    print(f"You moved {direction}.")
                    game.advance_turn() 
                else:
                    print("Blocked.")
        elif action == "BARRICADE":
            result = game.room_states.barricade_room(player_room)
            print(result)
        elif action == "TEST":
            # Simplified Heated Wire Test flow
            if len(cmd) < 2:
                print("Usage: TEST <NAME>")
            else:
                target_name = cmd[1]
                target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
                if not target:
                    print(f"Unknown target: {target_name}")
                elif game.station_map.get_room_name(*target.location) != player_room:
                    print(f"{target.name} is not here.")
                else:
                    # Check for required items
                    scalpel = next((i for i in game.player.inventory if "SCALPEL" in i.name.upper()), None)
                    wire = next((i for i in game.player.inventory if "WIRE" in i.name.upper()), None)

                    if not scalpel:
                        print("You need a SCALPEL to draw a blood sample.")
                    elif not wire:
                        print("You need COPPER WIRE for the test.")
                    else:
                        print(f"Drawing blood from {target.name}...")
                        print(game.blood_test_sim.start_test(target.name))
                        # Rapid heating and application
                        print(game.blood_test_sim.heat_wire())
                        print(game.blood_test_sim.heat_wire())
                        print(game.blood_test_sim.heat_wire())
                        print(game.blood_test_sim.heat_wire())

                        result = game.blood_test_sim.apply_wire(target.is_infected)
                        print(result)

                        if target.is_infected:
                            # Reveal infection!
                            game.missionary_system.trigger_reveal(target, "Blood Test Exposure")
        else:
            print("Unknown command. Try: MOVE, LOOK, GET, DROP, USE, INV, TAG, TEST, HEAT, APPLY, ATTACK, STATUS, SAVE, LOAD, EXIT")
