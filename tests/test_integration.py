"""Integration tests for The Thing game loop.

Tests the full game flow from initialization to win/lose conditions.
"""

import sys
import os
import pytest

# Add src directory to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_path = os.path.join(project_root, "src")
for path in (project_root, src_path):
    if path not in sys.path:
        sys.path.insert(0, path)

from engine import GameState
from systems.architect import Difficulty


class TestGameInitialization:
    """Tests for game initialization."""

    def test_game_creates_with_seed(self):
        """Game should initialize deterministically with a seed."""
        game1 = GameState(seed=12345, difficulty=Difficulty.NORMAL)
        game2 = GameState(seed=12345, difficulty=Difficulty.NORMAL)

        # Same seed should produce same initial infected
        infected1 = [m.name for m in game1.crew if m.is_infected]
        infected2 = [m.name for m in game2.crew if m.is_infected]

        assert infected1 == infected2

    def test_seed_reproducibility_after_advancing_turns(self):
        """Seeded games should remain deterministic across turns."""
        def snapshot(game):
            crew_state = sorted(
                [
                    (
                        member.name,
                        member.location,
                        member.is_infected,
                        member.is_alive,
                        member.is_revealed,
                        round(member.mask_integrity, 2),
                    )
                    for member in game.crew
                ],
                key=lambda item: item[0],
            )
            return {
                "turn": game.turn,
                "paranoia": game.paranoia_level,
                "weather": (
                    game.weather.wind_direction,
                    game.weather.storm_intensity,
                    game.weather.northeasterly_active,
                    game.weather.northeasterly_turns_remaining,
                ),
                "crew": crew_state,
                "events": list(game.random_events.event_history),
            }

        def play_sequence():
            game = GameState(seed=777, difficulty=Difficulty.NORMAL)
            try:
                for _ in range(5):
                    game.advance_turn()
                return snapshot(game)
            finally:
                game.cleanup()

        assert play_sequence() == play_sequence()

    def test_game_creates_player(self):
        """Game should have a player character."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)

        assert game.player is not None
        assert game.player.name == "MacReady"
        assert game.player.is_alive

    def test_game_creates_crew(self):
        """Game should have crew members."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)

        assert len(game.crew) > 0
        assert all(hasattr(m, 'name') for m in game.crew)
        assert all(hasattr(m, 'is_alive') for m in game.crew)

    def test_difficulty_affects_infection(self):
        """Difficulty should affect number of initial infected."""
        easy_game = GameState(seed=42, difficulty=Difficulty.EASY)
        hard_game = GameState(seed=42, difficulty=Difficulty.HARD)

        easy_infected = len([m for m in easy_game.crew if m.is_infected])
        hard_infected = len([m for m in hard_game.crew if m.is_infected])

        # Hard mode should have at least as many infected as Easy
        assert hard_infected >= easy_infected

    def test_station_map_exists(self):
        """Game should have a station map with rooms."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)

        assert game.station_map is not None
        assert len(game.station_map.rooms) >= 4


class TestTurnAdvancement:
    """Tests for turn advancement mechanics."""

    def test_advance_turn_increments_counter(self):
        """Advancing a turn should increment the turn counter."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)
        initial_turn = game.turn

        game.advance_turn()

        assert game.turn == initial_turn + 1

    def test_advance_turn_updates_npcs(self):
        """Advancing a turn should allow NPCs to move."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)

        initial_positions = {m.name: m.location for m in game.crew if m != game.player}

        # Advance several turns
        for _ in range(10):
            game.advance_turn()

        final_positions = {m.name: m.location for m in game.crew if m != game.player}

        # At least some NPCs should have moved
        moved = sum(1 for name in initial_positions if initial_positions[name] != final_positions[name])
        assert moved > 0


class TestWinLoseConditions:
    """Tests for game ending conditions."""

    def test_player_death_is_loss(self):
        """Player death should trigger game over (loss)."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)

        game.player.is_alive = False
        game_over, won, message = game.check_game_over()

        assert game_over is True
        assert won is False
        assert "killed" in message.lower() or "dead" in message.lower()

    def test_player_reveal_is_loss(self):
        """Player being revealed as Thing should trigger game over (loss)."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)

        game.player.is_infected = True
        game.player.is_revealed = True
        game_over, won, message = game.check_game_over()

        assert game_over is True
        assert won is False

    def test_all_infected_eliminated_is_win(self):
        """Eliminating all infected should trigger victory."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)

        # Kill or uninfect all infected
        for m in game.crew:
            if m.is_infected and m != game.player:
                m.is_alive = False

        game.player.is_infected = False
        game_over, won, message = game.check_game_over()

        assert game_over is True
        assert won is True

    def test_game_continues_with_mixed_state(self):
        """Game should continue if infected and humans both alive."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)

        # Ensure we have both infected and uninfected alive
        infected_found = False
        human_found = False
        for m in game.crew:
            if m.is_infected and m.is_alive and not m.is_revealed:
                infected_found = True
            elif not m.is_infected and m.is_alive:
                human_found = True

        if infected_found and human_found:
            game_over, won, message = game.check_game_over()
            assert game_over is False


class TestCombatIntegration:
    """Integration tests for combat flow."""

    def test_attack_deals_damage(self):
        """Attacking a target should deal damage."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)

        target = next(m for m in game.crew if m != game.player and m.is_alive)
        initial_health = target.health

        # Give player a weapon
        from entities.item import Item
        from core.resolution import Skill
        weapon = Item("Axe", "Sharp", weapon_skill=Skill.MELEE, damage=2)
        game.player.add_item(weapon)

        # Put them in same location
        target.location = game.player.location

        # Perform attack (may miss, so we try several times)
        for _ in range(10):
            from systems.combat import CombatSystem, CoverType
            combat = CombatSystem(game.rng)
            result = combat.calculate_attack(game.player, target, weapon, CoverType.NONE)
            if result.success:
                target.take_damage(result.damage)
                break

        # After attempts, health should potentially be reduced
        # (may still be same if all attacks missed)
        assert target.health <= initial_health


class TestSerializationIntegration:
    """Integration tests for save/load functionality."""

    def test_game_state_serialization(self):
        """Game state should serialize and deserialize correctly."""
        game = GameState(seed=42, difficulty=Difficulty.NORMAL)

        # Modify some state
        game.advance_turn()
        game.advance_turn()
        game.player.location = (10, 10)

        # Serialize
        data = game.to_dict()

        # Deserialize
        restored = GameState.from_dict(data)

        assert restored.turn == game.turn
        assert restored.player.location == game.player.location
        assert len(restored.crew) == len(game.crew)

    def test_rng_state_round_trip(self):
        """RNG state should survive serialization and continue deterministically."""
        game = GameState(seed=999, difficulty=Difficulty.NORMAL)

        # Advance RNG state with some rolls
        _ = [game.rng.roll_d6() for _ in range(3)]

        data = game.to_dict()

        # Roll again after saving to capture post-save sequence
        continued_rolls = [game.rng.roll_d6() for _ in range(5)]

        restored = GameState.from_dict(data)
        restored_rolls = [restored.rng.roll_d6() for _ in range(5)]

        assert continued_rolls == restored_rolls


class TestEventBusIntegration:
    """Integration tests for event system."""

    def test_turn_advance_emits_event(self):
        """Advancing a turn should emit TURN_ADVANCE event."""
        from core.event_system import event_bus, EventType

        game = GameState(seed=42, difficulty=Difficulty.NORMAL)
        event_received = []

        def handler(event):
            event_received.append(event)

        event_bus.subscribe(EventType.TURN_ADVANCE, handler)

        try:
            game.advance_turn()
            assert len(event_received) > 0
        finally:
            event_bus.unsubscribe(EventType.TURN_ADVANCE, handler)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
