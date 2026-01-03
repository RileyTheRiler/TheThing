## 2024-05-22 - Instantiation inside Loops
**Learning:** Instantiating logic classes (like `ResolutionSystem`) inside nested loops can cause significant performance overhead (O(N) allocations) and hides bugs (like signature mismatches) if the code path is rarely exercised or crashed before measuring.
**Action:** Always hoist stateless or reusable system instantiations out of loops. Verify function signatures statically or with a test before assuming optimization is the only task.

## 2024-05-23 - Pathfinding Loop Redundancy
**Learning:** The A* implementation contained three loops for neighbor processing: one for orthogonal neighbors, one for diagonal neighbors (which was incomplete), and one unified loop. This caused orthogonal neighbors to be processed twice and diagonal ones to be processed once, while the incomplete loop did nothing.
**Action:** When optimizing pathfinding or grid logic, always check for redundant loop iterations. Consolidating into a single loop using a unified `NEIGHBORS` constant improves performance (approx 10% in this case) and readability. Also, be careful when cleaning up code to ensure the remaining loop covers all cases (verified via `verify_pathfinding_correctness.py`).
