
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from core.event_system import event_bus, EventType, GameEvent
from systems.ai import AISystem
from systems.stealth import StealthSystem
from entities.crew_member import CrewMember, StealthPosture
from core.resolution import Attribute, Skill

class MockStationMap:
    def __init__(self):
        self.rooms = {
            "Rec Room": (0, 0, 10, 10)
        }
    def get_room_name(self, x, y):
        return "Rec Room"

class MockGameState:
    def __init__(self):
        self.station_map = MockStationMap()
        self.crew = []
        self.player = None
        self.rng = MockRNG()

class MockRNG:
    def random_float(self):
        return 0.5
    def choose(self, items):
        return items[0]
    def calculate_success(self, pool):
        return {'success_count': 1}
    def roll_check(self, pool, rng=None): # Added rng arg to match ResolutionSystem signature if needed
        return {'success_count': 1}

def test_perception_reaction():
    print("Testing AI Perception Hooks...")
    
    # 1. Setup
    game_state = MockGameState()
    ai_system = AISystem()
    stealth_system = StealthSystem()
    
    # Create Player
    player = CrewMember("MacReady", "Pilot", (0, 0))
    player.attributes[Attribute.PROWESS] = 3
    player.skills[Skill.STEALTH] = 3 
    player.stealth_posture = StealthPosture.STANDING
    game_state.player = player
    
    # Create Enemy NPC
    enemy = CrewMember("Blair", "Biologist", (0, 0))
    enemy.is_infected = True
    enemy.attributes[Attribute.LOGIC] = 3
    enemy.skills[Skill.OBSERVATION] = 3
    
    game_state.crew = [player, enemy]
    
    # Subscribe to diagnostic events
    events = []
    def on_diagnostic(event):
        events.append(event)
        print(f"DIAGNOSTIC: {event.payload}")
        
    def on_message(event):
        print(f"MESSAGE: {event.payload}")
        
    event_bus.subscribe(EventType.DIAGNOSTIC, on_diagnostic)
    event_bus.subscribe(EventType.MESSAGE, on_message)
    
    # 2. Trigger Detection Event (Manually via StealthSystem logic or fake event)
    # We will trigger the actual stealth check logic
    # To force detection/evasion, we can mock the resolution system or just emit the event manually
    # But let's try to trigger it via StealthSystem for end-to-end test
    
    print("\n--- Triggering Stealth Check (Detection Scenario) ---")
    
    # Force player failure / enemy success via attributes if possible, 
    # but easier to just emit the PERCEPTION_EVENT manually to test THIS system (AISystem)
    # Testing StealthSystem emission was already done in other tests.
    
    payload_detection = {
        "room": "Rec Room",
        "opponent": enemy.name,
        "opponent_ref": enemy,
        "player_ref": player,
        "game_state": game_state,
        "outcome": "detected",
        "player_successes": 0,
        "opponent_successes": 2,
        "subject_pool": 3,
        "observer_pool": 3
    }
    
    # Emit event simulating StealthSystem output
    event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, payload_detection))
    
    # Verify Reaction
    if getattr(enemy, 'detected_player', False):
         print("SUCCESS: Enemy marked as detected_player=True")
    else:
         print("FAILURE: Enemy NOT marked as detected_player")
         
    if getattr(enemy, 'alerted_to_player', False): # Self-alert check
         pass # Actually alert logic sets alerted_to_player on OTHERS, but detected_player on self
         
    # 3. Trigger Evasion Event
    print("\n--- Triggering Stealth Check (Evasion Scenario) ---")
    payload_evasion = {
        "room": "Rec Room",
        "opponent": enemy.name,
        "opponent_ref": enemy,
        "player_ref": player,
        "game_state": game_state,
        "outcome": "evaded",
        "player_successes": 2,
        "opponent_successes": 0,
        "subject_pool": 3,
        "observer_pool": 3
    }
    
    event_bus.emit(GameEvent(EventType.PERCEPTION_EVENT, payload_evasion))
    
    # Verify Reaction
    suspicion = getattr(enemy, 'suspicion_level', 0)
    print(f"Enemy Suspicion Level: {suspicion}")
    if suspicion > 0:
        print("SUCCESS: Enemy suspicion increased")
    else:
        print("FAILURE: Enemy suspicion NOT increased")

    # Cleanup
    ai_system.cleanup()
    stealth_system.cleanup()

if __name__ == "__main__":
    test_perception_reaction()
