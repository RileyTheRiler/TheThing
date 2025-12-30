"""
Meta-Progression System (Tier 10.1)
Tracks lifetime statistics and manages unlockable roles across game sessions.
Roles provide permanent bonuses that persist between games.
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from core.event_system import event_bus, EventType, GameEvent


# Meta progress file location
META_PROGRESS_FILE = "data/saves/meta_progress.json"
UNLOCKABLES_FILE = "data/unlockables.json"


@dataclass
class LifetimeStats:
    """Aggregate statistics across all game sessions for unlock tracking."""
    games_won: int = 0
    games_lost: int = 0
    things_killed: int = 0
    crew_members_saved: int = 0
    blood_tests_performed: int = 0
    systems_repaired: int = 0
    total_turns_survived: int = 0
    endings_achieved: Dict[str, int] = field(default_factory=dict)
    first_played: str = ""
    last_played: str = ""


@dataclass
class UnlockedRole:
    """Represents an unlocked role with its bonuses."""
    role_id: str
    name: str
    description: str
    bonuses: Dict[str, Any]
    unlocked_at: str = ""


class MetaProgressionSystem:
    """
    Manages meta-progression including lifetime stats and unlockable roles.
    
    Roles are unlocked by accumulating lifetime statistics across multiple
    game sessions. Once unlocked, roles can be selected at game start to
    provide permanent bonuses.
    """
    
    def __init__(self, progress_file: str = None, unlockables_file: str = None):
        self.progress_file = progress_file or META_PROGRESS_FILE
        self.unlockables_file = unlockables_file or UNLOCKABLES_FILE
        
        self.stats = LifetimeStats()
        self.unlocked_roles: Dict[str, UnlockedRole] = {}
        self.selected_role: Optional[str] = None
        self.role_definitions: Dict[str, dict] = {}
        
        self._load_role_definitions()
        self._load_progress()
        self._subscribe_events()
    
    def _subscribe_events(self):
        """Subscribe to game events for stat tracking."""
        event_bus.subscribe(EventType.COMBAT_LOG, self._on_combat)
        event_bus.subscribe(EventType.TEST_RESULT, self._on_blood_test)
        event_bus.subscribe(EventType.ENDING_REPORT, self._on_ending)
        event_bus.subscribe(EventType.REPAIR_COMPLETE, self._on_repair)
        event_bus.subscribe(EventType.TURN_ADVANCE, self._on_turn)
    
    def cleanup(self):
        """Unsubscribe from events."""
        event_bus.unsubscribe(EventType.COMBAT_LOG, self._on_combat)
        event_bus.unsubscribe(EventType.TEST_RESULT, self._on_blood_test)
        event_bus.unsubscribe(EventType.ENDING_REPORT, self._on_ending)
        event_bus.unsubscribe(EventType.REPAIR_COMPLETE, self._on_repair)
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self._on_turn)
    
    def _load_role_definitions(self):
        """Load role definitions from unlockables.json."""
        try:
            if os.path.exists(self.unlockables_file):
                with open(self.unlockables_file, 'r') as f:
                    data = json.load(f)
                    self.role_definitions = data.get("roles", {})
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load unlockables: {e}")
            self.role_definitions = {}
    
    def _load_progress(self):
        """Load meta-progression data from file."""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    
                    # Load lifetime stats
                    stats_data = data.get("stats", {})
                    self.stats = LifetimeStats(
                        games_won=stats_data.get("games_won", 0),
                        games_lost=stats_data.get("games_lost", 0),
                        things_killed=stats_data.get("things_killed", 0),
                        crew_members_saved=stats_data.get("crew_members_saved", 0),
                        blood_tests_performed=stats_data.get("blood_tests_performed", 0),
                        systems_repaired=stats_data.get("systems_repaired", 0),
                        total_turns_survived=stats_data.get("total_turns_survived", 0),
                        endings_achieved=stats_data.get("endings_achieved", {}),
                        first_played=stats_data.get("first_played", ""),
                        last_played=stats_data.get("last_played", "")
                    )
                    
                    # Load unlocked roles
                    for role_id, role_data in data.get("unlocked_roles", {}).items():
                        self.unlocked_roles[role_id] = UnlockedRole(
                            role_id=role_id,
                            name=role_data.get("name", role_id),
                            description=role_data.get("description", ""),
                            bonuses=role_data.get("bonuses", {}),
                            unlocked_at=role_data.get("unlocked_at", "")
                        )
                    
                    self.selected_role = data.get("selected_role")
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load meta progress: {e}")
    
    def save(self):
        """Save meta-progression data to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
            
            data = {
                "stats": asdict(self.stats),
                "unlocked_roles": {
                    role_id: asdict(role) 
                    for role_id, role in self.unlocked_roles.items()
                },
                "selected_role": self.selected_role
            }
            
            with open(self.progress_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save meta progress: {e}")
    
    def _on_combat(self, event: GameEvent):
        """Track Things killed from combat events."""
        target = event.payload.get("target")
        outcome = event.payload.get("outcome", "")
        
        if target and "killed" in outcome.lower():
            # Check if target was a Thing
            is_thing = event.payload.get("target_was_thing", False)
            if is_thing:
                self.stats.things_killed += 1
                self._check_unlocks()
    
    def _on_blood_test(self, event: GameEvent):
        """Track blood tests performed."""
        self.stats.blood_tests_performed += 1
        self._check_unlocks()
    
    def _on_repair(self, event: GameEvent):
        """Track systems repaired."""
        self.stats.systems_repaired += 1
        self._check_unlocks()
    
    def _on_turn(self, event: GameEvent):
        """Track turns survived."""
        self.stats.total_turns_survived += 1
        self._check_unlocks()
    
    def _on_ending(self, event: GameEvent):
        """Track game endings and wins/losses."""
        ending_type = event.payload.get("ending_type", "UNKNOWN")
        won = event.payload.get("won", False)
        crew_saved = event.payload.get("crew_saved", 0)
        
        # Track ending type
        self.stats.endings_achieved[ending_type] = \
            self.stats.endings_achieved.get(ending_type, 0) + 1
        
        # Track wins/losses
        if won:
            self.stats.games_won += 1
        else:
            self.stats.games_lost += 1
        
        # Track crew saved
        self.stats.crew_members_saved += crew_saved
        
        # Update timestamps
        now = datetime.now().isoformat()
        self.stats.last_played = now
        if not self.stats.first_played:
            self.stats.first_played = now
        
        self._check_unlocks()
        self.save()
    
    def _check_unlocks(self):
        """Check if any new roles should be unlocked."""
        for role_id, role_def in self.role_definitions.items():
            # Skip already unlocked or default role
            if role_id in self.unlocked_roles or role_id == "default":
                continue
            
            condition = role_def.get("unlock_condition")
            if not condition:
                continue
            
            stat_name = condition.get("stat")
            threshold = condition.get("threshold", 0)
            
            # Get current stat value
            current_value = getattr(self.stats, stat_name, 0)
            
            if current_value >= threshold:
                self._unlock_role(role_id, role_def)
    
    def _unlock_role(self, role_id: str, role_def: dict):
        """Unlock a new role."""
        self.unlocked_roles[role_id] = UnlockedRole(
            role_id=role_id,
            name=role_def.get("name", role_id),
            description=role_def.get("description", ""),
            bonuses=role_def.get("bonuses", {}),
            unlocked_at=datetime.now().isoformat()
        )
        
        # Emit unlock event
        event_bus.emit(GameEvent(
            EventType.META_UNLOCK,
            payload={
                "role_id": role_id,
                "role_name": role_def.get("name", role_id),
                "description": role_def.get("description", "")
            }
        ))
        
        self.save()
        print(f"[META] Unlocked role: {role_def.get('name', role_id)}!")
    
    def select_role(self, role_id: str) -> bool:
        """Select a role for the next game."""
        if role_id == "default" or role_id in self.unlocked_roles:
            self.selected_role = role_id
            self.save()
            return True
        return False
    
    def get_selected_role_bonuses(self) -> Dict[str, Any]:
        """Get bonuses for the currently selected role."""
        if not self.selected_role or self.selected_role == "default":
            return {}
        
        role = self.unlocked_roles.get(self.selected_role)
        if role:
            return role.bonuses
        
        return {}
    
    def get_combat_modifier(self) -> int:
        """Get combat roll modifier from selected role."""
        bonuses = self.get_selected_role_bonuses()
        return bonuses.get("combat_modifier", 0)
    
    def get_starting_items(self) -> List[str]:
        """Get starting items from selected role."""
        bonuses = self.get_selected_role_bonuses()
        return bonuses.get("starting_items", [])
    
    def get_repair_time_modifier(self) -> int:
        """Get repair time modifier from selected role."""
        bonuses = self.get_selected_role_bonuses()
        return bonuses.get("repair_time_modifier", 0)
    
    def get_max_health_modifier(self) -> int:
        """Get max health modifier from selected role."""
        bonuses = self.get_selected_role_bonuses()
        return bonuses.get("max_health_modifier", 0)
    
    def get_available_roles(self) -> List[Dict[str, Any]]:
        """Get list of all roles with their unlock status."""
        roles = []
        
        for role_id, role_def in self.role_definitions.items():
            is_unlocked = role_id == "default" or role_id in self.unlocked_roles
            condition = role_def.get("unlock_condition")
            
            progress = 0
            if condition:
                stat_name = condition.get("stat")
                threshold = condition.get("threshold", 1)
                current = getattr(self.stats, stat_name, 0)
                progress = min(100, int((current / threshold) * 100))
            
            roles.append({
                "id": role_id,
                "name": role_def.get("name", role_id),
                "description": role_def.get("description", ""),
                "unlocked": is_unlocked,
                "selected": self.selected_role == role_id,
                "condition": condition,
                "progress": progress if not is_unlocked else 100,
                "bonuses": role_def.get("bonuses", {})
            })
        
        return roles
    
    def get_stats_summary(self) -> str:
        """Get a summary of lifetime statistics."""
        lines = [
            "=== LIFETIME STATISTICS ===",
            f"Games Won: {self.stats.games_won}",
            f"Games Lost: {self.stats.games_lost}",
            f"Things Killed: {self.stats.things_killed}",
            f"Crew Members Saved: {self.stats.crew_members_saved}",
            f"Blood Tests Performed: {self.stats.blood_tests_performed}",
            f"Systems Repaired: {self.stats.systems_repaired}",
            f"Total Turns Survived: {self.stats.total_turns_survived}",
        ]
        
        if self.stats.endings_achieved:
            lines.append("")
            lines.append("Endings Achieved:")
            for ending, count in self.stats.endings_achieved.items():
                lines.append(f"  {ending}: {count}")
        
        return "\n".join(lines)
    
    def record_game_end(self, won: bool, crew_saved: int = 0, ending_type: str = "UNKNOWN"):
        """Manually record a game ending (for integration with existing systems)."""
        event = GameEvent(
            EventType.ENDING_REPORT,
            payload={
                "ending_type": ending_type,
                "won": won,
                "crew_saved": crew_saved
            }
        )
        self._on_ending(event)


# Global meta-progression instance
meta_progress = MetaProgressionSystem()
