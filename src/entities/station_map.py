"""StationMap entity class for The Thing game."""

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
        self.room_items = {}

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
        for name, (x1, y1, x2, y2) in self.rooms.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return name
        return "Corridor (Sector {},{})".format(x, y)

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
        """Deserialize station map from dictionary."""
        sm = cls(data["width"], data["height"])
        items_dict = data.get("room_items", {})
        for room, items_data in items_dict.items():
            sm.room_items[room] = [Item.from_dict(i) for i in items_data]
        return sm
