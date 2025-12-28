# The Thing - UI/UX Improvements Implementation Plan

## Overview

This plan covers 19 features across 4 tiers (Tier 4-7), building on the existing event-driven architecture, audio system, and web/terminal UIs.

---

## Tier 4 - Polish & Accessibility

### 1. Sound Effects System Enhancement
**Files to modify:**
- `src/audio/audio_manager.py` - Extend sound types
- `web/static/js/game.js` - Add Web Audio API support
- `web/static/js/audio.js` (new) - Browser audio manager

**Implementation:**
- Add new Sound enum values: DOOR_OPEN, DOOR_CLOSE, WIND_AMBIENT, BLIZZARD, FOOTSTEP_NEAR, FOOTSTEP_FAR, HEARTBEAT, RADIO_STATIC, POWER_HUM, CREATURE_GROWL
- Create `web/static/audio/` directory with audio files (or generate via Web Audio API oscillators)
- Subscribe to events: MOVEMENT → footsteps, door state changes → door sounds
- Add ambient sound loop system with crossfade between tracks
- Implement spatial audio (volume based on distance from player)

**Event mappings:**
```
MOVEMENT → FOOTSTEPS (pitch varies by floor type)
DOOR_STATE_CHANGE → DOOR_OPEN/DOOR_CLOSE
POWER_FAILURE → POWER_DOWN + ambient change
BIOLOGICAL_SLIP → CREATURE_GROWL
ENVIRONMENTAL_STATE_CHANGE (blizzard) → WIND_AMBIENT intensity
```

---

### 2. Screen Reader Support (ARIA)
**Files to modify:**
- `web/templates/index.html` - Add ARIA attributes
- `web/static/js/game.js` - Manage live regions
- `web/static/css/style.css` - Screen reader utility classes

**Implementation:**
- Add `role="log"` and `aria-live="polite"` to game output container
- Add `aria-live="assertive"` for critical alerts (attacks, deaths)
- Label all interactive elements: `aria-label` on buttons, map cells
- Add `role="status"` to health/trust/paranoia indicators
- Create visually-hidden text alternatives for ASCII map
- Add skip links for keyboard navigation
- Announce room changes and nearby crew via live region

**Key ARIA additions:**
```html
<div id="game-output" role="log" aria-live="polite" aria-atomic="false">
<div id="critical-alerts" role="alert" aria-live="assertive">
<div id="health-status" role="status" aria-label="Health: 100%">
<button aria-label="Move north" aria-keyshortcuts="w">
```

---

### 3. Settings Panel (Web UI)
**Files to modify:**
- `web/templates/index.html` - Settings modal HTML
- `web/static/js/game.js` - Settings logic
- `web/static/css/style.css` - Settings panel styling
- `server.py` - Settings persistence endpoint

**Implementation:**
- Create settings modal with tabbed interface:
  - **Audio Tab**: Master volume slider, toggle SFX, toggle ambient, toggle UI sounds
  - **Display Tab**: Font size slider (12-24px), theme selector (amber/green/white phosphor)
  - **Effects Tab**: Toggle scanlines, toggle glitch effects, text speed selector
  - **Accessibility Tab**: High contrast mode, reduced motion, screen reader mode
- Store settings in localStorage + sync to server
- Apply CSS custom properties for theming:
```css
:root[data-theme="amber"] { --terminal-color: #ffb000; }
:root[data-theme="green"] { --terminal-color: #33ff33; }
:root[data-theme="white"] { --terminal-color: #ffffff; }
```
- Font size applies to `#game-output` container
- Persist across sessions via localStorage

---

### 4. Save/Load Game UI
**Files to modify:**
- `web/templates/index.html` - Save/load modal
- `web/static/js/game.js` - Save slot management
- `web/static/css/style.css` - Save slot styling
- `server.py` - Save/load API endpoints

**Implementation:**
- Create modal with 5 save slots + 1 autosave (read-only)
- Each slot shows: slot name, timestamp, turn count, location, crew alive count
- Actions per slot: Save (with confirm if overwriting), Load, Delete, Rename
- Add "Quick Save" (Ctrl+S) and "Quick Load" (Ctrl+L) shortcuts
- Visual slot cards with preview info:
```
┌─────────────────────────────────┐
│ SLOT 1: "Before the lab test"  │
│ Turn 42 | Rec Room | 8 alive   │
│ Saved: Dec 28, 2025 3:45 PM    │
│ [LOAD] [SAVE] [DELETE] [RENAME]│
└─────────────────────────────────┘
```

**API endpoints:**
- `GET /api/saves` - List all saves with metadata
- `POST /api/saves/<slot>` - Save to slot
- `DELETE /api/saves/<slot>` - Delete save
- `PUT /api/saves/<slot>/rename` - Rename save

---

### 5. Tutorial Overlay
**Files to create/modify:**
- `web/static/js/tutorial.js` (new) - Tutorial system
- `web/static/css/tutorial.css` (new) - Overlay styling
- `web/templates/index.html` - Tutorial container
- `web/static/js/game.js` - Tutorial integration

**Implementation:**
- Multi-step tutorial with highlighted UI elements
- Steps:
  1. Welcome + game premise (center modal)
  2. Highlight command input → "Type commands here"
  3. Highlight map → "This shows the station layout"
  4. Highlight crew panel → "Track crew members and trust"
  5. Highlight status bar → "Monitor your health and stats"
  6. Highlight quick actions → "Click for common commands"
  7. Blood test mini-tutorial with practice mode
  8. Final tips + "Press ? for help anytime"

- Use semi-transparent overlay with spotlight cutout on target element
- "Next", "Skip", "Don't show again" buttons
- Store completion in localStorage
- Accessible: keyboard navigation, ARIA descriptions

---

## Tier 5 - Advanced Features

### 6. Crew Relationship Graph
**Files to create/modify:**
- `web/static/js/relationship-graph.js` (new) - D3.js or Canvas visualization
- `web/static/css/relationship-graph.css` (new)
- `web/templates/index.html` - Graph container
- `server.py` - Trust matrix API endpoint

**Implementation:**
- Force-directed graph using D3.js or custom Canvas
- Nodes = crew members (color-coded: alive/dead/infected-if-known)
- Edges = relationships (green=trust, red=suspicion, thickness=intensity)
- Node size reflects player's trust level in that person
- Click node to see detailed relationship info
- Real-time updates via SocketIO when trust changes
- Filter: show all, show only alive, show only suspects
- Legend explaining colors and line types

**Data structure from server:**
```json
{
  "nodes": [{"id": "MacReady", "alive": true, "trust": 75}, ...],
  "edges": [{"source": "MacReady", "target": "Childs", "trust": 60, "suspicion": 20}, ...]
}
```

---

### 7. Timeline View
**Files to create/modify:**
- `web/static/js/timeline.js` (new) - Horizontal timeline component
- `web/static/css/timeline.css` (new)
- `web/templates/index.html` - Timeline panel
- `server.py` - Event history endpoint
- `src/systems/event_logger.py` (new) - Persistent event logging

**Implementation:**
- Horizontal scrollable timeline with turn markers
- Event types as colored icons on timeline:
  - 🚶 Movement (who went where)
  - 💀 Deaths
  - 🔬 Tests performed
  - ⚡ Power events
  - 🚨 Alerts
  - 💬 Key dialogue
- Hover for event details
- Click to expand into detailed view
- Filter by event type, crew member, or room
- Current turn highlighted, auto-scroll to present
- Zoom controls (show 10/20/50 turns at once)

---

### 8. Autopsy Report Modal
**Files to modify:**
- `web/static/js/game.js` - Autopsy modal logic
- `web/templates/index.html` - Modal HTML
- `web/static/css/style.css` - Report styling
- `src/systems/commands.py` - Enhance EXAMINE for corpses
- `server.py` - Autopsy data endpoint

**Implementation:**
- When examining dead crew, show detailed modal:
```
╔══════════════════════════════════════╗
║      AUTOPSY REPORT: BENNINGS       ║
╠══════════════════════════════════════╣
║ Time of Death: Turn 23              ║
║ Location: Kennel                    ║
║ Cause: Assimilated by The Thing     ║
║                                      ║
║ OBSERVATIONS:                        ║
║ • Cellular structure shows alien    ║
║   biomass integration               ║
║ • Last seen alive: Turn 21 (Lab)    ║
║ • Was alone with: Fuchs, Blair      ║
║                                      ║
║ BLOOD TEST: POSITIVE (infected)     ║
║ WITNESS REPORTS: None               ║
╚══════════════════════════════════════╝
```
- Include: time of death, location, cause, last movements, who they were with, test results
- Style as clinical medical report (ASCII box drawing)

---

### 9. Room History Panel
**Files to create/modify:**
- `web/static/js/room-history.js` (new)
- `web/templates/index.html` - Room history panel
- `src/systems/room_tracker.py` (new) - Track room events
- `server.py` - Room history endpoint

**Implementation:**
- Panel showing current room's recent history:
  - Who visited (with timestamps/turns)
  - Items taken/dropped
  - Events that occurred (fights, tests, deaths)
  - Current occupants
- Collapsible list, most recent first
- Updates in real-time as events occur
- "This room has been quiet" if no recent activity
- Filter by event type

---

### 10. Minimap Improvements
**Files to modify:**
- `web/static/js/game.js` - Enhanced minimap rendering
- `web/static/css/style.css` - Fog of war styling

**Implementation:**
- **Fog of war**: Rooms not yet visited are dimmed/hidden
- **Crew position indicators**: Show colored dots for known crew locations
  - Green dot = trusted crew
  - Yellow dot = neutral
  - Red dot = suspected
  - Gray dot = unknown location
  - Skull = dead body
- **Room status indicators**:
  - Barricaded rooms have border
  - Dark rooms (no power) are dimmed
  - Current room highlighted
- **Tooltip on hover**: Room name, occupants, status
- Store exploration state in game state

---

## Tier 6 - Quality of Life

### 11. Command Favorites
**Files to modify:**
- `web/static/js/game.js` - Favorites system
- `web/templates/index.html` - Quick access bar
- `web/static/css/style.css` - Favorites styling

**Implementation:**
- Persistent favorites bar above command input
- Right-click command in history → "Add to favorites"
- Drag-and-drop reordering
- Max 8 favorites visible (overflow menu)
- Each favorite shows command + optional custom label
- Click to execute immediately
- Store in localStorage
- Default favorites: LOOK, INVENTORY, HELP, MAP

---

### 12. Undo/Confirm for Dangerous Actions
**Files to modify:**
- `web/static/js/game.js` - Confirmation modal
- `web/templates/index.html` - Confirmation dialog
- `server.py` - Two-phase dangerous action execution

**Implementation:**
- Dangerous actions list:
  - ACCUSE (accusing wrong person = consequences)
  - ATTACK (initiates combat)
  - USE FLAMETHROWER (permanent, destructive)
  - BARRICADE (traps people)
  - TEST (limited resources)
- Show confirmation modal:
```
┌─────────────────────────────────┐
│ ⚠️  CONFIRM ACTION              │
│                                 │
│ You are about to:               │
│ ACCUSE CHILDS of being infected │
│                                 │
│ This action cannot be undone.   │
│ Are you sure?                   │
│                                 │
│    [CONFIRM]    [CANCEL]        │
└─────────────────────────────────┘
```
- Escape or click outside = cancel
- Track consequences of previous similar actions
- Option to "Don't ask again for this session"

---

### 13. Mobile Responsive Layout
**Files to modify:**
- `web/static/css/style.css` - Media queries
- `web/static/css/mobile.css` (new) - Mobile-specific styles
- `web/templates/index.html` - Responsive containers
- `web/static/js/game.js` - Touch handlers

**Implementation:**
- Breakpoints: Desktop (>1024px), Tablet (768-1024px), Phone (<768px)
- Mobile layout:
  - Stack panels vertically (map on top, output, then input)
  - Collapsible side panels (crew list, stats)
  - Larger touch targets (48px minimum)
  - Swipe gestures: left/right to switch panels
  - Bottom quick-action bar with common commands
  - On-screen directional pad for movement
  - Virtual keyboard awareness (viewport adjustment)
- Tablet layout:
  - 2-column: map+output | crew+stats
  - Touch-friendly buttons
- Hamburger menu for settings/help on mobile

---

### 14. Keyboard Shortcut Overlay
**Files to modify:**
- `web/static/js/game.js` - Shortcut overlay system
- `web/templates/index.html` - Overlay HTML
- `web/static/css/style.css` - Cheat sheet styling

**Implementation:**
- Press `?` once for help, `??` (double tap) for shortcut overlay
- Full-screen overlay with categorized shortcuts:
```
╔═══════════════════════════════════════════════════════════╗
║                 KEYBOARD SHORTCUTS                        ║
╠═══════════════════════════════════════════════════════════╣
║ NAVIGATION          │ GAME ACTIONS        │ UI CONTROLS  ║
║ W - Move North      │ L - Look around     │ ? - Help     ║
║ A - Move West       │ I - Inventory       │ Esc - Close  ║
║ S - Move South      │ T - Talk to nearby  │ Tab - Focus  ║
║ D - Move East       │ E - Examine         │ F1 - Tutorial║
║ Enter - Run command │ H - Hide            │ F5 - Save    ║
║ ↑↓ - Command history│ R - Run             │ F9 - Load    ║
╚═══════════════════════════════════════════════════════════╝
```
- Press any key or click to dismiss
- Option to print/export as image

---

### 15. Game Speed Controls
**Files to modify:**
- `web/static/js/game.js` - Animation speed system
- `web/templates/index.html` - Speed control UI
- `server.py` - Pause state handling

**Implementation:**
- Speed control bar: [⏸️ Pause] [1x] [2x] [Skip]
- **Pause**: Freeze game time, still allow UI interaction
- **1x**: Normal text animation speed
- **2x**: Double speed text crawl
- **Skip/Instant**: Immediately show all text
- Settings persist to localStorage
- Keyboard shortcuts: Space = pause/resume, +/- = speed
- Visual indicator when paused (pulsing border)
- Server-side pause prevents NPC actions

---

## Tier 7 - Immersion

### 16. Weather Effects Overlay
**Files to create/modify:**
- `web/static/js/weather-effects.js` (new) - Canvas-based effects
- `web/static/css/weather.css` (new)
- `web/templates/index.html` - Weather canvas layer

**Implementation:**
- Canvas overlay on top of game content
- **Blizzard effect**:
  - Particle system with white/light-blue dots
  - Diagonal movement (wind direction)
  - Density increases with storm intensity
  - Slight screen shake
- **Snow effect** (calm weather):
  - Gentle falling particles
  - Lower opacity
- **Indoor dampening**: Effects reduced when inside buildings
- Performance: Use requestAnimationFrame, limit particle count
- Toggle in settings (some users may find distracting)
- Sync with game's environmental state

---

### 17. Power Outage Mode
**Files to modify:**
- `web/static/css/style.css` - Dark mode styles
- `web/static/js/game.js` - Power state handling
- `web/static/js/flashlight.js` (new) - Flashlight effect

**Implementation:**
- When power is out:
  - Screen dims significantly (opacity overlay)
  - Only circular "flashlight" area around cursor is visible
  - Flashlight follows mouse/touch
  - Reduced view radius on map
  - UI elements barely visible (glow effect)
  - CRT flicker effect
- Flashlight cone:
  - CSS radial gradient mask or canvas
  - Radius based on flashlight item in inventory
  - Battery drain over time (if flashlight item exists)
- Audio: ambient hum stops, eerie silence + distant sounds
- Power restored: Flicker effect, gradual brightening

---

### 18. Heartbeat Monitor
**Files to create/modify:**
- `web/static/js/heartbeat.js` (new) - ECG animation
- `web/static/css/heartbeat.css` (new)
- `web/templates/index.html` - Heartbeat widget

**Implementation:**
- Small ECG-style widget in corner or status bar
- Canvas drawing animated heartbeat line
- **Rates based on danger**:
  - 60 BPM: Safe, calm
  - 80 BPM: Tension, Thing nearby
  - 100+ BPM: Combat, immediate danger
  - Flatline: Player death
- Audio: Optional heartbeat sound synced to visual
- Pulse effect on health indicator when damaged
- Integrates with paranoia system (higher paranoia = faster base rate)

---

### 19. Radio Static Effect
**Files to create/modify:**
- `web/static/js/radio-effects.js` (new) - Static generator
- `web/static/css/radio.css` (new)
- Audio: Web Audio API noise generation

**Implementation:**
- When comms are jammed or radio room damaged:
  - Visual static overlay (noise texture animation)
  - CSS filter: grainy effect
  - Text in affected areas gets "corrupted" temporarily
  - Partial messages with `[STATIC]` interruptions
- Audio static:
  - White noise generator via Web Audio API
  - Crackle and pop sounds
  - Occasional voice snippets breaking through
- Intensity based on distance from radio room
- Clear signal when comms restored (satisfying clarity)

---

## Implementation Order (Recommended)

### Phase 1 - Foundation (Features 2, 3, 15)
1. Settings Panel (enables all other toggles)
2. Screen Reader Support (improves accessibility baseline)
3. Game Speed Controls (improves text experience)

### Phase 2 - Core Polish (Features 1, 4, 5)
4. Sound Effects Enhancement
5. Save/Load UI
6. Tutorial Overlay

### Phase 3 - Information Display (Features 8, 9, 10)
7. Autopsy Report Modal
8. Room History Panel
9. Minimap Improvements

### Phase 4 - Advanced Visualization (Features 6, 7)
10. Crew Relationship Graph
11. Timeline View

### Phase 5 - Quality of Life (Features 11, 12, 14)
12. Command Favorites
13. Dangerous Action Confirmation
14. Keyboard Shortcut Overlay

### Phase 6 - Mobile (Feature 13)
15. Mobile Responsive Layout

### Phase 7 - Immersion (Features 16, 17, 18, 19)
16. Weather Effects Overlay
17. Power Outage Mode
18. Heartbeat Monitor
19. Radio Static Effect

---

## Technical Considerations

### Performance
- Use `requestAnimationFrame` for all animations
- Throttle event handlers (especially mouse move for flashlight)
- Lazy-load heavy features (D3.js, complex effects)
- Web Workers for particle systems if needed

### Accessibility
- All visual effects must be toggleable
- Respect `prefers-reduced-motion` media query
- Maintain keyboard navigability throughout
- Test with screen readers (NVDA, VoiceOver)

### Browser Support
- Target: Chrome, Firefox, Safari, Edge (latest 2 versions)
- Fallbacks for older browsers (no effects, basic layout)
- Test touch interactions on real devices

### State Persistence
- localStorage for UI preferences
- Server-side save files for game state
- Sync mechanism if user switches devices

---

## File Structure After Implementation

```
web/
├── static/
│   ├── audio/
│   │   ├── door_open.mp3
│   │   ├── door_close.mp3
│   │   ├── footstep.mp3
│   │   ├── wind_ambient.mp3
│   │   └── ... (other audio files)
│   ├── css/
│   │   ├── style.css (enhanced)
│   │   ├── mobile.css (new)
│   │   ├── tutorial.css (new)
│   │   ├── weather.css (new)
│   │   ├── heartbeat.css (new)
│   │   └── relationship-graph.css (new)
│   └── js/
│       ├── game.js (enhanced)
│       ├── audio.js (new)
│       ├── tutorial.js (new)
│       ├── timeline.js (new)
│       ├── relationship-graph.js (new)
│       ├── room-history.js (new)
│       ├── weather-effects.js (new)
│       ├── flashlight.js (new)
│       ├── heartbeat.js (new)
│       └── radio-effects.js (new)
├── templates/
│   └── index.html (enhanced with new modals/panels)
src/
├── systems/
│   ├── event_logger.py (new - persistent event tracking)
│   └── room_tracker.py (new - room event history)
server.py (enhanced with new API endpoints)
```
