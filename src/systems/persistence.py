import json
import os
from core.event_system import event_bus, EventType, GameEvent

class SaveManager:
    def __init__(self, save_dir="data/saves", game_state_factory=None):
        self.save_dir = save_dir
        self.game_state_factory = game_state_factory
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        
    def on_turn_advance(self, event: GameEvent):
        """Subscriber for TURN_ADVANCE event. Handles auto-saving."""
        game_state = event.payload.get("game_state")
        if game_state and game_state.turn % 5 == 0:
            try:
                self.save_game(game_state, "autosave")
            except Exception:
                pass  # Don't interrupt gameplay on save failure
            
    def save_game(self, game_state, slot_name="auto"):
        """
        Saves the game state using to_dict().
        """
        filename = f"{slot_name}.json"
        filepath = os.path.join(self.save_dir, filename)
        
        try:
            data = game_state.to_dict()
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Game saved to {filepath}")
            return True
        except Exception as e:
            print(f"Failed to save game: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_game(self, slot_name="auto", factory=None):
        filename = f"{slot_name}.json"
        filepath = os.path.join(self.save_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"Save file not found: {filepath}")
            return None
            
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Use factory if provided to avoid circular dependencies
            hydrator = factory if factory else self.game_state_factory
            if hydrator:
                try:
                    return hydrator(data)
                except Exception as e:
                    print(f"Failed to hydrate game state from {filepath}: {e}")
                    import traceback
                    traceback.print_exc()
                    return None

            return data
        except json.JSONDecodeError as e:
            print(f"Malformed save file {filepath}: {e}")
            return None
        except Exception as e:
            print(f"Failed to load game from {filepath}: {e}")
            return None
