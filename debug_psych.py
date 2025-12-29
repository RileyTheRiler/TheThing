import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))
try:
    from systems.psychology import PsychologySystem
    import inspect
    print(f'File: {inspect.getfile(PsychologySystem)}')
    print(f'Sig: {inspect.signature(PsychologySystem.__init__)}')
except Exception as e:
    print(f"Error: {e}")
