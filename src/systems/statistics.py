"""
Game Statistics System (Tier 6.4)
Tracks gameplay statistics across sessions: kills, tests, turns survived, etc.
Statistics persist to a JSON file.
"""

import os
import json
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from core.event_system import event_bus, EventType, GameEvent


# Statistics file location
STATS_FILE = os.path.expanduser("~/.thething_stats.json")


@dataclass
class GameSessionStats:
    """Statistics for a single game session."""
    start_time: str = ""
    end_time: str = ""
    difficulty: str = "Normal"
    outcome: str = ""  # "victory", "death", "infection", "quit"
    turns_survived: int = 0
    things_killed: int = 0
    humans_killed: int = 0  # Tragic mistakes
    blood_tests_performed: int = 0
    things_revealed_by_test: int = 0
    accusations_made: int = 0
    successful_accusations: int = 0
    barricades_built: int = 0
    items_collected: int = 0
    damage_dealt: int = 0
    damage_taken: int = 0
    rooms_visited: int = 0
    random_events_witnessed: int = 0
    stealth_encounters: int = 0
    crafting_successes: int = 0
    ending_type: str = ""


@dataclass
class CareerStats:
    """Aggregate statistics across all game sessions."""
    total_games: int = 0
    victories: int = 0
    deaths: int = 0
    infections: int = 0
    quits: int = 0
    total_turns: int = 0
    total_things_killed: int = 0
    total_humans_killed: int = 0
    total_blood_tests: int = 0
    total_things_revealed: int = 0
    best_survival_turns: int = 0
    fastest_victory_turns: int = 999999
    total_stealth_encounters: int = 0
    total_crafting_successes: int = 0
    ending_types_witnessed: Dict[str, int] = field(default_factory=dict)
    sessions: List[Dict] = field(default_factory=list)


class StatisticsManager:
    """Manages game statistics tracking and persistence."""

    def __init__(self):
        self.career = CareerStats()
        self.current_session: Optional[GameSessionStats] = None
        self._visited_rooms = set()
        self.load()
        self._subscribe_events()

    def _subscribe_events(self):
        """Subscribe to game events for automatic tracking."""
        event_bus.subscribe(EventType.COMBAT_LOG, self._on_combat)
        event_bus.subscribe(EventType.TEST_RESULT, self._on_blood_test)
        event_bus.subscribe(EventType.BARRICADE_ACTION, self._on_barricade)
        event_bus.subscribe(EventType.ITEM_PICKUP, self._on_item_pickup)
        event_bus.subscribe(EventType.STEALTH_REPORT, self._on_stealth_report)
        event_bus.subscribe(EventType.CRAFTING_REPORT, self._on_crafting_report)
        event_bus.subscribe(EventType.ENDING_REPORT, self._on_ending_report)

    def load(self):
        """Load career statistics from file."""
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, 'r') as f:
                    data = json.load(f)
                    # Reconstruct CareerStats from dict
                    self.career = CareerStats(
                        total_games=data.get('total_games', 0),
                        victories=data.get('victories', 0),
                        deaths=data.get('deaths', 0),
                        infections=data.get('infections', 0),
                        quits=data.get('quits', 0),
                        total_turns=data.get('total_turns', 0),
                        total_things_killed=data.get('total_things_killed', 0),
                        total_humans_killed=data.get('total_humans_killed', 0),
                        total_blood_tests=data.get('total_blood_tests', 0),
                        total_things_revealed=data.get('total_things_revealed', 0),
                        best_survival_turns=data.get('best_survival_turns', 0),
                        fastest_victory_turns=data.get('fastest_victory_turns', 999999),
                        sessions=data.get('sessions', [])[-20:]  # Keep last 20
                    )
        except (IOError, json.JSONDecodeError):
            pass  # Use defaults

    def save(self):
        """Save career statistics to file."""
        try:
            data = asdict(self.career)
            # Only keep last 20 sessions to limit file size
            data['sessions'] = data['sessions'][-20:]
            with open(STATS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass  # Can't save

    def start_session(self, difficulty: str = "Normal"):
        """Start tracking a new game session."""
        self.current_session = GameSessionStats(
            start_time=datetime.now().isoformat(),
            difficulty=difficulty
        )
        self._visited_rooms = set()

    def end_session(self, outcome: str, turns: int):
        """End the current session and update career stats."""
        if not self.current_session:
            return

        self.current_session.end_time = datetime.now().isoformat()
        self.current_session.outcome = outcome
        self.current_session.turns_survived = turns
        self.current_session.rooms_visited = len(self._visited_rooms)

        # Update career stats
        self.career.total_games += 1
        self.career.total_turns += turns
        self.career.total_things_killed += self.current_session.things_killed
        self.career.total_humans_killed += self.current_session.humans_killed
        self.career.total_blood_tests += self.current_session.blood_tests_performed
        self.career.total_things_revealed += self.current_session.things_revealed_by_test
        self.career.total_stealth_encounters += self.current_session.stealth_encounters
        self.career.total_crafting_successes += self.current_session.crafting_successes
        
        if self.current_session.ending_type:
            etype = self.current_session.ending_type
            self.career.ending_types_witnessed[etype] = self.career.ending_types_witnessed.get(etype, 0) + 1

        if outcome == "victory":
            self.career.victories += 1
            if turns < self.career.fastest_victory_turns:
                self.career.fastest_victory_turns = turns
        elif outcome == "death":
            self.career.deaths += 1
        elif outcome == "infection":
            self.career.infections += 1
        else:
            self.career.quits += 1

        if turns > self.career.best_survival_turns:
            self.career.best_survival_turns = turns

        # Store session summary
        self.career.sessions.append(asdict(self.current_session))

        self.save()
        self.current_session = None

    def record_room_visit(self, room_name: str):
        """Record visiting a room."""
        self._visited_rooms.add(room_name)

    def record_kill(self, was_thing: bool):
        """Record a kill."""
        if self.current_session:
            if was_thing:
                self.current_session.things_killed += 1
            else:
                self.current_session.humans_killed += 1

    def record_blood_test(self, revealed_thing: bool):
        """Record a blood test."""
        if self.current_session:
            self.current_session.blood_tests_performed += 1
            if revealed_thing:
                self.current_session.things_revealed_by_test += 1

    def record_accusation(self, successful: bool):
        """Record an accusation."""
        if self.current_session:
            self.current_session.accusations_made += 1
            if successful:
                self.current_session.successful_accusations += 1

    def record_damage(self, dealt: int = 0, taken: int = 0):
        """Record damage dealt or taken."""
        if self.current_session:
            self.current_session.damage_dealt += dealt
            self.current_session.damage_taken += taken

    def record_random_event(self):
        """Record witnessing a random event."""
        if self.current_session:
            self.current_session.random_events_witnessed += 1

    # Event handlers
    def _on_combat(self, event: GameEvent):
        """Track combat statistics from events."""
        damage = event.payload.get('damage', 0)
        if damage > 0:
            # Assume player dealt damage for now
            self.record_damage(dealt=damage)

    def _on_blood_test(self, event: GameEvent):
        """Track blood test from events."""
        infected = event.payload.get('infected', False)
        self.record_blood_test(infected)

    def _on_barricade(self, event: GameEvent):
        """Track barricade building."""
        if self.current_session and event.payload.get('action') == 'built':
            self.current_session.barricades_built += 1

    def _on_item_pickup(self, event: GameEvent):
        """Track item collection."""
        if self.current_session:
            self.current_session.items_collected += 1

    def _on_stealth_report(self, event: GameEvent):
        """Track stealth encounters."""
        if self.current_session:
            self.current_session.stealth_encounters += 1

    def _on_crafting_report(self, event: GameEvent):
        """Track crafting successes."""
        if self.current_session and event.payload.get('event') == 'completed':
            self.current_session.crafting_successes += 1

    def _on_ending_report(self, event: GameEvent):
        """Track ending types."""
        if self.current_session:
            self.current_session.ending_type = event.payload.get('ending_type', "UNKNOWN")

    def get_current_session_summary(self) -> str:
        """Get a summary of the current session."""
        if not self.current_session:
            return "No active session."

        s = self.current_session
        lines = [
            "=== CURRENT SESSION ===",
            f"Difficulty: {s.difficulty}",
            f"Turns: {s.turns_survived}",
            f"Things Killed: {s.things_killed}",
            f"Blood Tests: {s.blood_tests_performed}",
            f"Rooms Visited: {len(self._visited_rooms)}",
        ]
        return "\n".join(lines)

    def get_career_summary(self) -> str:
        """Get a summary of career statistics."""
        c = self.career
        win_rate = (c.victories / max(1, c.total_games)) * 100

        lines = [
            "=== CAREER STATISTICS ===",
            f"Total Games: {c.total_games}",
            f"Victories: {c.victories} ({win_rate:.1f}%)",
            f"Deaths: {c.deaths}",
            f"Infections: {c.infections}",
            "",
            f"Total Turns Played: {c.total_turns}",
            f"Best Survival: {c.best_survival_turns} turns",
        ]

        if c.victories > 0 and c.fastest_victory_turns < 999999:
            lines.append(f"Fastest Victory: {c.fastest_victory_turns} turns")

        lines.extend([
            "",
            f"Total Things Killed: {c.total_things_killed}",
            f"Total Blood Tests: {c.total_blood_tests}",
            f"Things Revealed by Test: {c.total_things_revealed}",
        ])

        if c.total_humans_killed > 0:
            lines.append(f"Humans Killed (mistakes): {c.total_humans_killed}")

        return "\n".join(lines)


# Global statistics instance
stats = StatisticsManager()
