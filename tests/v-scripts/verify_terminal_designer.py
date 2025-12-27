"""
Verification script for Agent 5: The Terminal Designer
Tests the UI and Audio systems.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_command_parser():
    """Test the natural language command parser."""
    from ui.command_parser import CommandParser
    
    print("=" * 50)
    print("TESTING: Command Parser")
    print("=" * 50)
    
    parser = CommandParser(known_names=["MACREADY", "CHILDS", "BLAIR", "NORRIS", "PALMER"])
    
    # Test cases: (input, expected_action, expected_target)
    tests = [
        ("go north", "MOVE", "NORTH"),
        ("n", "MOVE", "NORTH"),
        ("look at macready", "LOOK", "MACREADY"),
        ("examine childs", "LOOK", "CHILDS"),
        ("check norris for breath", "LOOK", "NORRIS"),
        ("talk to blair", "TALK", "BLAIR"),
        ("pick up flamethrower", "GET", "FLAMETHROWER"),
        ("attack palmer", "ATTACK", "PALMER"),
        ("inventory", "INVENTORY", None),
        ("help", "HELP", None),
    ]
    
    passed = 0
    failed = 0
    
    for user_input, expected_action, expected_target in tests:
        result = parser.parse(user_input)
        
        action_match = result['action'] == expected_action
        target_match = (result.get('target') == expected_target) if expected_target else True
        
        if action_match and target_match:
            print(f"  [PASS] '{user_input}' -> {result['action']} {result.get('target', '')}")
            passed += 1
        else:
            print(f"  [FAIL] '{user_input}'")
            print(f"         Expected: {expected_action} {expected_target}")
            print(f"         Got: {result['action']} {result.get('target')}")
            failed += 1
    
    print(f"\nParser Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_renderer():
    """Test the ASCII renderer."""
    from ui.renderer import TerminalRenderer, Camera
    
    print("\n" + "=" * 50)
    print("TESTING: Terminal Renderer")
    print("=" * 50)
    
    # Create a mock station map
    class MockMap:
        def __init__(self):
            self.width = 20
            self.height = 20
            self.rooms = {
                "Rec Room": (5, 5, 10, 10),
                "Infirmary": (0, 0, 4, 4),
            }
            self.room_items = {"Rec Room": []}
        
        def get_room_name(self, x, y):
            for name, (x1, y1, x2, y2) in self.rooms.items():
                if x1 <= x <= x2 and y1 <= y <= y2:
                    return name
            return f"Corridor ({x},{y})"
    
    # Create mock game state and player
    class MockPlayer:
        def __init__(self):
            self.name = "MacReady"
            self.location = (7, 7)
            self.is_alive = True
    
    class MockGameState:
        def __init__(self):
            self.crew = [MockPlayer()]
    
    mock_map = MockMap()
    renderer = TerminalRenderer(mock_map)
    game_state = MockGameState()
    player = game_state.crew[0]
    
    try:
        output = renderer.render(game_state, player)
        print("  [PASS] Renderer produced output")
        print("  Output preview (first 5 lines):")
        for line in output.split('\n')[:5]:
            print(f"    {line}")
        
        # Check that player symbol appears
        if '@' in output:
            print("  [PASS] Player symbol '@' found in output")
        else:
            print("  [FAIL] Player symbol '@' not found")
            return False
        
        return True
    except Exception as e:
        print(f"  [FAIL] Renderer error: {e}")
        return False


def test_crt_effects():
    """Test CRT effects (non-timing tests only)."""
    from ui.crt_effects import CRTOutput, ANSI
    
    print("\n" + "=" * 50)
    print("TESTING: CRT Effects")
    print("=" * 50)
    
    crt = CRTOutput(palette="amber")
    
    # Test scanline
    test_text = "Line 1\nLine 2\nLine 3"
    result = crt.scanline(test_text)
    
    if ANSI.DIM in result:
        print("  [PASS] Scanline effect applies DIM to alternating lines")
    else:
        print("  [FAIL] Scanline effect not working")
        return False
    
    # Test glitch level
    crt.set_glitch_level(50)
    if crt.glitch_level == 50:
        print("  [PASS] Glitch level can be set")
    else:
        print("  [FAIL] Glitch level not set correctly")
        return False
    
    # Test prompt generation
    prompt = crt.prompt("TEST")
    if "TEST>" in prompt:
        print("  [PASS] Prompt generation works")
    else:
        print("  [FAIL] Prompt not generated correctly")
        return False
    
    return True


def test_audio_manager():
    """Test the audio manager (muted)."""
    from audio.audio_manager import AudioManager, Sound, AUDIO_AVAILABLE
    
    print("\n" + "=" * 50)
    print("TESTING: Audio Manager")
    print("=" * 50)
    
    print(f"  Audio available: {AUDIO_AVAILABLE}")
    
    # Create muted audio manager for testing
    audio = AudioManager(enabled=True)
    audio.mute()  # Mute to avoid sound during tests
    
    try:
        # Test event triggering
        audio.trigger_event('success')
        print("  [PASS] Event triggering works (muted)")
        
        # Test ambient loop
        audio.ambient_loop(Sound.THRUM)
        if audio.ambient_sound == Sound.THRUM:
            print("  [PASS] Ambient loop can be set")
        else:
            print("  [FAIL] Ambient loop not set")
            return False
        
        # Test stop ambient
        audio.stop_ambient()
        if audio.ambient_sound is None:
            print("  [PASS] Ambient loop can be stopped")
        else:
            print("  [FAIL] Ambient loop not stopped")
            return False
        
        # Test toggle mute
        was_muted = audio.muted
        audio.toggle_mute()
        if audio.muted != was_muted:
            print("  [PASS] Mute toggle works")
        else:
            print("  [FAIL] Mute toggle failed")
            return False
        
        return True
    except Exception as e:
        print(f"  [FAIL] Audio manager error: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("   AGENT 5: TERMINAL DESIGNER - VERIFICATION")
    print("=" * 60)
    
    results = {
        "Command Parser": test_command_parser(),
        "Terminal Renderer": test_renderer(),
        "CRT Effects": test_crt_effects(),
        "Audio Manager": test_audio_manager(),
    }
    
    print("\n" + "=" * 60)
    print("   SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("  *** ALL TESTS PASSED ***")
    else:
        print("  *** SOME TESTS FAILED ***")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
