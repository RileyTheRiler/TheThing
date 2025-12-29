#!/usr/bin/env python3
"""Verify that no src/ files use 'from src.' or 'import src.' imports.

This script scans all Python files in src/ and fails if any use the src. prefix,
which violates the project's import policy.
"""

import sys
from pathlib import Path


def check_imports(src_dir: Path) -> list[tuple[Path, int, str]]:
    """Scan Python files for src. imports.
    
    Returns:
        List of (file_path, line_number, line_content) tuples for violations.
    """
    violations = []
    
    for py_file in src_dir.rglob("*.py"):
        with open(py_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                stripped = line.strip()
                if stripped.startswith("from src.") or stripped.startswith("import src."):
                    violations.append((py_file, line_num, line.rstrip()))
    
    return violations


def main():
    src_dir = Path(__file__).parent / "src"
    
    if not src_dir.exists():
        print(f"❌ Error: {src_dir} does not exist")
        sys.exit(1)
    
    print(f"Scanning {src_dir} for 'src.' imports...")
    violations = check_imports(src_dir)
    
    if violations:
        print(f"\nFound {len(violations)} import violations:\n")
        for file_path, line_num, line_content in violations:
            rel_path = file_path.relative_to(src_dir.parent)
            print(f"  {rel_path}:{line_num}")
            print(f"    {line_content}")
        print("\nUse 'from core...', 'from systems...', etc. instead of 'from src.'")
        sys.exit(1)
    else:
        print("No 'src.' imports found. All imports follow the standard pattern.")
        sys.exit(0)


if __name__ == "__main__":
    main()
