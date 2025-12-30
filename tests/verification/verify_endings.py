
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from engine import GameState, Difficulty
from core.event_system import event_bus, EventType, GameEvent
from entities.item import Item

def verify_radio_rescue():
    print("\n--- Testing Radio Rescue Ending ---")
    game = GameState()
    game.paranoia_level = 0
    game.random_events.events = []
    
    # 1. Sabotage Radio
    game.sabotage.radio_operational = False
    print("Radio sabotaged.")
    
    # 2. Move to Radio Room
    room_coords = game.station_map.rooms["Radio Room"]
    cx, cy = (room_coords[0] + room_coords[2]) // 2, (room_coords[1] + room_coords[3]) // 2
    game.player.location = (cx, cy)
    print(f"Moved MacReady to Radio Room {game.player.location}")
    
    # 3. Attempt SOS (Should fail - radio damaged)
    caught_warnings = []
    def on_warning(e): caught_warnings.append(e.payload['text'])
    event_bus.subscribe(EventType.WARNING, on_warning)
    
    game.dispatcher.dispatch(game.context, "SOS")
    print(f"SOS without repair: {caught_warnings[-1] if caught_warnings else 'No warning'}")
    
    # 4. Repair (Should fail - no tools)
    game.dispatcher.dispatch(game.context, "REPAIR RADIO")
    print(f"Repair without tools: {caught_warnings[-1] if caught_warnings else 'No warning'}")
    
    # 5. Get Tools and Repair
    game.player.inventory.append(Item("Tools", "A heavy toolbox"))
    game.dispatcher.dispatch(game.context, "REPAIR RADIO")
    print(f"Radio operational status: {game.sabotage.radio_operational}")
    
    # 6. Send SOS
    game.dispatcher.dispatch(game.context, "SOS")
    print(f"Rescue signal active: {game.rescue_signal_active}")
    print(f"Turns remaining: {game.rescue_turns_remaining}")
    
    # 7. Wait until rescue
    caught_endings = []
    def on_ending(e): caught_endings.append(e.payload)
    event_bus.subscribe(EventType.ENDING_REPORT, on_ending)
    
    print("Waiting for rescue arrival (20 turns)...")
    for _ in range(25):
        if game.game_over: 
            print(f"Game over triggered on turn {game.turn}")
            break
        game.player.stress = 0
        game.player.location = (cx, cy)
        game.advance_turn()
        
    event_bus.unsubscribe(EventType.WARNING, on_warning)
    event_bus.unsubscribe(EventType.ENDING_REPORT, on_ending)
    
    if caught_endings and caught_endings[0]['ending_type'] == "RESCUE":
        print("SUCCESS: Radio Rescue ending triggered!")
    else:
        print(f"FAILURE: Rescue ending not triggered. Endings: {caught_endings}")

def verify_helicopter_escape():
    print("\n--- Testing Helicopter Escape Ending ---")
    game = GameState()
    game.paranoia_level = 0
    game.random_events.events = []
    
    # 1. Sabotage Chopper
    game.helicopter_operational = False
    game.helicopter_status = "BROKEN"
    print("Helicopter sabotaged.")
    
    # 2. Move to Hangar
    room_coords = game.station_map.rooms["Hangar"]
    cx, cy = (room_coords[0] + room_coords[2]) // 2, (room_coords[1] + room_coords[3]) // 2
    game.player.location = (cx, cy)
    print(f"Moved MacReady to Hangar {game.player.location}")
    
    # 3. Attempt Escape (Should fail)
    caught_warnings = []
    def on_warning(e): caught_warnings.append(e.payload['text'])
    event_bus.subscribe(EventType.WARNING, on_warning)
    
    game.dispatcher.dispatch(game.context, "ESCAPE")
    print(f"Escape without repair: {caught_warnings[-1] if caught_warnings else 'No warning'}")
    
    # 4. Repair (Should fail - missing parts)
    game.player.inventory.append(Item("Tools", "A heavy toolbox"))
    game.dispatcher.dispatch(game.context, "REPAIR HELICOPTER")
    print(f"Repair with only tools: {caught_warnings[-1] if caught_warnings else 'No warning'}")
    
    # 5. Get Parts and Repair
    game.player.inventory.append(Item("Replacement Parts", "Engine components"))
    game.dispatcher.dispatch(game.context, "REPAIR HELICOPTER")
    print(f"Helicopter status: {game.helicopter_status}")
    
    # 6. Escape
    caught_endings = []
    def on_ending(e): caught_endings.append(e.payload)
    event_bus.subscribe(EventType.ENDING_REPORT, on_ending)
    
    game.dispatcher.dispatch(game.context, "ESCAPE")
    
    event_bus.unsubscribe(EventType.WARNING, on_warning)
    event_bus.unsubscribe(EventType.ENDING_REPORT, on_ending)
    
    if caught_endings and caught_endings[0]['ending_type'] == "ESCAPE":
        print("SUCCESS: Helicopter Escape ending triggered!")
    else:
        print(f"FAILURE: Escape ending not triggered. Endings: {caught_endings}")

if __name__ == "__main__":
    try:
        verify_radio_rescue()
        verify_helicopter_escape()
    except Exception as e:
        print(f"Verification crashed: {e}")
        import traceback
        traceback.print_exc()
