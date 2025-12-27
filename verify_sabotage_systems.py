import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from engine import GameState
from systems.room_state import RoomState

def test_sabotage():
    print("Initializing Game...")
    game = GameState()
    
    print(f"Blood Bank Destroyed: {game.blood_bank_destroyed}")
    
    print("\n--- Triggering Blood Sabotage ---")
    result = game.sabotage.trigger_blood_sabotage(game)
    print(result)
    
    if game.blood_bank_destroyed:
        print("PASS: GameState flag set.")
    else:
        print("FAIL: GameState flag NOT set.")
        
    print("\n--- Checking Infirmary State ---")
    is_bloody = game.room_states.has_state("Infirmary", RoomState.BLOODY)
    if is_bloody:
        print("PASS: Infirmary marked as BLOODY.")
    else:
        print("FAIL: Infirmary NOT marked as BLOODY.")

if __name__ == "__main__":
    test_sabotage()
