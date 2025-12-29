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
from systems.architect import RandomnessEngine, GameMode, TimeSystem, Difficulty, DifficultySettings
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
from systems.dialogue import DialogueSystem

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
        # Fix: TimeSystem lacks 'hour' property, calculate manually (Start 08:00)
        current_hour = (game_state.time_system.turn_count + 8) % 24
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

    @property
    def temperature(self):
        return self.time_system.temperature if hasattr(self, "time_system") else -40.0

    def __init__(self, seed=None, difficulty=Difficulty.NORMAL, characters_path=None, start_hour=None, thresholds: SocialThresholds = None):
        # 1. Pre-initialization of essential attributes to avoid AttributeErrors in setters/listeners
        self.social_thresholds = thresholds or SocialThresholds()
        self.rng = RandomnessEngine(seed)
        self.player = None
        self.crew = []
        self._paranoia_level = 0
        self.design_registry = DesignBriefRegistry()
        self.action_cooldowns = {}
        
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
        self.paranoia_level = self.difficulty_settings["starting_paranoia"]
        self.mode = GameMode.INVESTIGATIVE
        # self.verbosity = Verbosity.STANDARD

        # 5. Core Simulation Systems
        self.station_map = StationMap()
        self.weather = WeatherSystem()
        self.sabotage = SabotageManager(self.difficulty_settings)
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
        self.stealth = StealthSystem()
        self.stealth_system = self.stealth  # Alias for systems expecting stealth_system attr
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
        self.turn_behavior_inventory = {"weather": 0, "sabotage": 0, "ai": 0, "random_events": 0}

        # 9. Narrative/Persistence
        self.helicopter_status = "BROKEN"
        self.rescue_signal_active = False
        self.rescue_turns_remaining = None 
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
        
        self.paranoia_level = min(100, self.paranoia_level + 1)
        
        # Advance time, environment, and emit TURN_ADVANCE via the TimeSystem
        self.time_system.advance_turn(self.power_on, game_state=self, rng=self.rng)
        if power_on is not None:
            self.power_on = power_on

        # TimeSystem and others react to TURN_ADVANCE event
        turn_inventory = {"weather": 0, "sabotage": 0, "ai": 0, "random_events": 0, "random_event_triggered": None}

        event_bus.emit(GameEvent(EventType.TURN_ADVANCE, {
            "game_state": self,
            "rng": self.rng,
            "turn": self.turn
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
            self.rescue_turns_remaining -= 1
            if self.rescue_turns_remaining == 5:
                event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Rescue ETA updated: 5 hours out."}))
            elif self.rescue_turns_remaining == 1:
                event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Rescue team landing imminent!"}))
            if self.rescue_turns_remaining <= 0:
                self.rescue_turns_remaining = 0
                event_bus.emit(GameEvent(EventType.REPAIR_COMPLETE, {
                    "status": self.helicopter_status,
                    "turn": self.turn
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
        if hasattr(self, 'audio') and self.audio:
            self.audio.cleanup()
        if hasattr(self, 'reporter') and self.reporter:
            self.reporter.cleanup()

    def check_win_condition(self):
        if not self.player or not self.player.is_alive:
            return False, None
        if self.player.is_infected and self.player.is_revealed:
            return False, None

        if self.helicopter_status == "ESCAPED":
            return True, "You pilot the chopper through the storm, leaving the nightmare of Outpost 31 behind."

        if self.rescue_signal_active and self.rescue_turns_remaining <= 0:
            return True, "Lights cut through the storm. The rescue team has arrived to extract you."

        living_crew = [m for m in self.crew if m.is_alive]
        living_infected = [m for m in living_crew if m.is_infected and m != self.player]

        if len(living_crew) == 1 and living_crew[0] == self.player:
            return True, "Silence falls over the station. You are the only one left alive. The threat is gone... you hope."

        if not living_infected and self.crew:
            total_infected = [m for m in self.crew if m.is_infected]
            if total_infected and all(not m.is_alive for m in total_infected):
                 return True, "All Things have been eliminated. Humanity survives... for now."

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
        return {
            "difficulty": self.difficulty.value,
            "power_on": self.power_on,
            "paranoia_level": self.paranoia_level,
            "mode": self.mode.value,
            "helicopter_status": self.helicopter_status,
            "rescue_signal_active": self.rescue_signal_active,
            "rescue_turns_remaining": self.rescue_turns_remaining,
            "rng": self.rng.to_dict(),
            "time_system": self.time_system.to_dict(),
            "station_map": self.station_map.to_dict(),
            "crew": [m.to_dict() for m in self.crew],
            "journal": self.journal,
            "trust": self.trust_system.matrix if hasattr(self, "trust_system") else {},
            "crafting": self.crafting.to_dict() if hasattr(self.crafting, "to_dict") else {}
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize game state from dictionary with defensive defaults and validation."""
        if not data or not isinstance(data, dict):
            return None

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
        game.rescue_signal_active = data.get("rescue_signal_active", False)
        game.rescue_turns_remaining = data.get("rescue_turns_remaining")

        if "rng" in data:
            game.rng.from_dict(data["rng"])

        if "time_system" in data:
            game.time_system = TimeSystem.from_dict(data["time_system"])
        else:
            game.time_system.turn_count = data.get("turn", 1) - 1

        if "station_map" in data:
            game.station_map = StationMap.from_dict(data["station_map"])

        crew_data = data.get("crew", [])
        if crew_data:
            game.crew = []
            for m_data in crew_data:
                member = CrewMember.from_dict(m_data)
                if member:
                    game.crew.append(member)

        game.player = next((m for m in game.crew if m.name == "MacReady"), None)
        if not game.player and game.crew:
            game.player = game.crew[0]

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
            data = game.save_manager.load_game(slot)
            if data:
                game = GameState.from_dict(data)
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
        elif action == "HEAT":
            print(game.forensics.blood_test.heat_wire())
        elif action == "TEST":
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
        elif action == "TALK":
            for m in game.crew:
                room = game.station_map.get_room_name(*m.location)
                if room == player_room:
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
                        result = game.player.roll_check(assoc_attr, skill_enum, game.rng, game.resolution)
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
                    att_res = game.player.roll_check(att_attr, w_skill, game.rng, game.resolution)

                    def_skill = Skill.MELEE
                    def_attr = Attribute.PROWESS

                    def_res = target.roll_check(def_attr, def_skill, game.rng, game.resolution)

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
        else:
            print("Unknown command. Try: MOVE, LOOK, GET, DROP, USE, INV, TAG, TEST, HEAT, APPLY, ATTACK, STATUS, SAVE, LOAD, EXIT")
