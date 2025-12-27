---
description: How to implement a new feature or system in The Thing
---

Before implementing any new feature, bug fix, or refactor, you MUST follow these steps to ensure consistency across the multi-agent workflow.

1. **Review Local Standards**
   - Read [AGENT_GUIDELINES.md](file:///c:/Users/riley/Desktop/The%20Thing/docs/AGENT_GUIDELINES.md) to understand current enums, event-bus patterns, and core logic locations.
   - Review [TruthLog.md](file:///c:/Users/riley/Desktop/The%20Thing/docs/TruthLog.md) for canonical simulation rules.

2. **Audit for Redundancy**
   - Check `src/core/resolution.py` to see if the math you need already exists.
   - Check `src/systems/` to see if a similar system is already in place.

3. **Design for Decoupling**
   - Identify which events your system needs to listen to (e.g., `TURN_ADVANCE`, `POWER_FAILURE`).
   - Define any new `EventType` enums in `src/core/event_system.py`.

4. **Implementation Plan**
   - Create your `implementation_plan.md` as per the standard workflow.
   - Ensure you use the unified `Prowess`, `Logic`, and `Influence` attributes if interacting with characters.

5. **Verify in Sandbox**
   - Create a verification script in `tests/v-scripts/` to validate your changes in isolation before integrating into `engine.py`.
