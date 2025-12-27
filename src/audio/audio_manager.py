"""
Audio Trigger System
Event-driven audio for ambient sounds and dramatic cues.
Uses winsound for lightweight beep-based audio (no external dependencies).
"""

import threading
import queue
from enum import Enum

# Try to import winsound (Windows only)
try:
    import winsound
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False


class Sound(Enum):
    """Available sound effects."""
    # Ambient
    THRUM = "thrum"           # Low, constant generator hum
    WIND = "wind"             # Antarctic wind howling
    STATIC = "static"         # Radio/equipment static
    
    # Event Sounds
    SCREECH = "screech"       # The Thing reveal
    DOOR = "door"             # Door opening/closing
    FOOTSTEPS = "footsteps"   # Movement
    POWER_DOWN = "power_down" # Generator failure
    POWER_UP = "power_up"     # Generator restored
    
    # UI Sounds
    BEEP = "beep"             # Command confirmation
    ERROR = "error"           # Invalid command
    ALERT = "alert"           # Warning/paranoia spike


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
        Sound.POWER_DOWN: (500, 100),   # Descending
        Sound.POWER_UP: (100, 500),     # Ascending
        Sound.BEEP: (440, 440),         # Standard beep (A4)
        Sound.ERROR: (200, 200),        # Low buzz
        Sound.ALERT: (880, 880),        # High beep (A5)
    }
    
    # Duration in milliseconds
    DURATIONS = {
        Sound.THRUM: 500,
        Sound.WIND: 300,
        Sound.STATIC: 100,
        Sound.SCREECH: 800,
        Sound.DOOR: 200,
        Sound.FOOTSTEPS: 100,
        Sound.POWER_DOWN: 1000,
        Sound.POWER_UP: 1000,
        Sound.BEEP: 100,
        Sound.ERROR: 200,
        Sound.ALERT: 150,
    }
    
    def __init__(self, enabled=True):
        self.enabled = enabled and AUDIO_AVAILABLE
        self.muted = False
        self.volume = 1.0  # Not actually used with winsound, but for future
        
        # Audio queue for async playback
        self.queue = queue.Queue()
        self.ambient_sound = None
        self.ambient_running = False
        self._running = True  # Control flag for thread
        
        # Start audio thread
        if self.enabled:
            self._audio_thread = threading.Thread(target=self._audio_worker, daemon=True)
            self._audio_thread.start()
    
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
                    self._play_sound(self.ambient_sound, ambient=True)
    
    def _play_sound(self, sound, ambient=False):
        """Actually play the sound using winsound."""
        if not self.enabled or not AUDIO_AVAILABLE:
            return
        
        freq_range = self.FREQUENCIES.get(sound, (440, 440))
        duration = self.DURATIONS.get(sound, 100)
        
        if ambient:
            duration = int(duration * 0.3)  # Shorter for ambient loop
        
        try:
            if len(freq_range) == 2 and freq_range[0] != freq_range[1]:
                # Play a sweep from low to high
                import time
                steps = 5
                step_duration = duration // steps
                freq_step = (freq_range[1] - freq_range[0]) // steps
                
                for i in range(steps):
                    freq = freq_range[0] + (i * freq_step)
                    winsound.Beep(max(37, min(32767, freq)), step_duration)
            else:
                # Single frequency
                winsound.Beep(freq_range[0], duration)
        except Exception:
            pass  # Silently fail on audio errors
    
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
        
        import time
        
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
