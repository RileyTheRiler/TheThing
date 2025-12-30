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
from systems.alert import AlertSystem
from systems.security import SecuritySystem
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
            direction = "UP" if clamped > previous_value else "DOWN"
            event_bus.emit(GameEvent(EventType.PARANOIA_THRESHOLD_CROSSED, {
                "value": clamped,
                "previous_value": previous_value,
                "bucket": bucket_label(new_bucket),
                "thresholds": list(self.social_thresholds.paranoia_thresholds),
                "direction": direction,
                "threshold": self.social_thresholds.paranoia_thresholds[new_bucket-1] if direction == "UP" else self.social_thresholds.paranoia_thresholds[new_bucket]
            }))

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
            "_save_version": CURRENT_SAVE_VERSION,
            "save_version": CURRENT_SAVE_VERSION,
            "turn": self.turn,
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
            "player_location": self.player.location if self.player else (0, 0),
            "journal": self.journal,
            "trust": self.trust_system.matrix if hasattr(self, "trust_system") else {},
            "crafting": self.crafting.to_dict() if hasattr(self.crafting, "to_dict") else {},
            "alert_system": self.alert_system.to_dict() if hasattr(self, "alert_system") else {},
            "security_system": self.security_system.to_dict() if hasattr(self, "security_system") else {}
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
        game.rescue_signal_active = data.get("rescue_signal_active", False)
        game.rescue_turns_remaining = data.get("rescue_turns_remaining")
        game.turn = data.get("turn", getattr(game, "turn", 1))

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
