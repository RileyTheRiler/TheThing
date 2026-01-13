## 2024-05-22 - [Terminal UI Onboarding]
**Learning:** In a terminal-based interface with complex commands, "Unknown command" on the first screen is a high-friction barrier. Users expect immediate guidance.
**Action:** Always provide a "Situation Report" or "Quick Start" hint on the initial boot screen for CLI apps, listing at least one valid command (like 'HELP').
## 2024-05-23 - Smart Legends for ASCII Maps
**Learning:** In ASCII interfaces where symbols are reused (like '*'), users struggle to identify specific objects without tedious "look" commands.
**Action:** Implement context-aware legends that dynamically list the specific names of visible entities (e.g., `[*=Shotgun, Key]`) based on the viewport, rather than a static key.
## 2024-05-24 - Context for Disabled States
**Learning:** Disabled buttons in narrative interfaces can feel broken if unexplained.
**Action:** Always add a `title` attribute or tooltip to disabled UI elements explaining the in-world reason (e.g., "Encrypted. Clearance Level 4 required") to turn a frustration into a flavor moment.
