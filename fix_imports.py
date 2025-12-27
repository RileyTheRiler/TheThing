"""
Fix all imports in src/ to use absolute imports with src. prefix
"""
import os
import re

def fix_imports_in_file(filepath):
    """Fix imports in a single file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Fix imports
    content = re.sub(r'from core\.', 'from src.core.', content)
    content = re.sub(r'from systems\.', 'from src.systems.', content)
    content = re.sub(r'from ui\.', 'from src.ui.', content)
    content = re.sub(r'from audio\.', 'from src.audio.', content)
    
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
