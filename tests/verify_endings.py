
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from engine import GameState
from core.resolution import Skill
from entities.item import Item

def verify_rescue_ending():
    print("\n=== Verifying Rescue Ending ===")
    game = GameState()

    # Teleport to Radio Room
    radio_room = game.station_map.rooms["Radio Room"]
    game.player.location = (radio_room[0], radio_room[1])

    # Ensure power is on
    game.power_on = True

    # Give player Comms skill - High enough to guarantee success
    game.player.skills[Skill.COMMS] = 10

    # Signal
    print("Attempting signal...")
    msg = game.attempt_radio_signal()
    print(f"Result: {msg}")

    if not game.rescue_signal_active:
        print("FAIL: Rescue signal not active.")
        return False

    if game.rescue_turns_remaining != 15:
        print(f"FAIL: Rescue turns not 15 (Got {game.rescue_turns_remaining})")
        return False

    # Fast forward
    print("Fast forwarding time...")
    game.rescue_turns_remaining = 0

    won, msg = game.check_win_condition()
    if won and "rescue team" in msg.lower():
        print(f"SUCCESS: {msg}")
        return True
    else:
        print(f"FAIL: Did not trigger rescue win. (Msg: {msg})")
        return False

def verify_helicopter_ending():
    print("\n=== Verifying Helicopter Ending ===")
    game = GameState()

    # Teleport to Hangar
    hangar = game.station_map.rooms["Hangar"]
    game.player.location = (hangar[0], hangar[1])

    # Give items
    game.player.add_item(Item("Wire", "Test Wire"), 0)
    game.player.add_item(Item("Fuel Can", "Test Fuel"), 0)

    # Give skills - High enough to guarantee 2 successes
    # With skill 20, pool is ~21. Expected successes ~3.5.
    game.player.skills[Skill.MECHANICS] = 20
    game.player.skills[Skill.PILOT] = 5

    # Repair
    print("Attempting repair...")
    msg = game.attempt_repair_helicopter()
    print(f"Result: {msg}")

    if game.helicopter_status != "FIXED":
        # Retry once if failed (randomness)
        print("Retrying repair...")
        game.player.add_item(Item("Wire", "Test Wire"), 0)
        game.player.add_item(Item("Fuel Can", "Test Fuel"), 0)
        msg = game.attempt_repair_helicopter()
        print(f"Result: {msg}")
        if game.helicopter_status != "FIXED":
             print("FAIL: Helicopter not fixed.")
             return False

    # Escape
    print("Attempting escape...")
    msg = game.attempt_escape()
    print(f"Result: {msg}")

    if game.helicopter_status != "ESCAPED":
        print("FAIL: Helicopter status not ESCAPED.")
        return False

    won, msg = game.check_win_condition()
    if won and "pilot the chopper" in msg.lower():
        print(f"SUCCESS: {msg}")
        return True
    else:
        print(f"FAIL: Did not trigger helicopter win. (Msg: {msg})")
        return False

def verify_sole_survivor_ending():
    print("\n=== Verifying Sole Survivor Ending ===")
    game = GameState()

    # Kill everyone else
    for m in game.crew:
        if m != game.player:
            m.take_damage(999) # Kill

    won, msg = game.check_win_condition()
    if won and "only one left" in msg.lower():
        print(f"SUCCESS: {msg}")
        return True
    else:
        print(f"FAIL: Did not trigger sole survivor win. (Msg: {msg})")
        return False

if __name__ == "__main__":
    r1 = verify_rescue_ending()
    r2 = verify_helicopter_ending()
    r3 = verify_sole_survivor_ending()

    if r1 and r2 and r3:
        print("\nAll verifications passed!")
        sys.exit(0)
    else:
        print("\nVerification failed.")
        sys.exit(1)
