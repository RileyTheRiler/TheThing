from typing import Optional, List, Dict, Any

import json
import os
import sys
import random
import time

from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, Skill, ResolutionSystem
from core.design_briefs import DesignBriefRegistry

from entities.crew_member import CrewMember
from entities.item import Item
from entities.station_map import StationMap

from systems.ai import AISystem
from systems.architect import RandomnessEngine, GameMode, TimeSystem, Difficulty, DifficultySettings, Verbosity
from systems.commands import CommandDispatcher, GameContext
from systems.combat import CombatSystem, CoverType
from systems.crafting import CraftingSystem
from systems.endgame import EndgameSystem
from systems.forensics import BiologicalSlipGenerator, BloodTestSim, ForensicDatabase, EvidenceLog, ForensicsSystem
from systems.missionary import MissionarySystem
from systems.persistence import SaveManager
from systems.psychology import PsychologySystem
from systems.random_events import RandomEventSystem
from systems.room_state import RoomState, RoomStateManager
from systems.sabotage import SabotageManager
from systems.social import DialogueManager, LynchMobSystem, TrustMatrix, SocialThresholds, bucket_for_thresholds, bucket_label
from systems.stealth import StealthSystem
from systems.weather import WeatherSystem
from systems.environmental_coordinator import EnvironmentalCoordinator

from ui.renderer import TerminalRenderer
from ui.crt_effects import CRTOutput
from ui.command_parser import CommandParser
from ui.message_reporter import MessageReporter
from audio.audio_manager import AudioManager, Sound


class GameState:
    @property
    def paranoia_level(self):
        return getattr(self, "_paranoia_level", 0)

    @paranoia_level.setter
    def paranoia_level(self, value):
        clamped = max(0, min(100, int(value)))
        previous_value = getattr(self, "_paranoia_level", None)
        self._paranoia_level = clamped

        if not hasattr(self, "social_thresholds"):
            return

        if previous_value is None:
            self._paranoia_bucket = bucket_for_thresholds(clamped, self.social_thresholds.paranoia_thresholds)
            return

        new_bucket = bucket_for_thresholds(clamped, self.social_thresholds.paranoia_thresholds)
        previous_bucket = getattr(self, "_paranoia_bucket", new_bucket)
        if new_bucket != previous_bucket:
            self._paranoia_bucket = new_bucket
            direction = "up" if clamped > previous_value else "down"
            event_bus.emit(GameEvent(EventType.PARANOIA_THRESHOLD, {
                "value": clamped,
                "previous_value": previous_value,
                "bucket": bucket_label(new_bucket),
                "thresholds": list(self.social_thresholds.paranoia_thresholds),
                "direction": direction
            }))
        else:
            base_dialogue = f"I'm {self.behavior_type}."
        
        # Advanced Mimicry: Use Knowledge Tags
        if self.is_infected and self.knowledge_tags and rng.random_float() < 0.4:
            tag = rng.choose(self.knowledge_tags) if hasattr(rng, 'choose') else random.choice(self.knowledge_tags)
            base_dialogue += f" I remember {tag}."

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
            "knowledge_tags": self.knowledge_tags,
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
        m.knowledge_tags = data.get("knowledge_tags", [])
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
            self._paranoia_bucket = new_bucket

    def __init__(self, seed=None, difficulty=Difficulty.NORMAL, characters_path=None, start_hour=None, thresholds: SocialThresholds = None):
        self.social_thresholds = thresholds or SocialThresholds()
        self.rng = RandomnessEngine(seed)
        self.time_system = TimeSystem()
        self.save_manager = SaveManager(game_state_factory=GameState.from_dict)

        self.time_system = TimeSystem(start_hour=start_hour if start_hour is not None else 19)
        self.save_manager = SaveManager(game_state_factory=GameState.from_dict)
        self.characters_config_path = characters_path or os.path.join("config", "characters.json")
        
        # Store difficulty and get settings
        self.difficulty = difficulty
        self.difficulty_settings = DifficultySettings.get_all(difficulty)

        self.power_on = True
        self.blood_bank_destroyed = False
        self.paranoia_level = self.difficulty_settings["starting_paranoia"]
        self.mode = GameMode.INVESTIGATIVE
        self.verbosity = Verbosity.STANDARD
        self.design_registry = DesignBriefRegistry()

        # Track which per-turn behaviors executed during TURN_ADVANCE
        self.turn_behavior_inventory = {
            "weather": 0,
            "sabotage": 0,
            "ai": 0,
            "random_events": 0
        }

        # Initialize core systems
        self.station_map = StationMap()
        self.weather = WeatherSystem()
        self.sabotage = SabotageManager(self.difficulty_settings)
        self.random_events = RandomEventSystem(self.rng)  # Agent 6.2
        self.environmental_coordinator = EnvironmentalCoordinator()
        
        self.room_states = RoomStateManager(list(self.station_map.rooms.keys()))
        
        # Initialize Audio & UI
        self.audio = AudioManager(self.rng)
        self.crt = CRTOutput()
        self.renderer = TerminalRenderer(self.station_map)
        self.reporter = MessageReporter(self.renderer)

        # Initialize Crew
        self.crew = []
        self.player = None
        self._initialize_crew()  # Loads from JSON

        # Initialize Subsystems requiring crew/map
        self.forensics = ForensicsSystem(self.crew)
        self.missionary = MissionarySystem(self.crew) # Agent 2.5
        self.psychology = PsychologySystem(self.crew) # Agent 2.4
        self.lynch_mob = LynchMobSystem(self.crew) # Agent 2.3
        self.dialogue = DialogueManager(self.crew)
        self.trust_system = TrustMatrix(self.crew)
        self.stealth = StealthSystem()
        self.crafting = CraftingSystem(self)
        self.endgame = EndgameSystem(self) # Agent 8
        self.combat = CombatSystem() # Tier 3.5

        self.parser = CommandParser(self.crew)
        self.parser.set_known_names([m.name for m in self.crew])
        
        self.dispatcher = CommandDispatcher(self)
        self.context = GameContext(self)

        # Game Loop State
        self.turn = 1
        self.running = True
        self.game_over = False

        # Narrative State
        self.helicopter_status = "BROKEN" # BROKEN, REPAIRED, ESCAPED
        self.rescue_signal_active = False
        self.rescue_turns_remaining = None 
        
        # Journal/Logs
        self.journal = []
        self.evidence_log = EvidenceLog()
        self.forensic_db = ForensicDatabase()

    def _initialize_crew(self):
        """Load crew data from configuration."""
        try:
            with open(self.characters_config_path, 'r') as f:
                data = json.load(f)
                
            if isinstance(data, list):
                crew_list = data
            else:
                crew_list = data.get("crew", [])

            for char_data in crew_list:
                # Parse attributes
                attrs = {}
                for k, v in char_data.get("attributes", {}).items():
                    try:
                        attrs[Attribute[k]] = v
                    except KeyError:
                        print(f"Warning: Invalid attribute {k} for {char_data['name']}")
                
                # Parse skills
                skills = {}
                for k, v in char_data.get("skills", {}).items():
                    try:
                        skills[Skill[k]] = v
                    except KeyError:
                        print(f"Warning: Invalid skill {k} for {char_data['name']}")
                
                member = CrewMember(
                    name=char_data["name"],
                    role=char_data["role"],
                    behavior_type=char_data["behavior_type"],
                    attributes=attrs,
                    skills=skills,
                    schedule=char_data.get("schedule"),
                    invariants=char_data.get("invariants")
                )
                
                # Hydrate forbidden rooms
                member.forbidden_rooms = char_data.get("forbidden_rooms", [])
                
                # Set initial location
                start_room = char_data.get("start_location", "Rec Room")
                if start_room in self.station_map.rooms:
                    room_coords = self.station_map.rooms[start_room]
                    # Simple placement: center of room
                    cx = (room_coords[0] + room_coords[2]) // 2
                    cy = (room_coords[1] + room_coords[3]) // 2
                    member.location = (cx, cy)
                
                self.crew.append(member)

            # Assign Player (MacReady)
            self.player = next((m for m in self.crew if m.name == "MacReady"), None)
            if not self.player:
                raise ValueError("MacReady not found in crew configuration!")

            # Determine initial infected
            self._assign_initial_infected()
            
        except FileNotFoundError:
            print(f"Error: Characters config not found at {self.characters_config_path}")
            sys.exit(1)
        except Exception as e:
            print(f"Error initializing crew: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def _assign_initial_infected(self):
        """Randomly assign 'The Thing' status to non-MacReady crew."""
        eligible = [m for m in self.crew if m.name != "MacReady"]
        if not eligible:
            return

        # Determine how many to infect based on difficulty
        min_infected = self.difficulty_settings["initial_infected_min"]
        max_infected = self.difficulty_settings["initial_infected_max"]
        num_infected = self.rng.randint(min_infected, min(max_infected, len(eligible)))

        # Randomly select crew to infect
        infected_crew = self.rng.sample(eligible, num_infected)
        for member in infected_crew:
            member.is_infected = True

    def advance_turn(self, power_on: Optional[bool] = None):
        """Advance the game by one turn. All per-turn behaviors are handled by event subscribers."""
        self.turn += 1
        
        # Reset per-turn flags
        for member in self.crew:
            member.slipped_vapor = False
        
        self.paranoia_level = min(100, self.paranoia_level + 1)
        if power_on is not None:
            self.power_on = power_on

        # Update TimeSystem and notify listeners
        self.time_system.advance_turn(self.power_on, game_state=self, rng=self.rng)
        
        # Track per-turn behaviors (weather, sabotage, AI, random events)
        turn_inventory = {k: 0 for k in self.turn_behavior_inventory}
        turn_inventory["random_event_triggered"] = None

        # 1. Emit TURN_ADVANCE Event (Triggers TimeSystem, WeatherSystem, InfectionSystem, etc.)
        event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {
            "game_state": self,
            "rng": self.rng,
            "turn": self.turn
        }))
        
        # 3. Process Local Environment Effects
        player_room = self.station_map.get_room_name(*self.player.location)
        paranoia_mod = self.room_states.get_paranoia_modifier(player_room)
        if paranoia_mod > 0:
            self.paranoia_level = min(100, self.paranoia_level + paranoia_mod)
        
        # 4. Lynch Mob Check (Agent 2)
        lynch_target = self.lynch_mob.check_thresholds(self.crew, current_paranoia=self.paranoia_level)
        if lynch_target:
            # Mob is active, NPCs will converge via event handler
            pass

        
        # 5. NPC AI Update
        # self.ai_system.update(self) # Need to verify if AI system is initialized or if logic is handled elsewhere.
        # Based on imports, there is AISystem. But it wasn't initialized in __init__ in the snippet I saw.
        # Assuming AI update logic is migrating to events or handled by CrewMember.update_ai loop
        for member in self.crew:
             # Using the new update_ai method if available, or fallback
             if hasattr(member, 'update_ai'):
                 member.update_ai(self)
        
        turn_inventory["ai"] += 1

        # 6. Random Events Check (Tier 6.2)
        random_event = self.random_events.check_for_event(self)
        turn_inventory["random_events"] += 1
        if random_event:
            turn_inventory["random_event_triggered"] = random_event.id
            self.random_events.execute_event(random_event, self)

        # Expose per-turn behavior inventory for debugging/tests
        self.turn_behavior_inventory = turn_inventory

        # 7. Update Rescue Timer
        if self.rescue_signal_active and self.rescue_turns_remaining is not None:
            self.rescue_turns_remaining -= 1
            if self.rescue_turns_remaining == 5:
                self.reporter.report_event("RADIO", "Rescue ETA updated: 5 hours out.", priority=True)
            elif self.rescue_turns_remaining == 1:
                self.reporter.report_event("RADIO", "Rescue team landing imminent!", priority=True)
            if self.rescue_turns_remaining is not None and self.rescue_turns_remaining <= 0:
                self.rescue_turns_remaining = 0
                event_bus.emit(GameEvent(EventType.REPAIR_COMPLETE, {
                    "status": self.helicopter_status,
                    "turn": self.turn
                }))

        # 8. Auto-save every 5 turns
        if self.turn % 5 == 0 and hasattr(self, 'save_manager'):
            try:
                self.save_manager.save_game(self, "autosave")
            except Exception:
                pass  # Don't interrupt gameplay on save failure
        self._emit_population_status()

    def _emit_population_status(self):
        """Emit population status event for monitoring and UI updates."""
        living_crew = len([m for m in self.crew if m.is_alive])
        living_humans = len([m for m in self.crew if m.is_alive and not m.is_infected])
        event_bus.emit(GameEvent(EventType.POPULATION_STATUS, {
            "living_crew": living_crew,
            "living_humans": living_humans,
            "paranoia_level": self.paranoia_level,
            "turn": self.turn
        }))

    def check_win_condition(self):
        """
        Returns: (won: bool, message: str)
        """
        if not self.player or not self.player.is_alive:
            return False, None
        if self.player.is_infected and self.player.is_revealed:
            return False, None

        # 1. Helicopter Escape
        if self.helicopter_status == "ESCAPED":
            return True, "You pilot the chopper through the storm, leaving the nightmare of Outpost 31 behind."

        # 2. Rescue Arrival
        if self.rescue_signal_active and self.rescue_turns_remaining <= 0:
            return True, "Lights cut through the storm. The rescue team has arrived to extract you."

        # Check living crew status
        living_crew = [m for m in self.crew if m.is_alive]
        living_infected = [m for m in living_crew if m.is_infected and m != self.player]

        # 3. Sole Survivor
        if len(living_crew) == 1 and living_crew[0] == self.player:
            return True, "Silence falls over the station. You are the only one left alive. The threat is gone... you hope."

        # 4. Extermination
        if not living_infected and self.crew:  # Ensure game has started
            # Complex check: Do we know they are dead? For now, if all infected are dead, you win.
            total_infected = [m for m in self.crew if m.is_infected]
            if total_infected and all(not m.is_alive for m in total_infected):
                 return True, "All Things have been eliminated. Humanity survives... for now."

        return False, None

    def check_lose_condition(self):
        """
        Returns: (lost: bool, message: str)
        """
        if not self.player:
            return True, "MacReady is gone. The Thing has won."

        if not self.player.is_alive:
            return True, "MacReady is dead. The Thing spreads unchecked across the ice."

        if self.player.is_infected and self.player.is_revealed:
            return True, "MacReady has become one of Them. The imitation is perfect."

        return False, None

    @classmethod
    def from_dict(cls, data):
        """Deserialize game state from dictionary with defensive defaults and validation."""
        if not data or not isinstance(data, dict):
            from ui.message_reporter import emit_error
            emit_error("FAILED TO LOAD: Invalid save data format.")
            return None

        # Get difficulty from save or default to NORMAL
        difficulty_value = data.get("difficulty", Difficulty.NORMAL.value)
        try:
            difficulty = Difficulty(difficulty_value)
        except ValueError:
            difficulty = Difficulty.NORMAL

        game = cls(difficulty=difficulty)
        
        # Power and Paranoia
        game.power_on = data.get("power_on", True)
        game.paranoia_level = data.get("paranoia_level", 0)
        
        # Mode
        mode_val = data.get("mode", GameMode.INVESTIGATIVE.value)
        try:
            game.mode = GameMode(mode_val)
        except ValueError:
            game.mode = GameMode.INVESTIGATIVE

        # Helicopter and Rescue
        game.helicopter_status = data.get("helicopter_status", "BROKEN")
        game.rescue_signal_active = data.get("rescue_signal_active", False)
        game.rescue_turns_remaining = data.get("rescue_turns_remaining")

        # RNG and Time System
        if "rng" in data:
            game.rng.from_dict(data["rng"])
        
        if "time_system" in data:
            game.time_system = TimeSystem.from_dict(data["time_system"])
        else:
            # Fallback if time_system missing
            game.time_system.turn_count = data.get("turn", 1) - 1

        # Station Map
        if "station_map" in data:
            game.station_map = StationMap.from_dict(data["station_map"])

        # Crew
        crew_data = data.get("crew", [])
        if crew_data:
            game.crew = []
            for m_data in crew_data:
                member = CrewMember.from_dict(m_data)
                if member:
                    game.crew.append(member)
        
        # Re-link player
        game.player = next((m for m in game.crew if m.name == "MacReady"), None)
        # If player missing, create a fallback so game doesn't crash
        if not game.player and game.crew:
            game.player = game.crew[0]
        elif not game.player:
            from ui.message_reporter import emit_error
            emit_error("CRITICAL ERROR: No crew found in save file.")

        game.journal = data.get("journal", [])
        
        # Trust System
        if hasattr(game, "trust_system"):
            game.trust_system.cleanup()
        game.trust_system = TrustMatrix(game.crew)
        trust_data = data.get("trust")
        if trust_data and isinstance(trust_data, dict):
            game.trust_system.matrix.update(trust_data)
        
        # Re-initialize subsystems that depend on fresh state
        game.renderer.map = game.station_map
        game.parser.set_known_names([m.name for m in game.crew])
        game.room_states = RoomStateManager(list(game.station_map.rooms.keys()))
        game.crafting = CraftingSystem.from_dict(data.get("crafting"), game)
        
        from ui.message_reporter import emit_message
        emit_message("*** GAME LOADED ***")
        
        return game
