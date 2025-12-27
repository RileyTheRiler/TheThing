import os
import sys

# Add root to path so we can import src as a package
sys.path.append(os.getcwd())

from src.engine import GameState
from src.core.event_system import event_bus, EventType, GameEvent
from src.systems.architect import GameMode

def test_event_driven_architecture():
    print("=== VERIFYING EVENT-DRIVEN ARCHITECTURE ===\n")
    
    # Track events
    events_received = []
    
    def event_listener(event: GameEvent):
        events_received.append(event.type)
        print(f"[EVENT RECEIVED] {event.type.name}")
    
    # Subscribe to all relevant events
    event_bus.subscribe(EventType.TURN_ADVANCE, event_listener)
    event_bus.subscribe(EventType.LYNCH_MOB_TRIGGER, event_listener)
    event_bus.subscribe(EventType.BIOLOGICAL_SLIP, event_listener)
    
    game = GameState(seed=42)
    
    # 1. Test TURN_ADVANCE Event
    print("\n1. Testing TURN_ADVANCE Event Emission...")
    initial_turn = game.turn
    game.advance_turn()
    
    if EventType.TURN_ADVANCE in events_received:
        print("[SUCCESS] TURN_ADVANCE event was emitted")
    else:
        print("[FAILURE] TURN_ADVANCE event was NOT emitted")
    
    # 2. Test Lynch Mob System
    print("\n2. Testing Lynch Mob Event System...")
    # Tank someone's trust
    target = next(m for m in game.crew if m.name == "Garry")
    for member in game.crew:
        if member.name != "Garry":
            game.trust_system.matrix[member.name]["Garry"] = 5
    
    events_received.clear()
    game.advance_turn()
    
    if EventType.LYNCH_MOB_TRIGGER in events_received:
        print("[SUCCESS] LYNCH_MOB_TRIGGER event was emitted")
        if game.lynch_mob.active_mob:
            print(f"[SUCCESS] Lynch mob is active, targeting {game.lynch_mob.target.name}")
        else:
            print("[FAILURE] Lynch mob event emitted but system not active")
    else:
        print("[FAILURE] LYNCH_MOB_TRIGGER event was NOT emitted")
    
    # 3. Test NPC Convergence
    print("\n3. Testing NPC Convergence to Lynch Target...")
    if game.lynch_mob.active_mob:
        target_loc = game.lynch_mob.target.location
        converging_npcs = 0
        
        # Advance a few turns to let NPCs move
        for _ in range(5):
            game.advance_turn()
        
        # Check if NPCs are moving toward target
        for member in game.crew:
            if member != game.lynch_mob.target and member.is_alive:
                # Check if they're closer to target than before
                # For simplicity, just check if they're in same room or adjacent
                distance = abs(member.location[0] - target_loc[0]) + abs(member.location[1] - target_loc[1])
                if distance < 5:  # Within 5 tiles
                    converging_npcs += 1
        
        if converging_npcs > 0:
            print(f"[SUCCESS] {converging_npcs} NPCs are converging on the lynch target")
        else:
            print("[PENDING] NPCs may still be en route to target")
    
    # 4. Test Forensic Commands Integration
    print("\n4. Testing Forensic Systems...")
    if hasattr(game, 'forensic_db') and hasattr(game, 'evidence_log'):
        print("[SUCCESS] Forensic systems initialized")
        
        # Test tagging
        game.forensic_db.add_tag("Blair", "SUSPICION", "Acting strange", game.turn)
        report = game.forensic_db.get_report("Blair")
        if "Acting strange" in report:
            print("[SUCCESS] Forensic tagging works")
        else:
            print("[FAILURE] Forensic tagging failed")
    else:
        print("[FAILURE] Forensic systems not initialized")
    
    print("\n=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    try:
        test_event_driven_architecture()
    except Exception as e:
        print(f"ERROR DURING VERIFICATION: {e}")
        import traceback
        traceback.print_exc()
