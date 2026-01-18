## 2024-05-22 - [Critical] Insecure Deserialization via Pickle
**Vulnerability:** The `RandomnessEngine` in `src/systems/architect.py` was using `pickle` to serialize and deserialize the Python `random` state. This allowed arbitrary code execution if a save file was tampered with.
**Learning:** Even standard library features like `random.getstate()` which return complex objects can be dangerous if blindly serialized with `pickle`. It's always safer to decompose complex objects into JSON-primitives (lists/dicts) for storage.
**Prevention:** Avoid `pickle` entirely. Always manually decompose objects into JSON-serializable structures (`to_dict`/`from_dict`). For `random` state, convert the internal tuple to a list for JSON storage and reconstruct the tuple for restoration.
## 2024-05-22 - Path Traversal in Save Manager
**Vulnerability:** The `SaveManager.save_game` and `load_game` methods accepted user-provided filenames without sanitization, allowing path traversal (e.g., `../filename`).
**Learning:** Even internal file operations need strict sanitization when filenames come from user input (CLI or Web API). The vulnerability allowed writing files outside the save directory.
**Prevention:** Used `os.path.basename()` to strip directory components from the input slot name, ensuring all saves stay within the configured save directory.

## 2024-05-24 - [Critical] Path Traversal in Save Manager
**Vulnerability:** The `SaveManager` used user-controlled input (`slot_name`) directly in file paths without sanitization. This allowed attackers to write files outside the save directory (Path Traversal) via `../../` sequences, potentially overwriting system files or executing arbitrary code if they could control file extensions or content effectively.
**Learning:** Never trust file path components coming from user input. Even seemingly harmless "names" or "slots" can be used for traversal attacks.
**Prevention:** Always sanitize filenames using `os.path.basename()` or strict allow-list validation (e.g., regex `^[a-zA-Z0-9_-]+$`) before using them in file system operations.

## 2026-01-18 - [High] Unintended Server Exposure via Double Bind
**Vulnerability:** `server.py` contained two `socketio.run` calls. The first one bound the server to `0.0.0.0` (all interfaces) before the correct, configuration-respecting call could execute.
**Learning:** Redundant code can be dangerous. The first instance of a blocking call (like `run()`) wins. Always verify startup logic and remove "temporary" testing code before committing.
**Prevention:** Use a single entry point for server startup. Audit entry files for duplicate blocking calls. Verify bind addresses in startup scripts.
