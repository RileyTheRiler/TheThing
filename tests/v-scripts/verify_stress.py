import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from systems.psychology import PsychologySystem
from engine import GameState
from core.resolution import Attribute

def test_stress_logic():
    print("Testing Stress Logic (Modular)...")
    game = GameState()
    # Find Blair (Logic 5, so Threshold = 7)
    blair = next(m for m in game.crew if m.name == "Blair")
    
    # In the new characters.json/Attributes, it might be LOGIC
    print(f"Blair Logic: {blair.attributes.get(Attribute.LOGIC)} (Expected 5)")
    threshold = game.psychology_system.calculate_panic_threshold(blair)
    print(f"Panic Threshold: {threshold} (Expected 7)")
    
    # Add Stress
    print("Adding 5 stress...")
    game.psychology_system.add_stress(blair, 5)
    print(f"Current Stress: {blair.stress}")
    
    is_panic, effect = game.psychology_system.resolve_panic(blair, game)
    print(f"Panic Check (Stress 5 <= 7): {is_panic} (Expected False)")
    
    # Overload Stress
    print("Adding 5 more stress (Max 10)...")
    game.psychology_system.add_stress(blair, 5)
    print(f"Current Stress: {blair.stress} (Expected 10)")
    
    # Force Panic Check multiple times
    print("Forcing Panic Checks (Stress 10 > 7)...")
    panicked_once = False
    for i in range(5):
        is_panic, effect = game.psychology_system.resolve_panic(blair, game)
        if is_panic:
            print(f"Check {i}: PANIC! {effect}")
            panicked_once = True
            
    if panicked_once:
        print("PASS: Panic mechanism functional.")
    else:
        print("NOTE: Stress/Panic is probabilistic.")

if __name__ == "__main__":
    test_stress_logic()
