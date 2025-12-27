import sys
import os

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from engine import GameState, CrewMember

def run_advanced_test():
    print("=== Agent 3: Advanced Missionary Verification ===")
    
    # Setup
    game = GameState()
    
    # 1. TEST HABIT TRACKING (Dissonance)
    print("\n--- TEST 1: Habit Tracking (Dissonance) ---")
    # Find a Cook (Preferred: Rec Room)
    cook = next((m for m in game.crew if m.role == "Cook"), None)
    if not cook:
        print("FAIL: No Cook found.")
        return
    
    cook.is_infected = True
    cook.mask_integrity = 100.0
    
    # Move Cook to Generator (Dissonance area)
    cook.location = (15, 15) # Generator
    print(f"Moving {cook.name} ({cook.role}) to Generator (Preferred: Rec Room).")
    
    # Initial mask
    initial_mask = cook.mask_integrity
    
    # Process updates
    game.missionary_system.update(game)
    
    # Decay should be: base_decay (2.0) + habit_penalty (5.0) = 7.0
    expected_decay = 7.0
    actual_decay = initial_mask - cook.mask_integrity
    
    print(f"Mask Integrity: {initial_mask} -> {cook.mask_integrity} (Actual Decay: {actual_decay})")
    
    if actual_decay >= 7.0:
        print("PASS: Habit-based dissonance applied.")
    else:
        print(f"FAIL: Dissonance not applied correctly. Expected >= 7.0, got {actual_decay}")

    # 2. TEST SEARCHLIGHT HARVEST
    print("\n--- TEST 2: Searchlight Harvest ---")
    agent = game.player # MacReady
    agent.is_infected = True
    
    # Ensure MacReady has an invariant with a slip_chance
    if not agent.invariants:
        agent.invariants = [{"type": "visual", "slip_chance": 0.4}]
    
    # Find a target (Childs)
    target = next((m for m in game.crew if m.name == "Childs"), None)
    
    # Move them together
    agent.location = (1, 1) # Infirmary
    target.location = (1, 1) # Infirmary
    
    # Move others away
    for m in game.crew:
        if m != agent and m != target:
            m.location = (18, 18)
            
    initial_slip_chances = [inv.get('slip_chance', 0) for inv in agent.invariants if 'slip_chance' in inv]
    print(f"Agent's Initial Slip Chances: {initial_slip_chances}")
    
    # Perform Communion (which triggers Harvest)
    print("Performing Communion...")
    game.missionary_system.perform_communion(agent, target, game)
    
    final_slip_chances = [inv.get('slip_chance', 0) for inv in agent.invariants if 'slip_chance' in inv]
    print(f"Agent's Final Slip Chances: {final_slip_chances}")
    
    # Check if any slip chance was reduced (all should be 50% of original)
    success = True
    for i in range(len(initial_slip_chances)):
        if final_slip_chances[i] >= initial_slip_chances[i]:
            success = False
            break
            
    if success and final_slip_chances:
        print("PASS: Searchlight Harvest reduced slip chances.")
    else:
        print("FAIL: Slip chances not reduced.")

if __name__ == "__main__":
    run_advanced_test()
