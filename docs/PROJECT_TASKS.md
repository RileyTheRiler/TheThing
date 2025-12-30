# The Thing: Antarctic Research Station 31 - Project Tasks

This document contains actionable implementation tasks organized by feature area. Each task includes implementation guidance pointing to relevant code locations.

---

## 🎭 Advanced AI & Social Dynamics

### 1. NPC Collaboration: Infected Coordination
**Priority:** High | **Complexity:** Medium

When an infected NPC detects the player, they should quietly signal other nearby infected NPCs to coordinate a pincer movement or ambush.

**Implementation Steps:**
1. Add `_broadcast_infected_alert()` method in `src/systems/ai.py:160` (near `_broadcast_alert`)
2. Filter recipients to only infected NPCs using `getattr(npc, 'is_infected', False)`
3. Set a shared `ambush_target_location` on coordinating NPCs
4. Implement pincer logic: calculate flanking positions using `pathfinding.py` to approach from opposite directions
5. Add new `suspicion_state: "coordinating"` to track infected NPCs working together
6. Emit `EventType.INFECTED_COORDINATION` for UI feedback

**Key Files:**
- `src/systems/ai.py:160-175` - Alert broadcasting
- `src/systems/pathfinding.py` - Flanking position calculation
- `src/entities/crew_member.py:55-66` - Suspicion state tracking

---

### 2. Dialogue Branching: "Explain Away" Mechanic
**Priority:** Medium | **Complexity:** Medium

Link `get_reaction_dialogue` to allow the player to attempt to explain suspicious behavior when caught sneaking (CHARISMA + DECEPTION check).

**Implementation Steps:**
1. Create `src/systems/dialogue_system.py` with `DialogueBranchingSystem` class
2. Add `EXPLAIN_AWAY` command handler in `src/systems/commands.py`
3. Roll: `INFLUENCE + DECEPTION` vs `LOGIC + EMPATHY` of the accuser
4. Success: Reduce suspicion by 3-5, emit forgiving dialogue
5. Failure: Increase suspicion by 2, emit skeptical dialogue, possible trust penalty
6. Critical Failure (0 successes): Immediate accusation trigger
7. Subscribe to `PERCEPTION_EVENT` outcomes to offer "Explain Away" prompt

**Key Files:**
- `src/systems/social.py:382-437` - Existing DialogueManager
- `src/entities/crew_member.py:377-385` - `get_reaction_dialogue()`
- `src/core/resolution.py` - Dice pool mechanics

---

### 3. AI Schedule Disruption: Interrogate Whereabouts
**Priority:** Medium | **Complexity:** Low

If a player catches an NPC out of their scheduled location (role dissonance), unlock a special "Interrogate Whereabouts" command with higher success probability.

**Implementation Steps:**
1. Add `is_out_of_schedule()` method to `CrewMember` checking current location vs `schedule` entries
2. Modify `src/systems/interrogation.py` to add `WHEREABOUTS_BONUS = 2` when target is out-of-place
3. Cross-reference with `src/systems/missionary.py:30-40` role habitats table
4. Add UI indicator when NPC is "out of place" (visual marker for player)
5. Success reveals NPC's actual schedule and recent movement history

**Key Files:**
- `src/systems/interrogation.py` - Main interrogation logic
- `src/systems/missionary.py:30-40` - Role habitat definitions
- `src/entities/crew_member.py` - Schedule data structure

---

### 4. Global Alert Status: Station-Wide Vigilance
**Priority:** High | **Complexity:** Medium

If the player is caught by a human NPC, trigger a "Station Alert" making all NPCs more vigilant for a set duration.

**Implementation Steps:**
1. Add `alert_status` and `alert_turns_remaining` to `GameState` in `src/engine.py`
2. Create `AlertSystem` class in `src/systems/alert.py`
3. Subscribe to `PERCEPTION_EVENT` with outcome="detected"
4. When triggered: Set `alert_turns_remaining = 10`, boost all NPC `observation` pools by +2
5. Decay alert by 1 each turn; when 0, restore normal perception
6. Add visual/audio cues: "ALERT: Suspicious activity reported!" via `EventType.WARNING`
7. NPCs in alert mode move faster (reduce pathfinding cost) and actively patrol

**Key Files:**
- `src/engine.py` - GameState management
- `src/systems/ai.py:176-196` - Turn update loop
- `src/systems/stealth.py:87-91` - Observer pool calculation

---

## 🏢 Environment & Interactables

### 5. Distraction Mechanics: Throwable Items
**Priority:** High | **Complexity:** Medium

Allow the player to throw items (Flare, Empty Can, Rock) to create a `PERCEPTION_EVENT` at a target location, pulling NPC attention.

**Implementation Steps:**
1. Add `THROW <ITEM> <DIRECTION/ROOM>` command in `src/systems/commands.py`
2. Create `DistrationSystem` in `src/systems/distraction.py`
3. Mark throwable items in `data/items.json` with `"throwable": true, "noise_level": 5`
4. Calculate landing position based on direction (3-5 tiles away)
5. Emit `PERCEPTION_EVENT` with source="distraction", high noise_level at landing tile
6. NPCs within range react: interrupt current action, pathfind to noise source
7. Add 2-turn investigation behavior at distraction point before resuming schedule

**Key Files:**
- `src/systems/ai.py:39-79` - `on_perception_event()` handler
- `src/entities/station_map.py` - Position calculations
- `data/items.json` - Item definitions

**New Items to Add:**
```json
{"name": "Empty Can", "throwable": true, "noise_level": 4},
{"name": "Flare", "throwable": true, "noise_level": 6, "creates_light": true},
{"name": "Rock", "throwable": true, "noise_level": 3}
```

---

### 6. Security Systems: Cameras & Motion Sensors
**Priority:** Medium | **Complexity:** High

Add functional security cameras or motion sensors that emit `PERCEPTION_EVENTs` to a "Security Station" which NPCs can check.

**Implementation Steps:**
1. Create `src/systems/security.py` with `SecuritySystem` class
2. Define camera/sensor positions in `src/entities/station_map.py` (similar to hiding_spots)
3. Cameras detect movement in their cone of view (3x3 tile area)
4. Motion sensors trigger on any movement through their tile
5. Log detections to `security_log` list in GameState
6. Add `SECURITY` room or console in Radio Room where NPCs check logs
7. NPCs with "Security" role periodically check console and investigate logged events
8. Player can `SABOTAGE CAMERA` to disable (requires tools, makes noise)

**Key Files:**
- `src/entities/station_map.py:232-258` - Hiding spots pattern to follow
- `src/systems/sabotage.py` - Existing sabotage mechanics
- `src/systems/ai.py` - NPC behavior hooks

**Camera Data Structure:**
```python
self.cameras = {
    (6, 6): {"room": "Rec Room", "facing": "S", "range": 3},
    (12, 2): {"room": "Radio Room", "facing": "E", "range": 3},
}
```

---

### 7. Enhanced Vent Encounters
**Priority:** Low | **Complexity:** Low

Expand ventilation system with risk of meeting "The Thing" in close quarters and echoing noise mechanics.

**Implementation Steps:**
1. Modify `handle_vent_movement()` in `src/systems/stealth.py:283-322`
2. Increase base noise to 8+ (echoing effect)
3. Add `vent_encounter_chance` config (currently 15%, consider raising)
4. When Thing encountered in vent: Limited escape options, high danger
5. Add `CRAWL_SPEED` modifier when in vents (takes 2 turns per tile)
6. Sound propagates to adjacent vent nodes, alerting Things in duct network

**Key Files:**
- `src/systems/stealth.py:283-322` - Vent movement handler
- `src/entities/station_map.py:62-90` - Vent graph structure
- `src/systems/ai.py:305-360` - Thing AI behavior

---

## 📊 Systemic Engine Work

### 8. Stealth Skill Progression: XP System
**Priority:** Medium | **Complexity:** Medium

Implement a system where successful evasions grant "Stealth XP," eventually lowering base noise or increasing stealth pool.

**Implementation Steps:**
1. Add `stealth_xp` and `stealth_level` to `CrewMember` in `src/entities/crew_member.py`
2. Create `ProgressionSystem` in `src/systems/progression.py`
3. Subscribe to `STEALTH_REPORT` events with outcome="evaded"
4. Grant XP based on difficulty: `(observer_pool - player_successes) * 10`
5. Level thresholds: [100, 300, 600, 1000] XP
6. Benefits per level:
   - Level 1: -1 base noise
   - Level 2: +1 stealth pool
   - Level 3: -1 base noise
   - Level 4: +1 stealth pool, unlock "Silent Takedown"
7. Emit `SKILL_LEVEL_UP` event for feedback

**Key Files:**
- `src/systems/stealth.py:147-162` - Stealth report emission
- `src/entities/crew_member.py` - Character stats
- `src/core/resolution.py` - Skill modifiers

---

### 9. Enhanced Thermal Detection
**Priority:** Low | **Complexity:** Medium

Expand thermal signature mechanics: The Thing's heat is detectable in darkness but not in frozen rooms.

**Implementation Steps:**
1. Review existing `thermal_detected` logic in `src/systems/stealth.py:212-218`
2. Add `THERMAL` attribute to all characters (Things have higher values)
3. In darkness (`RoomState.DARK`), enable thermal detection roll
4. In frozen rooms (`RoomState.FROZEN`), disable thermal detection (signatures masked)
5. Add `THERMAL_GOGGLES` item that gives player +3 thermal detection pool
6. Things can detect humans by heat; implement reverse detection

**Key Files:**
- `src/systems/stealth.py:212-218` - Existing thermal logic
- `src/systems/environmental_coordinator.py` - Environment modifiers
- `src/systems/room_state.py` - Room state queries

---

### 10. Persistence of Perception: Enhanced Search Memory
**Priority:** Medium | **Complexity:** Low

NPCs "remember" where they last saw the player and continue searching that area and adjacent corridors for several turns.

**Implementation Steps:**
1. Review existing `_enter_search_mode()` in `src/systems/ai.py:498-535`
2. Extend `SEARCH_TURNS` from 5 to 8 for more thorough sweeps
3. Add adjacent room names to search pattern (not just corridors)
4. Implement "spiral out" pattern: start at last-seen, expand search radius each turn
5. If player detected during search, reset search timer and update anchor
6. Add `search_history` list tracking rooms already checked this search

**Key Files:**
- `src/systems/ai.py:498-560` - Search mode implementation
- `src/entities/crew_member.py:68-75` - Search state variables

---

## 🎮 Gameplay Features

### 11. Alternative Endings (Roadmap Item 6.3)
**Priority:** High | **Complexity:** High

Implement multiple victory conditions beyond "eliminate all infected."

**Endings to Implement:**
1. **Helicopter Escape**: Radio operational + helicopter repaired + reach Hangar helipad
2. **Radio Rescue**: Radio operational + survive 50 turns + rescue team arrives
3. **Sole Survivor**: All other crew dead (infected or not) + player alive
4. **Pyrrhic Victory**: Station destroyed (all power sabotaged) + player escapes to ice

**Implementation Steps:**
1. Add ending conditions check in `src/systems/endgame.py`
2. Track `helicopter_operational` and `radio_operational` in GameState
3. Add `REPAIR HELICOPTER` and `REPAIR RADIO` commands (require specific items)
4. Implement turn counter for rescue timer
5. Add escape routes from Hangar and Radio Room
6. Create unique ending narrations for each outcome

**Key Files:**
- `src/systems/endgame.py` - Win/lose condition checks
- `src/systems/sabotage.py` - Equipment status tracking
- `src/game_loop.py` - Ending display

---

### 12. Enhanced Crafting Recipes
**Priority:** Low | **Complexity:** Low

Expand crafting system with tactical items.

**New Recipes:**
```json
{
  "Noise Maker": {"components": ["Empty Can", "Wire"], "noise_level": 8, "throwable": true},
  "Tripwire Alarm": {"components": ["Wire", "Empty Can"], "deployable": true, "alerts_on_trigger": true},
  "Thermal Blanket": {"components": ["Cloth", "Fuel"], "masks_heat": true},
  "Barricade Kit": {"components": ["Planks", "Nails"], "instant_barricade": true},
  "Blood Test Kit": {"components": ["Scalpel", "Copper Wire", "Container"], "portable_test": true}
}
```

**Implementation Steps:**
1. Add recipes to `data/crafting.json`
2. Add new item behaviors in `src/entities/item.py`
3. Add `DEPLOY <ITEM>` command for placeable items
4. Tripwires emit `PERCEPTION_EVENT` when triggered

**Key Files:**
- `data/crafting.json` - Recipe definitions
- `src/systems/crafting.py` - Crafting logic
- `src/entities/item.py` - Item behavior

---

## 🔧 Technical Improvements

### 13. Event-Based Audio Cues
**Priority:** Low | **Complexity:** Low

Tie audio feedback to game events for atmosphere.

**Implementation Steps:**
1. Subscribe `AudioManager` to key events in `src/audio/audio_manager.py`
2. Event mappings:
   - `STEALTH_REPORT` (detected) → tension sting
   - `COMBAT_LOG` → impact sounds
   - `WARNING` → alert klaxon
   - `TRUST_THRESHOLD_CROSSED` → suspicion whisper
3. Add ambient sound based on room (generator hum, wind, radio static)

**Key Files:**
- `src/audio/audio_manager.py` - Audio playback
- `src/core/event_system.py` - Event subscription

---

### 14. Save/Load Validation
**Priority:** Medium | **Complexity:** Low

Add validation and migration for save files.

**Implementation Steps:**
1. Add `save_version` field to save data in `src/systems/persistence.py`
2. Implement `migrate_save(data, from_version, to_version)`
3. Validate required fields on load, use defaults for missing
4. Add checksum for corruption detection
5. Backup previous save before overwriting

**Key Files:**
- `src/systems/persistence.py` - Save/load logic
- `src/engine.py` - GameState serialization

---

## 📋 Task Summary by Priority

### High Priority
1. NPC Collaboration: Infected Coordination
2. Global Alert Status: Station-Wide Vigilance
3. Distraction Mechanics: Throwable Items
4. Alternative Endings

### Medium Priority
5. Dialogue Branching: "Explain Away" Mechanic
6. AI Schedule Disruption: Interrogate Whereabouts
7. Security Systems: Cameras & Motion Sensors
8. Stealth Skill Progression: XP System
9. Persistence of Perception: Enhanced Search Memory
10. Save/Load Validation

### Low Priority
11. Enhanced Vent Encounters
12. Enhanced Thermal Detection
13. Enhanced Crafting Recipes
14. Event-Based Audio Cues

---

## Implementation Order Recommendation

1. **Distraction Mechanics** → Enables tactical gameplay immediately
2. **Global Alert Status** → Creates tension and consequence
3. **NPC Collaboration** → Makes infected more threatening
4. **Alternative Endings** → Completes game loop (roadmap item)
5. **Stealth Skill Progression** → Adds RPG depth
6. **Dialogue Branching** → Enhances social gameplay
7. **Security Systems** → New stealth challenge layer

Each task is designed to integrate with the existing event-driven architecture and can be implemented independently without breaking other systems.
