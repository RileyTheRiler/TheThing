import json
import os
import pickle
from datetime import datetime

class SaveManager:
    def __init__(self, save_dir="data/saves", gamestate_factory=None):
        self.save_dir = save_dir
        self.gamestate_factory = gamestate_factory
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            
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

    def load_game(self, slot_name="auto"):
        filename = f"{slot_name}.json"
        filepath = os.path.join(self.save_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"Save file not found: {filepath}")
            return None
            
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Rehydrate if factory is provided
            if self.gamestate_factory:
                return self.gamestate_factory(data)

            return data
        except Exception as e:
            print(f"Failed to load game: {e}")
            return None
