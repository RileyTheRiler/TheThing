import shutil
import subprocess

import pytest


def test_no_src_prefixed_imports_in_src_tree():
    """Ensure project modules avoid src.* import prefixes inside src/."""
    rg_executable = shutil.which("rg")
    assert rg_executable, "ripgrep (rg) must be installed for import linting."

    result = subprocess.run(
        [rg_executable, r"from src\.", "src/"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        pytest.fail(
            "Found forbidden 'from src.' imports in src/:\n" + result.stdout
        )

    assert (
        result.returncode == 1
    ), f"ripgrep failed while checking imports: {result.stderr}"
