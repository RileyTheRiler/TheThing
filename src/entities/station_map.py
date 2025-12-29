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
