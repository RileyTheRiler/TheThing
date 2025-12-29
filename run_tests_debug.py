import pytest
import sys

# Redirect stdout/stderr to a file
with open("pytest_output.txt", "w") as f:
    sys.stdout = f
    sys.stderr = f
    print("Running pytest...")
    retcode = pytest.main(["tests/test_stealth_mechanics.py", "-v"])
    print(f"Pytest finished with code {retcode}")
