## 2024-05-22 - [Critical] Insecure Deserialization via Pickle
**Vulnerability:** The `RandomnessEngine` in `src/systems/architect.py` was using `pickle` to serialize and deserialize the Python `random` state. This allowed arbitrary code execution if a save file was tampered with.
**Learning:** Even standard library features like `random.getstate()` which return complex objects can be dangerous if blindly serialized with `pickle`. It's always safer to decompose complex objects into JSON-primitives (lists/dicts) for storage.
**Prevention:** Avoid `pickle` entirely. Always manually decompose objects into JSON-serializable structures (`to_dict`/`from_dict`). For `random` state, convert the internal tuple to a list for JSON storage and reconstruct the tuple for restoration.

## 2025-01-12 - [Critical] Path Traversal in SaveManager
**Vulnerability:** The `SaveManager` used user-supplied input (save slot names) directly in `os.path.join()` without sanitization. This allowed attackers to write files outside the designated save directory using `../` sequences, potentially leading to arbitrary file overwrite or information disclosure.
**Learning:** Never trust user input used in file operations, even if it seems benign like a "save slot name". `os.path.join` is not a security function and will happily resolve `../` to parent directories.
**Prevention:** Implement strict whitelisting for filenames (e.g., alphanumeric only) and use `os.path.basename` to strip directory components. Explicitly sanitize inputs at the entry point of the file system operation.
