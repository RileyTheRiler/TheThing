"""StationMap entity class for The Thing game."""

from typing import List, Dict
from entities.item import Item


class StationMap:
    """Represents the Antarctic research station layout.

    The station is a 20x20 grid with named rooms. Items can be placed
    in rooms and crew members navigate between them.
    """

    def __init__(self, width=20, height=20):
        self.width = width
        self.height = height
        self.grid = [['.' for _ in range(width)] for _ in range(height)]
        # Station layout - 9 rooms across the 20x20 grid
        self.rooms = {
            # Original rooms
            "Rec Room": (5, 5, 10, 10),       # Central gathering area
            "Infirmary": (0, 0, 4, 4),        # Medical bay (northwest)
            "Generator": (15, 15, 19, 19),    # Power room (southeast)
            "Kennel": (0, 15, 4, 19),         # Dog housing (southwest)
            # New rooms
            "Radio Room": (11, 0, 14, 4),     # Communications (north)
            "Storage": (15, 0, 19, 4),        # Supplies and fuel (northeast)
            "Lab": (11, 11, 14, 14),          # Scientific research (center-east)
            "Sleeping Quarters": (0, 6, 4, 10),  # Crew bunks (west)
            "Mess Hall": (5, 0, 9, 4),        # Food and kitchen (north-center)
            "Hangar": (5, 15, 10, 19),        # Helicopter storage (south-center)
        }
        # Vent locations (coordinates where a vent exists)
        self.vents = {
            (2, 2), (7, 2), (13, 2), (17, 2), # North vents
            (2, 8), (7, 8), (13, 8), (17, 8), # Central vents
            (2, 17), (7, 17), (13, 17), (17, 17) # South vents
        }
        self.room_items = {}
        # Precompute room lookup to avoid repeated room-scan on every query.
        # Hot paths (rendering, AI movement) call get_room_name thousands of times;
        # this keeps the lookup O(1) instead of iterating every room definition.
        self._coord_to_room = self._build_room_lookup()
        # Designated hiding spots with metadata for stealth/combat interactions.
        # Each entry: (x, y): {"room": name, "cover_bonus": int, "blocks_los": bool, "label": str}
        self.hiding_spots = self._build_hiding_spots()
        # Lightweight vent graph for network traversal + entry/exit metadata
        self.vent_graph = self._build_vent_graph()

    def _build_room_lookup(self):
        lookup = {}
        for y in range(self.height):
            for x in range(self.width):
                room_name = None
                for name, (x1, y1, x2, y2) in self.rooms.items():
                    if x1 <= x <= x2 and y1 <= y <= y2:
                        room_name = name
                        break
                lookup[(x, y)] = room_name or f"Corridor (Sector {x},{y})"
        return lookup

    def _build_vent_graph(self):
        """Create vent graph with adjacency and entry/exit classification."""
        # Manually connect vents in a grid-like lattice to avoid pathfinding costs later.
        neighbors = {
            (2, 2): [(7, 2), (2, 8)],
            (7, 2): [(2, 2), (13, 2), (7, 8)],
            (13, 2): [(7, 2), (17, 2), (13, 8)],
            (17, 2): [(13, 2), (17, 8)],
            (2, 8): [(2, 2), (7, 8), (2, 17)],
            (7, 8): [(2, 8), (7, 2), (13, 8)],
            (13, 8): [(7, 8), (13, 2), (17, 8), (13, 17)],
            (17, 8): [(13, 8), (17, 2), (17, 17)],
            (2, 17): [(2, 8), (7, 17)],
            (7, 17): [(2, 17), (13, 17)],
            (13, 17): [(7, 17), (17, 17), (13, 8)],
            (17, 17): [(13, 17), (17, 8)]
        }

        graph = {}
        for coord, adjacent in neighbors.items():
            room_name = self.get_room_name(*coord)
            # Entry/exit nodes are vents that touch a named room rather than raw corridor sectors
            node_type = "entry_exit" if "Corridor" not in room_name else "junction"
            graph[coord] = {
                "neighbors": adjacent,
                "room": room_name,
                "type": node_type
            }
        return graph

    def add_item_to_room(self, item, x, y, turn=0):
        """Add an item to a room at the given coordinates."""
        room_name = self.get_room_name(x, y)
        if room_name not in self.room_items:
            self.room_items[room_name] = []
        self.room_items[room_name].append(item)
        item.add_history(turn, f"Dropped in {room_name}")

    def get_items_in_room(self, x, y):
        """Get all items in the room at the given coordinates."""
        room_name = self.get_room_name(x, y)
        return self.room_items.get(room_name, [])

    def remove_item_from_room(self, item_name, x, y):
        """Remove and return an item from a room by name."""
        room_name = self.get_room_name(x, y)
        if room_name in self.room_items:
            for i, item in enumerate(self.room_items[room_name]):
                if item.name.upper() == item_name.upper():
                    return self.room_items[room_name].pop(i)
        return None

    def is_walkable(self, x, y):
        """Check if a position is within map bounds."""
        return 0 <= x < self.width and 0 <= y < self.height

    def get_room_name(self, x, y):
        """Get the name of the room at the given coordinates."""
        # Fast O(1) lookup using precomputed grid map (see _build_room_lookup).
        # Falls back gracefully for out-of-bounds coordinates to preserve behavior.
        return self._coord_to_room.get((x, y), f"Corridor (Sector {x},{y})")

    def is_at_vent(self, x, y):
        """Check if there is a vent at the given coordinates."""
        return (x, y) in self.vents

    def is_vent_entry(self, x, y):
        """Return True when this vent acts as an entry/exit point into the ducts."""
        node = self.vent_graph.get((x, y))
        return bool(node and node.get("type") == "entry_exit")

    def get_vent_neighbors(self, x: int, y: int):
        """Return neighbor vent coordinates reachable from the given vent node."""
        node = self.vent_graph.get((x, y))
        if not node:
            return []
        return node.get("neighbors", [])

    def get_vent_neighbor_in_direction(self, x: int, y: int, direction: str):
        """Return a neighbor coordinate that best matches a cardinal direction."""
        direction = direction.upper()
        dx_dy = {
            "N": (0, -1), "NORTH": (0, -1),
            "S": (0, 1), "SOUTH": (0, 1),
            "E": (1, 0), "EAST": (1, 0),
            "W": (-1, 0), "WEST": (-1, 0),
        }
        if direction not in dx_dy:
            return None
        dx, dy = dx_dy[direction]
        for nx, ny in self.get_vent_neighbors(x, y):
            if (nx - x == dx and dy == 0) or (ny - y == dy and dx == 0):
                return (nx, ny)
        return None

    def get_vent_entry_nodes(self):
        """Return a list of vent coordinates that can be used as entry/exit points."""
        return [coord for coord, data in self.vent_graph.items() if data.get("type") == "entry_exit"]

    def get_connections(self, room_name: str) -> List[str]:
        """Get names of rooms connected to the given room."""
        # Simple adjacency map for the station layout
        connections = {
            "Rec Room": ["Mess Hall", "Infirmary", "Radio Room", "Storage", "Sleeping Quarters", "Lab", "Generator", "Hangar", "Kennel"],
            "Infirmary": ["Rec Room", "Radio Room", "Mess Hall", "Sleeping Quarters"],
            "Generator": ["Rec Room", "Hangar", "Lab", "Kennel"],
            "Kennel": ["Rec Room", "Hangar", "Sleeping Quarters", "Generator"],
            "Radio Room": ["Rec Room", "Mess Hall", "Storage", "Infirmary"],
            "Storage": ["Rec Room", "Mess Hall", "Radio Room", "Lab"],
            "Lab": ["Rec Room", "Storage", "Generator", "Hangar"],
            "Sleeping Quarters": ["Rec Room", "Infirmary", "Kennel", "Mess Hall"],
            "Mess Hall": ["Rec Room", "Radio Room", "Storage", "Sleeping Quarters", "Infirmary"],
            "Hangar": ["Rec Room", "Lab", "Generator", "Kennel"]
        }
        return connections.get(room_name, [])

    def get_adjacent_rooms(self, x: int, y: int) -> List[str]:
        """Get names of rooms adjacent to the current position."""
        current_room = self.get_room_name(x, y)
        return self.get_connections(current_room)

    def render(self, crew):
        """Render the map with crew member positions."""
        display_grid = [row[:] for row in self.grid]
        for member in crew:
            if member.is_alive:
                x, y = member.location
                if 0 <= x < self.width and 0 <= y < self.height:
                    display_grid[y][x] = member.name[0]
        output = []
        for row in display_grid:
            output.append(" ".join(row))
        return "\n".join(output)

    def to_dict(self):
        """Serialize station map to dictionary for save/load."""
        # room_items is Dict[RoomName, List[Item]]
        items_dict = {}
        for room, items in self.room_items.items():
            items_dict[room] = [i.to_dict() for i in items]

        return {
            "width": self.width,
            "height": self.height,
            "room_items": items_dict
            # rooms and grid are static/derived, so we don't save them
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize station map from dictionary with defensive defaults."""
        if not data or not isinstance(data, dict):
            # Fallback to default map if data is missing/corrupt
            return cls()

        width = data.get("width", 20)
        height = data.get("height", 20)
        sm = cls(width, height)
        
        items_dict = data.get("room_items", {})
        for room, items_data in items_dict.items():
            if not isinstance(items_data, list):
                continue
            sm.room_items[room] = []
            for i_data in items_data:
                item = Item.from_dict(i_data)
                if item:
                    sm.room_items[room].append(item)
        return sm

    def _build_hiding_spots(self) -> Dict[tuple, Dict]:
        """Define static hiding spots across the station grid.

        These locations provide defensive bonuses and sometimes block line-of-sight.
        Coordinates are chosen within the existing room rectangles to align with furniture.
        """
        return {
            (6, 6): {"room": "Rec Room", "cover_bonus": 2, "blocks_los": True, "label": "the rec room booths"},
            (1, 1): {"room": "Infirmary", "cover_bonus": 1, "blocks_los": False, "label": "a medicine cabinet"},
            (16, 18): {"room": "Generator", "cover_bonus": 3, "blocks_los": True, "label": "a bank of fuel drums"},
            (1, 17): {"room": "Kennel", "cover_bonus": 2, "blocks_los": False, "label": "the kennel cages"},
            (11, 1): {"room": "Radio Room", "cover_bonus": 1, "blocks_los": True, "label": "under the console"},
            (17, 1): {"room": "Storage", "cover_bonus": 3, "blocks_los": True, "label": "stacked crates"},
            (12, 12): {"room": "Lab", "cover_bonus": 2, "blocks_los": False, "label": "a row of lab benches"},
            (2, 7): {"room": "Sleeping Quarters", "cover_bonus": 1, "blocks_los": False, "label": "between bunks"},
            (6, 1): {"room": "Mess Hall", "cover_bonus": 1, "blocks_los": False, "label": "the galley counter"},
            (7, 17): {"room": "Hangar", "cover_bonus": 2, "blocks_los": True, "label": "behind tool racks"},
        }

    def is_hiding_spot(self, x: int, y: int) -> bool:
        """Return True if the coordinate is a designated hiding tile."""
        return (x, y) in self.hiding_spots

    def get_hiding_spot(self, x: int, y: int) -> Dict:
        """Return hiding spot metadata for the coordinate or None."""
        return self.hiding_spots.get((x, y))
