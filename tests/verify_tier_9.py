"""Verification tests for Tier 9: Director's Cut Update."""
# -*- coding: utf-8 -*-
import sys
import os

from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from engine import GameState
from core.event_system import event_bus, EventType, GameEvent
from entities.item import Item
from systems.architect import Difficulty


def test_advanced_crafting():
    """Test that Flamethrower can be crafted from Blowtorch + Fuel + Wire."""
    print("\n=== Testing Advanced Crafting ===")
    
    game = GameState(seed=42, difficulty=Difficulty.EASY)
    
    # Give player the ingredients
    blowtorch = Item(name="Blowtorch", description="High-heat torch", category="tool", uses=5)
    fuel = Item(name="Fuel Canister", description="Fuel", category="material", uses=3)
    wire = Item(name="Copper Wire", description="Wire", category="material", uses=-1)
    
    game.player.inventory.extend([blowtorch, fuel, wire])
    
    print(f"Player inventory before crafting: {[i.name for i in game.player.inventory]}")
    
    # Attempt to craft flamethrower
    success = game.crafting.queue_craft(
        game.player,
        "flamethrower_crafted",
        game,
        game.player.inventory
    )
    
    if success:
        # Advance turns to complete crafting
        for _ in range(4):  # craft_time is 3, so advance 4 to be safe
            game.advance_turn()
        
        print(f"Player inventory after crafting: {[i.name for i in game.player.inventory]}")
        
        # Check if flamethrower is in inventory
        has_flamethrower = any("Flamethrower" in i.name for i in game.player.inventory)
        
        if has_flamethrower:
            print("[PASS] Advanced Crafting: SUCCESS - Flamethrower crafted!")
            return True
        else:
            print("[FAIL] Advanced Crafting: FAILED - Flamethrower not in inventory")
            return False
    else:
        print("[FAIL] Advanced Crafting: FAILED - Could not queue craft")

        return False


def test_map_variants():
    """Test that map variants randomize starting conditions."""
    print("\n=== Testing Map Variants ===")
    
    # Create multiple games and check for variance
    variants_detected = []
    
    for seed in range(10):
        game = GameState(seed=seed, difficulty=Difficulty.NORMAL)
        
        # Check various conditions
        if not game.power_on:
            variants_detected.append(f"Seed {seed}: Power off")
        
        if game.room_states.has_state("Kennel", game.room_states.room_states.get("Kennel", set())):
            # Check if frozen
            from systems.room_state import RoomState
            if RoomState.FROZEN in game.room_states.get_states("Kennel"):
                variants_detected.append(f"Seed {seed}: Kennel frozen")
        
        if game.room_states.is_entry_blocked("Storage"):
            variants_detected.append(f"Seed {seed}: Storage barricaded")
        
        game.cleanup()
    
    print(f"Variants detected across 10 seeds: {len(variants_detected)}")
    for variant in variants_detected[:5]:  # Show first 5
        print(f"  - {variant}")
    
    if len(variants_detected) > 0:
        print("[PASS] Map Variants: SUCCESS - Random variants detected!")
        return True
    else:
        print("[FAIL] Map Variants: FAILED - No variants detected")
        return False


def test_freeze_out_ending():
    """Test that Freeze Out ending triggers correctly."""
    print("\n=== Testing Freeze Out Ending ===")
    
    game = GameState(seed=42, difficulty=Difficulty.EASY)
    
    # Set up conditions for Freeze Out
    game.generator_destroyed = True
    game.time_system.temperature = -65  # Below -60
    game.rescue_signal_active = False
    game.escape_route = None
    
    ending_triggered = False
    ending_id = None
    
    def on_ending(event):
        nonlocal ending_triggered, ending_id
        ending_triggered = True
        ending_id = event.payload.get("ending_id")
        print(f"Ending triggered: {ending_id}")
        print(f"Message: {event.payload.get('message')}")
    
    event_bus.subscribe(EventType.ENDING_REPORT, on_ending)
    
    # Advance turn to trigger check
    game.advance_turn()
    
    event_bus.unsubscribe(EventType.ENDING_REPORT, on_ending)
    game.cleanup()
    
    if ending_triggered and ending_id == "freeze_out":
        print("[PASS] Freeze Out Ending: SUCCESS!")
        return True
    else:
        print(f"[FAIL] Freeze Out Ending: FAILED - Triggered: {ending_triggered}, ID: {ending_id}")
        return False


def test_blair_ending():
    """Test that Blair Thing ending triggers when UFO is constructed."""
    print("\n=== Testing Blair Thing Ending ===")
    
    game = GameState(seed=42, difficulty=Difficulty.EASY)
    
    ending_triggered = False
    ending_id = None
    
    def on_ending(event):
        nonlocal ending_triggered, ending_id
        ending_triggered = True
        ending_id = event.payload.get("ending_id")
        print(f"Ending triggered: {ending_id}")
        print(f"Message: {event.payload.get('message')}")
    
    event_bus.subscribe(EventType.ENDING_REPORT, on_ending)
    
    # Emit UFO_CONSTRUCTED event
    event_bus.emit(GameEvent(EventType.UFO_CONSTRUCTED, {"game_state": game}))
    
    event_bus.unsubscribe(EventType.ENDING_REPORT, on_ending)
    game.cleanup()
    
    if ending_triggered and ending_id == "blair_thing":
        print("[PASS] Blair Thing Ending: SUCCESS!")
        return True
    else:
        print(f"[FAIL] Blair Thing Ending: FAILED - Triggered: {ending_triggered}, ID: {ending_id}")
        return False


def main():
    """Run all Tier 9 verification tests."""
    print("=" * 60)
    print("TIER 9: DIRECTOR'S CUT UPDATE - VERIFICATION")
    print("=" * 60)
    
    results = []
    
    results.append(("Advanced Crafting", test_advanced_crafting()))
    results.append(("Map Variants", test_map_variants()))
    results.append(("Freeze Out Ending", test_freeze_out_ending()))
    results.append(("Blair Thing Ending", test_blair_ending()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return all(p for _, p in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
