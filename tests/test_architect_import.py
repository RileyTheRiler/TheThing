"""Import validation for the systems.architect module."""

import importlib
import sys


def test_architect_import_does_not_modify_sys_path():
    """Ensure architect loads cleanly without mutating import paths."""
    sys.modules.pop("systems.architect", None)
    original_sys_path = list(sys.path)

    module = importlib.import_module("systems.architect")

    assert module is not None
    assert sys.path == original_sys_path
