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

    # Pre-allocate neighbor offsets to avoid instantiation in loops
    ORTHOGONAL_NEIGHBORS = [(-1, 0), (0, -1), (0, 1), (1, 0)]
    DIAGONAL_NEIGHBORS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

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
        # heapq.heapify(open_set) # Not needed for single element

        # Track where we came from
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}

        # g_score: cost from start to current node
        g_score: Dict[Tuple[int, int], float] = {start: 0}

        # f_score: g_score + heuristic
        f_score: Dict[Tuple[int, int], float] = {start: self._heuristic(start, goal)}

        # Track what's in open set for O(1) lookup
        open_set_hash = {start}

        # Cache map dimensions for faster bounds checking
        map_width = station_map.width
        map_height = station_map.height
        # Localize globals for speed in loop
        heappush = heapq.heappush
        heappop = heapq.heappop
        neighbors = NEIGHBORS
        heuristic_weight = HEURISTIC_WEIGHT
        goal_x, goal_y = goal

        while open_set:
            # Get node with lowest f_score
            _, _, current = heappop(open_set)
            open_set_hash.discard(current)

            if current == goal:
                return self._reconstruct_path(came_from, current)

            # Process orthogonal neighbors
            for dx, dy in self.ORTHOGONAL_NEIGHBORS:
                nx, ny = current[0] + dx, current[1] + dy

                # Inline is_walkable check
                if not (0 <= nx < map_width and 0 <= ny < map_height):
                    continue

                neighbor = (nx, ny)
                tentative_g = g_score[current] + 1.0

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g

                    # Inline heuristic
                    dx_h = abs(nx - goal[0])
                    dy_h = abs(ny - goal[1])
                    # Octile distance: max(dx, dy) + (sqrt(2) - 1) * min(dx, dy)
                    h_val = max(dx_h, dy_h) + 0.41421356 * min(dx_h, dy_h)

                    f_score[neighbor] = tentative_g + h_val
                    if neighbor not in open_set_hash:
                        counter += 1
                        heapq.heappush(open_set, (f_score[neighbor], counter, neighbor))
                        open_set_hash.add(neighbor)

            # Process diagonal neighbors
            for dx, dy in self.DIAGONAL_NEIGHBORS:
                nx, ny = current[0] + dx, current[1] + dy
            cx, cy = current
            current_g = g_score[current]

            # Process neighbors
            for dx, dy, cost in neighbors:
                nx, ny = cx + dx, cy + dy

                # Inline is_walkable check
                if not (0 <= nx < map_width and 0 <= ny < map_height):
                    continue

                neighbor = (nx, ny)
                tentative_g = current_g + cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g

                    # Inline heuristic: Octile distance
                    # max(dx, dy) + (sqrt(2) - 1) * min(dx, dy)
                    dx_h = abs(nx - goal_x)
                    dy_h = abs(ny - goal_y)

                    if dx_h > dy_h:
                        h_val = dx_h + heuristic_weight * dy_h
                    else:
                        h_val = dy_h + heuristic_weight * dx_h

                    f_score[neighbor] = tentative_g + h_val

                    if neighbor not in open_set_hash:
                        counter += 1
                        heappush(open_set, (f_score[neighbor], counter, neighbor))
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
