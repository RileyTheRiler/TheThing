"""A* Pathfinding system for NPC navigation."""

import heapq
from typing import List, Tuple, Optional, Dict


class PathfindingSystem:
    """A* pathfinding for NPC navigation in the station.

    Provides efficient path calculation with optional caching to avoid
    recalculating paths every turn.
    """

    def __init__(self):
        self._path_cache: Dict[Tuple[Tuple[int, int], Tuple[int, int]], List[Tuple[int, int]]] = {}
        self._cache_turn = -1

    def clear_cache(self):
        """Clear the path cache. Call when map state changes (barricades, etc)."""
        self._path_cache.clear()

    def find_path(self, start: Tuple[int, int], goal: Tuple[int, int],
                  station_map, current_turn: int = 0) -> Optional[List[Tuple[int, int]]]:
        """Find a path from start to goal using A* algorithm.

        Args:
            start: Starting (x, y) position
            goal: Target (x, y) position
            station_map: StationMap instance for walkability checks
            current_turn: Current game turn for cache invalidation

        Returns:
            List of (x, y) positions from start to goal, or None if no path exists
        """
        # Invalidate cache on new turn
        if current_turn != self._cache_turn:
            self.clear_cache()
            self._cache_turn = current_turn

        # Check cache
        cache_key = (start, goal)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        # A* implementation
        path = self._astar(start, goal, station_map)

        # Cache result
        if path:
            self._path_cache[cache_key] = path

        return path

    def get_next_step(self, start: Tuple[int, int], goal: Tuple[int, int],
                      station_map, current_turn: int = 0) -> Optional[Tuple[int, int]]:
        """Get the next step toward a goal.

        Args:
            start: Current (x, y) position
            goal: Target (x, y) position
            station_map: StationMap instance
            current_turn: Current game turn

        Returns:
            Next (x, y) position to move to, or None if no path exists
        """
        if start == goal:
            return None

        path = self.find_path(start, goal, station_map, current_turn)
        if path and len(path) > 1:
            return path[1]  # path[0] is the start position
        return None

    def get_move_delta(self, start: Tuple[int, int], goal: Tuple[int, int],
                       station_map, current_turn: int = 0) -> Tuple[int, int]:
        """Get the delta (dx, dy) for the next step toward a goal.

        Args:
            start: Current (x, y) position
            goal: Target (x, y) position
            station_map: StationMap instance
            current_turn: Current game turn

        Returns:
            (dx, dy) tuple for movement, or (0, 0) if no path
        """
        next_pos = self.get_next_step(start, goal, station_map, current_turn)
        if next_pos:
            return (next_pos[0] - start[0], next_pos[1] - start[1])
        return (0, 0)

    def _astar(self, start: Tuple[int, int], goal: Tuple[int, int],
               station_map) -> Optional[List[Tuple[int, int]]]:
        """A* pathfinding algorithm implementation.

        Args:
            start: Starting position
            goal: Goal position
            station_map: StationMap for walkability

        Returns:
            Path as list of positions, or None if unreachable
        """
        # Priority queue: (f_score, counter, position)
        # Counter is used as tiebreaker for equal f_scores
        counter = 0
        open_set = [(0, counter, start)]
        heapq.heapify(open_set)

        # Track where we came from
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}

        # g_score: cost from start to current node
        g_score: Dict[Tuple[int, int], float] = {start: 0}

        # f_score: g_score + heuristic
        f_score: Dict[Tuple[int, int], float] = {start: self._heuristic(start, goal)}

        # Track what's in open set for O(1) lookup
        open_set_hash = {start}

        while open_set:
            # Get node with lowest f_score
            _, _, current = heapq.heappop(open_set)
            open_set_hash.discard(current)

            if current == goal:
                return self._reconstruct_path(came_from, current)

            # Check all 8 neighbors (including diagonals)
            for dx, dy in [(-1, -1), (-1, 0), (-1, 1),
                           (0, -1),          (0, 1),
                           (1, -1),  (1, 0), (1, 1)]:
                neighbor = (current[0] + dx, current[1] + dy)

                # Check walkability
                if not station_map.is_walkable(neighbor[0], neighbor[1]):
                    continue

                # Calculate movement cost (diagonal is slightly more)
                move_cost = 1.414 if dx != 0 and dy != 0 else 1.0
                tentative_g = g_score[current] + move_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    # This path is better
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, goal)

                    if neighbor not in open_set_hash:
                        counter += 1
                        heapq.heappush(open_set, (f_score[neighbor], counter, neighbor))
                        open_set_hash.add(neighbor)

        # No path found
        return None

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Chebyshev distance heuristic (allows diagonal movement).

        Args:
            a: First position
            b: Second position

        Returns:
            Estimated distance between positions
        """
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        # Chebyshev distance for 8-directional movement
        return max(dx, dy) + (1.414 - 1) * min(dx, dy)

    def _reconstruct_path(self, came_from: Dict[Tuple[int, int], Tuple[int, int]],
                          current: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Reconstruct path from came_from map.

        Args:
            came_from: Dictionary mapping each position to its predecessor
            current: End position

        Returns:
            List of positions from start to current
        """
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path


# Global pathfinding instance for shared use
pathfinder = PathfindingSystem()
