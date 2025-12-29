## 2024-05-22 - [Terminal UI Onboarding]
**Learning:** In a terminal-based interface with complex commands, "Unknown command" on the first screen is a high-friction barrier. Users expect immediate guidance.
**Action:** Always provide a "Situation Report" or "Quick Start" hint on the initial boot screen for CLI apps, listing at least one valid command (like 'HELP').
## 2024-05-23 - Smart Legends for ASCII Maps
**Learning:** In ASCII interfaces where symbols are reused (like '*'), users struggle to identify specific objects without tedious "look" commands.
**Action:** Implement context-aware legends that dynamically list the specific names of visible entities (e.g., `[*=Shotgun, Key]`) based on the viewport, rather than a static key.
# Palette Journal

_No critical UX or accessibility learnings recorded yet._
## 2024-05-24 - [Accessible Icon Buttons]
**Learning:** Icon-only buttons are a major accessibility trap. Using 'title' is insufficient for screen readers.
**Action:** Always pair icon-only buttons with 'aria-label' for the action name and 'aria-keyshortcuts' if applicable. Wrap the icon itself in a span with 'aria-hidden=true' to prevent the screen reader from announcing the glyph character (e.g., 'Black Up-Pointing Triangle').
