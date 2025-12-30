"""
ASCII Renderer with Camera/Viewport System
The "eye" through which the player sees the station.
"""

class Camera:
    """Viewport controller that follows the player."""
    
    def __init__(self, viewport_width=20, viewport_height=20):
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.x = 0  # Top-left corner of viewport
        self.y = 0
        self.padding = 5  # How close to edge before panning
    
    def follow(self, target_x, target_y, map_width, map_height):
        """Center viewport on target, clamped to map bounds."""
        # Calculate ideal camera position (centered on target)
        ideal_x = target_x - self.viewport_width // 2
        ideal_y = target_y - self.viewport_height // 2
        
        # Clamp to map bounds
        self.x = max(0, min(ideal_x, map_width - self.viewport_width))
        self.y = max(0, min(ideal_y, map_height - self.viewport_height))
    
    def world_to_screen(self, world_x, world_y):
        """Convert world coordinates to screen coordinates."""
        return (world_x - self.x, world_y - self.y)
    
    def is_visible(self, world_x, world_y):
        """Check if world position is within viewport."""
        screen_x, screen_y = self.world_to_screen(world_x, world_y)
        return (0 <= screen_x < self.viewport_width and 
                0 <= screen_y < self.viewport_height)


class TerminalRenderer:
    """
    Renders the game world as ASCII art through a 20x20 viewport.
    Simulates a 1982 terminal display.
    """
    
    # Character legend
    CHAR_PLAYER = '@'
    CHAR_NPC = lambda name: name[0].upper() if name else '?'
    CHAR_WALL = '#'
    CHAR_FLOOR = '.'
    CHAR_DOOR = '+'
    CHAR_ITEM = '*'
    CHAR_CORPSE = '%'
    CHAR_UNKNOWN = ' '
    CHAR_OUT_OF_PLACE = '!'
    
    def __init__(self, station_map, viewport_size=20):
        self.map = station_map
        self.camera = Camera(viewport_size, viewport_size)
        self.show_room_labels = True
        self.fog_of_war = False  # Optional: hide unexplored areas
    
    def render(self, game_state, player=None):
        """
        Generate the ASCII display for the current game state.
        Returns a list of strings (one per row).
        """
        schedule_flags = self._compute_out_of_schedule(game_state)

        if player:
            self.camera.follow(
                player.location[0], 
                player.location[1],
                self.map.width,
                self.map.height
            )
        
        # Build the display grid
        display = []
        
        # Header with coordinates
        header = self._render_header()
        display.append(header)
        display.append("+" + "-" * (self.camera.viewport_width * 2 - 1) + "+")
        
        for screen_y in range(self.camera.viewport_height):
            world_y = screen_y + self.camera.y
            row_chars = []
            
            for screen_x in range(self.camera.viewport_width):
                world_x = screen_x + self.camera.x
                char = self._get_char_at(world_x, world_y, game_state, player, schedule_flags)
                row_chars.append(char)
            
            # Add row with border
            display.append("|" + " ".join(row_chars) + "|")
        
        display.append("+" + "-" * (self.camera.viewport_width * 2 - 1) + "+")
        
        # Legend
        display.append(self._render_legend(game_state, player, schedule_flags))
        
        return "\n".join(display)
    
    def _render_header(self):
        """Render coordinate header."""
        # Show column numbers (every 5)
        nums = []
        for i in range(self.camera.viewport_width):
            world_x = i + self.camera.x
            if world_x % 5 == 0:
                nums.append(str(world_x % 10))
            else:
                nums.append(" ")
        return " " + " ".join(nums) + " "
    
    def _compute_out_of_schedule(self, game_state):
        """Cache out-of-schedule flags for crew to align UI with interrogation bonus logic."""
        flags = {}
        if not game_state or not getattr(game_state, "crew", None):
            return flags

        for member in game_state.crew:
            if hasattr(member, "is_out_of_schedule"):
                try:
                    flags[member.name] = member.is_out_of_schedule(game_state)
                except Exception:
                    flags[member.name] = False
        return flags

    def _get_char_at(self, x, y, game_state, player, schedule_flags=None):
        """Determine what character to display at this position."""
        # Bounds check
        if not (0 <= x < self.map.width and 0 <= y < self.map.height):
            return self.CHAR_UNKNOWN
        
        # Layer 1: Player (highest priority)
        if player and player.location == (x, y):
            return self.CHAR_PLAYER
        
        # Layer 2: NPCs
        for member in game_state.crew:
            if member.location == (x, y) and member != player:
                if not member.is_alive:
                    return self.CHAR_CORPSE
                if schedule_flags and schedule_flags.get(member.name):
                    return self.CHAR_OUT_OF_PLACE
                return member.name[0].upper()
        
        # Layer 3: Items
        room_name = self.map.get_room_name(x, y)
        items = self.map.room_items.get(room_name, [])
        if items and self._is_room_origin(x, y, room_name):
            return self.CHAR_ITEM
        
        # Layer 4: Room structure
        return self._get_terrain_char(x, y)
    
    def _is_room_origin(self, x, y, room_name):
        """Check if this is the 'origin' point of a room (for item display)."""
        if room_name.startswith("Corridor"):
            return False
        room_bounds = self.map.rooms.get(room_name)
        if room_bounds:
            return (x, y) == (room_bounds[0], room_bounds[1])
        return False
    
    def _get_terrain_char(self, x, y):
        """Get the terrain character at this position."""
        room_name = self.map.get_room_name(x, y)
        
        if room_name.startswith("Corridor"):
            return self.CHAR_FLOOR
        
        # Check if on room boundary
        if room_name in self.map.rooms:
            x1, y1, x2, y2 = self.map.rooms[room_name]
            on_border = (x == x1 or x == x2 or y == y1 or y == y2)
            
            # Doors at midpoints of walls
            if on_border:
                mid_x = (x1 + x2) // 2
                mid_y = (y1 + y2) // 2
                if (x == mid_x and (y == y1 or y == y2)) or \
                   (y == mid_y and (x == x1 or x == x2)):
                    return self.CHAR_DOOR
                return self.CHAR_WALL
        
        return self.CHAR_FLOOR
    
    def _render_legend(self, game_state, player=None, schedule_flags=None):
        """Render the character legend with context-aware hints."""
        legend_items = []

        # Priority 0: Player Context (Room & Action Hints)
        if player:
            px, py = player.location
            room_name = self.map.get_room_name(px, py)

            # Action Hint: Items at location?
            # Items are abstractly in the room, accessible if player is in the room.
            # But visually we put them at top-left.
            # Let's check if there are items in this room.
            items_here = self.map.room_items.get(room_name, [])
            if items_here:
                count = len(items_here)
                hint = f"{count} item{'s' if count > 1 else ''} here"
                legend_items.append(f"[{room_name}: {hint} - GET?]")
            elif not room_name.startswith("Corridor"):
                legend_items.append(f"[{room_name}]")

            # Action Hint: Dead Body?
            corpse_here = next((m for m in game_state.crew if m.location == (px, py) and not m.is_alive), None)
            if corpse_here:
                legend_items.append(f"[ Corpse: {corpse_here.name} - TEST/SEARCH? ]")

        # Priority 1: NPCs in current viewport
        visible_npcs = []
        out_of_place_visible = []
        for member in game_state.crew:
            if self.camera.is_visible(*member.location) and member != player:
                status = "" if member.is_alive else " (DEAD)"
                # Use % for corpse in legend if dead to match map
                out_of_place = schedule_flags.get(member.name) if schedule_flags else False
                symbol = "%" if not member.is_alive else (self.CHAR_OUT_OF_PLACE if out_of_place else member.name[0])
                visible_npcs.append(f"{symbol}={member.name}{status}")
                if out_of_place and member.is_alive:
                    out_of_place_visible.append(member)
        
        if visible_npcs:
            legend_items.append(f"[{'] ['.join(visible_npcs[:3])}]")

        if out_of_place_visible:
            try:
                from systems.interrogation import InterrogationSystem
                bonus = getattr(InterrogationSystem, "WHEREABOUTS_BONUS", 0)
            except Exception:
                bonus = 0

            details = []
            for member in out_of_place_visible[:2]:
                if hasattr(member, "get_schedule_info"):
                    info = member.get_schedule_info(game_state)
                    expected = info.get("expected_room") or "?"
                    details.append(f"{member.name}->{expected}")
                else:
                    details.append(member.name)
            if len(out_of_place_visible) > 2:
                details.append("...")
            bonus_hint = f"+{bonus}" if bonus else "+?"
            legend_items.append(f"[{self.CHAR_OUT_OF_PLACE}=Out of place ({bonus_hint} INTERROGATE): {', '.join(details)}]")

        # Priority 2: Items in current viewport (if not already covered by local context)
        visible_items = []
        for room_name, items in self.map.room_items.items():
            if not items: continue
            room_bounds = self.map.rooms.get(room_name)
            if not room_bounds: continue

            # Check if * marker is visible
            origin_x, origin_y = room_bounds[0], room_bounds[1]
            if self.camera.is_visible(origin_x, origin_y):
                # List items only if we are NOT in that room (otherwise covered by context)
                if player and self.map.get_room_name(*player.location) != room_name:
                    for item in items:
                        if item.name not in visible_items:
                            visible_items.append(item.name)

        if visible_items:
            # Truncate if too many
            if len(visible_items) > 2:
                item_str = f"{visible_items[0]}, {visible_items[1]}, ..."
            else:
                item_str = ", ".join(visible_items)
            legend_items.append(f"[*={item_str}]")

        base_legend = "[@=You]"
        if not legend_items:
            return f"{base_legend} [.=Floor] [#=Wall] [+=Door]"

        return f"{base_legend} {' '.join(legend_items)}"

    
    def render_minimap(self, game_state, player):
        """Render a small 5x5 local area minimap."""
        lines = []
        px, py = player.location
        
        for dy in range(-2, 3):
            row = []
            for dx in range(-2, 3):
                wx, wy = px + dx, py + dy
                if dx == 0 and dy == 0:
                    row.append('@')
                elif not (0 <= wx < self.map.width and 0 <= wy < self.map.height):
                    row.append(' ')
                else:
                    # Check for NPCs
                    npc = next((m for m in game_state.crew 
                               if m.location == (wx, wy) and m != player), None)
                    if npc:
                        row.append(npc.name[0])
                    else:
                        row.append('.')
            lines.append("".join(row))
        
        return "\n".join(lines)
