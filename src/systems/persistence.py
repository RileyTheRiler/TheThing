import json
import os
import hashlib
import shutil
from datetime import datetime
from core.event_system import event_bus, EventType, GameEvent

# Current save file version - increment when save format changes
CURRENT_SAVE_VERSION = 2

# Migration functions for each version upgrade
MIGRATIONS = {
    # (from_version, to_version): migration_function
    # Example: (0, 1): migrate_v0_to_v1
}

REQUIRED_FIELDS = [
    "difficulty",
    "rng",
    "time_system",
    "station_map",
    "crew",
    "save_version",
    "checksum",
]


def compute_checksum(data: dict) -> str:
    """
    Compute a SHA-256 checksum for save data integrity verification.
    Excludes the checksum field itself from computation.
    """
    # Create a copy without checksum to compute hash
    data_copy = {
        k: v for k, v in data.items()
        if k not in {'_checksum', 'checksum'}
    }
    json_str = json.dumps(data_copy, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()[:16]


def _extract_version(data: dict) -> int:
    """Return the version value from known metadata keys."""
    if not isinstance(data, dict):
        return 0
    return int(data.get('save_version') or data.get('_save_version') or 0)


def validate_save_data(data: dict, required_fields=None) -> tuple:
    """
    Validate save data structure and checksum.

    Returns:
        (is_valid: bool, error_message: str or None)
    """
    if not isinstance(data, dict):
        return False, "Save data is not a valid dictionary"

    required = required_fields if required_fields is not None else REQUIRED_FIELDS

    # Check for required fields
    missing = []
    for field in required:
        if field == "save_version":
            if 'save_version' not in data and '_save_version' not in data:
                missing.append(field)
        elif field == "checksum":
            if 'checksum' not in data and '_checksum' not in data:
                missing.append(field)
        elif field not in data:
            missing.append(field)
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"

    # Verify checksum if present
    stored_checksum = data.get('checksum') or data.get('_checksum')
    if stored_checksum:
        computed = compute_checksum(data)
        if stored_checksum != computed:
            return False, "Save file checksum mismatch - file may be corrupted"

    return True, None


def migrate_save(data: dict, from_version: int, to_version: int) -> dict:
    """
    Migrate save data from one version to another.
    Applies migrations sequentially.

    Args:
        data: The save data dictionary
        from_version: Source version number
        to_version: Target version number

    Returns:
        Migrated data dictionary
    """
    current = from_version
    migrated_data = data.copy()

    # Normalize legacy metadata keys early
    if '_save_version' in migrated_data and 'save_version' not in migrated_data:
        migrated_data['save_version'] = migrated_data.pop('_save_version')
    if '_saved_at' in migrated_data and 'saved_at' not in migrated_data:
        migrated_data['saved_at'] = migrated_data.pop('_saved_at')
    if '_checksum' in migrated_data and 'checksum' not in migrated_data:
        migrated_data['checksum'] = migrated_data.pop('_checksum')

    # Fill defensive defaults for required structures
    defaults = {
        "crew": [],
        "journal": [],
        "trust": {},
        "crafting": {},
        "alert_system": {},
        "security_system": {},
        "rescue_signal_active": False,
        "rescue_turns_remaining": None,
        "helicopter_status": "BROKEN",
        "power_on": True,
        "paranoia_level": 0,
        "difficulty": "Normal",
        "mode": "Investigative",
        "rng": {"seed": None, "rng_state": None},
        "time_system": {"temperature": -40, "turn_count": 0, "start_hour": 19, "hour": 19},
        "station_map": {}
    }
    for key, default in defaults.items():
        migrated_data.setdefault(key, default)

    while current < to_version:
        migration_key = (current, current + 1)
        if migration_key in MIGRATIONS:
            migrated_data = MIGRATIONS[migration_key](migrated_data)
        current += 1

    migrated_data['save_version'] = to_version
    return migrated_data


class SaveManager:
    def __init__(self, save_dir="data/saves", game_state_factory=None):
        self.save_dir = save_dir
        self.game_state_factory = game_state_factory
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        
    def on_turn_advance(self, event: GameEvent):
        """Subscriber for TURN_ADVANCE event. Handles auto-saving."""
        game_state = event.payload.get("game_state")
        current_turn = event.payload.get("turn")
        if game_state:
            self.apply_suspicion_decay(game_state, current_turn)
        if game_state and game_state.turn % 5 == 0:
            try:
                self.save_game(game_state, "autosave")
            except Exception:
                pass  # Don't interrupt gameplay on save failure
            
    def backup_save(self, filepath: str) -> bool:
        """
        Create a backup of an existing save file before overwriting.

        Args:
            filepath: Path to the save file to backup

        Returns:
            True if backup succeeded or no backup needed, False on error
        """
        if not os.path.exists(filepath):
            return True  # No file to backup

        try:
            backup_dir = os.path.join(self.save_dir, "backups")
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)

            # Create timestamped backup filename
            base_name = os.path.basename(filepath)
            name, ext = os.path.splitext(base_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{name}_{timestamp}{ext}"
            backup_path = os.path.join(backup_dir, backup_name)

            shutil.copy2(filepath, backup_path)

            # Keep only last 5 backups per slot
            self._cleanup_old_backups(backup_dir, name, keep=5)

            return True
        except Exception:
            return False  # Backup failed but don't block save

    def _cleanup_old_backups(self, backup_dir: str, slot_prefix: str, keep: int = 5):
        """Remove old backups, keeping only the most recent ones."""
        try:
            backups = [
                f for f in os.listdir(backup_dir)
                if f.startswith(slot_prefix) and f.endswith('.json')
            ]
            backups.sort(reverse=True)  # Newest first (timestamp in name)

            for old_backup in backups[keep:]:
                os.remove(os.path.join(backup_dir, old_backup))
        except Exception:
            pass  # Cleanup failure is non-critical

    def save_game(self, game_state, slot_name="auto"):
        """
        Saves the game state using to_dict().
        Adds version and checksum for validation.
        Creates backup of existing save before overwriting.
        """
        filename = f"{slot_name}.json"
        filepath = os.path.join(self.save_dir, filename)

        try:
            # Backup existing save first
            self.backup_save(filepath)

            # Get game state data
            data = game_state.to_dict()

            # Add save metadata
            data['save_version'] = CURRENT_SAVE_VERSION
            data['saved_at'] = datetime.now().isoformat()

            # Compute and add checksum (must be last)
            data['checksum'] = compute_checksum(data)

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Game saved to {filepath}")
            return True
        except Exception as e:
            print(f"Failed to save game: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_game(self, slot_name="auto", factory=None):
        """
        Load and validate a saved game.
        Performs checksum verification and version migration if needed.
        """
        filename = f"{slot_name}.json"
        filepath = os.path.join(self.save_dir, filename)

        if not os.path.exists(filepath):
            print(f"Save file not found: {filepath}")
            return None

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Initial checksum verification on raw data
            is_valid, error = validate_save_data(data, required_fields=[])
            if not is_valid:
                print(f"Save validation failed: {error}")
                # Attempt to load from backup if available
                backup_data = self._try_load_backup(slot_name)
                if backup_data:
                    print("Loaded from backup instead.")
                    data = backup_data
                else:
                    return None

            # Check version and migrate if needed
            save_version = _extract_version(data)
            if save_version < CURRENT_SAVE_VERSION:
                print(f"Migrating save from v{save_version} to v{CURRENT_SAVE_VERSION}...")
                data = migrate_save(data, save_version, CURRENT_SAVE_VERSION)
                # Re-save with updated version
                self._resave_migrated(filepath, data)

            # Validate schema after migration
            is_valid, error = validate_save_data(data)
            if not is_valid:
                print(f"Save validation failed post-migration: {error}")
                return None

            # Ensure checksum is up to date
            data['checksum'] = compute_checksum(data)

            # Use provided factory, or instance factory, or return raw data
            hydrator = factory if factory else self.game_state_factory
            if hydrator:
                try:
                    return hydrator(data)
                except Exception as e:
                    print(f"Failed to hydrate game state from {filepath}: {e}")
                    import traceback
                    traceback.print_exc()
                    return None

            return data
        except json.JSONDecodeError as e:
            print(f"Malformed save file {filepath}: {e}")
            return None
        except Exception as e:
            print(f"Failed to load game from {filepath}: {e}")
            return None

    def _try_load_backup(self, slot_name: str) -> dict:
        """Attempt to load the most recent backup for a slot."""
        try:
            backup_dir = os.path.join(self.save_dir, "backups")
            if not os.path.exists(backup_dir):
                return None

            backups = [
                f for f in os.listdir(backup_dir)
                if f.startswith(slot_name) and f.endswith('.json')
            ]
            if not backups:
                return None

            backups.sort(reverse=True)  # Most recent first
            backup_path = os.path.join(backup_dir, backups[0])

            with open(backup_path, 'r') as f:
                data = json.load(f)

            # Validate backup too (legacy-friendly first pass)
            is_valid, _ = validate_save_data(data, required_fields=[])
            if not is_valid:
                return None

            backup_version = _extract_version(data)
            if backup_version < CURRENT_SAVE_VERSION:
                data = migrate_save(data, backup_version, CURRENT_SAVE_VERSION)
                data['checksum'] = compute_checksum(data)

            is_valid, _ = validate_save_data(data)
            return data if is_valid else None
        except Exception:
            return None

    def _resave_migrated(self, filepath: str, data: dict):
        """Re-save data after migration with updated checksum."""
        try:
            # Preserve existing save before overwriting with migrated data
            self.backup_save(filepath)
            data['checksum'] = compute_checksum(data)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass  # Migration resave failure is non-critical

    def apply_suspicion_decay(self, game_state, current_turn=None):
        """
        Apply suspicion decay rules to all crew members.
        """
        if current_turn is None and hasattr(game_state, "turn"):
            current_turn = game_state.turn

        for member in getattr(game_state, "crew", []):
            if hasattr(member, "decay_suspicion"):
                member.decay_suspicion(current_turn)
