## 2024-05-24 - Duplicate Loops in Pathfinding
**Learning:** The A* implementation in `src/systems/pathfinding.py` contained redundant and broken loops. It iterated over orthogonal neighbors, then diagonal neighbors (broken), and then all neighbors again. This resulted in wasted CPU cycles and potential bugs.
**Action:** Always verify loop logic when optimizing algorithms. Removing duplicate loops is a high-value, low-risk optimization.
## 2024-05-24 - Broken Test Suite in Performance Check
**Learning:** The existing performance tests (`tests/test_ai_performance.py`) were broken due to a missing `StealthPosture.HIDDEN` attribute in `src/entities/crew_member.py` or `src/systems/stealth.py`.
**Action:** Always fix the test suite before relying on it for verification. Broken tests mask regressions.
