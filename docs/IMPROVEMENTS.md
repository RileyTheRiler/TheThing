# Architecture Improvements Roadmap

This document tracks planned improvements for "The Thing: Antarctic Research Station 31" based on architectural review.

## Overview

The game uses an **event-driven, multi-agent architecture** where 8+ independent systems communicate through a central EventBus. This creates emergent gameplay but several issues need addressing.

---

## Tier 1: Critical Fixes (Blocking/Breaking) - COMPLETED

- [x] **1.1** Fix import paths to comply with AGENT_GUIDELINES (remove `src.` prefix) - `engine.py`
- [x] **1.2** Remove duplicate TAG/LOG/DOSSIER command handlers - `engine.py`
- [x] **1.3** Fix broken `game.forensics` reference to use `game.blood_test_sim` - `engine.py`
- [x] **1.4** Implement win/lose conditions - `engine.py`
- [x] **1.5** Remove unused `src/process/` directory

---

## Tier 2: Architecture Improvements - COMPLETE

- [x] **2.1** Extract `Item` class to `src/entities/item.py`
- [x] **2.2** Extract `CrewMember` class to `src/entities/crew_member.py`
- [x] **2.3** Extract `StationMap` class to `src/entities/station_map.py`
- [x] **2.4** Refactor `main()` game loop into `src/game_loop.py`
- [x] **2.5** Add proper NPC pathfinding (A* instead of greedy step) - `src/systems/pathfinding.py`
- [x] **2.6** Implement "Reporting Pattern" - `src/ui/message_reporter.py` with event-based output

---

## Tier 3: Gameplay Enhancements - COMPLETE

- [x] **3.1** Add difficulty settings (Easy/Normal/Hard with infection rates, mask decay, paranoia)
- [x] **3.2** Expand combat system with initiative, cover, and retreat mechanics - `src/systems/combat.py`
- [x] **3.3** Add more rooms (Radio Room, Storage, Lab, Sleeping Quarters, Mess Hall)
- [x] **3.4** Implement Thing-creature combat AI when revealed (hunting, attacking, infection)
- [x] **3.5** Add interrogation/accusation dialogue system - `src/systems/interrogation.py`
- [x] **3.6** Implement barricade entry mechanics - BREAK command, NPC barricade handling

---

## Tier 4: Documentation & Testing - COMPLETE

- [x] **4.1** Complete `TruthLog.md` with all 15 mechanics documented
- [x] **4.2** Add in-game HELP command with topic categories
- [x] **4.3** Convert verification scripts to pytest format - `tests/test_game_systems.py`
- [x] **4.4** Add integration test for full game loop - `tests/test_integration.py`
- [x] **4.5** Create player tutorial/intro sequence - `src/game_loop.py` `_show_tutorial()`

---

## Tier 5: Platform & Polish - COMPLETE

- [x] **5.1** Replace Windows-only `winsound` with cross-platform audio - `src/audio/audio_manager.py`
- [x] **5.2** Add command history/arrow key navigation - `src/game_loop.py` with readline/pyreadline3
- [x] **5.3** Implement auto-save on turn advance (every 5 turns) - `src/engine.py`
- [x] **5.4** Add colorblind-friendly palette option - `src/ui/crt_effects.py` with 5 palettes

---

## Tier 6: Extended Features - COMPLETE

- [x] **6.1** Add in-game settings menu - `src/ui/settings.py` (palette, speed, audio)
- [x] **6.2** Implement random events system - `src/systems/random_events.py`
- [x] **6.3** Add alternative endings (helicopter escape, radio rescue, sole survivor) - `src/systems/endgame.py`
- [x] **6.4** Add game statistics tracking - `src/systems/statistics.py`
- [x] **6.5** Implement stealth/hiding mechanics (avoid Thing detection) - `src/systems/stealth.py`
- [x] **6.6** Add item crafting system (combine items for new tools/weapons) - `src/systems/crafting.py`

---

## Architecture Strengths (Preserve These)

| Strength | Implementation |
|----------|----------------|
| Event-Driven Decoupling | EventBus in `src/core/event_system.py` |
| Data-Driven Design | Characters/items in JSON config |
| Serializable State | `to_dict()`/`from_dict()` pattern |
| Deterministic RNG | Seeded `RandomnessEngine` |
| Atmospheric UI | CRT effects, paranoia-based glitch |
| Deep Simulation | Weather, psychology, trust, infection interact |

---

## Implementation Notes

### Import Path Standard (AGENT_GUIDELINES)
```python
# CORRECT:
from systems.missionary import MissionarySystem
from core.resolution import Attribute, Skill

# INCORRECT:
from src.systems.missionary import MissionarySystem
from src.core.resolution import Attribute, Skill
```

### Win/Lose Conditions
- **WIN**: All infected crew eliminated, player alive
- **LOSE**: Player killed OR player infected and revealed
- **ESCAPE**: Helicopter operational + reach Kennel helipad (future)

### New Commands (Tier 3)
```
ATTACK <NAME>      - Attack with initiative rolls and cover support
COVER [TYPE]       - Take cover (LIGHT/HEAVY/FULL or auto-select)
RETREAT            - Attempt to flee from revealed Things
INTERROGATE <NAME> [TOPIC] - Question crew (WHEREABOUTS/ALIBI/SUSPICION/BEHAVIOR/KNOWLEDGE)
ACCUSE <NAME>      - Formal accusation triggering crew vote
BREAK <DIRECTION>  - Break through a barricade
BARRICADE          - Barricade current room (can be reinforced)
```

### Color Palettes (Tier 5.4)
Available palettes in `CRTOutput`:
| Palette | Description |
|---------|-------------|
| `amber` | Classic amber CRT terminal (default) |
| `green` | Classic green phosphor terminal |
| `white` | Modern white terminal |
| `colorblind` | High contrast blue/cyan (deuteranopia/protanopia safe) |
| `high-contrast` | Maximum contrast white on black (low vision friendly) |

Usage: `CRTOutput(palette="colorblind")` or `crt.set_palette("high-contrast")`

### Command History (Tier 5.2)
Arrow key navigation and command history:
- **Up/Down arrows**: Cycle through previous commands
- **History file**: `~/.thething_history` (persists between sessions)
- **Max entries**: 100 commands
- **Cross-platform**: Uses `readline` (Unix) or `pyreadline3` (Windows)

### Reporting Pattern (Tier 2.6)
Systems emit events instead of returning strings:
```python
# Old pattern (returns string):
return f"Barricade erected. Strength: {strength}/3"

# New pattern (emits event):
event_bus.emit(GameEvent(EventType.BARRICADE_ACTION, {
    'action': 'built',
    'room': room_name,
    'strength': strength
}))
```

Event types for reporting:
| EventType | Purpose |
|-----------|---------|
| `MESSAGE` | General output |
| `WARNING` | High-visibility alerts |
| `COMBAT_LOG` | Attack results |
| `DIALOGUE` | NPC speech |
| `BARRICADE_ACTION` | Barricade events |
| `TEST_RESULT` | Blood test outcomes |

The `MessageReporter` class subscribes to these and routes them through `CRTOutput`.
