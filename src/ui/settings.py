"""
Settings Manager (Tier 6.1)
In-game settings menu for palette, text speed, and audio configuration.
Settings persist to a JSON file in the user's home directory.
"""

import os
import json

# Settings file location
SETTINGS_FILE = os.path.expanduser("~/.thething_settings.json")

# Default settings
DEFAULT_SETTINGS = {
    "palette": "amber",
    "text_speed": "normal",  # slow, normal, fast, instant
    "audio_enabled": True,
    "effects_enabled": True,  # CRT effects (scanlines, glitch)
    "auto_save": True,
    "auto_save_interval": 5,  # turns between auto-saves
}

# Text speed multipliers (for crawl_speed)
TEXT_SPEEDS = {
    "slow": 0.04,
    "normal": 0.02,
    "fast": 0.008,
    "instant": 0.0,
}


class SettingsManager:
    """Manages game settings with persistence."""

    def __init__(self):
        self.settings = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        """Load settings from file."""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                    # Merge with defaults (in case new settings were added)
                    self.settings.update(saved)
        except (IOError, json.JSONDecodeError):
            pass  # Use defaults

    def save(self):
        """Save settings to file."""
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except IOError:
            pass  # Can't save

    def get(self, key, default=None):
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Set a setting value and save."""
        self.settings[key] = value
        self.save()

    def get_text_speed_value(self):
        """Get the crawl_speed value for current text speed setting."""
        speed_name = self.settings.get("text_speed", "normal")
        return TEXT_SPEEDS.get(speed_name, 0.02)

    def apply_to_game(self, game_state):
        """Apply current settings to a game state."""
        # Apply palette
        palette = self.settings.get("palette", "amber")
        game_state.crt.set_palette(palette)

        # Apply text speed
        game_state.crt.crawl_speed = self.get_text_speed_value()

        # Apply audio settings
        game_state.audio.enabled = self.settings.get("audio_enabled", True)

        # Apply CRT effects
        game_state.crt.enabled = self.settings.get("effects_enabled", True)


def show_settings_menu(game_state, settings_manager):
    """Display the settings menu and handle user input.

    Args:
        game_state: The current GameState instance
        settings_manager: The SettingsManager instance

    Returns:
        True if settings were changed, False otherwise
    """
    from ui.crt_effects import CRTOutput

    changed = False

    while True:
        print("\n" + "=" * 50)
        print("   SETTINGS")
        print("=" * 50)

        # Display current settings
        palette = settings_manager.get("palette")
        text_speed = settings_manager.get("text_speed")
        audio = "ON" if settings_manager.get("audio_enabled") else "OFF"
        effects = "ON" if settings_manager.get("effects_enabled") else "OFF"
        auto_save = "ON" if settings_manager.get("auto_save") else "OFF"

        print(f"\n  [1] Color Palette: {palette.upper()}")
        print(f"  [2] Text Speed: {text_speed.upper()}")
        print(f"  [3] Audio: {audio}")
        print(f"  [4] CRT Effects: {effects}")
        print(f"  [5] Auto-Save: {auto_save}")
        print(f"\n  [0] Return to Game")

        print("\n" + "-" * 50)
        try:
            choice = input("Enter choice: ").strip()
        except EOFError:
            break

        if choice == "0" or choice.lower() == "q":
            break

        elif choice == "1":
            # Palette selection
            palettes = CRTOutput.get_available_palettes()
            print("\nAvailable Palettes:")
            palette_list = list(palettes.keys())
            for i, (name, desc) in enumerate(palettes.items(), 1):
                marker = " *" if name == palette else ""
                print(f"  [{i}] {name}: {desc}{marker}")

            try:
                p_choice = input("Select palette (number): ").strip()
                p_idx = int(p_choice) - 1
                if 0 <= p_idx < len(palette_list):
                    new_palette = palette_list[p_idx]
                    settings_manager.set("palette", new_palette)
                    game_state.crt.set_palette(new_palette)
                    print(f"Palette changed to {new_palette}.")
                    changed = True
            except (ValueError, IndexError, EOFError):
                print("Invalid selection.")

        elif choice == "2":
            # Text speed selection
            speeds = ["slow", "normal", "fast", "instant"]
            print("\nText Speeds:")
            for i, speed in enumerate(speeds, 1):
                marker = " *" if speed == text_speed else ""
                print(f"  [{i}] {speed.upper()}{marker}")

            try:
                s_choice = input("Select speed (number): ").strip()
                s_idx = int(s_choice) - 1
                if 0 <= s_idx < len(speeds):
                    new_speed = speeds[s_idx]
                    settings_manager.set("text_speed", new_speed)
                    game_state.crt.crawl_speed = TEXT_SPEEDS[new_speed]
                    print(f"Text speed changed to {new_speed}.")
                    changed = True
            except (ValueError, IndexError, EOFError):
                print("Invalid selection.")

        elif choice == "3":
            # Toggle audio
            current = settings_manager.get("audio_enabled")
            settings_manager.set("audio_enabled", not current)
            game_state.audio.enabled = not current
            status = "OFF" if current else "ON"
            print(f"Audio turned {status}.")
            changed = True

        elif choice == "4":
            # Toggle CRT effects
            current = settings_manager.get("effects_enabled")
            settings_manager.set("effects_enabled", not current)
            game_state.crt.enabled = not current
            status = "OFF" if current else "ON"
            print(f"CRT effects turned {status}.")
            changed = True

        elif choice == "5":
            # Toggle auto-save
            current = settings_manager.get("auto_save")
            settings_manager.set("auto_save", not current)
            status = "OFF" if current else "ON"
            print(f"Auto-save turned {status}.")
            changed = True

        else:
            print("Invalid choice.")

    return changed


# Global settings instance
settings = SettingsManager()
