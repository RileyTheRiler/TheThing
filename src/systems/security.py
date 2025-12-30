"""Security system for The Thing game.

Manages security cameras and motion sensors that detect movement and log
events to a security console that NPCs can check.
"""

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from core.event_system import event_bus, EventType, GameEvent

if TYPE_CHECKING:
    from engine import GameState


class SecurityDevice:
    """Base class for security devices."""

    def __init__(self, position: Tuple[int, int], room: str, device_type: str):
        self.position = position
        self.room = room
        self.device_type = device_type
        self.operational = True
        self.sabotaged_turns = 0  # Turns until device is restored

    def is_operational(self) -> bool:
        """Check if device is currently working."""
        return self.operational and self.sabotaged_turns <= 0


class Camera(SecurityDevice):
    """Security camera with directional cone of view."""

    # Direction vectors for cone calculation
    DIRECTIONS = {
        "N": (0, -1),
        "S": (0, 1),
        "E": (1, 0),
        "W": (-1, 0),
    }

    def __init__(self, position: Tuple[int, int], room: str, facing: str, range_tiles: int = 3):
        super().__init__(position, room, "camera")
        self.facing = facing.upper()
        self.range_tiles = range_tiles

    def get_visible_tiles(self) -> List[Tuple[int, int]]:
        """Return all tiles this camera can see (cone of view)."""
        if not self.is_operational():
            return []

        visible = []
        dx, dy = self.DIRECTIONS.get(self.facing, (0, 0))
        x, y = self.position

        # Camera sees a cone spreading out in the facing direction
        # Range 1: 1 tile wide, Range 2: 3 tiles wide, Range 3: 5 tiles wide
        for dist in range(1, self.range_tiles + 1):
            center_x = x + dx * dist
            center_y = y + dy * dist

            # Width of cone at this distance
            spread = dist - 1  # 0, 1, 2 tiles to each side

            if dx != 0:  # Facing E/W, spread along Y
                for offset in range(-spread, spread + 1):
                    visible.append((center_x, center_y + offset))
            else:  # Facing N/S, spread along X
                for offset in range(-spread, spread + 1):
                    visible.append((center_x + offset, center_y))

        return visible

    def can_see(self, target_pos: Tuple[int, int]) -> bool:
        """Check if camera can see the given position."""
        return target_pos in self.get_visible_tiles()


class MotionSensor(SecurityDevice):
    """Motion sensor that triggers on any movement through its tile."""

    def __init__(self, position: Tuple[int, int], room: str):
        super().__init__(position, room, "motion_sensor")

    def detects(self, target_pos: Tuple[int, int]) -> bool:
        """Check if sensor detects movement at position."""
        return self.is_operational() and target_pos == self.position


class SecurityLog:
    """Log of security detections for review at security console."""

    MAX_LOG_SIZE = 50  # Keep last 50 entries

    def __init__(self):
        self.entries: List[Dict] = []
        self.unread_count = 0

    def add_entry(self, turn: int, device_type: str, device_room: str,
                  target_name: str, target_pos: Tuple[int, int], description: str):
        """Add a detection entry to the log."""
        entry = {
            "turn": turn,
            "device_type": device_type,
            "device_room": device_room,
            "target": target_name,
            "position": target_pos,
            "description": description,
            "read": False
        }
        self.entries.append(entry)
        self.unread_count += 1

        # Trim old entries
        if len(self.entries) > self.MAX_LOG_SIZE:
            removed = self.entries.pop(0)
            if not removed["read"]:
                self.unread_count -= 1

    def get_unread(self) -> List[Dict]:
        """Get all unread entries."""
        return [e for e in self.entries if not e["read"]]

    def mark_all_read(self):
        """Mark all entries as read."""
        for entry in self.entries:
            entry["read"] = True
        self.unread_count = 0

    def get_recent(self, count: int = 10) -> List[Dict]:
        """Get the most recent entries."""
        return self.entries[-count:]

    def to_dict(self) -> Dict:
        """Serialize log for saving."""
        return {
            "entries": self.entries,
            "unread_count": self.unread_count
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SecurityLog':
        """Deserialize log from save data."""
        log = cls()
        if data:
            log.entries = data.get("entries", [])
            log.unread_count = data.get("unread_count", 0)
        return log


class SecuritySystem:
    """Manages security cameras and motion sensors throughout the station.

    When the player or NPCs move into camera view or trigger sensors,
    events are logged to a security console that NPCs can check.
    """

    # Sabotage configuration
    SABOTAGE_NOISE = 4  # Noise level when sabotaging
    SABOTAGE_DURATION = 15  # Turns until device auto-repairs

    def __init__(self, game_state: Optional['GameState'] = None):
        self.game_state = game_state
        self.cameras: Dict[Tuple[int, int], Camera] = {}
        self.motion_sensors: Dict[Tuple[int, int], MotionSensor] = {}
        self.security_log = SecurityLog()

        # Initialize default security devices
        self._init_default_devices()

        # Subscribe to movement events
        event_bus.subscribe(EventType.MOVEMENT, self.on_movement)
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        """Unsubscribe from events."""
        event_bus.unsubscribe(EventType.MOVEMENT, self.on_movement)
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def _init_default_devices(self):
        """Set up default camera and sensor positions."""
        # Cameras - positioned to watch key areas
        default_cameras = [
            ((6, 6), "Rec Room", "S", 3),      # Watches Rec Room entrance
            ((12, 2), "Radio Room", "E", 3),   # Watches Radio Room
            ((17, 2), "Storage", "W", 3),      # Watches Storage room
            ((7, 17), "Hangar", "N", 3),       # Watches Hangar entrance
            ((12, 12), "Lab", "S", 3),         # Watches Lab
        ]

        for pos, room, facing, range_tiles in default_cameras:
            self.cameras[pos] = Camera(pos, room, facing, range_tiles)

        # Motion sensors - positioned at critical chokepoints
        default_sensors = [
            ((13, 3), "Radio Room"),   # Radio Room entrance
            ((16, 17), "Generator"),   # Generator entrance
            ((1, 17), "Kennel"),       # Kennel corner
        ]

        for pos, room in default_sensors:
            self.motion_sensors[pos] = MotionSensor(pos, room)

    def on_movement(self, event: GameEvent):
        """Handle movement events and check for detections."""
        payload = event.payload
        if not payload:
            return

        mover = payload.get("mover")
        new_pos = payload.get("to")
        game_state = payload.get("game_state")

        if not mover or not new_pos:
            return

        turn = game_state.turn if game_state else 0

        # Check cameras
        for camera in self.cameras.values():
            if camera.can_see(new_pos):
                self._log_detection(
                    turn, "camera", camera.room,
                    getattr(mover, "name", "Unknown"),
                    new_pos,
                    f"Camera in {camera.room} detected movement"
                )

        # Check motion sensors
        for sensor in self.motion_sensors.values():
            if sensor.detects(new_pos):
                self._log_detection(
                    turn, "motion_sensor", sensor.room,
                    getattr(mover, "name", "Unknown"),
                    new_pos,
                    f"Motion sensor in {sensor.room} triggered"
                )

    def _log_detection(self, turn: int, device_type: str, device_room: str,
                       target_name: str, target_pos: Tuple[int, int], description: str):
        """Log a security detection."""
        self.security_log.add_entry(
            turn, device_type, device_room, target_name, target_pos, description
        )

        # Emit event for UI/other systems
        event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, {
            "source": "security",
            "device_type": device_type,
            "device_room": device_room,
            "target": target_name,
            "position": target_pos,
            "description": description
        }))

    def on_turn_advance(self, event: GameEvent):
        """Tick down sabotage timers on turn advance."""
        # Repair cameras
        for camera in self.cameras.values():
            if camera.sabotaged_turns > 0:
                camera.sabotaged_turns -= 1
                if camera.sabotaged_turns <= 0:
                    camera.operational = True

        # Repair motion sensors
        for sensor in self.motion_sensors.values():
            if sensor.sabotaged_turns > 0:
                sensor.sabotaged_turns -= 1
                if sensor.sabotaged_turns <= 0:
                    sensor.operational = True

    def sabotage_device(self, position: Tuple[int, int], game_state: 'GameState') -> Tuple[bool, str]:
        """Attempt to sabotage a security device at the given position.

        Returns (success, message).
        """
        device = self.cameras.get(position) or self.motion_sensors.get(position)

        if not device:
            return False, "No security device at this location."

        if not device.is_operational():
            return False, f"The {device.device_type.replace('_', ' ')} is already disabled."

        # Sabotage the device
        device.operational = False
        device.sabotaged_turns = self.SABOTAGE_DURATION

        device_name = device.device_type.replace('_', ' ')

        # Emit noise event (sabotage makes noise)
        event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, {
            "source": "sabotage",
            "noise_level": self.SABOTAGE_NOISE,
            "location": position,
            "game_state": game_state
        }))

        # Log to journal
        if hasattr(game_state, 'journal'):
            game_state.journal.append(
                f"[Turn {game_state.turn}] {device_name.title()} in {device.room} was sabotaged"
            )

        return True, f"You disable the {device_name} in {device.room}. It will be offline for {self.SABOTAGE_DURATION} turns."

    def get_device_at(self, position: Tuple[int, int]) -> Optional[SecurityDevice]:
        """Get the security device at a position, if any."""
        return self.cameras.get(position) or self.motion_sensors.get(position)

    def get_devices_in_room(self, room_name: str) -> List[SecurityDevice]:
        """Get all security devices in a given room."""
        devices = []
        for camera in self.cameras.values():
            if camera.room == room_name:
                devices.append(camera)
        for sensor in self.motion_sensors.values():
            if sensor.room == room_name:
                devices.append(sensor)
        return devices

    def get_all_camera_positions(self) -> List[Tuple[int, int]]:
        """Return positions of all cameras (for map rendering)."""
        return list(self.cameras.keys())

    def get_all_sensor_positions(self) -> List[Tuple[int, int]]:
        """Return positions of all motion sensors (for map rendering)."""
        return list(self.motion_sensors.keys())

    def check_console(self, npc=None) -> List[Dict]:
        """Check the security console and get unread alerts.

        If an NPC checks, they may investigate logged events.
        """
        unread = self.security_log.get_unread()
        self.security_log.mark_all_read()
        return unread

    def has_unread_alerts(self) -> bool:
        """Check if there are unread security alerts."""
        return self.security_log.unread_count > 0

    def get_status(self) -> str:
        """Get a status summary of security devices."""
        active_cameras = sum(1 for c in self.cameras.values() if c.is_operational())
        active_sensors = sum(1 for s in self.motion_sensors.values() if s.is_operational())
        total_cameras = len(self.cameras)
        total_sensors = len(self.motion_sensors)

        alerts = f" ({self.security_log.unread_count} unread alerts)" if self.security_log.unread_count > 0 else ""

        return f"Cameras: {active_cameras}/{total_cameras} | Sensors: {active_sensors}/{total_sensors}{alerts}"

    def to_dict(self) -> Dict:
        """Serialize security system state for saving."""
        cameras_data = {}
        for pos, cam in self.cameras.items():
            cameras_data[f"{pos[0]},{pos[1]}"] = {
                "operational": cam.operational,
                "sabotaged_turns": cam.sabotaged_turns,
                "facing": cam.facing,
                "range": cam.range_tiles,
                "room": cam.room
            }

        sensors_data = {}
        for pos, sensor in self.motion_sensors.items():
            sensors_data[f"{pos[0]},{pos[1]}"] = {
                "operational": sensor.operational,
                "sabotaged_turns": sensor.sabotaged_turns,
                "room": sensor.room
            }

        return {
            "cameras": cameras_data,
            "motion_sensors": sensors_data,
            "security_log": self.security_log.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict, game_state: Optional['GameState'] = None) -> 'SecuritySystem':
        """Deserialize security system from save data."""
        system = cls(game_state)

        if not data:
            return system

        # Restore camera states
        cameras_data = data.get("cameras", {})
        for pos_str, cam_data in cameras_data.items():
            x, y = map(int, pos_str.split(","))
            if (x, y) in system.cameras:
                system.cameras[(x, y)].operational = cam_data.get("operational", True)
                system.cameras[(x, y)].sabotaged_turns = cam_data.get("sabotaged_turns", 0)

        # Restore sensor states
        sensors_data = data.get("motion_sensors", {})
        for pos_str, sensor_data in sensors_data.items():
            x, y = map(int, pos_str.split(","))
            if (x, y) in system.motion_sensors:
                system.motion_sensors[(x, y)].operational = sensor_data.get("operational", True)
                system.motion_sensors[(x, y)].sabotaged_turns = sensor_data.get("sabotaged_turns", 0)

        # Restore security log
        system.security_log = SecurityLog.from_dict(data.get("security_log", {}))

        return system
