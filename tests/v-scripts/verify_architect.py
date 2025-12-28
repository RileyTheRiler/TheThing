
import sys
import os
import shutil

# Ensure src is in python path
src_path = os.path.join(os.getcwd(), 'src')
if src_path not in sys.path:
    sys.path.append(src_path)

# Import directly as 'engine' and 'process' since src is in path
try:
    from engine import GameState, GameMode
    from process.resolution import Attribute, Skill
except ImportError as e:
    print(f"Import Error: {e}")
    # Fallback to try src. if direct fails? No, simpler to fail hard and debug path.
    print(f"sys.path: {sys.path}")
    raise

def run_verification():
    print("=== VERIFYING ARCHITECT AGENT CHOREOGRAPHY ===")
    
    # Test 1: Randomness & Seeding
    print("\n[TEST 1] Randomness Engine & Seeding")
    game1 = GameState(seed=42)
    roll1 = game1.rng.roll_2d6()
    
    game2 = GameState(seed=42)
    roll2 = game2.rng.roll_2d6()
    
    print(f"Game 1 Roll: {roll1}")
    print(f"Game 2 Roll: {roll2}")
    
    if roll1 == roll2:
        print("PASS: Seeding produces deterministic results.")
    else:
        print("FAIL: Rolls differ despite same seed.")

    # Test 2: Time System & Thermal Decay
    print("\n[TEST 2] Time System & Thermal Decay")
    initial_temp = game1.temperature
    print(f"Initial Temp: {initial_temp}")
    
    game1.power_on = False
    print("Power turned OFF. Advancing 3 turns...")
    game1.advance_turn()
    game1.advance_turn()
    game1.advance_turn()
    
    final_temp = game1.temperature
    print(f"Final Temp: {final_temp}")
    
    if final_temp < initial_temp:
        print("PASS: Temperature decayed correctly.")
    else:
        print("FAIL: Temperature did not decay.")

    # Test 3: Persistence (Save/Load)
    print("\n[TEST 3] Persistence Layer")
    save_slot = "verify_arch"
    
    # Modify state before saving
    game1.player.health = 1
    game1.player.location = (10, 10)
    print(f"State to Save: HP={game1.player.health}, Loc={game1.player.location}")
    
    # Ensure save directory exists
    if not os.path.exists("data/saves"):
        os.makedirs("data/saves")

    success = game1.save_manager.save_game(game1, save_slot)
    if not success:
        print("FAIL: save_game returned failure.")
    
    # Create new game and load
    game3 = GameState()
    loaded_data = game3.save_manager.load_game(save_slot)
    
    if loaded_data:
        loaded_game = GameState.from_dict(loaded_data)

        print(f"Loaded State: HP={loaded_game.player.health}, Loc={loaded_game.player.location}")
        if loaded_game.player.health == 1 and loaded_game.player.location == (10, 10):
             print("PASS: Game state restored correctly.")
        else:
             print("FAIL: State mismatch.")
    else:
        print("FAIL: Could not load game.")

    # Cleanup
    save_path = f"data/saves/{save_slot}.json"
    if os.path.exists(save_path):
        os.remove(save_path)
        print("Cleanup: Removed save file.")

if __name__ == "__main__":
    run_verification()
