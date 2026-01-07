import json
import os
import hashlib
import shutil
from copy import deepcopy
from datetime import datetime
from core.event_system import event_bus, EventType, GameEvent

# Current save file version - increment when save format changes
CURRENT_SAVE_VERSION = 2

# Migration functions for each version upgrade
MIGRATIONS = {
    # (from_version, to_version): migration_function
    # Example: (0, 1): migrate_v0_to_v1
}

# Save slot configuration
SAVE_SLOTS = ["slot_1", "slot_2", "slot_3", "slot_4", "slot_5"]
AUTO_SAVE_INTERVAL = 10  # Auto-save every N turns

def _sanitize_slot_name(name: str) -> str:
    """
    Sanitize save slot name to prevent path traversal.
    Only alphanumeric, underscores, and hyphens allowed.
    """
    if not name:
        return "auto"

    # Remove directory separators and dangerous characters
    safe_name = os.path.basename(name)
    # Filter to allowed chars only
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in ('_', '-'))

    return safe_name or "auto"

DEFAULT_REQUIRED_FIELDS = {
    "turn": 1,
    "crew": [],
    "player_location": (0, 0)
}

# Optional but expected structural fields. These get normalized to safe defaults
# to keep GameState.from_dict resilient to malformed or legacy saves.
STRUCTURAL_DEFAULTS = {
    "rng": {},
    "time_system": {},
    "station_map": {},
    "journal": [],
    "trust": {},
    "crafting": {},
    "alert_system": {},
    "security_system": {}
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
        if k not in {"_checksum", "checksum"}
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
    missing = [f for f in DEFAULT_REQUIRED_FIELDS.keys() if f not in data]
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

    # Basic type validation for structural fields
    if not isinstance(data.get("crew", []), list):
        return False, "Crew data must be a list"
    if not isinstance(data.get("turn"), int):
        return False, "Field 'turn' must be an integer"
    player_loc = data.get("player_location")
    if not isinstance(player_loc, (list, tuple)) or len(player_loc) != 2:
        return False, "Field 'player_location' must be a coordinate pair"

    for key, expected in STRUCTURAL_DEFAULTS.items():
        if key in data and not isinstance(data.get(key), type(expected)):
            return False, f"Field '{key}' has invalid type"

    # Verify checksum if present
    stored_checksum = data.get('_checksum') or data.get('checksum')
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
    if not isinstance(data, dict):
        raise ValueError("Save data must be a dictionary for migration")

    current = from_version
    migrated_data = deepcopy(data)

    # Normalize legacy keys
    if 'player_pos' in migrated_data and 'player_location' not in migrated_data:
        migrated_data['player_location'] = migrated_data.pop('player_pos')
    if 'crew_members' in migrated_data and 'crew' not in migrated_data:
        migrated_data['crew'] = migrated_data.pop('crew_members')

    # Apply structural defaults before running explicit migrations
    for key, default in DEFAULT_REQUIRED_FIELDS.items():
        if key not in migrated_data or migrated_data[key] is None:
            migrated_data[key] = deepcopy(default)

    for key, default in STRUCTURAL_DEFAULTS.items():
        value = migrated_data.get(key)
        if not isinstance(value, type(default)):
            migrated_data[key] = deepcopy(default)

    # Derive turn from legacy time_system data if absent
    if not migrated_data.get("turn"):
        ts_data = migrated_data.get("time_system", {})
        if isinstance(ts_data, dict) and isinstance(ts_data.get("turn_count"), int):
            migrated_data["turn"] = ts_data.get("turn_count", 0) + 1
        else:
            migrated_data["turn"] = 1

    # Ensure player_location is JSON-serializable (list instead of tuple)
    if isinstance(migrated_data.get("player_location"), tuple):
        migrated_data["player_location"] = list(migrated_data["player_location"])

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

    migrated_data['_save_version'] = to_version
    migrated_data['save_version'] = to_version
    migrated_data.setdefault('_saved_at', datetime.now().isoformat())
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
        if game_state and game_state.turn % AUTO_SAVE_INTERVAL == 0:
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
        slot_name = _sanitize_slot_name(slot_name)
        filename = f"{slot_name}.json"
        filepath = os.path.join(self.save_dir, filename)

        try:
            # Backup existing save first
            if not self.backup_save(filepath):
                raise RuntimeError("Failed to create backup before saving")

            # Get game state data
            data = game_state.to_dict()

            # Add save metadata
            data['_save_version'] = CURRENT_SAVE_VERSION
            data['save_version'] = CURRENT_SAVE_VERSION
            data['_saved_at'] = datetime.now().isoformat()
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
        slot_name = _sanitize_slot_name(slot_name)
        filename = f"{slot_name}.json"
        filepath = os.path.join(self.save_dir, filename)

        if not os.path.exists(filepath):
            print(f"Save file not found: {filepath}")
            return None

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Verify checksum on the raw data first
            stored_checksum = data.get('_checksum') or data.get('checksum')
            if stored_checksum and compute_checksum(data) != stored_checksum:
                print("Save validation failed: Save file checksum mismatch - file may be corrupted")
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

            # Check version and migrate (also fills defaults/normalizes legacy fields)
            save_version = data.get('save_version', data.get('_save_version', 0) or 0)
            data = migrate_save(data, save_version, CURRENT_SAVE_VERSION)

            # Refresh checksum to cover migrated/defaulted data
            new_checksum = compute_checksum(data)
            needs_resave = (
                save_version < CURRENT_SAVE_VERSION
                or stored_checksum != new_checksum
                or '_checksum' not in data
                or 'save_version' not in data
            )
            data['_checksum'] = new_checksum

            # Check version and migrate if needed
            save_version = _extract_version(data)
            if save_version < CURRENT_SAVE_VERSION:
                print(f"Migrating save from v{save_version} to v{CURRENT_SAVE_VERSION}...")

            if needs_resave:
                self._resave_migrated(filepath, data)

            # Ensure migrated/defaulted data still passes validation
            is_valid, error = validate_save_data(data)
            if not is_valid:
                print(f"Post-migration validation failed: {error}")
                return None

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
            # Ensure metadata is up to date
            data['_save_version'] = data.get('_save_version', CURRENT_SAVE_VERSION)
            data['save_version'] = data.get('save_version', data['_save_version'])
            data.setdefault('_saved_at', datetime.now().isoformat())

            data['_checksum'] = compute_checksum(data)
            # Backup before writing migrated data
            self.backup_save(filepath)
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

    # === Multi-Slot Save Management (Tier 10.3) ===
    
    def get_slot_metadata(self, slot_name: str) -> dict:
        """
        Get metadata for a save slot without loading the full game state.
        
        Args:
            slot_name: Name of the slot to check
            
        Returns:
            Dictionary with slot metadata or None if slot is empty
        """
        slot_name = _sanitize_slot_name(slot_name)
        filename = f"{slot_name}.json"
        filepath = os.path.join(self.save_dir, filename)
        
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Extract metadata
            return {
                "slot_name": slot_name,
                "timestamp": data.get("saved_at") or data.get("_saved_at", "Unknown"),
                "turn": data.get("turn", 0),
                "difficulty": data.get("difficulty", "Normal"),
                "player_location": data.get("player_location", [0, 0]),
                "crew_count": len(data.get("crew", [])),
                "save_version": data.get("save_version") or data.get("_save_version", 0),
                "survivor_mode": data.get("survivor_mode", False),
                "thumbnail": self._extract_thumbnail(data)
            }
        except (IOError, json.JSONDecodeError):
            return None
    
    def _extract_thumbnail(self, data: dict) -> str:
        """Extract or generate ASCII thumbnail from save data."""
        # Check if thumbnail was saved
        if "thumbnail" in data:
            return data["thumbnail"]
        
        # Generate simple thumbnail from player location
        location = data.get("player_location", [0, 0])
        room_name = data.get("current_room", "Unknown")
        
        # Simple ASCII representation
        lines = [
            "╔════════════╗",
            f"║  Turn {data.get('turn', 0):3d}  ║",
            f"║ {room_name[:10]:^10s} ║",
            "╚════════════╝"
        ]
        return "\n".join(lines)
    
    def list_save_slots(self) -> list:
        """
        List all available save slots with their metadata.
        
        Returns:
            List of slot info dictionaries, including empty slots
        """
        slots = []
        
        for slot_name in SAVE_SLOTS:
            metadata = self.get_slot_metadata(slot_name)
            
            if metadata:
                slots.append({
                    "slot_name": slot_name,
                    "empty": False,
                    **metadata
                })
            else:
                slots.append({
                    "slot_name": slot_name,
                    "empty": True,
                    "display_name": slot_name.replace("_", " ").title()
                })
        
        # Also include autosave if it exists
        autosave_meta = self.get_slot_metadata("autosave")
        if autosave_meta:
            slots.insert(0, {
                "slot_name": "autosave",
                "empty": False,
                "is_autosave": True,
                **autosave_meta
            })
        
        return slots
    
    def save_to_slot(self, game_state, slot_number: int) -> bool:
        """
        Save game to a numbered slot (1-5).
        
        Args:
            game_state: The game state to save
            slot_number: Slot number (1-5)
            
        Returns:
            True if save succeeded
        """
        if not 1 <= slot_number <= len(SAVE_SLOTS):
            print(f"Invalid slot number: {slot_number}. Use 1-{len(SAVE_SLOTS)}.")
            return False
        
        slot_name = SAVE_SLOTS[slot_number - 1]
        return self.save_game(game_state, slot_name)
    
    def load_from_slot(self, slot_number: int, factory=None):
        """
        Load game from a numbered slot (1-5).
        
        Args:
            slot_number: Slot number (1-5)
            factory: Optional factory function to hydrate game state
            
        Returns:
            Loaded game state or None
        """
        if not 1 <= slot_number <= len(SAVE_SLOTS):
            print(f"Invalid slot number: {slot_number}. Use 1-{len(SAVE_SLOTS)}.")
            return None
        
        slot_name = SAVE_SLOTS[slot_number - 1]
        return self.load_game(slot_name, factory)
    
    def delete_slot(self, slot_number: int) -> bool:
        """
        Delete a save slot.
        
        Args:
            slot_number: Slot number (1-5)
            
        Returns:
            True if deletion succeeded
        """
        if not 1 <= slot_number <= len(SAVE_SLOTS):
            print(f"Invalid slot number: {slot_number}.")
            return False
        
        slot_name = SAVE_SLOTS[slot_number - 1]
        filepath = os.path.join(self.save_dir, f"{slot_name}.json")
        
        try:
            if os.path.exists(filepath):
                # Create backup before deleting
                self.backup_save(filepath)
                os.remove(filepath)
                print(f"Deleted save slot {slot_number}.")
                return True
            else:
                print(f"Slot {slot_number} is already empty.")
                return True
        except Exception as e:
            print(f"Failed to delete slot: {e}")
            return False
    
    # === Campaign Save Management (Tier 10.2) ===
    
    def save_campaign(self, campaign_state: dict) -> bool:
        """
        Save survivor mode campaign state.
        
        Args:
            campaign_state: Dictionary containing campaign progress
            
        Returns:
            True if save succeeded
        """
        filepath = os.path.join(self.save_dir, "campaign.json")
        
        try:
            # Backup existing campaign
            self.backup_save(filepath)
            
            campaign_state["saved_at"] = datetime.now().isoformat()
            campaign_state["save_version"] = CURRENT_SAVE_VERSION
            campaign_state["checksum"] = compute_checksum(campaign_state)
            
            with open(filepath, 'w') as f:
                json.dump(campaign_state, f, indent=2)
            
            print("Campaign progress saved.")
            return True
        except Exception as e:
            print(f"Failed to save campaign: {e}")
            return False
    
    def load_campaign(self) -> dict:
        """
        Load survivor mode campaign state.
        
        Returns:
            Campaign state dictionary or None
        """
        filepath = os.path.join(self.save_dir, "campaign.json")
        
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Verify checksum
            stored_checksum = data.get("checksum")
            if stored_checksum:
                computed = compute_checksum(data)
                if stored_checksum != computed:
                    print("Warning: Campaign save may be corrupted.")
            
            return data
        except (IOError, json.JSONDecodeError) as e:
            print(f"Failed to load campaign: {e}")
            return None
    
    def delete_campaign(self) -> bool:
        """
        Delete the campaign save (for permadeath ending).
        
        Returns:
            True if deletion succeeded
        """
        filepath = os.path.join(self.save_dir, "campaign.json")
        
        try:
            if os.path.exists(filepath):
                # Create final backup before deleting
                self.backup_save(filepath)
                os.remove(filepath)
                print("Campaign ended. Save deleted.")
                return True
            return True
        except Exception as e:
            print(f"Failed to delete campaign: {e}")
            return False
    
    def get_save_slots_display(self) -> str:
        """
        Get a formatted string showing all save slots for display.
        
        Returns:
            Formatted string for console display
        """
        slots = self.list_save_slots()
        lines = ["=== SAVE SLOTS ===", ""]
        
        for i, slot in enumerate(slots):
            if slot.get("is_autosave"):
                prefix = "AUTO"
            elif slot["slot_name"].startswith("slot_"):
                prefix = f"  {slot['slot_name'][-1]}"
            else:
                prefix = "  ?"
            
            if slot.get("empty"):
                lines.append(f"[{prefix}] - Empty -")
            else:
                timestamp = slot.get("timestamp", "Unknown")
                if isinstance(timestamp, str) and "T" in timestamp:
                    timestamp = timestamp.split("T")[0]
                
                turn = slot.get("turn", 0)
                difficulty = slot.get("difficulty", "Normal")
                
                lines.append(f"[{prefix}] Turn {turn} | {difficulty} | {timestamp}")
        
        lines.append("")
        lines.append("Use SAVE <1-5> or LOAD <1-5> to manage saves.")
        
        return "\n".join(lines)
