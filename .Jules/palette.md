## 2024-05-22 - [Terminal UI Onboarding]
**Learning:** In a terminal-based interface with complex commands, "Unknown command" on the first screen is a high-friction barrier. Users expect immediate guidance.
**Action:** Always provide a "Situation Report" or "Quick Start" hint on the initial boot screen for CLI apps, listing at least one valid command (like 'HELP').
## 2024-05-23 - Smart Legends for ASCII Maps
**Learning:** In ASCII interfaces where symbols are reused (like '*'), users struggle to identify specific objects without tedious "look" commands.
**Action:** Implement context-aware legends that dynamically list the specific names of visible entities (e.g., `[*=Shotgun, Key]`) based on the viewport, rather than a static key.
# Palette Journal

_No critical UX or accessibility learnings recorded yet._
## 2024-05-23 - Accessibility First: Missing ARIA Labels on Core UI
**Learning:** Found significant accessibility gaps in the core UI: modal close buttons, navigation controls, and primary inputs were missing 'aria-label' attributes. While 'title' was present on some, it's insufficient for screen readers on icon-only buttons.
**Action:** Systematically audited 'index.html' and added descriptive 'aria-label' attributes to all icon-only buttons and inputs. Future UI additions must include these by default.
