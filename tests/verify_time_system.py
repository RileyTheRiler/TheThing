import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from systems.architect import TimeSystem, RandomnessEngine
from core.event_system import event_bus, EventType

def test_time_system_determinism():
    print("Testing TimeSystem Determinism...")
    
    # Start at 19:00
    ts = TimeSystem(start_hour=19, start_temp=20)
    rng = RandomnessEngine(seed=42)
    
    class MockGameState:
        def __init__(self):
            self.power_on = True
    
    gs = MockGameState()
    
    # Turn 0 -> 19:00
    assert ts.hour == 19
    assert ts.turn_count == 0
    
    # Advance 1 turn
    ts.advance_turn(gs, rng)
    assert ts.hour == 20
    assert ts.turn_count == 1
    
    # Advance to rollover
    for _ in range(4): # 21, 22, 23, 0
        ts.advance_turn(gs, rng)
    
    assert ts.hour == 0
    assert ts.turn_count == 5
    print("HOUR calculation and rollover passed.")

def test_thermal_decay():
    print("\nTesting Thermal Decay...")
    ts = TimeSystem(start_hour=19, start_temp=20)
    rng = RandomnessEngine(seed=42)
    
    class MockGameState:
        def __init__(self, power=True):
            self.power_on = power
            
    gs_power_off = MockGameState(power=False)
    
    # Power OFF: -5 degrees per turn
    ts.advance_turn(gs_power_off, rng)
    assert ts.temperature == 15
    
    ts.advance_turn(gs_power_off, rng)
    assert ts.temperature == 10
    
    # Power ON: +2 degrees per turn (until 20)
    gs_power_on = MockGameState(power=True)
    ts.advance_turn(gs_power_on, rng)
    assert ts.temperature == 12
    
    print("THERMAL decay/recovery passed.")

def test_event_emission():
    print("\nTesting Event Emission...")
    ts = TimeSystem(start_hour=19)
    rng = RandomnessEngine(seed=42)
    
    received_event = False
    def on_turn_advance(event):
        nonlocal received_event
        received_event = True
        
    event_bus.subscribe(EventType.TURN_ADVANCE, on_turn_advance)
    
    class MockGameState:
        def __init__(self):
            self.power_on = True
    
    ts.advance_turn(MockGameState(), rng)
    
    assert received_event == True
    print("EVENT emission passed.")

if __name__ == "__main__":
    try:
        test_time_system_determinism()
        test_thermal_decay()
        test_event_emission()
        print("\nALL TESTS PASSED!")
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAN ERROR OCCURRED: {e}")
        sys.exit(1)
