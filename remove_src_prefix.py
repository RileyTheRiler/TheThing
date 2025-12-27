"""
Remove src. prefix from imports in src/ to comply with AGENT_GUIDELINES.md
"""
import os
import re

def fix_imports_in_file(filepath):
    """Fix imports in a single file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Fix imports: remove 'src.' from 'from src.package'
    # match 'from src.systems' -> 'from systems'
    content = re.sub(r'from src\.', 'from ', content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    src_dir = 'src'
    fixed_count = 0

    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if fix_imports_in_file(filepath):
                    print(f"Fixed: {filepath}")
                    fixed_count += 1

    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == "__main__":
    main()
