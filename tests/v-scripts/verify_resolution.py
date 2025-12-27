import sys
import os
import random

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from core.resolution import Attribute, Skill
from engine import GameState, CrewMember

def test_dice_stats():
    print("Testing Dice Statistics (1000 rolls per pool)...")
    # New logic: Success is a 6.
    for pool in [1, 3, 5, 8]:
        successes = 0
        for _ in range(1000):
            dice = [random.randint(1, 6) for _ in range(pool)]
            if dice.count(6) > 0:
                successes += 1
        
        prob = (successes / 1000) * 100
        print(f"Pool {pool}: {prob:.1f}% success rate (Expected ~{100 * (1 - (5/6)**pool):.1f}%)")

def test_crew_stats():
    print("\nTesting Crew Stats...")
    game = GameState()
    macready = next(m for m in game.crew if m.name == "MacReady")
    childs = next(m for m in game.crew if m.name == "Childs")
    
    # Updated Enums
    print(f"MacReady Phys: {macready.attributes[Attribute.PROWESS]} (Expected 3)")
    print(f"MacReady Pilot: {macready.skills.get(Skill.PILOT, 0)} (Expected 3)")
    
    # Updated Enums
    print(f"Childs Phys: {childs.attributes[Attribute.PROWESS]} (Expected 5)")
    print(f"Childs Melee: {childs.skills.get(Skill.MELEE, 0)} (Expected 3)")
    
    # Test Roll
    print("\nTesting Roll Check...")
    result = macready.roll_check(Attribute.PROWESS, Skill.PILOT)
    print(f"MacReady Pilots (Pool {result['pool_size']}): {result['dice']} -> Success: {result['success']}")

def test_mapping():
    print("\nTesting Attribute Mapping...")
    print(f"Firearms -> {Skill.get_attribute(Skill.FIREARMS)} (Expected PROWESS)")
    print(f"Observation -> {Skill.get_attribute(Skill.MEDICINE)} (Expected LOGIC from Medicine)")

if __name__ == "__main__":
    test_dice_stats()
    test_mapping()
    test_crew_stats()
    print("\nVerification Complete.")
