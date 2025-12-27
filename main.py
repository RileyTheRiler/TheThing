#!/usr/bin/env python3
"""
The Thing: Antarctic Research Station 31
Main launcher - run from project root
"""

import sys
import os

# Add src directory to Python path for relative imports
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, src_path)

# Now import and run the game
if __name__ == "__main__":
    from engine import main
    main()
