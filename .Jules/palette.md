## 2024-05-22 - [Terminal UI Onboarding]
**Learning:** In a terminal-based interface with complex commands, "Unknown command" on the first screen is a high-friction barrier. Users expect immediate guidance.
**Action:** Always provide a "Situation Report" or "Quick Start" hint on the initial boot screen for CLI apps, listing at least one valid command (like 'HELP').
## 2024-05-23 - Smart Legends for ASCII Maps
**Learning:** In ASCII interfaces where symbols are reused (like '*'), users struggle to identify specific objects without tedious "look" commands.
**Action:** Implement context-aware legends that dynamically list the specific names of visible entities (e.g., `[*=Shotgun, Key]`) based on the viewport, rather than a static key.
## 2024-05-24 - Accessible Icon Buttons
**Learning:** Icon-only buttons (like ✕, ▲) rely on visual context that is lost to screen readers. Relying on `title` attributes alone is insufficient for accessibility.
**Action:** Always pair icon-only buttons with explicit `aria-label` attributes describing the action (e.g., "Close Modal", "Go North").
# Palette Journal

_No critical UX or accessibility learnings recorded yet._

## 2024-05-24 - [Disabled Button Tooltips]
**Learning:** Standard HTML `title` tooltips often fail to appear on `disabled` buttons because these elements suppress pointer events in many browsers.
**Action:** Wrap disabled buttons in a container to hold the tooltip, or use `aria-disabled="true"` with CSS styling instead of the `disabled` attribute for more robust accessibility.
## 2024-05-24 - [Semantic Input Labels]
**Learning:** In CLI-style web interfaces, input fields often lack visual labels to maintain the aesthetic, which critically harms accessibility for screen reader users who cannot see the "CMD>" prompt.
**Action:** Always include an `aria-label` or visually hidden `<label>` for command line inputs in web interfaces, even if the visual design implies the function.
## 2024-05-24 - [Accessible Icon-Only Buttons in Retro UI]
**Learning:** Retro interfaces often rely on character glyphs (✕, ▲, ►) as icons. While stylistically consistent, these are invisible or confusing to screen readers without explicit labels.
**Action:** When using text characters as icons, always wrap them in an accessible container or attach an `aria-label` to the interactive element to describe the action, not the glyph.
## 2024-05-24 - [Redundant Modal Actions]
**Learning:** Legacy codebases often accumulate copy-paste errors in modal templates, resulting in multiple "Close" buttons that clutter the DOM and confuse screen reader navigation.
**Action:** When auditing modals, specifically check for and consolidate redundant close actions into a single, clearly labeled interactive element.
