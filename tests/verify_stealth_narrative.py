import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from engine import GameState
from core.event_system import event_bus, EventType
from entities.crew_member import StealthPosture
from audio.audio_manager import Sound

def test_stealth_audio_and_dialogue():
    print("--- Testing Stealth Audio and Contextual Dialogue ---")
    
    # Setup mock game state
    game = GameState()
    player = game.player
    player.name = "MacReady"
    
    # Create an NPC with a specific behavior
    npc = [m for m in game.crew if m.name != "MacReady"][0]
    npc.behavior_type = "Nervous"
    npc.is_infected = True
    
    # Place them in the same room
    player.location = (10, 10)
    npc.location = (10, 10)
    
    captured_events = []
    def log_event(event):
        captured_events.append(event)
        if event.type == EventType.DIALOGUE:
            print(f"[DIALOGUE] {event.payload.get('speaker')}: \"{event.payload.get('text')}\"")
        elif event.type == EventType.MOVEMENT:
            print(f"[MOVEMENT] {event.payload.get('actor')} moves.")
            
    event_bus.subscribe(EventType.DIALOGUE, log_event)
    event_bus.subscribe(EventType.MOVEMENT, log_event)
    
    # Mock AudioManager.play to see what gets queued
    original_play = game.audio.play
    played_sounds = []
    def mock_play(sound, priority=5):
        played_sounds.append((sound, priority))
        print(f"[AUDIO] Queued: {sound.name} (Priority: {priority})")
        
    game.audio.play = mock_play

    # 1. Test "Sprinting" noise (Standing)
    print("\n1. Testing High Noise (Standing)...")
    player.set_posture(StealthPosture.STANDING)
    print(f"Noise Level: {player.get_noise_level()}")
    
    # Trigger movement event manually to check audio selection
    event_bus.emit(GameEvent(EventType.MOVEMENT, {
        "actor": player.name,
        "destination": "Rec Room"
    }))
    
    # 2. Test "Sneaking" noise (Crouching)
    print("\n2. Testing Medium Noise (Crouching)...")
    player.set_posture(StealthPosture.CROUCHING)
    print(f"Noise Level: {player.get_noise_level()}")
    event_bus.emit(GameEvent(EventType.MOVEMENT, {
        "actor": player.name,
        "destination": "Rec Room"
    }))

    # 3. Test "Crawling" noise (Crawling)
    print("\n3. Testing Low Noise (Crawling)...")
    player.set_posture(StealthPosture.CRAWLING)
    print(f"Noise Level: {player.get_noise_level()}")
    event_bus.emit(GameEvent(EventType.MOVEMENT, {
        "actor": player.name,
        "destination": "Rec Room"
    }))

    # 4. Test Detection Dialogue
    print("\n4. Testing NPC Detection Dialogue (Nervous)...")
    npc.behavior_type = "Nervous"
    # Force detection by lowering player prowess/stealth and raising NPC logic/observation
    from core.resolution import Attribute, Skill
    player.attributes[Attribute.PROWESS] = 0
    player.skills[Skill.STEALTH] = 0
    npc.attributes[Attribute.LOGIC] = 20
    npc.skills[Skill.OBSERVATION] = 10
    
    # Advance turn to trigger StealthSystem.on_turn_advance
    game.stealth.cooldown = 0
    game.advance_turn()
    
    last_dialogue = next((e.payload.get('text') for e in reversed(captured_events) if e.type == EventType.DIALOGUE), None)
    if last_dialogue:
        print(f"Captured Dialogue: \"{last_dialogue}\"")
        if any(phrase in last_dialogue for phrase in ["Who's there?!", "Stay back!", "I... I hear you!"]):
            print("SUCCESS: Nervous dialogue captured.")
        else:
            print("FAILURE: Dialogue captured but not matching personality.")
    else:
        print("FAILURE: No dialogue event captured.")

    # 5. Test Aggressive Behavior
    print("\n5. Testing NPC Detection Dialogue (Aggressive)...")
    npc.behavior_type = "Aggressive"
    npc.location = (10, 10) # Pin location
    game.stealth.cooldown = 0
    game.advance_turn()
    
    last_dialogue = next((e.payload.get('text') for e in reversed(captured_events) if e.type == EventType.DIALOGUE), None)
    if last_dialogue:
        print(f"Captured Dialogue: \"{last_dialogue}\"")
        if any(phrase in last_dialogue for phrase in ["Show yourself!", "I know you're there!", "Come out and fight!"]):
            print("SUCCESS: Aggressive dialogue captured.")
        else:
            print("FAILURE: Dialogue captured but not matching personality.")
    else:
        print("FAILURE: No dialogue event captured.")

    print("\n--- Test Summary ---")
    print(f"Sounds played: {[s[0].name for s in played_sounds]}")
    
    # Cleanup
    game.audio.play = original_play
    event_bus.unsubscribe(EventType.DIALOGUE, log_event)
    event_bus.unsubscribe(EventType.MOVEMENT, log_event)

from core.event_system import GameEvent
if __name__ == "__main__":
    test_stealth_audio_and_dialogue()
