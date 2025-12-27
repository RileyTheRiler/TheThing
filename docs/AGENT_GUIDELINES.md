# Recommendations for Future Agents

This document defines the technical standards for "The Thing" project. All agents (and humans) must review these guidelines before implementing new features or refactoring modules.

## 1. Global Standards (The "Architect" Layer)
- **Single Source of Truth**: Core game math (rolls, infection probability, thermal decay) MUST reside in `src/core/resolution.py`. Do NOT duplicate this logic in other modules.
- **Unified Enums**: Always use the `Attribute` and `Skill` enums from `src/core/resolution.py`.
    - **Attributes**: `Prowess`, `Logic`, `Influence`, `Resolve`.
    - **Skills**: `Melee`, `Firearms`, `Pilot`, `Repair`, `Medicine`, `Persuasion`, `Empathy`, `Observation`, etc.

## 2. Decoupling & Communication
- **Event-Driven Architecture**: Use the `EventBus` from `src/core/event_system.py` to decouple systems. 
    - **BAD**: `engine.py` explicitly calling `WeatherSystem.tick()`.
    - **GOOD**: `WeatherSystem` subscribing to `EventType.TURN_ADVANCE`.
- **The "Reporting" Pattern**: Systems should NOT return strings for the UI/HUD from their update methods. Instead, emit a `GAME_EVENT` with a `message` payload. This allows the Terminal Designer or HUD to handle display logic independently.

## 3. Environmental Modifiers
- **Global Context**: Systems like `RoomStateManager` should be used to provide modifiers to core resolution.
- **Implementation**: When performing a `roll_check`, the system should query the `RoomStateManager` for local conditions (e.g., `DARK`, `FROZEN`) and adjust the dice pool accordingly based on `src/core/resolution.py` standards.

## 4. NPC Behavior & Role Habits
- **Data-Driven Habits**: NPC "Role Habits" (preferred rooms, schedules) MUST reside in `data/characters.json`. Do NOT hardcode room names in system classes.
- **Information Hiding**: State variables describing an NPC's hidden nature (e.g., `is_infected`, `mask_integrity`) MUST be kept separate from their visible "Public Profile" to prevent accidental player metagaming.

## 5. Data & Persistence
- **Character Data**: The primary source of truth for character profiles is `config/characters.json`.
- **Serialization**: All game objects (`CrewMember`, `Item`, `StationMap`) MUST implement `to_dict()` and `from_dict(cls, data)` methods for JSON-based saving/loading. Avoid `pickle`.
- **RNG Determinism**: Always use the `RandomnessEngine` from `src/systems/architect.py`. Use the instance passed via `GameState.rng` to ensure save/load consistency.

## 4. Testing & Verification
- **V-Scripts**: All manual verification scripts must be placed in `tests/v-scripts/`.
- **Imports**: Verification scripts must include the project root in `sys.path` to ensure absolute imports from `src` work correctly.

## 5. Coding Style
- **Type Hinting**: Use Python type hints where possible (e.g., `def on_event(event: GameEvent):`).
- **Defensive Keys**: When accessing serializable data or trust matrices, use `dict.get(key)` or check for key existence to prevent crashes during partial game loads.
- **Import Paths**: ALWAYS use relative imports from the `src/` directory. NEVER use `src.` prefix in import statements.
    - **CORRECT**: `from systems.missionary import MissionarySystem`
    - **CORRECT**: `from core.resolution import Attribute, Skill`
    - **INCORRECT**: `from src.systems.missionary import MissionarySystem`
    - **INCORRECT**: `from src.core.resolution import Attribute, Skill`
