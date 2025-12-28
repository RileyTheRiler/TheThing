import sys
import os

sys.path.append(os.getcwd())

from src import engine
from src.core.event_system import event_bus, EventType

print(f"Subscribers for TURN_ADVANCE: {len(event_bus._subscribers.get(EventType.TURN_ADVANCE, []))}")
subscribers = event_bus._subscribers.get(EventType.TURN_ADVANCE, [])
infection_found = False
for sub in subscribers:
    print(f" - {sub.__module__}.{sub.__name__}")
    if "infection" in sub.__module__:
        infection_found = True

if infection_found:
    print("SUCCESS: Infection system is registered.")
else:
    print("FAILURE: Infection system is NOT registered.")
