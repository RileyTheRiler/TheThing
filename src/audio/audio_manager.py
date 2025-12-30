"""
Audio Trigger System
Event-driven audio for ambient sounds and dramatic cues.
Cross-platform audio using winsound (Windows), terminal bell, or subprocess.
"""

import threading
import queue
import sys
import os
import subprocess
import time
from enum import Enum
from core.event_system import event_bus, EventType, GameEvent

# Determine audio backend
AUDIO_BACKEND = None

# Try Windows winsound first
try:
    import winsound
    AUDIO_BACKEND = 'winsound'
except ImportError:
    pass

# Check for macOS afplay
if AUDIO_BACKEND is None and sys.platform == 'darwin':
    try:
        subprocess.run(['which', 'afplay'], capture_output=True, check=True)
        AUDIO_BACKEND = 'afplay'
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

# Check for Linux paplay (PulseAudio) or aplay (ALSA)
if AUDIO_BACKEND is None and sys.platform.startswith('linux'):
    for cmd in ['paplay', 'aplay']:
        try:
            subprocess.run(['which', cmd], capture_output=True, check=True)
            AUDIO_BACKEND = cmd
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

# Fallback to terminal bell
if AUDIO_BACKEND is None:
    AUDIO_BACKEND = 'bell'

AUDIO_AVAILABLE = AUDIO_BACKEND is not None


class Sound(Enum):
    """Available sound effects."""
    # Ambient
    THRUM = "thrum"           # Low, constant generator hum
    WIND = "wind"             # Antarctic wind howling
    STATIC = "static"         # Radio/equipment static

    # Event Sounds
    SCREECH = "screech"       # The Thing reveal
    DOOR = "door"             # Door opening/closing
    FOOTSTEPS = "footsteps"   # Standard walking
    HEAVY_FOOTSTEPS = "heavy_steps" # Running/Loud
    SHUFFLE = "shuffle"       # Crawling/Sneaking
    POWER_DOWN = "power_down" # Generator failure
    POWER_UP = "power_up"     # Generator restored
    TENSION = "tension"       # Detected/suspicion sting
    SUSPICION = "suspicion"   # Low suspicion whisper
    IMPACT = "impact"         # Combat hit

    # UI Sounds
    BEEP = "beep"             # Command confirmation
    ERROR = "error"           # Invalid command
    ALERT = "alert"           # Warning/paranoia spike
    CLICK = "click"           # Pickup/Drop
    SUCCESS = "success"       # Task completion


class AudioManager:
    """
    Manages audio playback for the game.
    Uses winsound.Beep() for frequency-based sound generation.
    """
    
    # Frequency mappings for different sounds (Hz)
    FREQUENCIES = {
        Sound.THRUM: (100, 200),        # Low rumble
        Sound.WIND: (300, 600),         # Whistling wind
        Sound.STATIC: (800, 1200),      # Crackling static
        Sound.SCREECH: (1500, 2500),    # High-pitched alien
        Sound.DOOR: (200, 400),         # Clunk
        Sound.FOOTSTEPS: (150, 250),    # Thuds
        Sound.HEAVY_FOOTSTEPS: (100, 200), # Deeper Thuds
        Sound.SHUFFLE: (400, 500),      # Higher friction sound
        Sound.POWER_DOWN: (500, 100),   # Descending
        Sound.POWER_UP: (100, 500),     # Ascending
        Sound.BEEP: (440, 440),         # Standard beep (A4)
        Sound.ERROR: (200, 200),        # Low buzz
        Sound.ALERT: (880, 880),        # High beep (A5)
        Sound.CLICK: (1200, 1200),      # High click
        Sound.SUCCESS: (440, 880),      # Ascending
        Sound.TENSION: (600, 900),      # Tense rising sting
        Sound.SUSPICION: (250, 350),    # Low whisper-like tone
        Sound.IMPACT: (150, 100),       # Combat thud
    }
    
    # Duration in milliseconds
    DURATIONS = {
        Sound.THRUM: 500,
        Sound.WIND: 300,
        Sound.STATIC: 100,
        Sound.SCREECH: 800,
        Sound.DOOR: 200,
        Sound.FOOTSTEPS: 100,
        Sound.HEAVY_FOOTSTEPS: 150,
        Sound.SHUFFLE: 50,
        Sound.POWER_DOWN: 1000,
        Sound.POWER_UP: 1000,
        Sound.BEEP: 100,
        Sound.ERROR: 200,
        Sound.ALERT: 150,
        Sound.CLICK: 50,
        Sound.SUCCESS: 400,
        Sound.TENSION: 300,
        Sound.SUSPICION: 250,
        Sound.IMPACT: 100,
    }
    
    # Tier 6.4: Audio feedback alignment map
    EVENT_MAP = {
        # Warnings
        EventType.WARNING: Sound.ALERT,
        EventType.ERROR: Sound.ERROR,
        EventType.POWER_FAILURE: Sound.POWER_DOWN,

        # Combat / Action
        EventType.ATTACK_RESULT: Sound.BEEP,
        EventType.LYNCH_MOB_TRIGGER: Sound.SCREECH,
        EventType.COMBAT_LOG: Sound.IMPACT,  # Combat hit sounds

        # Stealth / Detection
        EventType.STEALTH_REPORT: Sound.TENSION,  # Detection tension sting

        # Trust / Suspicion
        EventType.TRUST_THRESHOLD_CROSSED: Sound.SUSPICION,  # Suspicion whisper

        # Discoveries / Success
        EventType.COMMUNION_SUCCESS: Sound.SUCCESS, # Dramatic success
        EventType.TEST_RESULT: Sound.BEEP,
        EventType.SOS_EMITTED: Sound.BEEP,
        EventType.ESCAPE_SUCCESS: Sound.SUCCESS,

        # Movement handled dynamically now
        EventType.MOVEMENT: Sound.FOOTSTEPS,

        # Items
        EventType.ITEM_PICKUP: Sound.CLICK,
        EventType.ITEM_DROP: Sound.CLICK,

        # Room
        EventType.BARRICADE_ACTION: Sound.DOOR,

        # Dialogue
        EventType.DIALOGUE: Sound.BEEP # Simple chirp for text
    }
    
    def __init__(self, enabled=True, rng=None, player_ref=None, station_map=None):
        self.enabled = enabled and AUDIO_AVAILABLE
        self.muted = False
        self.volume = 1.0
        self.player_ref = player_ref  # Reference to player for spatial filtering
        self.station_map = station_map
        from systems.architect import RandomnessEngine
        self.rng = rng or RandomnessEngine()
        
        # Audio queue for async playback
        self.queue = queue.Queue()
        self.ambient_sound = None
        self.ambient_running = False
        self._running = True  # Control flag for thread
        
        # Start audio thread
        if self.enabled:
            self._audio_thread = threading.Thread(target=self._audio_worker, daemon=True)
            self._audio_thread.start()

        # Tier 6.4: Subscribe to events
        self._subscribe_to_events()

    def cleanup(self):
        """Unsubscribe and shutdown."""
        for event_type in self.EVENT_MAP:
            event_bus.unsubscribe(event_type, self.handle_game_event)
        self.shutdown()

    def _subscribe_to_events(self):
        """Subscribe to all events defined in EVENT_MAP."""
        for event_type in self.EVENT_MAP:
            event_bus.subscribe(event_type, self.handle_game_event)

    def handle_game_event(self, event: GameEvent):
        """Callback for event bus to trigger audio."""
        if not self._running or not self.enabled:
            return
            
        sound = self.EVENT_MAP.get(event.type)
        if not sound:
            return

        # Determine priority based on event type
        priority = 5
        is_critical = event.type in (EventType.LYNCH_MOB_TRIGGER, EventType.POWER_FAILURE, EventType.BIOLOGICAL_SLIP)
        if is_critical:
            priority = 10
        
        # Dynamic Movement Audio
        if event.type == EventType.MOVEMENT:
            # Check for actor to allow dynamic noise
            # Note: We can't access CrewMember directly from here easily unless passed in event or we lookup
            # But the event usually has 'actor' as a name string.
            # However, for the Player, we have self.player_ref!
            
            # If it's the player moving:
            actor_name = event.payload.get("actor")
            if self.player_ref and actor_name == self.player_ref.name:
                noise = event.payload.get("noise", self.player_ref.get_noise_level())
                if event.payload.get("vent"):
                    # Vents are loud, even compared to heavy footsteps
                    noise = max(noise, 8)
                    priority = max(priority, 8)
                if noise >= 6:
                    sound = Sound.HEAVY_FOOTSTEPS
                    priority = 7 # Louder/More important
                elif noise < 4:
                    sound = Sound.SHUFFLE
                    priority = 3 # Softer/Less important
        
        # Spatial Filtering
        # If the event has a room/location, only play it if it's "close" to the player
        # Unless it's a critical global event.
        if not is_critical and self.player_ref and self.station_map:
            # Events like MOVEMENT have 'destination'
            # Events like ATTACK_RESULT, ITEM_PICKUP have 'room'
            event_room = event.payload.get("room") or event.payload.get("destination")
            
            # If we don't have a room in payload, check for coordinates
            if not event_room:
                coords = event.payload.get("location")
                if coords:
                    event_room = self.station_map.get_room_name(*coords)
            
            if event_room:
                # Get player's current room
                player_room = self.station_map.get_room_name(*self.player_ref.location)
                
                # Spatial rules:
                # 1. Same room: Always play
                # 2. Different room: Only play if Priority > 7 (medium loudness)
                # 3. Else skip
                if event_room != player_room and priority <= 7:
                    return
                
        self.play(sound, priority)
    
    def _audio_worker(self):
        """Background thread for processing audio queue."""
        while self._running:
            try:
                sound, priority = self.queue.get(timeout=0.1)
                if not self.muted:
                    self._play_sound(sound)
                self.queue.task_done()
            except queue.Empty:
                # Play ambient if nothing in queue
                if self.ambient_sound and self.ambient_running and not self.muted:
                    # Use volume to control density of ambient sound
                    # Lower volume = fewer loops play (creating gaps/sparser sound)
                    if self.volume >= 1.0 or self.rng.random() < self.volume:
                        self._play_sound(self.ambient_sound, ambient=True)
    
    def _play_sound(self, sound, ambient=False):
        """Play sound using the available backend."""
        if not self.enabled or not AUDIO_AVAILABLE:
            return
        
        # Check volume threshold - effectively mute if volume is zero
        if self.volume <= 0.0:
            return

        # Volume check (0.0 volume is effectively muted)
        if self.volume <= 0.0:
            return

        freq_range = self.FREQUENCIES.get(sound, (440, 440))
        duration = self.DURATIONS.get(sound, 100)

        if ambient:
            duration = int(duration * 0.3)  # Shorter for ambient loop
            # Simulate volume control for ambient sounds by adjusting density
            if self.rng.random() > self.volume:
                time.sleep(duration / 1000.0)
                return

        try:
            if AUDIO_BACKEND == 'winsound':
                self._play_winsound(freq_range, duration)
            elif AUDIO_BACKEND == 'bell':
                self._play_bell(sound)
            # Note: afplay/aplay require audio files, so fall back to bell
            elif AUDIO_BACKEND in ('afplay', 'aplay', 'paplay'):
                self._play_bell(sound)
        except Exception:
            pass  # Silently fail on audio errors

    def _play_winsound(self, freq_range, duration):
        """Play sound using Windows winsound.Beep()."""
        import winsound
        if len(freq_range) == 2 and freq_range[0] != freq_range[1]:
            # Play a sweep from low to high
            steps = 5
            step_duration = duration // steps
            freq_step = (freq_range[1] - freq_range[0]) // steps

            for i in range(steps):
                freq = freq_range[0] + (i * freq_step)
                winsound.Beep(max(37, min(32767, freq)), step_duration)
        else:
            # Single frequency
            winsound.Beep(freq_range[0], duration)

    def _play_bell(self, sound):
        """Play terminal bell as fallback audio."""
        # Only play bell for important sounds to avoid annoyance
        important_sounds = {Sound.SCREECH, Sound.ALERT, Sound.ERROR, Sound.POWER_DOWN}
        if sound in important_sounds:
            sys.stdout.write('\a')
            sys.stdout.flush()
    
    def play(self, sound, priority=5):
        """
        Queue a sound effect for playback.
        
        Args:
            sound: Sound enum value
            priority: 1-10, higher = more important
        """
        if not self.enabled:
            return
        
        self.queue.put((sound, priority))
    
    def play_sync(self, sound):
        """Play a sound synchronously (blocks)."""
        if not self.enabled or self.muted:
            return
        self._play_sound(sound)
    
    def ambient_loop(self, sound):
        """
        Start playing an ambient sound in the background.
        
        Args:
            sound: Sound enum value (usually THRUM or WIND)
        """
        self.ambient_sound = sound
        self.ambient_running = True
    
    def stop_ambient(self):
        """Stop the ambient sound loop."""
        self.ambient_running = False
        self.ambient_sound = None
    
    def mute(self):
        """Mute all audio."""
        self.muted = True
    
    def unmute(self):
        """Unmute audio."""
        self.muted = False
    
    def toggle_mute(self):
        """Toggle mute state."""
        self.muted = not self.muted
        return self.muted

    def set_volume(self, volume):
        """
        Set volume level (0.0 to 1.0).
        """
        self.volume = max(0.0, min(1.0, volume))

    def increase_volume(self, amount=0.1):
        """Increase volume by amount."""
        self.set_volume(self.volume + amount)

    def decrease_volume(self, amount=0.1):
        """Decrease volume by amount."""
        self.set_volume(self.volume - amount)

    def get_volume(self):
        """Get current volume level."""
        return self.volume
    
    def shutdown(self):
        """Stop the audio thread."""
        self._running = False
        if self.enabled and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=1.0)

    def trigger_event(self, event_type):
        """
        Trigger audio based on game events.
        
        Args:
            event_type: String identifier for the event
        """
        event_sounds = {
            'power_loss': Sound.POWER_DOWN,
            'power_restore': Sound.POWER_UP,
            'thing_reveal': Sound.SCREECH,
            'high_paranoia': Sound.STATIC,
            'door_open': Sound.DOOR,
            'move': Sound.FOOTSTEPS,
            'error': Sound.ERROR,
            'success': Sound.BEEP,
            'alert': Sound.ALERT,
        }
        
        sound = event_sounds.get(event_type)
        if sound:
            priority = 10 if event_type == 'thing_reveal' else 5
            self.play(sound, priority)
    
    def dramatic_reveal(self):
        """
        Play the dramatic Thing reveal sequence.
        Multiple escalating sounds.
        """
        if not self.enabled or self.muted:
            return
        
        # Stop ambient
        was_ambient = self.ambient_running
        self.stop_ambient()
        
        # Static buildup
        for _ in range(3):
            self.play_sync(Sound.STATIC)
            time.sleep(0.1)
        
        # THE SCREECH
        self.play_sync(Sound.SCREECH)
        
        # Resume ambient
        if was_ambient:
            self.ambient_loop(Sound.THRUM)
