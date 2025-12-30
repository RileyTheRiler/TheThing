"""
Integration tests for alternative ending scenarios.
Tests the full workflow from trigger to ENDING_REPORT event.
"""
import unittest
from types import SimpleNamespace

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from core.event_system import event_bus, EventType, GameEvent
from systems.endgame import EndgameSystem
from systems.architect import RandomnessEngine


class DummyCrewMember:
    """Minimal crew member for testing."""
    def __init__(self, name, is_infected=False, is_alive=True):
        self.name = name
        self.is_infected = is_infected
        self.is_alive = is_alive
        self.is_revealed = False
        self.health = 5


class TestAlternativeEndingsIntegration(unittest.TestCase):
    """Integration tests for alternative ending workflows."""

    def setUp(self):
        """Set up test fixtures."""
        event_bus._subscribers.clear()
        self.ending_events = []
        event_bus.subscribe(EventType.ENDING_REPORT, self._capture_ending)

    def tearDown(self):
        """Clean up after tests."""
        event_bus._subscribers.clear()

    def _capture_ending(self, event: GameEvent):
        """Capture ending events for verification."""
        self.ending_events.append(event)

    def test_helicopter_escape_full_workflow(self):
        """Test complete helicopter escape workflow."""
        # Setup
        endgame = EndgameSystem()
        player = DummyCrewMember("MacReady", is_infected=False)
        crew = [
            player,
            DummyCrewMember("Childs", is_infected=True),
            DummyCrewMember("Blair", is_infected=False)
        ]
        game_state = SimpleNamespace(
            player=player,
            crew=crew,
            helicopter_status="BROKEN",
            rescue_signal_active=False,
            rescue_turns_remaining=None,
            turn=10
        )

        # Step 1: Repair helicopter (simulated via event)
        repair_event = GameEvent(EventType.HELICOPTER_REPAIRED, {"game_state": game_state})
        endgame.on_helicopter_repaired(repair_event)

        # Verify helicopter is now fixed
        self.assertEqual(game_state.helicopter_status, "FIXED")
        self.assertEqual(len(self.ending_events), 0)  # No ending yet

        # Step 2: Player escapes via helicopter
        escape_event = GameEvent(EventType.ESCAPE_SUCCESS, {"game_state": game_state})
        event_bus.emit(escape_event)

        # Verify ending was triggered
        self.assertEqual(len(self.ending_events), 1)
        ending = self.ending_events[0]
        self.assertEqual(ending.type, EventType.ENDING_REPORT)
        self.assertEqual(ending.payload["ending_type"], "ESCAPE")
        self.assertEqual(ending.payload["result"], "win")
        self.assertIn("chopper", ending.payload["message"].lower())

        # Verify endgame system is marked as resolved
        self.assertTrue(endgame.resolved)

        endgame.cleanup()

    def test_radio_rescue_full_workflow(self):
        """Test complete radio rescue workflow."""
        # Setup
        endgame = EndgameSystem()
        player = DummyCrewMember("MacReady", is_infected=False)
        crew = [
            player,
            DummyCrewMember("Nauls", is_infected=False),
            DummyCrewMember("Palmer", is_infected=True)  # Add infected to prevent early EXTERMINATION
        ]
        game_state = SimpleNamespace(
            player=player,
            crew=crew,
            helicopter_status="BROKEN",
            rescue_signal_active=False,
            rescue_turns_remaining=None,
            turn=5
        )

        # Step 1: Send SOS signal
        sos_event = GameEvent(EventType.SOS_EMITTED, {"game_state": game_state})
        endgame.on_sos_emitted(sos_event)

        # Verify rescue countdown started
        self.assertTrue(game_state.rescue_signal_active)
        self.assertEqual(game_state.rescue_turns_remaining, 20)
        self.assertEqual(len(self.ending_events), 0)  # No ending yet

        # Step 2: Advance 19 turns (rescue hasn't arrived yet)
        for i in range(19):
            game_state.rescue_turns_remaining -= 1
            game_state.turn += 1
            turn_event = GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state})
            endgame.on_turn_advance(turn_event)

            # Debug: Check if ending triggered unexpectedly
            if self.ending_events:
                print(f"Unexpected ending on turn {i+1}: {self.ending_events[0].payload}")

        self.assertEqual(len(self.ending_events), 0,
                        f"Expected no ending yet, but got: {self.ending_events[0].payload if self.ending_events else 'none'}")

        # Step 3: Final turn - rescue arrives
        game_state.rescue_turns_remaining -= 1
        game_state.turn += 1
        turn_event = GameEvent(EventType.TURN_ADVANCE, {"game_state": game_state})
        endgame.on_turn_advance(turn_event)

        # Verify rescue ending triggered
        self.assertEqual(len(self.ending_events), 1)
        ending = self.ending_events[0]
        self.assertEqual(ending.type, EventType.ENDING_REPORT)
        self.assertEqual(ending.payload["ending_type"], "RESCUE")
        self.assertEqual(ending.payload["result"], "win")
        self.assertIn("rescue", ending.payload["message"].lower())

        endgame.cleanup()

    def test_sole_survivor_workflow(self):
        """Test sole survivor ending when all others die."""
        # Setup
        endgame = EndgameSystem()
        player = DummyCrewMember("MacReady", is_infected=False)
        victim1 = DummyCrewMember("Childs", is_infected=False)
        victim2 = DummyCrewMember("Palmer", is_infected=True)

        crew = [player, victim1, victim2]
        game_state = SimpleNamespace(
            player=player,
            crew=crew,
            helicopter_status="BROKEN",
            rescue_signal_active=False,
            rescue_turns_remaining=None,
            turn=15
        )

        # Kill first victim
        victim1.is_alive = False
        death_event1 = GameEvent(EventType.CREW_DEATH, {
            "game_state": game_state,
            "name": "Childs"
        })
        endgame.on_crew_death(death_event1)

        self.assertEqual(len(self.ending_events), 0)  # No ending yet

        # Kill second victim - player is now sole survivor
        victim2.is_alive = False
        death_event2 = GameEvent(EventType.CREW_DEATH, {
            "game_state": game_state,
            "name": "Palmer"
        })
        endgame.on_crew_death(death_event2)

        # Verify sole survivor ending
        self.assertEqual(len(self.ending_events), 1)
        ending = self.ending_events[0]
        self.assertEqual(ending.payload["ending_type"], "SOLE_SURVIVOR")
        self.assertEqual(ending.payload["result"], "win")
        self.assertIn("only one left", ending.payload["message"].lower())

        endgame.cleanup()


if __name__ == "__main__":
    unittest.main()
