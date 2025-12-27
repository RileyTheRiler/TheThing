import unittest
import random
import json
import os
from src.systems.architect import RandomnessEngine

class TestRandomnessSecurity(unittest.TestCase):
    def test_safe_state_restoration(self):
        """Verify that RNG state is correctly saved and restored without pickle."""
        # Setup
        engine1 = RandomnessEngine(seed=42)
        # Advance state
        val1 = engine1.roll_2d6()

        # Save state
        data = engine1.to_dict()

        # Verify data structure (should be JSON serializable)
        json_str = json.dumps(data) # Should not raise error
        loaded_data = json.loads(json_str)

        # Restore to new engine
        engine2 = RandomnessEngine()
        engine2.from_dict(loaded_data)

        # Verify states match by rolling next value
        # Note: we need to sync them first.
        # engine1 has already rolled once.
        # engine2 should be at the same state as engine1 was *after* the roll if we saved after the roll.

        # Let's do it properly:
        # 1. Create engine, seed it.
        # 2. Roll some values.
        # 3. Save state.
        # 4. Roll more values.
        # 5. Restore state to new engine.
        # 6. New engine should produce same "more values" as original.

        eng_orig = RandomnessEngine(seed=12345)
        for _ in range(5):
            eng_orig.roll_d6()

        saved_state = eng_orig.to_dict()

        # Continue original
        orig_next_vals = [eng_orig.roll_d6() for _ in range(5)]

        # Restore copy
        eng_copy = RandomnessEngine()
        eng_copy.from_dict(saved_state)
        copy_next_vals = [eng_copy.roll_d6() for _ in range(5)]

        self.assertEqual(orig_next_vals, copy_next_vals, "RNG state not correctly restored")

    def test_legacy_exploit_ignored(self):
        """Verify that legacy pickle fields are ignored."""
        import base64
        import pickle
        import os

        class Exploit(object):
            def __reduce__(self):
                return (os.system, ('touch pwned_test.txt',))

        payload = pickle.dumps(Exploit())
        b64_payload = base64.b64encode(payload).decode('utf-8')

        data = {
            "seed": 666,
            "state_b64": b64_payload # Malicious legacy field
        }

        engine = RandomnessEngine()
        engine.from_dict(data)

        self.assertFalse(os.path.exists("pwned_test.txt"), "Vulnerability exploit should not execute")

    def tearDown(self):
        if os.path.exists("pwned_test.txt"):
            os.remove("pwned_test.txt")

if __name__ == "__main__":
    unittest.main()
