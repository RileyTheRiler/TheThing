## 2024-05-22 - [Critical] Insecure Deserialization via Pickle
**Vulnerability:** The `RandomnessEngine` in `src/systems/architect.py` was using `pickle` to serialize and deserialize the Python `random` state. This allowed arbitrary code execution if a save file was tampered with.
**Learning:** Even standard library features like `random.getstate()` which return complex objects can be dangerous if blindly serialized with `pickle`. It's always safer to decompose complex objects into JSON-primitives (lists/dicts) for storage.
**Prevention:** Avoid `pickle` entirely. Always manually decompose objects into JSON-serializable structures (`to_dict`/`from_dict`). For `random` state, convert the internal tuple to a list for JSON storage and reconstruct the tuple for restoration.
## 2024-05-22 - Path Traversal in Save Manager
**Vulnerability:** The `SaveManager.save_game` and `load_game` methods accepted user-provided filenames without sanitization, allowing path traversal (e.g., `../filename`).
**Learning:** Even internal file operations need strict sanitization when filenames come from user input (CLI or Web API). The vulnerability allowed writing files outside the save directory.
**Prevention:** Used `os.path.basename()` to strip directory components from the input slot name, ensuring all saves stay within the configured save directory.
