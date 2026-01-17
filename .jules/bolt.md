## 2024-05-22 - Instantiation inside Loops
**Learning:** Instantiating logic classes (like `ResolutionSystem`) inside nested loops can cause significant performance overhead (O(N) allocations) and hides bugs (like signature mismatches) if the code path is rarely exercised or crashed before measuring.
**Action:** Always hoist stateless or reusable system instantiations out of loops. Verify function signatures statically or with a test before assuming optimization is the only task.

## 2024-05-23 - Redundant Loop Iteration
**Learning:** Found a pattern where orthogonal and diagonal neighbors were iterated in separate loops (sometimes with empty bodies) BEFORE a unified loop that handled everything. This caused 1.5x-2x redundant work per node expansion.
**Action:** Inspect loops in hot paths (like A*) for redundancy. Ensure the loop logic matches the intent and doesn't duplicate work done in subsequent loops.

## 2024-05-24 - Double Budget Billing in Movement Loops
**Learning:** In `AISystem._pathfind_step`, a legacy loop structure caused the action budget to be charged twice per movement: once in a vestigial checking loop, and again in the actual movement loop. This effectively halved the AI's action economy.
**Action:** When refactoring movement logic, ensure budget checks are performed once per high-level action (like "move to target") rather than per low-level step, or use a "budget_used" flag consistently across all code paths.
