## 2024-05-22 - [Terminal UI Onboarding]
**Learning:** In a terminal-based interface with complex commands, "Unknown command" on the first screen is a high-friction barrier. Users expect immediate guidance.
**Action:** Always provide a "Situation Report" or "Quick Start" hint on the initial boot screen for CLI apps, listing at least one valid command (like 'HELP').
## 2024-05-23 - Smart Legends for ASCII Maps
**Learning:** In ASCII interfaces where symbols are reused (like '*'), users struggle to identify specific objects without tedious "look" commands.
**Action:** Implement context-aware legends that dynamically list the specific names of visible entities (e.g., `[*=Shotgun, Key]`) based on the viewport, rather than a static key.
# Palette Journal

_No critical UX or accessibility learnings recorded yet._

## 2024-05-24 - Semantic Labels for Command Inputs
**Learning:** In terminal-style interfaces, the primary interaction point (the input field) often lacks a visible label for aesthetic reasons. This creates a critical barrier for screen reader users who see an unlabeled edit field.
**Action:** Always ensure terminal input fields have an `aria-label` (e.g., "Enter command") even if the visual design relies on a prompt symbol like `CMD>`.
