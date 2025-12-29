
import time
import cProfile
import pstats
import io
from typing import List

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from engine import GameState, CrewMember
from systems.ai import AISystem

def create_profiling_state(crew_count: int = 10) -> GameState:
    """Create a game state with N crew members for profiling."""
    game = GameState(seed=12345)
    
    # Ensure we have enough crew
    base_crew = list(game.crew)
    game.crew = []
    
    # Duplicate crew to reach desired count
    for i in range(crew_count):
        source = base_crew[i % len(base_crew)]
        # Create a basic clone (simplification for profiling)
        # We need a new instance to not mess up references
        new_member = CrewMember(
            name=f"Clone_{i}_{source.name}",
            role=source.role,
            behavior_type=source.behavior_type,
            attributes=source.attributes.copy(),
            skills=source.skills.copy()
        )
        new_member.location = (0, 0) # Start everyone at 0,0
        new_member.schedule = source.schedule
        game.crew.append(new_member)
        
    # Ensure player exists and is separate from crew list logic if needed
    # but GameState usually keeps player in crew list.
    # Let's just make sure one is the player.
    game.player = game.crew[0]
    
    return game

def profile_ai_turns(turns: int = 100, crew_count: int = 10):
    """Profile AI system update for N turns."""
    game = create_profiling_state(crew_count)
    ai_system = AISystem()
    
    print(f"Profiling {turns} turns with {crew_count} crew members...")
    
    # Setup profiler
    pr = cProfile.Profile()
    pr.enable()
    
    start_time = time.time()
    
    for _ in range(turns):
        # We only want to profile the AI update itself
        ai_system.update(game)
        
    end_time = time.time()
    pr.disable()
    
    total_time = end_time - start_time
    avg_time = (total_time / turns) * 1000 # ms
    
    print(f"\nTotal time: {total_time:.4f}s")
    print(f"Average time per turn: {avg_time:.2f}ms")
    print(f"Time per entity per turn: {(avg_time / crew_count):.2f}ms")
    
    # Print stats
    s = io.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(20) # Top 20 functions
    print(s.getvalue())

if __name__ == "__main__":
    profile_ai_turns(turns=50, crew_count=15)
