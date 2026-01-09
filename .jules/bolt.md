## 2024-05-22 - Instantiation inside Loops
**Learning:** Instantiating logic classes (like `ResolutionSystem`) inside nested loops can cause significant performance overhead (O(N) allocations) and hides bugs (like signature mismatches) if the code path is rarely exercised or crashed before measuring.
**Action:** Always hoist stateless or reusable system instantiations out of loops. Verify function signatures statically or with a test before assuming optimization is the only task.

## 2024-05-22 - Redundant Loops and Dead Code
**Learning:** Found redundant loops in `PathfindingSystem` that processed neighbors twice. Also found dead code in `StealthSystem` referencing non-existent Enum members (`HIDDEN`, `EXPOSED`) which caused crashes during testing.
**Action:** Consolidate loops where possible. Always check Enum definitions before referencing them in logic, as "dead code" might actually be "crashing code" waiting to happen.
