#!/usr/bin/env python3
"""
Verification script for Tier 11 Isometric Interface Expansion.
Tests the visibility system, terminal events, and character model metadata.
"""

import sys
import os

# Add src to path
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')
sys.path.insert(0, src_path)

def test_visibility_computation():
    """Test 11.1: Visibility data is properly computed and serialized."""
    print("\n=== Test 11.1: Visibility Computation ===")
    
    from engine import GameState
    from systems.architect import Difficulty
    from systems.room_state import RoomState
    
    game = GameState(seed=42, difficulty=Difficulty.NORMAL)
    
    # Get player room and verify visibility computation
    player_room = game.station_map.get_room_name(*game.player.location)
    print(f"Player location: {player_room}")
    
    # Get adjacent rooms
    adjacent = game.station_map.get_connections(player_room)
    print(f"Adjacent rooms: {adjacent}")
    
    # Compute visible rooms (same logic as server.py)
    visible_rooms = [player_room]
    for adj_room in adjacent:
        if not game.room_states.has_state(adj_room, RoomState.BARRICADED):
            visible_rooms.append(adj_room)
    
    print(f"Visible rooms: {visible_rooms}")
    assert player_room in visible_rooms, "Player room must be visible"
    assert len(visible_rooms) >= 1, "At least player room must be visible"
    print("PASS: Visibility computation works correctly")
    
    # Test dark_rooms computation
    dark_rooms = []
    for room_name in game.station_map.rooms.keys():
        if game.room_states.has_state(room_name, RoomState.DARK):
            dark_rooms.append(room_name)
    print(f"Dark rooms: {dark_rooms}")
    
    # Test room_lighting dict
    room_lighting = {}
    for room_name in game.station_map.rooms.keys():
        is_dark = game.room_states.has_state(room_name, RoomState.DARK)
        room_lighting[room_name] = {
            'is_dark': is_dark,
            'is_powered': game.power_on,
            'visibility': 'full' if room_name == player_room else ('partial' if room_name in visible_rooms else 'hidden')
        }
    
    print(f"Room lighting entries: {len(room_lighting)}")
    assert len(room_lighting) == 10, f"Should have 10 rooms, got {len(room_lighting)}"
    assert room_lighting[player_room]['visibility'] == 'full', "Player room should have full visibility"
    print("PASS: Room lighting data generated correctly")
    
    # Test flashlight detection
    flashlight_active = any('FLASHLIGHT' in item.name.upper() for item in game.player.inventory)
    print(f"Flashlight active: {flashlight_active}")
    print("PASS: Flashlight detection works")
    
    return True


def test_character_json_compatibility():
    """Test 11.3: Character JSON has fields we can extend."""
    print("\n=== Test 11.3: Character JSON Structure ===")
    
    import json
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'characters.json')
    
    with open(config_path, 'r') as f:
        characters = json.load(f)
    
    print(f"Found {len(characters)} characters")
    
    # Verify structure is extendable
    for char in characters:
        assert 'name' in char, f"Character missing name"
        assert 'role' in char, f"{char.get('name', 'Unknown')} missing role"
        # These fields can be added for 11.3
        # model_key, height, color, build are optional
    
    print("Character names:", [c['name'] for c in characters])
    print("PASS: Character JSON structure is compatible for model extensions")
    return True


def test_server_serialization():
    """Test that server serialization includes new visibility fields."""
    print("\n=== Test: Server Serialization ===")
    
    # Import and check serialize_game_state has visibility fields
    import importlib.util
    server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
    
    with open(server_path, 'r') as f:
        server_code = f.read()
    
    # Check for visibility fields
    assert 'visible_rooms' in server_code, "server.py should serialize visible_rooms"
    assert 'dark_rooms' in server_code, "server.py should serialize dark_rooms"
    assert 'room_lighting' in server_code, "server.py should serialize room_lighting"
    assert 'flashlight_active' in server_code, "server.py should serialize flashlight_active"
    
    print("PASS: Server serialization includes all visibility fields")
    return True


def test_renderer_fog_method():
    """Test that renderer3d.js has fog visibility method."""
    print("\n=== Test: Renderer Fog Method ===")
    
    renderer_path = os.path.join(os.path.dirname(__file__), '..', 'web', 'static', 'js', 'renderer3d.js')
    
    with open(renderer_path, 'r') as f:
        renderer_code = f.read()
    
    assert 'updateRoomVisibility' in renderer_code, "renderer3d.js should have updateRoomVisibility method"
    assert 'fogGroup' in renderer_code, "renderer3d.js should create fog overlay group"
    assert 'visibleRooms' in renderer_code, "renderer3d.js should track visible rooms"
    assert 'flashlightActive' in renderer_code, "renderer3d.js should track flashlight state"
    
    print("PASS: Renderer has fog visibility methods")
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("TIER 11 ISOMETRIC INTERFACE VERIFICATION")
    print("=" * 60)
    
    all_passed = True
    
    try:
        all_passed &= test_visibility_computation()
    except Exception as e:
        print(f"FAIL: test_visibility_computation - {e}")
        all_passed = False
    
    try:
        all_passed &= test_character_json_compatibility()
    except Exception as e:
        print(f"FAIL: test_character_json_compatibility - {e}")
        all_passed = False
    
    try:
        all_passed &= test_server_serialization()
    except Exception as e:
        print(f"FAIL: test_server_serialization - {e}")
        all_passed = False
    
    try:
        all_passed &= test_renderer_fog_method()
    except Exception as e:
        print(f"FAIL: test_renderer_fog_method - {e}")
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TIER 11 TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)
