## 2024-05-22 - [Critical] Insecure Deserialization via Pickle
**Vulnerability:** The `RandomnessEngine` in `src/systems/architect.py` was using `pickle` to serialize and deserialize the Python `random` state. This allowed arbitrary code execution if a save file was tampered with.
**Learning:** Even standard library features like `random.getstate()` which return complex objects can be dangerous if blindly serialized with `pickle`. It's always safer to decompose complex objects into JSON-primitives (lists/dicts) for storage.
**Prevention:** Avoid `pickle` entirely. Always manually decompose objects into JSON-serializable structures (`to_dict`/`from_dict`). For `random` state, convert the internal tuple to a list for JSON storage and reconstruct the tuple for restoration.
