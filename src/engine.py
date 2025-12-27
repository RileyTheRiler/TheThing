from systems.missionary import MissionarySystem
from systems.psychology import PsychologySystem
from core.resolution import Attribute, Skill, ResolutionSystem
from systems.social import TrustMatrix, LynchMobSystem, DialogueManager
from systems.architect import RandomnessEngine, GameMode, TimeSystem, Difficulty, DifficultySettings
from systems.persistence import SaveManager
from core.event_system import event_bus, EventType, GameEvent

# Agent 6: Dungeon Master Systems
from systems.weather import WeatherSystem
from systems.sabotage import SabotageManager
from systems.room_state import RoomStateManager, RoomState
from systems.random_events import RandomEventSystem

# Agent 4: Forensics
from systems.forensics import BiologicalSlipGenerator, BloodTestSim, ForensicDatabase, EvidenceLog

# Terminal Designer Systems (Agent 5)
from ui.renderer import TerminalRenderer
from ui.crt_effects import CRTOutput
from ui.command_parser import CommandParser
from ui.message_reporter import MessageReporter
from audio.audio_manager import AudioManager, Sound

# Entity Classes
from entities.item import Item
from entities.crew_member import CrewMember
from entities.station_map import StationMap

import json
import os
import sys
import random
import time


class GameState:
    def __init__(self, seed=None, difficulty=Difficulty.NORMAL):
        self.rng = RandomnessEngine(seed)
        self.time_system = TimeSystem()
        self.save_manager = SaveManager()

        # Store difficulty and get settings
        self.difficulty = difficulty
        self.difficulty_settings = DifficultySettings.get_all(difficulty)

        self.turn = 1
        self.power_on = True
        self.blood_bank_destroyed = False
        self.paranoia_level = self.difficulty_settings["starting_paranoia"]
        self.mode = GameMode.INVESTIGATIVE

        self.station_map = StationMap()
        self.crew = self._initialize_crew()
        self.journal = []

        # Tier 6.3: Alternative Endings State
        self.helicopter_status = "BROKEN"  # BROKEN, FIXED, ESCAPED
        self.rescue_signal_active = False
        self.rescue_turns_remaining = None

        self.player = next((m for m in self.crew if m.name == "MacReady"), None)
        self._initialize_items()
        self._initialize_infection()
        
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
        self.reporter = MessageReporter(self.crt)  # Tier 2.6: Event-based reporting
        
        # Agent 6: DM Systems (Now Event-Driven)
        self.weather = WeatherSystem()
        self.sabotage = SabotageManager()
        self.room_states = RoomStateManager(list(self.station_map.rooms.keys()))
        self.random_events = RandomEventSystem(self.rng)  # Tier 6.2

        # Integration helper
        self.resolution = ResolutionSystem()
        
        # Hook Listeners
        event_bus.subscribe(EventType.BIOLOGICAL_SLIP, self.on_biological_slip)
        event_bus.subscribe(EventType.LYNCH_MOB_TRIGGER, self.on_lynch_mob_trigger)

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
        """Initialize items in rooms for a new game."""
        items = [
            # Original items
            ("Whiskey", "J&B Scotch Bottle.", "Rec Room", None, 0),
            ("Flamethrower", "Standard issue M2A1.", "Rec Room", Skill.FIREARMS, 3),
            ("Scalpel", "Surgical steel.", "Infirmary", Skill.MELEE, 1),
            ("Wire", "Copper wire roll.", "Generator", None, 0),
            # New room items
            ("Radio", "Long-range radio equipment.", "Radio Room", None, 0),
            ("Headphones", "Heavy-duty radio headphones.", "Radio Room", None, 0),
            ("Fuel Can", "Kerosene for the generator.", "Storage", None, 0),
            ("Toolbox", "Basic mechanical tools.", "Storage", Skill.MELEE, 1),
            ("Rope", "Heavy nylon rope, 50 feet.", "Storage", None, 0),
            ("Lantern", "Battery-powered emergency lantern.", "Storage", None, 0),
            ("Microscope", "High-powered lab microscope.", "Lab", None, 0),
            ("Petri Dishes", "Stack of sterile petri dishes.", "Lab", None, 0),
            ("Fire Axe", "Emergency fire axe.", "Mess Hall", Skill.MELEE, 2),
            ("Canned Food", "Assorted canned goods.", "Mess Hall", None, 0),
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

    def _initialize_infection(self):
        """Infect initial crew members based on difficulty settings."""
        # Don't infect the player
        eligible = [m for m in self.crew if m.name != "MacReady"]
        if not eligible:
            return

        # Determine how many to infect based on difficulty
        min_infected = self.difficulty_settings["initial_infected_min"]
        max_infected = self.difficulty_settings["initial_infected_max"]
        num_infected = random.randint(min_infected, min(max_infected, len(eligible)))

        # Randomly select crew to infect
        infected_crew = random.sample(eligible, num_infected)
        for member in infected_crew:
            member.is_infected = True

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

        # 6. Random Events Check (Tier 6.2)
        random_event = self.random_events.check_for_event(self)
        if random_event:
            self.random_events.execute_event(random_event, self)

        # 7. Update Rescue Timer
        if self.rescue_signal_active and self.rescue_turns_remaining is not None:
            self.rescue_turns_remaining -= 1
            if self.rescue_turns_remaining == 5:
                self.reporter.report_event("RADIO", "Rescue ETA updated: 5 hours out.", priority=True)
            elif self.rescue_turns_remaining == 1:
                self.reporter.report_event("RADIO", "Rescue team landing imminent!", priority=True)

        # 8. Auto-save every 5 turns
        if self.turn % 5 == 0 and hasattr(self, 'save_manager'):
            try:
                self.save_manager.save_game(self, "autosave")
            except Exception:
                pass  # Don't interrupt gameplay on save failure

    def attempt_repair_helicopter(self) -> str:
        """Attempt to repair the helicopter in the Hangar."""
        player_room = self.station_map.get_room_name(*self.player.location)
        if player_room != "Hangar":
            return "You must be in the Hangar to repair the helicopter."

        if self.helicopter_status != "BROKEN":
            return "The helicopter is already operational."

        # Check for required items
        has_wire = any(i.name == "Wire" for i in self.player.inventory)
        has_fuel = any(i.name == "Fuel Can" for i in self.player.inventory)

        if not has_wire or not has_fuel:
            missing = []
            if not has_wire: missing.append("Wire (electrical repair)")
            if not has_fuel: missing.append("Fuel Can (refueling)")
            return f"Cannot repair. Missing: {', '.join(missing)}."

        # Skill Check (Mechanics/Pilot/Repair)
        # Primary: Mechanics or Repair. Bonus for Pilot.
        skill = Skill.MECHANICS if Skill.MECHANICS in self.player.skills else Skill.REPAIR
        attribute = Skill.get_attribute(skill)

        # Difficulty 3 (Challenging)
        dice_pool = self.player.attributes.get(attribute, 1) + self.player.skills.get(skill, 0)

        # Bonus for Pilot skill
        if Skill.PILOT in self.player.skills:
             dice_pool += 1

        successes = self.rng.calculate_success(dice_pool)['success_count']

        if successes >= 2:
            self.helicopter_status = "FIXED"
            # Consume items
            self.player.remove_item("Wire")
            self.player.remove_item("Fuel Can")
            return "Success! You've repaired the electrical system and refueled the chopper. It's ready to fly."
        else:
            return "Repair failed. It's more complicated than it looks. You need to focus."

    def attempt_radio_signal(self) -> str:
        """Attempt to signal for rescue using the Radio."""
        player_room = self.station_map.get_room_name(*self.player.location)
        if player_room != "Radio Room":
            return "You need to be in the Radio Room."

        if not self.power_on:
            return "The radio is dead. No power."

        if self.rescue_signal_active:
            return f"Rescue already signaled. ETA: {self.rescue_turns_remaining} turns."

        if hasattr(self, 'sabotage') and self.sabotage and not self.sabotage.radio_operational:
            return "The radio equipment is sabotaged. It won't transmit."

        # Skill Check (Comms)
        skill = Skill.COMMS
        attribute = Skill.get_attribute(skill)

        dice_pool = self.player.attributes.get(attribute, 1) + self.player.skills.get(skill, 0)
        successes = self.rng.calculate_success(dice_pool)['success_count']

        if successes >= 1:
            self.rescue_signal_active = True
            self.rescue_turns_remaining = 15  # 15 turns to rescue
            return "Signal established! McMurdo acknowledges. Rescue team inbound. ETA: 15 hours (turns)."
        else:
            return "Static. Just static. You can't punch through the storm interference."

    def attempt_escape(self) -> str:
        """Attempt to fly the helicopter to safety."""
        player_room = self.station_map.get_room_name(*self.player.location)
        if player_room != "Hangar":
            return "You are not near the helicopter."

        if self.helicopter_status == "BROKEN":
            return "The helicopter is broken. It won't fly."

        # Skill Check (Pilot)
        skill = Skill.PILOT
        attribute = Skill.get_attribute(skill)

        dice_pool = self.player.attributes.get(attribute, 1) + self.player.skills.get(skill, 0)

        # Weather penalty
        if self.weather.get_visibility() < 0.3:  # WHITEOUT condition
            dice_pool -= 3
        elif self.weather.get_visibility() < 0.6: # Poor
            dice_pool -= 1

        if dice_pool < 1: dice_pool = 1

        successes = self.rng.calculate_success(dice_pool)['success_count']

        if successes >= 1:
            self.helicopter_status = "ESCAPED"
            return "Engines spooling up... You lift off into the Antarctic night."
        else:
            return "The wind is too strong! You can't get lift-off. Wait for a break in the weather."

    def check_win_condition(self):
        """
        WIN:
        1. All infected crew are dead/neutralized AND player is alive and human (Extermination).
        2. Player escapes via Helicopter (Escape).
        3. Rescue team arrives and player is alive/human (Rescue).
        4. Player is Sole Survivor (Grim Victory).

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

        # 3. Sole Survivor (Everyone else dead)
        if len(living_crew) == 1 and living_crew[0] == self.player:
            return True, "Silence falls over the station. You are the only one left alive. The threat is gone... you hope."

        # 4. Extermination (All Things dead)
        if not living_infected:
            total_infected = [m for m in self.crew if m.is_infected]
            if total_infected:
                return True, "All Things have been eliminated. Humanity survives... for now."

        return False, None

    def check_lose_condition(self):
        """
        LOSE: Player is dead OR player is infected and revealed.
        Returns: (lost: bool, message: str)
        """
        if not self.player:
            return True, "MacReady is gone. The Thing has won."

        if not self.player.is_alive:
            return True, "MacReady has died. The Thing spreads unchecked across the ice."

        if self.player.is_infected and self.player.is_revealed:
            return True, "MacReady has become one of Them. The imitation is perfect."

        # Check if everyone is dead
        living_crew = [m for m in self.crew if m.is_alive]
        if len(living_crew) == 0:
            return True, "The station is silent. No one survived."

        # Check if everyone (including player) is infected
        living_humans = [m for m in self.crew if m.is_alive and not m.is_infected]
        if not living_humans:
            return True, "There are no humans left. The Thing has won."

        return False, None

    def check_game_over(self):
        """
        Check both win and lose conditions.
        Returns: (game_over: bool, won: bool, message: str)
        """
        lost, lose_msg = self.check_lose_condition()
        if lost:
            return True, False, lose_msg

        won, win_msg = self.check_win_condition()
        if won:
            return True, True, win_msg

        return False, False, None

    def to_dict(self):
        return {
            "turn": self.turn,
            "power_on": self.power_on,
            "paranoia_level": self.paranoia_level,
            "mode": self.mode.value,
            "difficulty": self.difficulty.value,
            "temperature": self.time_system.temperature,
            "helicopter_status": self.helicopter_status,
            "rescue_signal_active": self.rescue_signal_active,
            "rescue_turns_remaining": self.rescue_turns_remaining,
            "rng": self.rng.to_dict(),
            "time_system": self.time_system.to_dict(),
            "station_map": self.station_map.to_dict(),
            "crew": [m.to_dict() for m in self.crew],
            "journal": self.journal,
            "trust": self.trust_system.matrix  # Assuming dict
        }

    @classmethod
    def from_dict(cls, data):
        # Get difficulty from save or default to NORMAL
        difficulty_value = data.get("difficulty", "Normal")
        difficulty = Difficulty(difficulty_value)

        game = cls(difficulty=difficulty)  # Init with saved difficulty
        # Overwrite content
        game.turn = data["turn"]
        game.power_on = data["power_on"]
        game.paranoia_level = data["paranoia_level"]
        game.mode = GameMode(data["mode"])

        game.helicopter_status = data.get("helicopter_status", "BROKEN")
        game.rescue_signal_active = data.get("rescue_signal_active", False)
        game.rescue_turns_remaining = data.get("rescue_turns_remaining")

        game.rng.from_dict(data["rng"])
        game.time_system = TimeSystem.from_dict(data["time_system"])

        game.station_map = StationMap.from_dict(data["station_map"])

        game.crew = [CrewMember.from_dict(m) for m in data["crew"]]
        # Re-link player
        game.player = next((m for m in game.crew if m.name == "MacReady"), None)

        game.journal = data["journal"]
        game.trust_system.matrix = data.get("trust", {})
        
        return game

