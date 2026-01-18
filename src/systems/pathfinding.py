"""A* Pathfinding system for NPC navigation."""

import heapq
from typing import List, Tuple, Optional, Dict

# Pre-computed neighbor constants to avoid allocation in loops
# Format: (dx, dy, cost)
NEIGHBORS = (
    (-1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0), (1, 0, 1.0),  # Orthogonal
    (-1, -1, 1.41421356), (-1, 1, 1.41421356), (1, -1, 1.41421356), (1, 1, 1.41421356)  # Diagonal
)

# Heuristic weight for tie-breaking
HEURISTIC_WEIGHT = 0.41421356

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
        Optimized to use 1D arrays instead of dictionaries for O(1) access.

        Args:
            start: Starting position
            goal: Goal position
            station_map: StationMap for walkability

        Returns:
            Path as list of positions, or None if unreachable
        """
        map_width = station_map.width
        map_height = station_map.height
        size = map_width * map_height

        start_x, start_y = start
        goal_x, goal_y = goal
        start_idx = start_y * map_width + start_x

        # Arrays initialized to default values
        # g_score: cost from start to node. Inf means not visited/unreachable.
        g_score = [float('inf')] * size
        # came_from: parent index. -1 means no parent.
        came_from = [-1] * size
        # in_open_set: boolean tracking for O(1) lookup
        in_open_set = [False] * size

        g_score[start_idx] = 0.0

        # Priority queue: (f_score, counter, x, y)
        # Counter is used as tiebreaker for equal f_scores
        counter = 0
        h_start = self._heuristic(start, goal)
        open_set = [(h_start, counter, start_x, start_y)]
        in_open_set[start_idx] = True

        # Localize globals for speed in loop
        heappush = heapq.heappush
        heappop = heapq.heappop
        neighbors = NEIGHBORS
        heuristic_weight = HEURISTIC_WEIGHT

        while open_set:
            # Get node with lowest f_score
            _, _, cx, cy = heappop(open_set)
            c_idx = cy * map_width + cx
            in_open_set[c_idx] = False

            if cx == goal_x and cy == goal_y:
                return self._reconstruct_path_array(came_from, c_idx, map_width)

            current_g = g_score[c_idx]

            # Process neighbors
            for dx, dy, cost in neighbors:
                nx, ny = cx + dx, cy + dy

                # Inline is_walkable check
                if not (0 <= nx < map_width and 0 <= ny < map_height):
                    continue

                n_idx = ny * map_width + nx
                tentative_g = current_g + cost

                if tentative_g < g_score[n_idx]:
                    came_from[n_idx] = c_idx
                    g_score[n_idx] = tentative_g

                    # Inline heuristic: Octile distance
                    # max(dx, dy) + (sqrt(2) - 1) * min(dx, dy)
                    dx_h = abs(nx - goal_x)
                    dy_h = abs(ny - goal_y)

                    if dx_h > dy_h:
                        h_val = dx_h + heuristic_weight * dy_h
                    else:
                        h_val = dy_h + heuristic_weight * dx_h

                    f_val = tentative_g + h_val

                    if not in_open_set[n_idx]:
                        counter += 1
                        in_open_set[n_idx] = True
                        heappush(open_set, (f_val, counter, nx, ny))

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

    def _reconstruct_path_array(self, came_from: List[int], current_idx: int, width: int) -> List[Tuple[int, int]]:
        """Reconstruct path from came_from array.

        Args:
            came_from: List mapping each position index to its predecessor index
            current_idx: End position index
            width: Map width for coordinate conversion

        Returns:
            List of positions from start to current
        """
        path = []
        while current_idx != -1:
            y, x = divmod(current_idx, width)
            path.append((x, y))
            current_idx = came_from[current_idx]
        path.reverse()
        return path

    # Deprecated but kept for compatibility if referenced elsewhere
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
