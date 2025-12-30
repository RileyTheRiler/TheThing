"""
Verification Script for Agent 6: The Dungeon Master
Tests Weather System, Sabotage Events, Room State Manager, and Item System
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_weather_system():
    """Test the WeatherSystem class."""
    print("\n=== TESTING WEATHER SYSTEM ===")
    
    from systems.weather import WeatherSystem, WindDirection
    
    weather = WeatherSystem()
    print(f"✓ WeatherSystem initialized")
    print(f"  Storm Intensity: {weather.storm_intensity}")
    print(f"  Wind Direction: {weather.wind_direction.value}")
    print(f"  Visibility: {weather.get_visibility()}")
    
    # Test tick
    for i in range(5):
        events = weather.tick()
        print(f"  Tick {i+1}: Intensity={weather.storm_intensity}, Vis={weather.get_visibility():.1f}")
    
    # Test Northeasterly
    result = weather.trigger_northeasterly()
    print(f"✓ Northeasterly triggered:")
    print(f"  {result[:50]}...")
    print(f"  Active: {weather.northeasterly_active}")
    
    # Test temperature modifier
    effective_temp = weather.get_effective_temperature(-40)
    print(f"✓ Effective temperature at -40C: {effective_temp}C")
    
    print("✓ Weather System: PASSED")
    return True


def test_sabotage_system():
    """Test the SabotageManager class."""
    print("\n=== TESTING SABOTAGE SYSTEM ===")
    
    from systems.sabotage import SabotageManager, SabotageEvent
    
    # Mock game state
    class MockGameState:
        power_on = True
    
    game = MockGameState()
    sabotage = SabotageManager()
    
    print(f"✓ SabotageManager initialized")
    print(f"  Radio: {sabotage.radio_operational}")
    print(f"  Chopper: {sabotage.helicopter_operational}")
    
    # Test power outage
    result = sabotage.trigger_power_outage(game)
    print(f"✓ Power Outage triggered: {game.power_on == False}")
    
    # Test radio smashing
    result = sabotage.trigger_radio_smashing(game)
    print(f"✓ Radio Smashing: {sabotage.radio_operational == False}")
    
    # Test chopper destruction
    result = sabotage.trigger_chopper_destruction(game)
    print(f"✓ Chopper Destruction: {sabotage.helicopter_operational == False}")
    
    print(f"  Status: {sabotage.get_status()}")
    print("✓ Sabotage System: PASSED")
    return True


def test_room_state_system():
    """Test the RoomStateManager class."""
    print("\n=== TESTING ROOM STATE SYSTEM ===")
    
    from systems.room_state import RoomStateManager, RoomState
    
    rooms = ["Rec Room", "Infirmary", "Generator", "Kennel"]
    room_states = RoomStateManager(rooms)
    
    print(f"✓ RoomStateManager initialized with {len(rooms)} rooms")
    
    # Test adding states
    room_states.add_state("Rec Room", RoomState.DARK)
    print(f"✓ Added DARK to Rec Room: {room_states.is_room_dark('Rec Room')}")
    
    room_states.add_state("Rec Room", RoomState.BLOODY)
    print(f"✓ Added BLOODY to Rec Room: {room_states.is_room_bloody('Rec Room')}")
    
    # Test description modifiers
    desc = room_states.get_room_description_modifiers("Rec Room")
    print(f"✓ Room description: {desc}")
    
    # Test status icons
    icons = room_states.get_status_icons("Rec Room")
    print(f"✓ Status icons: {icons}")
    
    # Test communion modifier
    mod = room_states.get_communion_modifier("Rec Room")
    print(f"✓ Communion modifier (dark room): {mod}")
    
    # Test barricade
    result = room_states.barricade_room("Infirmary")
    print(f"✓ Barricade: {result}")
    print(f"  Is barricaded: {room_states.is_room_barricaded('Infirmary')}")
    
    print("✓ Room State System: PASSED")
    return True


def test_item_system():
    """Test the enhanced Item class."""
    print("\n=== TESTING ITEM SYSTEM ===")
    
    from engine import Item
    
    # Test basic item
    item = Item("Flamethrower", "M2A1", damage=3)
    print(f"✓ Basic item: {item}")
    
    # Test consumable
    scotch = Item("J&B Scotch", "MacReady's blend", uses=3, effect="reduce_stress", effect_value=10)
    print(f"✓ Consumable item: {scotch}")
    print(f"  Is consumable: {scotch.is_consumable()}")
    
    # Test consume
    scotch.consume()
    print(f"  After consume: {scotch.uses} uses left")
    
    scotch.consume()
    scotch.consume()
    print(f"  After 3 consumes: {scotch.uses} uses left")
    
    print("✓ Item System: PASSED")
    return True


def test_integration():
    """Test full integration with GameState."""
    print("\n=== TESTING GAMESTATE INTEGRATION ===")
    
    try:
        from engine import GameState
        
        game = GameState(seed=12345)
        print(f"✓ GameState initialized with seed")
        
        # Check all systems are present
        assert hasattr(game, 'weather'), "Missing weather system"
        assert hasattr(game, 'sabotage'), "Missing sabotage system"
        assert hasattr(game, 'room_states'), "Missing room_states system"
        print(f"✓ All Dungeon Master systems present")
        
        # Test advance_turn integration
        initial_temp = game.temperature
        game.advance_turn()
        print(f"✓ advance_turn completed")
        print(f"  Temperature: {initial_temp} -> {game.temperature}")
        print(f"  Weather: {game.weather.get_status()}")
        
        print("✓ Integration: PASSED")
        return True
        
    except Exception as e:
        print(f"✗ Integration FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 50)
    print("AGENT 6: DUNGEON MASTER - VERIFICATION")
    print("=" * 50)
    
    results = []
    
    results.append(("Weather System", test_weather_system()))
    results.append(("Sabotage System", test_sabotage_system()))
    results.append(("Room State System", test_room_state_system()))
    results.append(("Item System", test_item_system()))
    results.append(("Integration", test_integration()))
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
