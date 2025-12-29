import pytest
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from engine import GameState
from systems.architect import Difficulty

class TestRNGDeterminism:
    """
    Verify that the game is fully deterministic when seeded.
    Two game instances with the same seed must produce identical outcomes.
    """

    def test_end_to_end_determinism(self):
        from core.event_system import event_bus
        event_bus.clear()
        
        seed = 99999
        
        # Run 1
        game1 = GameState(seed=seed, difficulty=Difficulty.NORMAL)
        self._run_game_script(game1)
        state1 = self._capture_state_snapshot(game1)
        
        # Clear bus between runs to prevent cross-contamination of listeners
        event_bus.clear()
        
        # Run 2
        game2 = GameState(seed=seed, difficulty=Difficulty.NORMAL)
        self._run_game_script(game2)
        state2 = self._capture_state_snapshot(game2)
        
        # Assertions
        assert state1 == state2, "Game states diverged despite identical seeds!"
        assert len(game1.random_events.event_history) == len(game2.random_events.event_history), "Event history mismatch"
        
        # Verify RNG internal state match
        # Note: Depending on implementation, RandomnessEngine.to_dict() might be useful here
        rng1_state = game1.rng.to_dict()['rng_state']
        rng2_state = game2.rng.to_dict()['rng_state']
        assert rng1_state == rng2_state, "RNG internal state diverged!"

    def _run_game_script(self, game):
        """Perform a sequence of game actions."""
        # Turn 1: Just advance
        game.advance_turn()
        
        # Turn 2: Move Player
        game.player.move(1, 0, game.station_map) # East
        game.advance_turn()
        
        # Turn 3: Interaction (Rolls dice)
        # Attempt to attack a crew member if present, or just roll a check
        from core.resolution import Attribute, Skill
        resolution_result = game.player.roll_check(Attribute.PROWESS, Skill.MELEE, game.rng)
        
        # Turn 4: Weather tick (happens in advance_turn)
        game.advance_turn()
        
        # Turn 5: Move an NPC (AI logic)
        # This happens automatically during advance_turn via AISystem
        game.advance_turn()

    def _capture_state_snapshot(self, game):
        """Capture relevant state for comparison."""
        
        crew_positions = {m.name: m.location for m in game.crew}
        crew_health = {m.name: m.health for m in game.crew}
        crew_infected = {m.name: m.is_infected for m in game.crew}
        
        snapshot = {
            "turn": game.turn,
            "paranoia": game.paranoia_level,
            "weather": {
                "storm_intensity": game.weather.storm_intensity,
                "wind_direction": game.weather.wind_direction.value,
                "temp": game.time_system.temperature
            },
            "crew_positions": crew_positions,
            "crew_health": crew_health,
            "crew_infected": crew_infected,
            "event_history": list(game.random_events.event_history)
        }
        return snapshot

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
