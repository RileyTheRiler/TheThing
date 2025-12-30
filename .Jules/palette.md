## 2024-05-22 - [Terminal UI Onboarding]
**Learning:** In a terminal-based interface with complex commands, "Unknown command" on the first screen is a high-friction barrier. Users expect immediate guidance.
**Action:** Always provide a "Situation Report" or "Quick Start" hint on the initial boot screen for CLI apps, listing at least one valid command (like 'HELP').
## 2024-05-23 - Smart Legends for ASCII Maps
**Learning:** In ASCII interfaces where symbols are reused (like '*'), users struggle to identify specific objects without tedious "look" commands.
**Action:** Implement context-aware legends that dynamically list the specific names of visible entities (e.g., `[*=Shotgun, Key]`) based on the viewport, rather than a static key.
# Palette Journal

## 2024-05-24 - Unicode Icons Accessibility
**Learning:** Relying on unicode characters for icons (e.g., ✕, ▲) creates unpredictable screen reader experiences (e.g., reading "Multiplication X" instead of "Close").
**Action:** Always wrap decorative unicode icons in `aria-hidden="true"` and provide explicit `aria-label` for the interactive element.
