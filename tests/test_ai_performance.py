
import unittest
import time
import pytest
from engine import GameState, CrewMember
from systems.ai import AISystem

class TestAIPerformance(unittest.TestCase):
    def setUp(self):
        self.turns_to_test = 10
        
    def _create_state(self, crew_count: int) -> GameState:
        game = GameState(seed=123)
        base_crew = list(game.crew)
        game.crew = []
        
        for i in range(crew_count):
            source = base_crew[i % len(base_crew)]
            new_member = CrewMember(
                name=f"Clone_{i}",
                role=source.role,
                behavior_type=source.behavior_type,
                attributes=source.attributes.copy(),
                skills=source.skills.copy()
            )
            # Spread them out slightly to force different pathfinding
            new_member.location = (i % 10, i % 10)
            # Give them a schedule so they try to move
            new_member.schedule = [{"start": 0, "end": 24, "room": "Generator"}]
            game.crew.append(new_member)
            
        game.player = game.crew[0]
        game.time_system.hour = 12 # Ensure active schedule
        return game

    def test_baseline_performance_small(self):
        """Test performance with small crew (3). Guardrail: < 10ms/turn"""
        crew_count = 3
        game = self._create_state(crew_count)
        ai = AISystem()
        
        start = time.time()
        for _ in range(self.turns_to_test):
            ai.update(game)
        avg_ms = ((time.time() - start) / self.turns_to_test) * 1000
        
        print(f"Small crew (3): {avg_ms:.2f}ms/turn")
        self.assertLess(avg_ms, 10.0, "Small crew performance exceeded 10ms budget")

    def test_baseline_performance_medium(self):
        """Test performance with medium crew (8). Guardrail: < 50ms/turn"""
        crew_count = 8
        game = self._create_state(crew_count)
        ai = AISystem()
        
        start = time.time()
        for _ in range(self.turns_to_test):
            ai.update(game)
        avg_ms = ((time.time() - start) / self.turns_to_test) * 1000
        
        print(f"Medium crew (8): {avg_ms:.2f}ms/turn")
        self.assertLess(avg_ms, 50.0, "Medium crew performance exceeded 50ms budget")

    def test_baseline_performance_large(self):
        """Test performance with large crew (15). Guardrail: < 100ms/turn"""
        crew_count = 15
        game = self._create_state(crew_count)
        ai = AISystem()
        
        start = time.time()
        for _ in range(self.turns_to_test):
            ai.update(game)
        avg_ms = ((time.time() - start) / self.turns_to_test) * 1000
        
        print(f"Large crew (15): {avg_ms:.2f}ms/turn")
        self.assertLess(avg_ms, 100.0, "Large crew performance exceeded 100ms budget")

    def test_scaling_efficiency(self):
        """Verify adding crew doesn't cause exponential slowdown."""
        small_crew = 3
        large_crew = 15
        
        # Measure small
        game_s = self._create_state(small_crew)
        ai_s = AISystem()
        start_s = time.time()
        for _ in range(self.turns_to_test):
            ai_s.update(game_s)
        time_s = time.time() - start_s
        
        # Measure large
        game_l = self._create_state(large_crew)
        ai_l = AISystem()
        start_l = time.time()
        for _ in range(self.turns_to_test):
            ai_l.update(game_l)
        time_l = time.time() - start_l
        
        # Ideally 5x crew should be roughly 5x time. Allow some overhead.
        ratio = time_l / time_s
        crew_ratio = large_crew / small_crew
        
        print(f"Scaling ratio: {ratio:.2f} (Crew ratio: {crew_ratio})")
        
        # We want to avoid O(N^2) behavior.
        # If it was N^2, ratio would be ~25. If linear, ~5.
        # Assert it's closer to linear than quadratic.
        self.assertLess(ratio, crew_ratio * 3.0, "Performance scaling appears super-linear")

if __name__ == '__main__':
    unittest.main()
