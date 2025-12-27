import sys
import os
from pathlib import Path
import json

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))

from engine import GameState
from core.event_system import event_bus, EventType
from entities.item import Item
from systems.architect import Difficulty

def test_crafting_logic():
    print("--- Testing Crafting Logic ---")
    game = GameState(seed=42, difficulty=Difficulty.NORMAL)
    
    # Manually add items for crafting
    # Recipe: makeshift_torch requires Oil Lantern + Copper Wire
    lantern = Item("Oil Lantern", "Provides light.")
    wire = Item("Copper Wire", "Useful for rigging.")
    
    game.player.add_item(lantern)
    game.player.add_item(wire)
    
    print(f"Initial Inventory: {[i.name for i in game.player.inventory]}")
    
    # 1. Test invalid recipe
    print("\nAttempting invalid recipe 'garbage'...")
    success = game.crafting.queue_craft(game.player, "garbage", game)
    assert not success, "Should fail for unknown recipe"
    
    # 2. Test insufficient ingredients
    # Recipe: improvised_spear requires Mop Handle + Copper Wire
    print("\nAttempting 'improvised_spear' without Mop Handle...")
    success = game.crafting.queue_craft(game.player, "improvised_spear", game)
    assert not success, "Should fail for missing Mop Handle"
    
    # 3. Test valid recipe (delayed)
    # Recipe: makeshift_torch (craft_time: 1)
    print("\nAttempting valid 'makeshift_torch' (1 turn wait)...")
    success = game.crafting.queue_craft(game.player, "makeshift_torch", game)
    assert success, "Should successfully queue makeshift_torch"
    assert len(game.crafting.active_jobs) == 1, "Job should be active"
    
    # Items should still be in inventory until consumption
    assert any(i.name == "Oil Lantern" for i in game.player.inventory)
    assert any(i.name == "Copper Wire" for i in game.player.inventory)
    
    # Advance turn
    print("Advancing turn...")
    game.advance_turn()
    
    # Job should be completed
    assert len(game.crafting.active_jobs) == 0, "Job should be completed"
    assert any(i.name == "Makeshift Torch" for i in game.player.inventory), "Makeshift Torch should be in inventory"
    assert not any(i.name == "Oil Lantern" for i in game.player.inventory), "Oil Lantern should be consumed"
    assert not any(i.name == "Copper Wire" for i in game.player.inventory), "Copper Wire should be consumed"
    
    # 4. Test instant crafting (0 turns)
    # Recipe: heated_wire requires Copper Wire (craft_time: 0)
    print("\nAttempting instant 'heated_wire'...")
    wire2 = Item("Copper Wire", "Another roll.")
    game.player.add_item(wire2)
    
    success = game.crafting.queue_craft(game.player, "heated_wire", game)
    assert success, "Should successfully craft heated_wire instantly"
    assert any(i.name == "Heated Wire" for i in game.player.inventory), "Heated Wire should be in inventory immediately"
    assert not any(i.name == "Copper Wire" for i in game.player.inventory), "Copper Wire should be consumed immediately"

    print("\n--- Crafting Logic Verification Passed ---")

def test_command_wiring():
    print("\n--- Testing Command Wiring ---")
    game = GameState(seed=42, difficulty=Difficulty.NORMAL)
    from systems.commands import GameContext
    context = GameContext(game=game)
    
    # Give items
    game.player.add_item(Item("Oil Lantern", "Provides light."))
    game.player.add_item(Item("Copper Wire", "Useful for rigging."))
    
    print("Executing 'CRAFT makeshift_torch' via dispatcher...")
    success = game.command_dispatcher.dispatch("CRAFT", ["makeshift_torch"], context)
    assert success, "Command should be matched"
    
    # Crafting is queued, turn should have advanced
    assert len(game.crafting.active_jobs) == 1
    assert game.turn == 2 # Started at 1, advanced once
    
    # Advance one more time to finish
    game.advance_turn()
    assert any(i.name == "Makeshift Torch" for i in game.player.inventory)
    
    print("--- Command Wiring Verification Passed ---")

if __name__ == "__main__":
    try:
        test_crafting_logic()
        test_command_wiring()
        print("\nALL VERIFICATIONS PASSED")
    except AssertionError as e:
        print(f"\nVERIFICATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAN ERROR OCCURRED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
