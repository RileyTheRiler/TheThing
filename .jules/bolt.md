## 2024-05-22 - Instantiation inside Loops
**Learning:** Instantiating logic classes (like `ResolutionSystem`) inside nested loops can cause significant performance overhead (O(N) allocations) and hides bugs (like signature mismatches) if the code path is rarely exercised or crashed before measuring.
**Action:** Always hoist stateless or reusable system instantiations out of loops. Verify function signatures statically or with a test before assuming optimization is the only task.

## 2025-01-05 - Redundant Neighbor Iteration in A*
**Learning:** The A* implementation was iterating over orthogonal neighbors twice due to a copy-paste error or legacy code refactoring that left two loops active (one specific, one general). This doubled the work for the most common movement type.
**Action:** Consolidate neighbor processing into a single loop using a pre-computed list of all neighbors (orthogonal + diagonal). This reduces redundant checks and heuristic calculations.
