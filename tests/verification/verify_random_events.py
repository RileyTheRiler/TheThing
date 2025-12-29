
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from engine import GameState, Difficulty
from systems.random_events import RandomEventSystem, EventCategory, RandomEvent
from core.event_system import event_bus, EventType, GameEvent

def test_force_move():
    print("Testing Force Move Event...")
    game = GameState(difficulty=Difficulty.NORMAL)
    
    # Setup player in specific room
    start_room = "Rec Room"
    room_coords = game.station_map.rooms[start_room]
    cx = (room_coords[0] + room_coords[2]) // 2
    cy = (room_coords[1] + room_coords[3]) // 2
    game.player.location = (cx, cy)
    
    print(f"Player start: {start_room} {game.player.location}")
    
    # Mock event
    event = RandomEvent(
        id="test_force_move",
        name="Test Move",
        description="Force Move",
        category=EventCategory.EQUIPMENT,
        severity=1,
        effect=lambda g: game.random_events._execute_effects(g, [{"type": "force_move_player"}])
    )
    
    # Execute
    game.random_events.execute_event(event, game)
    
    # Check location changed
    new_room = game.station_map.get_room_name(*game.player.location)
    print(f"Player end: {new_room} {game.player.location}")
    
    if new_room != start_room:
        print("SUCCESS: Player moved.")
    else:
        # Note: In rare cases, if Rec Room only connected to itself (impossible) or rng picked same room?
        # Rec Room connects to Hallways usually. 
        print("FAILURE: Player did not move (or moved to same room?)")

def test_spawn_item():
    print("\nTesting Spawn Item Event...")
    game = GameState()
    
    # Mock event
    event = RandomEvent(
        id="test_spawn_item",
        name="Test Spawn",
        description="Spawn Item",
        category=EventCategory.DISCOVERY,
        severity=1,
        effect=lambda g: game.random_events._execute_effects(g, [{"type": "spawn_item", "location": "player_room"}])
    )
    
    # We can't easily check internal list without mocking or modifying engine, 
    # but we can check if MESSAGE event was emitted.
    
    caught_messages = []
    def on_message(e):
        caught_messages.append(e.payload['text'])
        
    event_bus.subscribe(EventType.MESSAGE, on_message)
    
    game.random_events.execute_event(event, game)
    
    event_bus.unsubscribe(EventType.MESSAGE, on_message)
    
    found = any("You spot a" in msg for msg in caught_messages)
    if found:
        print(f"SUCCESS: Item spawn message detected: {[m for m in caught_messages if 'You spot a' in m]}")
    else:
        print(f"FAILURE: No spawn message. Got: {caught_messages}")

def test_weather_clear():
    print("\nTesting Weather Clear Event...")
    game = GameState()
    game.weather.intensity = 3
    
    event = RandomEvent(
        id="test_clear",
        name="Test Clear",
        description="Clear Weather",
        category=EventCategory.WEATHER,
        severity=1,
        effect=lambda g: game.random_events._execute_effects(g, [{"type": "weather_clear", "amount": 1}])
    )
    
    game.random_events.execute_event(event, game)
    
    print(f"Weather intensity: {game.weather.intensity}")
    if game.weather.intensity == 2:
        print("SUCCESS: Weather intensity reduced.")
    else:
        print(f"FAILURE: Weather intensity not reduced correctly. {game.weather.intensity}")


if __name__ == "__main__":
    try:
        test_force_move()
        test_spawn_item()
        test_weather_clear()
        print("\nAll verification tests completed.")
    except Exception as e:
        print(f"\nCRITICAL FAILURE: {e}")
        import traceback
        traceback.print_exc()
