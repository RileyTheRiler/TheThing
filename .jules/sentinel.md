## 2024-05-22 - [Critical] Insecure Deserialization via Pickle
**Vulnerability:** The `RandomnessEngine` in `src/systems/architect.py` was using `pickle` to serialize and deserialize the Python `random` state. This allowed arbitrary code execution if a save file was tampered with.
**Learning:** Even standard library features like `random.getstate()` which return complex objects can be dangerous if blindly serialized with `pickle`. It's always safer to decompose complex objects into JSON-primitives (lists/dicts) for storage.
**Prevention:** Avoid `pickle` entirely. Always manually decompose objects into JSON-serializable structures (`to_dict`/`from_dict`). For `random` state, convert the internal tuple to a list for JSON storage and reconstruct the tuple for restoration.

## 2024-05-22 - Hardcoded Debug Mode in Production
**Vulnerability:** The `server.py` file had `debug=True` hardcoded in the `socketio.run()` call, enabling the Werkzeug interactive debugger in all environments.
**Learning:** This likely occurred because the developer set it for testing and forgot to revert it or hook it up to the `debug_mode` variable which was already being parsed from environment variables.
**Prevention:** Always verify that debug flags are driven by environment variables (`FLASK_DEBUG`) and default to `False`. Ensure entry points do not override these variables with hardcoded values.
