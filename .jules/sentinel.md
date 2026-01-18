## 2024-05-22 - [Critical] Insecure Deserialization via Pickle
**Vulnerability:** The `RandomnessEngine` in `src/systems/architect.py` was using `pickle` to serialize and deserialize the Python `random` state. This allowed arbitrary code execution if a save file was tampered with.
**Learning:** Even standard library features like `random.getstate()` which return complex objects can be dangerous if blindly serialized with `pickle`. It's always safer to decompose complex objects into JSON-primitives (lists/dicts) for storage.
**Prevention:** Avoid `pickle` entirely. Always manually decompose objects into JSON-serializable structures (`to_dict`/`from_dict`). For `random` state, convert the internal tuple to a list for JSON storage and reconstruct the tuple for restoration.

## 2024-05-24 - [Critical] Path Traversal in Save Manager
**Vulnerability:** The `SaveManager` used user-controlled input (`slot_name`) directly in file paths without sanitization. This allowed attackers to write files outside the save directory (Path Traversal) via `../../` sequences, potentially overwriting system files or executing arbitrary code if they could control file extensions or content effectively.
**Learning:** Never trust file path components coming from user input. Even seemingly harmless "names" or "slots" can be used for traversal attacks.
**Prevention:** Always sanitize filenames using `os.path.basename()` or strict allow-list validation (e.g., regex `^[a-zA-Z0-9_-]+$`) before using them in file system operations.
