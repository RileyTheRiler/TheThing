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

## Tier 2: Architecture Improvements - MOSTLY COMPLETE

- [x] **2.1** Extract `Item` class to `src/entities/item.py`
- [x] **2.2** Extract `CrewMember` class to `src/entities/crew_member.py`
- [x] **2.3** Extract `StationMap` class to `src/entities/station_map.py`
- [x] **2.4** Refactor `main()` game loop into `src/game_loop.py`
- [x] **2.5** Add proper NPC pathfinding (A* instead of greedy step) - `src/systems/pathfinding.py`
- [ ] **2.6** Implement "Reporting Pattern" - systems emit events instead of returning strings

---

## Tier 3: Gameplay Enhancements - COMPLETE

- [x] **3.1** Add difficulty settings (Easy/Normal/Hard with infection rates, mask decay, paranoia)
- [x] **3.2** Expand combat system with initiative, cover, and retreat mechanics - `src/systems/combat.py`
- [x] **3.3** Add more rooms (Radio Room, Storage, Lab, Sleeping Quarters, Mess Hall)
- [x] **3.4** Implement Thing-creature combat AI when revealed (hunting, attacking, infection)
- [x] **3.5** Add interrogation/accusation dialogue system - `src/systems/interrogation.py`
- [x] **3.6** Implement barricade entry mechanics - BREAK command, NPC barricade handling

---

## Tier 4: Documentation & Testing

- [ ] **4.1** Complete `TruthLog.md` with all 10+ mechanics
- [ ] **4.2** Add in-game HELP command with full command list
- [ ] **4.3** Convert verification scripts to pytest format
- [ ] **4.4** Add integration test for full game loop
- [ ] **4.5** Create player tutorial/intro sequence

---

## Tier 5: Platform & Polish

- [ ] **5.1** Replace Windows-only `winsound` with cross-platform audio
- [ ] **5.2** Add command history/arrow key navigation
- [ ] **5.3** Implement auto-save on turn advance
- [ ] **5.4** Add colorblind-friendly palette option

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
