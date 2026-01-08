## 2024-05-22 - [Critical] Insecure Deserialization via Pickle
**Vulnerability:** The `RandomnessEngine` in `src/systems/architect.py` was using `pickle` to serialize and deserialize the Python `random` state. This allowed arbitrary code execution if a save file was tampered with.
**Learning:** Even standard library features like `random.getstate()` which return complex objects can be dangerous if blindly serialized with `pickle`. It's always safer to decompose complex objects into JSON-primitives (lists/dicts) for storage.
**Prevention:** Avoid `pickle` entirely. Always manually decompose objects into JSON-serializable structures (`to_dict`/`from_dict`). For `random` state, convert the internal tuple to a list for JSON storage and reconstruct the tuple for restoration.

## 2024-01-08 - Path Traversal in SaveManager
**Vulnerability:** The `SaveManager.save_game` and `load_game` methods blindly trusted the `slot_name` argument, constructing file paths using `os.path.join(self.save_dir, f"{slot_name}.json")`. This allowed an attacker to supply a string like `../../etc/passwd` to read or write files outside the intended save directory.
**Learning:** Never assume that "internal" inputs (like save slot names passed from a command handler) are safe. Even if the UI seemingly restricts input, the underlying backend logic must strictly validate and sanitize any parameter used in filesystem operations.
**Prevention:** I implemented `_sanitize_slot_name` which strips directory traversals and non-alphanumeric characters (preserving spaces), ensuring that file operations are strictly confined to the `data/saves/` directory. Always use a whitelist approach (e.g., regex `[^a-zA-Z0-9 _-]`) for filenames rather than a blacklist.
