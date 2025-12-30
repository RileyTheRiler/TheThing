from typing import Optional, List, Dict, Any

import json
import os
import sys
import random
import time

from core.event_system import event_bus, EventType, GameEvent
from core.resolution import Attribute, Skill, ResolutionSystem
from core.design_briefs import DesignBriefRegistry

from entities.crew_member import CrewMember as EntityCrewMember
from entities.item import Item
from entities.station_map import StationMap

from systems.ai import AISystem
from systems.alert import AlertSystem
from systems.security import SecuritySystem, SecurityLog
from systems.architect import RandomnessEngine, GameMode, TimeSystem, Difficulty, DifficultySettings, Verbosity
from systems.architect import RandomnessEngine, GameMode, TimeSystem, Difficulty, DifficultySettings
from systems.commands import CommandDispatcher, GameContext
from systems.combat import CombatSystem, CoverType
from systems.crafting import CraftingSystem
from systems.endgame import EndgameSystem
from systems.forensics import BiologicalSlipGenerator, BloodTestSim, ForensicDatabase, EvidenceLog, ForensicsSystem
from systems.missionary import MissionarySystem
from systems.persistence import SaveManager, CURRENT_SAVE_VERSION
from systems.psychology import PsychologySystem
from systems.random_events import RandomEventSystem
from systems.room_state import RoomState, RoomStateManager
from systems.sabotage import SabotageManager
from systems.social import DialogueManager, LynchMobSystem, TrustMatrix, SocialThresholds, bucket_for_thresholds, bucket_label
from systems.stealth import StealthSystem
from systems.progression import ProgressionSystem
from systems.weather import WeatherSystem
from systems.environmental_coordinator import EnvironmentalCoordinator
from systems.dialogue import DialogueSystem
from systems.dialogue_system import DialogueBranchingSystem

from ui.renderer import TerminalRenderer
from ui.crt_effects import CRTOutput
from ui.command_parser import CommandParser
from ui.message_reporter import MessageReporter
from audio.audio_manager import AudioManager, Sound


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
        self.security_role = False
        self.next_security_check_turn = 0

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

    def roll_check(self, attribute, skill=None, rng=None, resolution_system=None):
        attr_val = self.attributes.get(attribute, 1) 
        skill_val = self.skills.get(skill, 0)
        pool_size = attr_val + skill_val
        
        # Use provided ResolutionSystem or fallback to static class method
        if resolution_system:
            return resolution_system.roll_check(pool_size, rng)
        return ResolutionSystem.roll_check(pool_size, rng)

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

# Ensure the engine uses the primary CrewMember implementation from entities
CrewMember = EntityCrewMember

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
            direction = "UP" if clamped > previous_value else "DOWN"
            event_bus.emit(GameEvent(EventType.PARANOIA_THRESHOLD_CROSSED, {
                "value": clamped,
                "previous_value": previous_value,
                "bucket": bucket_label(new_bucket),
                "thresholds": list(self.social_thresholds.paranoia_thresholds),
                "direction": direction,
                "threshold": self.social_thresholds.paranoia_thresholds[new_bucket-1] if direction == "UP" else self.social_thresholds.paranoia_thresholds[new_bucket]
            }))
        if not hasattr(self, "schedule"):
            return

        # 0. PRIORITY: Lynch Mob Hunting (Agent 2)
        if hasattr(self, "lynch_mob") and hasattr(self, "station_map") and self.lynch_mob.active_mob and self.lynch_mob.target:
        if hasattr(self, "lynch_mob") and self.lynch_mob.active_mob and self.lynch_mob.target:
            target = self.lynch_mob.target
            if target != self and target.is_alive:
                # Move toward the lynch target
                tx, ty = target.location
                self._pathfind_step(tx, ty, self.station_map)
                return

        # 1. Check Schedule
        # Schedule entries: {"start": 8, "end": 20, "room": "Rec Room"}
        # Fix: TimeSystem lacks 'hour' property, calculate manually (Start 08:00)
        if not hasattr(self, "schedule"):
            return
        current_hour = (self.time_system.turn_count + 8) % 24
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
            target_pos = self.station_map.rooms.get(destination)
            if target_pos:
                tx, ty, _, _ = target_pos
                self._pathfind_step(tx, ty, self.station_map)
                return

        # 2. Idling / Wandering
        if self.rng.random_float() < 0.3:
            dx = self.rng.choose([-1, 0, 1])
            dy = self.rng.choose([-1, 0, 1])
            self.move(dx, dy, self.station_map)

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

    @property
    def temperature(self):
        return self.time_system.temperature if hasattr(self, "time_system") else -40.0

    @property
    def radio_operational(self):
        if hasattr(self, "sabotage") and hasattr(self.sabotage, "radio_operational"):
            return self.sabotage.radio_operational
        return getattr(self, "_radio_operational", True)

    @radio_operational.setter
    def radio_operational(self, value: bool):
        self._radio_operational = bool(value)
        if hasattr(self, "sabotage"):
            self.sabotage.radio_operational = bool(value)

    @property
    def helicopter_operational(self):
        if hasattr(self, "sabotage") and hasattr(self.sabotage, "helicopter_operational"):
            return self.sabotage.helicopter_operational
        return getattr(self, "_helicopter_operational", True)

    @helicopter_operational.setter
    def helicopter_operational(self, value: bool):
        self._helicopter_operational = bool(value)
        if hasattr(self, "sabotage"):
            self.sabotage.helicopter_operational = bool(value)

    def __init__(self, seed=None, difficulty=Difficulty.NORMAL, characters_path=None, start_hour=None, thresholds: SocialThresholds = None):
        # 1. Pre-initialization of essential attributes to avoid AttributeErrors in setters/listeners
        self.social_thresholds = thresholds or SocialThresholds()
        self.rng = RandomnessEngine(seed)
        self.player = None
        self.crew = []
        self._paranoia_level = 0
        self.design_registry = DesignBriefRegistry()
        self.action_cooldowns = {}
        self._radio_operational = True
        self._helicopter_operational = True
        
        # 2. Basic Configuration
        self.characters_config_path = characters_path or os.path.join("config", "characters.json")
        self.difficulty = difficulty
        self.difficulty_settings = DifficultySettings.get_all(difficulty)
        
        # 3. Time and Persistence
        self.time_system = TimeSystem(start_hour=start_hour if start_hour is not None else 19)
        self.save_manager = SaveManager(game_state_factory=GameState.from_dict)
        
        # 4. Global State
        self.power_on = True
        self.blood_bank_destroyed = False
        self.alert_status = "CALM"
        self.alert_turns_remaining = 0
        self.paranoia_level = self.difficulty_settings["starting_paranoia"]
        self.mode = GameMode.INVESTIGATIVE
        self.security_log = SecurityLog()
        # self.verbosity = Verbosity.STANDARD

        # 5. Core Simulation Systems
        self.station_map = StationMap()
        self.weather = WeatherSystem()
        self.sabotage = SabotageManager(self.difficulty_settings)
        self.radio_operational = self.sabotage.radio_operational
        self.helicopter_operational = self.sabotage.chopper_operational
        self.random_events = RandomEventSystem(self.rng, config_registry=self.design_registry)
        self.environmental_coordinator = EnvironmentalCoordinator()
        self.room_states = RoomStateManager(list(self.station_map.rooms.keys()))
        
        # 6. Initialize Crew (sets self.player)
        self._initialize_crew()  

        # 7. Initialize Subsystems requiring crew/map/player
        self.audio = AudioManager(enabled=True, rng=self.rng, player_ref=self.player, station_map=self.station_map)
        self.crt = CRTOutput()
        self.renderer = TerminalRenderer(self.station_map)
        self.reporter = MessageReporter(self.crt, self)

        self.forensics = ForensicsSystem(rng=self.rng)
        self.missionary = MissionarySystem()
        self.psychology = PsychologySystem()
        self.trust_system = TrustMatrix(self.crew, thresholds=self.social_thresholds)
        self.lynch_mob = LynchMobSystem(self.trust_system)
        self.dialogue = DialogueManager()
        self.dialogue_system = DialogueSystem(rng=self.rng)
        self.dialogue_branching = DialogueBranchingSystem(rng=self.rng)
        self.stealth = StealthSystem()
        self.stealth_system = self.stealth  # Alias for systems expecting stealth_system attr
        self.alert_system = AlertSystem(self)
        self.security_system = SecuritySystem(self)
        self.progression = ProgressionSystem(self)
        self.crafting = CraftingSystem()
        self.endgame = EndgameSystem(self.design_registry) # Agent 8
        self.combat = CombatSystem(self.rng, self.room_states)
        self.ai_system = AISystem()

        self.parser = CommandParser(self.crew)
        self.parser.set_known_names([m.name for m in self.crew])
        self.dispatcher = CommandDispatcher()
        self.context = GameContext(self)

        # 8. Loop State
        self.turn = 1
        self.running = True
        self.game_over = False
        self.last_ending_payload = None
        self._last_action_successful = False
        self.turn_behavior_inventory = {"weather": 0, "sabotage": 0, "ai": 0, "random_events": 0}

        # 9. Narrative/Persistence
        self.helicopter_status = "BROKEN"
        self.escape_route = None  # helicopter | overland
        self.overland_escape_turns = None
        self.rescue_signal_active = False
        self.rescue_turns_remaining = None 
        self.rescue_eta_turns = 20
        self.alert_status = "calm"
        self.alert_turns_remaining = 0
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
                attrs = {}
                for k, v in char_data.get("attributes", {}).items():
                    try:
                        attrs[Attribute[k.upper()]] = v
                    except KeyError:
                        pass
                
                skills = {}
                for k, v in char_data.get("skills", {}).items():
                    try:
                        skills[Skill[k.upper()]] = v
                    except KeyError:
                        pass
                
                member = CrewMember(
                    name=char_data["name"],
                    role=char_data["role"],
                    behavior_type=char_data.get("behavior", char_data.get("behavior_type", "Neutral")),
                    attributes=attrs,
                    skills=skills,
                    schedule=char_data.get("schedule"),
                    invariants=char_data.get("invariants")
                )
                
                member.forbidden_rooms = char_data.get("forbidden_rooms", [])
                member.security_role = char_data.get("security_role", False)
                
                start_room = char_data.get("start_location", "Rec Room")
                if start_room in self.station_map.rooms:
                    room_coords = self.station_map.rooms[start_room]
                    cx = (room_coords[0] + room_coords[2]) // 2
                    cy = (room_coords[1] + room_coords[3]) // 2
                    member.location = (cx, cy)
                
                self.crew.append(member)

            self.player = next((m for m in self.crew if m.name == "MacReady"), None)
            if not self.player and self.crew:
                self.player = self.crew[0]
            
            self._assign_initial_infected()
            
        except Exception as e:
            # Fallback for tests or missing config
            if not self.crew:
                 m = CrewMember("MacReady", "Pilot", "Neutral")
                 self.crew = [m]
                 self.player = m

    def _assign_initial_infected(self):
        """Randomly assign 'The Thing' status to non-MacReady crew."""
        eligible = [m for m in self.crew if m.name != "MacReady"]
        if not eligible:
            return

        min_infected = self.difficulty_settings.get("initial_infected_min", 1)
        max_infected = self.difficulty_settings.get("initial_infected_max", 2)
        num_infected = self.rng.randint(min_infected, min(max_infected, len(eligible)))

        infected_crew = self.rng.sample(eligible, num_infected)
        for member in infected_crew:
            member.is_infected = True

    def get_ambient_warnings(self):
        """Collect all location hint warnings from crew members.
        
        Returns a list of warning strings about characters being out of place.
        """
        warnings = []
        for member in self.crew:
            if member.is_alive and member != self.player:
                hints = member.check_location_hints(self)
                warnings.extend(hints)
        return warnings

    def advance_turn(self, power_on: Optional[bool] = None):
        """Advance the game by one turn."""
        self.turn += 1
        
        for member in self.crew:
            member.slipped_vapor = False
            if hasattr(member, "record_movement"):
                member.record_movement(self)
        
        self.paranoia_level = min(100, self.paranoia_level + 1)
        
        # Advance time, environment, and emit TURN_ADVANCE via the TimeSystem
        self.time_system.advance_turn(self.power_on, game_state=self, rng=self.rng)
        if power_on is not None:
            self.power_on = power_on

        # TimeSystem and others react to TURN_ADVANCE event
        turn_inventory = {"weather": 0, "sabotage": 0, "ai": 0, "random_events": 0, "random_event_triggered": None}

        if self.rescue_signal_active and self.rescue_turns_remaining is not None:
            self.rescue_turns_remaining -= 1
            if self.rescue_turns_remaining == 5:
                event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Rescue ETA updated: 5 hours out."}))
            elif self.rescue_turns_remaining == 1:
                event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Rescue team landing imminent!"}))
            if self.rescue_turns_remaining <= 0:
                self.rescue_turns_remaining = 0

        event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {
            "game_state": self,
            "rng": self.rng,
            "turn": self.turn,
            "turn_inventory": turn_inventory
        }))
        
        player_room = self.station_map.get_room_name(*self.player.location)
        paranoia_mod = self.room_states.get_paranoia_modifier(player_room)
        if paranoia_mod > 0:
            self.paranoia_level = min(100, self.paranoia_level + paranoia_mod)
        
        self.lynch_mob.check_thresholds(self.crew, current_paranoia=self.paranoia_level)
        
        
        turn_inventory["ai"] += 1

        random_event = self.random_events.check_for_event(self)
        turn_inventory["random_events"] += 1
        if random_event:
            turn_inventory["random_event_triggered"] = random_event.id
            self.random_events.execute_event(random_event, self)

        self.turn_behavior_inventory = turn_inventory

        if self.rescue_signal_active and self.rescue_turns_remaining is not None:
            if not self.radio_operational:
                event_bus.emit(GameEvent(EventType.WARNING, {"text": "The radio is dead. Your SOS beacon fails."}))
                self.rescue_signal_active = False
                self.rescue_turns_remaining = None
            else:
                self.rescue_turns_remaining -= 1
                if self.rescue_turns_remaining == 5:
                    event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Rescue ETA updated: 5 hours out."}))
                elif self.rescue_turns_remaining == 1:
                    event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Rescue team landing imminent!"}))
                if self.rescue_turns_remaining <= 0:
                    self.rescue_turns_remaining = 0
                    event_bus.emit(GameEvent(EventType.SOS_SENT, {
                        "game_state": self,
                        "arrived": True,
                        "turn": self.turn
                    }))

        if self.escape_route == "overland" and self.overland_escape_turns is not None:
            self.overland_escape_turns -= 1
            if self.overland_escape_turns <= 0:
                self.overland_escape_turns = 0
                self.helicopter_status = "ESCAPED"
                event_bus.emit(GameEvent(EventType.ESCAPE_SUCCESS, {
                    "game_state": self,
                    "route": "overland"
                }))
            else:
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": f"The whiteout howls. {self.overland_escape_turns} hours until you reach the rendezvous grid."
                }))

        if self.turn % 5 == 0 and hasattr(self, 'save_manager'):
            try:
                self.save_manager.save_game(self, "autosave")
            except Exception:
                pass
        self._emit_population_status()
        if hasattr(self, 'reporter'):
            self.reporter.flush()

    def _emit_population_status(self):
        """Emit population status event for monitoring and UI updates."""
        living_crew = len([m for m in self.crew if m.is_alive])
        living_humans = len([m for m in self.crew if m.is_alive and not m.is_infected])
        event_bus.emit(GameEvent(EventType.POPULATION_STATUS, {
            "living_crew": living_crew,
            "living_humans": living_humans,
            "player_alive": self.player.is_alive if self.player else False,
            "paranoia_level": self.paranoia_level,
            "turn": self.turn
        }))

    def _has_item(self, keyword: str):
        return next((i for i in self.player.inventory if keyword.upper() in i.name.upper()), None)

    def attempt_repair_radio(self):
        """Repair the radio if the player has the right tools and access."""
        self._last_action_successful = False
        player_room = self.station_map.get_room_name(*self.player.location)

        if player_room != "Radio Room":
            msg = "You must be in the Radio Room to repair the radio."
            event_bus.emit(GameEvent(EventType.WARNING, {"text": msg}))
            return msg

        if self.radio_operational:
            msg = "The radio is already operational."
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": msg}))
            return msg

        tools = self._has_item("TOOLS")
        parts = self._has_item("REPLACEMENT") or self._has_item("WIRE")
        if not tools or not parts:
            msg = "You need Tools and spare wiring to repair the radio."
            event_bus.emit(GameEvent(EventType.WARNING, {"text": msg}))
            return msg

        self.radio_operational = True
        self._last_action_successful = True
        msg = "You patch the radio back together. It hums with static, ready to broadcast."
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": msg}))
        return msg

    def attempt_repair_helicopter(self):
        """Attempt to repair the helicopter using available parts."""
        self._last_action_successful = False
        player_room = self.station_map.get_room_name(*self.player.location)

        if player_room != "Hangar":
            msg = "You must be in the Hangar to repair the helicopter."
            event_bus.emit(GameEvent(EventType.WARNING, {"text": msg}))
            return msg

        if self.helicopter_status == "FIXED" and self.helicopter_operational:
            msg = "The helicopter is already fixed."
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": msg}))
            return msg

        tools = self._has_item("TOOLS")
        parts = (
            self._has_item("REPLACEMENT")
            or self._has_item("FUEL")
            or self._has_item("WIRE")
        )

        if not tools or not parts:
            msg = "You need Tools and replacement parts to fix the helicopter."
            event_bus.emit(GameEvent(EventType.WARNING, {"text": msg}))
            return msg

        self.helicopter_operational = True
        event_bus.emit(GameEvent(EventType.HELICOPTER_REPAIRED, {"game_state": self}))
        self._last_action_successful = True
        return "You rebuild the damaged assemblies. The helicopter whines back to life."

    def attempt_radio_signal(self):
        """Broadcast an SOS if the radio can reach the outside world."""
        self._last_action_successful = False
        player_room = self.station_map.get_room_name(*self.player.location)

        if player_room != "Radio Room":
            msg = "You must be in the Radio Room to send an SOS."
            event_bus.emit(GameEvent(EventType.WARNING, {"text": msg}))
            return msg

        if not self.radio_operational:
            msg = "The radio is damaged. Repair it before broadcasting."
            event_bus.emit(GameEvent(EventType.WARNING, {"text": msg}))
            return msg

        if self.rescue_signal_active:
            msg = "The SOS signal is already broadcasting."
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": msg}))
            return msg

        self.rescue_signal_active = True
        # 20-turn default window; turn advance will immediately tick this down.
        self.rescue_turns_remaining = 20
        self._last_action_successful = True
        event_bus.emit(GameEvent(EventType.SOS_EMITTED, {"game_state": self}))
        return "You key the microphone and broadcast a desperate SOS across every channel."

    def attempt_escape(self):
        """Attempt to fly out using the repaired helicopter."""
        self._last_action_successful = False
        player_room = self.station_map.get_room_name(*self.player.location)

        if player_room != "Hangar":
            msg = "You must be in the Hangar to fly the helicopter."
            event_bus.emit(GameEvent(EventType.WARNING, {"text": msg}))
            return msg

        if not self.helicopter_operational or self.helicopter_status != "FIXED":
            msg = "The helicopter is not operational. It needs repairs."
            event_bus.emit(GameEvent(EventType.WARNING, {"text": msg}))
            return msg

        if not self.radio_operational:
            msg = "The radio is dead—you can't coordinate a safe escape route through the storm."
            event_bus.emit(GameEvent(EventType.WARNING, {"text": msg}))
            return msg

        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "You climb into the pilot's seat and engage the rotors..."}))
        event_bus.emit(GameEvent(EventType.ESCAPE_SUCCESS, {"game_state": self}))
        self._last_action_successful = True
        return "You yank the collective and lift off, skimming above the outpost toward the endless white."
    def attempt_repair_radio(self):
        player_room = self.station_map.get_room_name(*self.player.location)
        if player_room != "Radio Room":
            return False, "You must be in the Radio Room to repair the radio.", EventType.WARNING
        if self.radio_operational:
            return False, "The radio is already operational.", EventType.MESSAGE

        tools = next((i for i in self.player.inventory if "TOOL" in i.name.upper()), None)
        if not tools:
            return False, "You need TOOLS to repair the radio.", EventType.WARNING

        self.radio_operational = True
        if hasattr(self, "sabotage"):
            self.sabotage.radio_operational = True
            self.sabotage.radio_working = True
        return True, "You spend some time rewiring the radio. It's working again.", EventType.MESSAGE

    def attempt_repair_helicopter(self):
        player_room = self.station_map.get_room_name(*self.player.location)
        if player_room != "Hangar":
            return False, "You must be in the Hangar to repair the helicopter.", EventType.WARNING
        if self.helicopter_status == "ESCAPED":
            return False, "There's no helicopter left to repair.", EventType.WARNING
        if self.helicopter_status == "FIXED" and self.helicopter_operational:
            return False, "The helicopter is already fixed.", EventType.MESSAGE

        tools = next((i for i in self.player.inventory if "TOOL" in i.name.upper()), None)
        parts = next((i for i in self.player.inventory if "PART" in i.name.upper()), None)
        if not tools or not parts:
            return False, "You need TOOLS and REPLACEMENT PARTS to fix the helicopter.", EventType.WARNING

        self.helicopter_operational = True
        self.helicopter_status = "FIXED"
        if hasattr(self, "sabotage"):
            self.sabotage.chopper_operational = True
            self.sabotage.helicopter_working = True
        event_bus.emit(GameEvent(EventType.HELICOPTER_REPAIRED, {"game_state": self}))
        return True, "The engine roars to life. The helicopter is ready for takeoff.", EventType.MESSAGE

    def attempt_radio_signal(self):
        player_room = self.station_map.get_room_name(*self.player.location)
        if player_room != "Radio Room":
            return False, "You must be in the Radio Room to send an SOS.", EventType.WARNING
        if not self.radio_operational:
            return False, "The radio is damaged. It needs repairs first.", EventType.WARNING
        if getattr(self, "rescue_signal_active", False):
            return False, "The SOS signal is already broadcasting.", EventType.MESSAGE

        self.rescue_signal_active = True
        self.rescue_turns_remaining = self.rescue_eta_turns
        event_bus.emit(GameEvent(EventType.SOS_EMITTED, {"game_state": self}))
        return True, f"You broadcast a high-frequency SOS. Rescue ETA: {self.rescue_eta_turns} hours.", EventType.MESSAGE

    def attempt_escape(self):
        player_room = self.station_map.get_room_name(*self.player.location)
        if player_room != "Hangar":
            return False, "You must be in the Hangar to attempt an escape.", EventType.WARNING

        if self.escape_route == "overland":
            return False, "You are already trekking into the storm. Keep moving.", EventType.MESSAGE

        if self.helicopter_operational and self.helicopter_status == "FIXED":
            pilot_skill = getattr(self.player, "skills", {}).get(Skill.PILOT, 0)
            roll = self.rng.calculate_success(max(1, 1 + pilot_skill))
            if roll.get("success"):
                self.escape_route = "helicopter"
                self.helicopter_status = "ESCAPED"
                event_bus.emit(GameEvent(EventType.ESCAPE_SUCCESS, {
                    "game_state": self,
                    "route": "helicopter"
                }))
                return True, "You climb into the cockpit and gun the throttle. The chopper claws into the sky.", EventType.MESSAGE
            return False, "The engines cough and stall. You'll need to try again.", EventType.WARNING

        # Overland escape is only viable when the station is dark and no evac routes remain
        if not self.power_on and not self.radio_operational and not self.helicopter_operational:
            self.escape_route = "overland"
            self.overland_escape_turns = 3
            return True, "With Outpost 31 lost, you shoulder your pack and start the long walk into the ice. Survive 3 more hours.", EventType.MESSAGE

        return False, "The helicopter is down and the station isn't abandoned enough to risk an overland escape.", EventType.WARNING

    def cleanup(self):
        """Clean up game state and unsubscribe from events."""
        # Core Systems
        if hasattr(self, 'time_system') and self.time_system:
            self.time_system.cleanup()
        if hasattr(self, 'weather') and self.weather:
            self.weather.cleanup()
        if hasattr(self, 'sabotage') and self.sabotage:
            self.sabotage.cleanup()
        if hasattr(self, 'environmental_coordinator') and self.environmental_coordinator:
            self.environmental_coordinator.cleanup()
            
        # Social Systems
        if hasattr(self, 'trust_system') and self.trust_system:
            self.trust_system.cleanup()
        if hasattr(self, 'lynch_mob') and self.lynch_mob:
            self.lynch_mob.cleanup()
            
        # Feature Systems
        if hasattr(self, 'random_events') and self.random_events:
            self.random_events.cleanup()
        if hasattr(self, 'endgame') and self.endgame:
            self.endgame.cleanup()
        if hasattr(self, 'crafting') and self.crafting:
            self.crafting.cleanup()
        if hasattr(self, 'psychology') and self.psychology:
            self.psychology.cleanup()
        if hasattr(self, 'missionary') and self.missionary:
            self.missionary.cleanup()
        if hasattr(self, 'ai_system') and self.ai_system:
            self.ai_system.cleanup()
        if hasattr(self, 'alert_system') and self.alert_system:
            self.alert_system.cleanup()
        if hasattr(self, 'security_system') and self.security_system:
            self.security_system.cleanup()
        if hasattr(self, 'progression') and self.progression:
            self.progression.cleanup()
        if hasattr(self, 'audio') and self.audio:
            self.audio.cleanup()
        if hasattr(self, 'reporter') and self.reporter:
            self.reporter.cleanup()

    def check_win_condition(self):
        if self.last_ending_payload:
            return self.last_ending_payload.get("result") == "win", self.last_ending_payload.get("message")

        if not self.player or not self.player.is_alive:
            return False, None
        if self.player.is_infected and self.player.is_revealed:
            return False, None

        def msg(key, fallback):
            try:
                return self.endgame.states.get(key, {}).get("message", fallback)
            except Exception:
                return fallback

        if self.helicopter_status == "ESCAPED":
            return True, msg("ESCAPE", "You pilot the chopper through the storm, leaving the nightmare of Outpost 31 behind.")

        if self.rescue_signal_active and self.rescue_turns_remaining is not None and self.rescue_turns_remaining <= 0:
            if not self.power_on and getattr(self.sabotage, "power_sabotaged", False):
                return True, msg("PYRRHIC", "You flee into the ice as Outpost 31 dies behind you.")
            return True, msg("RESCUE", "Lights cut through the storm. The rescue team has arrived to extract you.")
            if self.escape_route == "overland":
                return True, "With the generators dead and the station ruined, you vanish into the whiteout."
            return True, "You pilot the chopper through the storm, leaving the nightmare of Outpost 31 behind."

        if self.escape_route == "overland" and self.overland_escape_turns == 0:
            return True, "With the generators dead and the station ruined, you vanish into the whiteout."

        if self.rescue_signal_active and self.rescue_turns_remaining is not None and self.rescue_turns_remaining <= 0:
            return True, "Lights cut through the storm. The rescue team has arrived to extract you."

        living_crew = [m for m in self.crew if m.is_alive]
        living_infected = [m for m in living_crew if m.is_infected and m != self.player]

        if len(living_crew) == 1 and living_crew[0] == self.player:
            return True, msg("SOLE_SURVIVOR", "Silence falls over the station. You are the only one left alive. The threat is gone... you hope.")

        if not living_infected and self.crew:
            total_infected = [m for m in self.crew if m.is_infected]
            if total_infected and all(not m.is_alive for m in total_infected):
                 return True, msg("EXTERMINATION", "All Things have been eliminated. Humanity survives... for now.")

        return False, None

    def check_lose_condition(self):
        if not self.player:
            return True, "MacReady is gone. The Thing has won."

        if not self.player.is_alive:
            return True, "MacReady is dead. The Thing spreads unchecked across the ice."

        if self.player.is_infected and self.player.is_revealed:
            return True, "MacReady has become one of Them. The imitation is perfect."

        return False, None

    def check_game_over(self):
        """Check for game over conditions. Returns (game_over, won, message)."""
        if self.last_ending_payload:
            payload = self.last_ending_payload
            return True, payload.get("result") == "win", payload.get("message")

        # Check lose conditions first
        lost, lose_message = self.check_lose_condition()
        if lost:
            return True, False, lose_message
        
        # Check win conditions
        won, win_message = self.check_win_condition()
        if won:
            return True, True, win_message
        
        # Game continues
        return False, False, None

    def to_dict(self):
        """Serialize game state to dictionary for saving."""
        if hasattr(self, "alert_system") and self.alert_system:
            # Mirror alert system fields for save visibility
            self.alert_status = "alert" if self.alert_system.is_active else "calm"
            self.alert_turns_remaining = self.alert_system.turns_remaining
        return {
            "_save_version": CURRENT_SAVE_VERSION,
            "save_version": CURRENT_SAVE_VERSION,
            "turn": self.turn,
            "difficulty": self.difficulty.value,
            "power_on": self.power_on,
            "paranoia_level": self.paranoia_level,
            "mode": self.mode.value,
            "helicopter_status": self.helicopter_status,
            "helicopter_operational": self.helicopter_operational,
            "radio_operational": self.radio_operational,
            "escape_route": self.escape_route,
            "overland_escape_turns": self.overland_escape_turns,
            "rescue_signal_active": self.rescue_signal_active,
            "rescue_turns_remaining": self.rescue_turns_remaining,
            "rescue_eta_turns": self.rescue_eta_turns,
            "alert_status": self.alert_status,
            "alert_turns_remaining": self.alert_turns_remaining,
            "rng": self.rng.to_dict(),
            "time_system": self.time_system.to_dict(),
            "station_map": self.station_map.to_dict(),
            "crew": [m.to_dict() for m in self.crew],
            "player_location": self.player.location if self.player else (0, 0),
            "journal": self.journal,
            "trust": self.trust_system.matrix if hasattr(self, "trust_system") else {},
            "crafting": self.crafting.to_dict() if hasattr(self.crafting, "to_dict") else {},
            "alert_system": self.alert_system.to_dict() if hasattr(self, "alert_system") else {},
            "security_system": self.security_system.to_dict() if hasattr(self, "security_system") else {},
            "security_log": self.security_log.to_dict() if hasattr(self, "security_log") else {}
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize game state from dictionary with defensive defaults and validation."""
        if not data or not isinstance(data, dict):
            return None

        save_version = data.get("save_version", data.get("_save_version", 0))

        difficulty_value = data.get("difficulty", Difficulty.NORMAL.value)
        try:
            difficulty = Difficulty(difficulty_value)
        except ValueError:
            difficulty = Difficulty.NORMAL

        game = cls(difficulty=difficulty)

        game.power_on = data.get("power_on", True)
        game.paranoia_level = data.get("paranoia_level", 0)

        mode_val = data.get("mode", GameMode.INVESTIGATIVE.value)
        try:
            game.mode = GameMode(mode_val)
        except ValueError:
            game.mode = GameMode.INVESTIGATIVE

        game.helicopter_status = data.get("helicopter_status", "BROKEN")
        game.helicopter_operational = data.get("helicopter_operational", True)
        game.radio_operational = data.get("radio_operational", True)
        game.helicopter_operational = data.get("helicopter_operational", game.helicopter_operational)
        game.radio_operational = data.get("radio_operational", game.radio_operational)
        game.escape_route = data.get("escape_route")
        game.overland_escape_turns = data.get("overland_escape_turns")
        game.rescue_signal_active = data.get("rescue_signal_active", False)
        game.rescue_turns_remaining = data.get("rescue_turns_remaining")
        game.turn = data.get("turn", getattr(game, "turn", 1))
        game.rescue_eta_turns = data.get("rescue_eta_turns", game.rescue_eta_turns)
        game.alert_status = data.get("alert_status", "calm")
        game.alert_status = data.get("alert_status", "CALM")
        game.alert_turns_remaining = data.get("alert_turns_remaining", 0)

        if "rng" in data:
            game.rng.from_dict(data["rng"])

        if "time_system" in data:
            game.time_system = TimeSystem.from_dict(data["time_system"])
        else:
            game.time_system.turn_count = data.get("turn", 1) - 1

        if "station_map" in data:
            game.station_map = StationMap.from_dict(data["station_map"])
        else:
            game.station_map = StationMap()

        crew_data = data.get("crew", [])
        if crew_data:
            game.crew = []
            for m_data in crew_data:
                try:
                    member = CrewMember.from_dict(m_data)
                except Exception:
                    name = m_data.get("name", "Unknown") if isinstance(m_data, dict) else "Unknown"
                    member = CrewMember(name, m_data.get("role", "None") if isinstance(m_data, dict) else "None", m_data.get("behavior_type", "Neutral") if isinstance(m_data, dict) else "Neutral")
                if member:
                    game.crew.append(member)
        else:
            game.crew = []

        game.player = next((m for m in game.crew if m.name == "MacReady"), None)
        if not game.player:
            fallback_player = CrewMember("MacReady", "Pilot", "Neutral")
            game.crew.insert(0, fallback_player)
            game.player = fallback_player

        if "player_location" in data and game.player:
            loc = data.get("player_location")
            if isinstance(loc, (list, tuple)) and len(loc) == 2:
                game.player.location = (loc[0], loc[1])

        game.journal = data.get("journal", [])

        if hasattr(game, "trust_system") and game.trust_system:
            game.trust_system.cleanup()
        game.trust_system = TrustMatrix(game.crew, thresholds=game.social_thresholds)
        trust_data = data.get("trust")
        if trust_data and isinstance(trust_data, dict):
            game.trust_system.matrix.update(trust_data)

        game.renderer.map = game.station_map
        game.parser.set_known_names([m.name for m in game.crew])
        game.room_states = RoomStateManager(list(game.station_map.rooms.keys()))
        game.crafting = CraftingSystem.from_dict(data.get("crafting"), game)
        game.security_log = SecurityLog.from_dict(data.get("security_log", {}))

        # Rehydrate security system state
        security_data = data.get("security_system")
        if security_data:
            if hasattr(game, "security_system") and game.security_system:
                game.security_system = SecuritySystem.from_dict(
                    security_data,
                    game_state=game,
                    existing_system=game.security_system
                )
            else:
                game.security_system = SecuritySystem.from_dict(security_data, game_state=game)

        if hasattr(game, "sabotage"):
            game.sabotage.radio_operational = game.radio_operational
            game.sabotage.radio_working = game.radio_operational
            game.sabotage.chopper_operational = game.helicopter_operational
            game.sabotage.helicopter_working = game.helicopter_operational
        # Restore alert system/state
        alert_data = data.get("alert_system", {})
        if hasattr(game, "alert_system") and game.alert_system:
            game.alert_system.cleanup()
        game.alert_system = AlertSystem.from_dict(alert_data, game)
        game.alert_status = data.get("alert_status", game.alert_status)
        game.alert_turns_remaining = data.get("alert_turns_remaining", game.alert_turns_remaining)
        if hasattr(game, "alert_system") and game.alert_system:
            game.alert_system.cleanup()
        game.alert_system = AlertSystem.from_dict(data.get("alert_system"), game)

        return game

# --- Game Loop ---
def main():
    """Main game loop - can be called from launcher or run directly"""
    game = GameState(seed=None)

    # Agent 5 Boot Sequence
    game.crt.boot_sequence()
    game.audio.ambient_loop(Sound.THRUM)

    # PALETTE UX: Situation Report (One-time)
    game.crt.output("\n--- SITUATION REPORT ---")
    game.crt.output("MISSION: Survive the winter. Trust no one.")
    game.crt.output("OBJECTIVE: Identify the infected. Do not let them escape.")
    game.crt.output("HINT: Type 'HELP' for a list of commands. Start by looking around.")
    game.crt.output("------------------------\n")

    while True:
        # Update CRT glitch based on paranoia
        game.crt.set_glitch_level(game.paranoia_level)

        player_room = game.station_map.get_room_name(*game.player.location)
        weather_status = game.weather.get_status()
        room_icons = game.room_states.get_status_icons(player_room)

        # Fix: TimeSystem lacks 'hour' property, calculate manually (Start 08:00)
        current_hour = (game.time_system.turn_count + 8) % 24
        game.crt.output(f"\n[TURN {game.turn}] MODE: {game.mode.value} | TIME: {current_hour:02}:00 | TEMP: {game.temperature:.1f}C | POWER: {'ON' if game.power_on else 'OFF'}")
        game.crt.output(f"[LOC: {player_room}] {room_icons}")
        game.crt.output(f"[{weather_status}]")

        try:
            prompt = game.crt.prompt("CMD")
            user_input = input(prompt).strip()
            if not user_input:
                continue

            # Use CommandParser
            parsed = game.parser.parse(user_input)
            if not parsed:
                suggestion = game.parser.suggest_correction(user_input)
                if suggestion:
                    print(f"Unknown command. {suggestion}")
                else:
                    print("I don't understand that command.")
                continue

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
        elif action == "HELP":
            game.crt.output(game.parser.get_help_text())
        elif action == "ADVANCE":
            game.advance_turn()
        elif action == "SAVE":
            slot = cmd[1] if len(cmd) > 1 else "auto"
            game.save_manager.save_game(game, slot)
        elif action == "LOAD":
            slot = cmd[1] if len(cmd) > 1 else "auto"
            loaded_game = game.save_manager.load_game(slot)
            if loaded_game:
                game.cleanup()
                game = loaded_game
                print("*** GAME LOADED ***")
        elif action == "STATUS":
            for m in game.crew:
                status = "Alive" if m.is_alive else "DEAD"
                msg = f"{m.name} ({m.role}): Loc {m.location} | HP: {m.health} | {status}"
                avg_trust = game.trust_system.get_average_trust(m.name)
                msg += f" | Trust: {avg_trust:.1f}"
                print(msg)
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
