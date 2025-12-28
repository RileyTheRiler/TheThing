# The Truth Log

This document tracks the canonical rules for the game's simulation layer.

## 1. Infection Mechanics (`systems/infection.py`)
- **Condition:** Two or more characters in the same coordinate.
- **Source:** At least one character must be `is_infected=True`.
- **Chance:**
    - **Base:** 10% per turn.
    - **Darkness (Power Off):** 50% per turn.

## 2. Biological Tells (`engine.py` - `CrewMember.get_dialogue`)
- **Vapor Check:**
    - **Condition:** Temperature < 0°C.
    - **Human:** Always emits `[VAPOR]`.
    - **Thing:** Emits `[VAPOR]` 80% of the time. 20% chance of **Biological Slip** (missing vapor).

## 3. Map
- 20x20 Grid.
- Locations: Rec Room (5,5), Infirmary (0,0), Generator (15,15), Kennel (0,15).
