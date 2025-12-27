
import sys
import os

print(f"CWD: {os.getcwd()}")
src_path = os.path.join(os.getcwd(), 'src')
print(f"Adding to path: {src_path}")
sys.path.append(src_path)

print(f"Path: {sys.path}")

try:
    import systems
    print(f"Imported systems: {systems}")
    print(f"Systems file: {getattr(systems, '__file__', 'No file')}")
except ImportError as e:
    print(f"Failed to import systems: {e}")

try:
    import systems.infection
    print(f"Imported systems.infection: {systems.infection}")
except ImportError as e:
    print(f"Failed to import systems.infection: {e}")
except Exception as e:
    print(f"Other error importing systems.infection: {e}")

try:
    import systems.architect
    print(f"Imported systems.architect: {systems.architect}")
except ImportError as e:
    print(f"Failed to import systems.architect: {e}")
