"""Tests for Security System: Cameras & Motion Sensors.

Verifies that security cameras and motion sensors detect movement
and log events to a security console that NPCs can check.
"""

import sys
sys.path.insert(0, "src")


class MockCrewMember:
    """Mock crew member for testing."""
    def __init__(self, name, location=(5, 5)):
        self.name = name
        self.location = location
        self.is_alive = True
        self.inventory = []


class MockStationMap:
    """Mock station map for testing."""
    def __init__(self):
        self.rooms = {
            "Rec Room": (0, 0, 10, 10),
            "Radio Room": (11, 0, 14, 4),
            "Storage": (15, 0, 19, 4),
            "Lab": (11, 11, 14, 14),
            "Hangar": (5, 15, 10, 19),
            "Generator": (15, 15, 19, 19),
            "Kennel": (0, 15, 4, 19),
        }

    def is_walkable(self, x, y):
        return 0 <= x <= 20 and 0 <= y <= 20

    def get_room_name(self, x, y):
        for name, (x1, y1, x2, y2) in self.rooms.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return name
        return "Corridor"


class MockGameState:
    """Mock game state for testing."""
    def __init__(self):
        self.player = MockCrewMember("MacReady", location=(5, 5))
        self.crew = [self.player]
        self.station_map = MockStationMap()
        self.turn = 1
        self.journal = []

    def advance_turn(self):
        self.turn += 1


def test_security_system_init():
    """Test that SecuritySystem initializes correctly."""
    from systems.security import SecuritySystem

    system = SecuritySystem()

    # Should have default cameras and sensors
    assert len(system.cameras) > 0
    assert len(system.motion_sensors) > 0
    assert system.security_log is not None

    system.cleanup()
    print("[PASS] SecuritySystem initializes correctly")


def test_camera_visible_tiles():
    """Test camera cone of view calculation."""
    from systems.security import Camera

    # Camera at (6, 6) facing South with range 3
    camera = Camera((6, 6), "Rec Room", "S", 3)

    visible = camera.get_visible_tiles()

    # Should see tiles in a spreading cone south
    # Range 1: (6, 7)
    # Range 2: (5, 8), (6, 8), (7, 8)
    # Range 3: (4, 9), (5, 9), (6, 9), (7, 9), (8, 9)
    assert (6, 7) in visible  # Directly south
    assert (6, 8) in visible  # Further south
    assert (5, 8) in visible  # Spread left
    assert (7, 8) in visible  # Spread right

    # Should not see tiles behind or to the side
    assert (6, 5) not in visible  # Behind (north)
    assert (10, 6) not in visible  # Far east (not in cone)

    print("[PASS] Camera visible tiles calculated correctly")


def test_camera_detection():
    """Test that cameras detect movement in their view."""
    from systems.security import Camera

    camera = Camera((6, 6), "Rec Room", "S", 3)

    # Should detect someone at (6, 7) - directly in view
    assert camera.can_see((6, 7)) == True

    # Should not detect someone behind
    assert camera.can_see((6, 5)) == False

    # Should not detect someone outside range
    assert camera.can_see((6, 15)) == False

    print("[PASS] Camera detection works correctly")


def test_camera_directions():
    """Test cameras facing different directions."""
    from systems.security import Camera

    # Test North-facing camera
    north_cam = Camera((10, 10), "Lab", "N", 2)
    assert north_cam.can_see((10, 9)) == True  # North
    assert north_cam.can_see((10, 11)) == False  # South (behind)

    # Test East-facing camera
    east_cam = Camera((10, 10), "Lab", "E", 2)
    assert east_cam.can_see((11, 10)) == True  # East
    assert east_cam.can_see((9, 10)) == False  # West (behind)

    # Test West-facing camera
    west_cam = Camera((10, 10), "Lab", "W", 2)
    assert west_cam.can_see((9, 10)) == True  # West
    assert west_cam.can_see((11, 10)) == False  # East (behind)

    print("[PASS] Camera directions work correctly")


def test_motion_sensor_detection():
    """Test motion sensor triggers on exact position."""
    from systems.security import MotionSensor

    sensor = MotionSensor((13, 3), "Radio Room")

    # Should trigger when someone walks on the sensor
    assert sensor.detects((13, 3)) == True

    # Should not trigger for adjacent tiles
    assert sensor.detects((12, 3)) == False
    assert sensor.detects((13, 4)) == False

    print("[PASS] Motion sensor detection works correctly")


def test_security_log():
    """Test security log entries."""
    from systems.security import SecurityLog

    log = SecurityLog()

    # Add an entry
    log.add_entry(1, "camera", "Rec Room", "MacReady", (6, 7), "Camera detected movement")

    assert log.unread_count == 1
    assert len(log.entries) == 1

    # Add more entries
    log.add_entry(2, "motion_sensor", "Radio Room", "Childs", (13, 3), "Motion sensor triggered")

    assert log.unread_count == 2

    # Get unread entries
    unread = log.get_unread()
    assert len(unread) == 2

    # Mark all as read
    log.mark_all_read()
    assert log.unread_count == 0

    # Entries should still exist
    assert len(log.entries) == 2

    print("[PASS] Security log works correctly")


def test_sabotage_device():
    """Test sabotaging security devices."""
    from systems.security import SecuritySystem

    game_state = MockGameState()
    system = SecuritySystem(game_state)

    # Find a camera position
    camera_pos = list(system.cameras.keys())[0]
    camera = system.cameras[camera_pos]

    # Camera should be operational
    assert camera.is_operational() == True

    # Sabotage it
    success, message = system.sabotage_device(camera_pos, game_state)

    assert success == True
    assert "disable" in message.lower()
    assert camera.is_operational() == False

    # Try to sabotage again - should fail
    success, message = system.sabotage_device(camera_pos, game_state)
    assert success == False
    assert "already" in message.lower()

    system.cleanup()
    print("[PASS] Device sabotage works correctly")


def test_sabotage_decay():
    """Test that sabotaged devices repair over time."""
    from systems.security import SecuritySystem
    from core.event_system import GameEvent, EventType

    game_state = MockGameState()
    system = SecuritySystem(game_state)

    # Sabotage a camera
    camera_pos = list(system.cameras.keys())[0]
    camera = system.cameras[camera_pos]

    system.sabotage_device(camera_pos, game_state)
    assert camera.is_operational() == False

    initial_turns = camera.sabotaged_turns

    # Simulate turn advances
    event = GameEvent(EventType.TURN_ADVANCE, {})
    system.on_turn_advance(event)

    assert camera.sabotaged_turns == initial_turns - 1

    # Advance until repaired
    for _ in range(initial_turns):
        system.on_turn_advance(event)

    assert camera.is_operational() == True

    system.cleanup()
    print("[PASS] Sabotage decay works correctly")


def test_camera_disabled_no_detection():
    """Test that disabled cameras don't detect movement."""
    from systems.security import Camera

    camera = Camera((6, 6), "Rec Room", "S", 3)

    # Should detect when operational
    assert camera.can_see((6, 7)) == True

    # Disable camera
    camera.operational = False

    # Should not detect anymore
    assert camera.can_see((6, 7)) == False
    assert len(camera.get_visible_tiles()) == 0

    print("[PASS] Disabled cameras don't detect")


def test_sensor_disabled_no_detection():
    """Test that disabled sensors don't trigger."""
    from systems.security import MotionSensor

    sensor = MotionSensor((13, 3), "Radio Room")

    # Should trigger when operational
    assert sensor.detects((13, 3)) == True

    # Disable sensor
    sensor.operational = False

    # Should not trigger anymore
    assert sensor.detects((13, 3)) == False

    print("[PASS] Disabled sensors don't trigger")


def test_get_devices_in_room():
    """Test getting all devices in a specific room."""
    from systems.security import SecuritySystem

    system = SecuritySystem()

    # Get devices in Rec Room
    rec_room_devices = system.get_devices_in_room("Rec Room")

    # Should have at least one camera there
    assert len(rec_room_devices) > 0

    # Check device type
    device_types = [d.device_type for d in rec_room_devices]
    assert "camera" in device_types or "motion_sensor" in device_types

    system.cleanup()
    print("[PASS] Get devices in room works correctly")


def test_security_status():
    """Test security status string generation."""
    from systems.security import SecuritySystem

    system = SecuritySystem()

    status = system.get_status()

    # Should contain camera and sensor counts
    assert "Cameras:" in status
    assert "Sensors:" in status

    # Sabotage a device
    camera_pos = list(system.cameras.keys())[0]
    system.cameras[camera_pos].operational = False

    new_status = system.get_status()

    # Active count should be lower
    # (Original might be "5/5", now should be "4/5")
    assert new_status != status or "4/" in new_status

    system.cleanup()
    print("[PASS] Security status works correctly")


def test_serialization():
    """Test save/load of security system."""
    from systems.security import SecuritySystem

    system = SecuritySystem()

    # Sabotage a camera
    camera_pos = list(system.cameras.keys())[0]
    system.sabotage_device(camera_pos, MockGameState())

    # Add log entries
    system.security_log.add_entry(1, "camera", "Rec Room", "MacReady", (6, 7), "Test")

    # Serialize
    data = system.to_dict()

    # Verify data structure
    assert "cameras" in data
    assert "motion_sensors" in data
    assert "security_log" in data

    system.cleanup()

    # Restore
    restored = SecuritySystem.from_dict(data)

    # Check camera is still sabotaged
    assert restored.cameras[camera_pos].is_operational() == False

    # Check log entry exists
    assert len(restored.security_log.entries) == 1

    restored.cleanup()
    print("[PASS] Serialization works correctly")


def test_has_unread_alerts():
    """Test checking for unread alerts."""
    from systems.security import SecuritySystem

    system = SecuritySystem()

    # Initially no unread
    assert system.has_unread_alerts() == False

    # Add an entry
    system.security_log.add_entry(1, "camera", "Rec Room", "MacReady", (6, 7), "Test")

    assert system.has_unread_alerts() == True

    # Check console (marks as read)
    system.check_console()

    assert system.has_unread_alerts() == False

    system.cleanup()
    print("[PASS] Has unread alerts works correctly")


def test_security_log_max_size():
    """Test that security log respects max size limit."""
    from systems.security import SecurityLog

    log = SecurityLog()

    # Add more entries than MAX_LOG_SIZE
    for i in range(60):
        log.add_entry(i, "camera", "Rec Room", f"Person{i}", (6, 7), "Test")

    # Should be capped at MAX_LOG_SIZE
    assert len(log.entries) == log.MAX_LOG_SIZE

    # Oldest entries should be removed
    assert log.entries[0]["turn"] > 0

    print("[PASS] Security log max size works correctly")


if __name__ == "__main__":
    test_security_system_init()
    test_camera_visible_tiles()
    test_camera_detection()
    test_camera_directions()
    test_motion_sensor_detection()
    test_security_log()
    test_sabotage_device()
    test_sabotage_decay()
    test_camera_disabled_no_detection()
    test_sensor_disabled_no_detection()
    test_get_devices_in_room()
    test_security_status()
    test_serialization()
    test_has_unread_alerts()
    test_security_log_max_size()

    print("\n=== ALL SECURITY SYSTEM TESTS PASSED ===")
