# The Truth Log

This document tracks the canonical rules for the game's simulation layer. All mechanics are deterministic given the same RNG seed.

---

## 1. Infection Mechanics (`systems/infection.py`)

### Communion (Transmission)
- **Condition**: Two or more characters at the same location
- **Source**: At least one character must be `is_infected=True`
- **Chance**:
  - **Light**: 10% per turn (base)
  - **Darkness**: 50% per turn (power off)
- **Formula**: `P(Infection) = BaseChance * (1.0 - MaskIntegrity/100) * (1 + Paranoia/100)`

### Secret Assimilation (`systems/missionary.py`)
- **Condition**: Infected NPC alone with single human target
- **Effect**: Target becomes infected, mask reset to 100%
- **Searchlight Harvest**: Reduces agent's slip_chance by 50%

---

## 2. Mask Integrity (`systems/missionary.py`)

The "Mask" represents how well an infected creature maintains its human disguise.

### Decay
- **Base Decay**: 2.0 points per turn
- **Cold Stress** (temp < -50C): Decay x1.5
- **High Paranoia** (>70): Decay x1.5 (stress multiplier)
- **Role Dissonance**: -5 points if NPC is outside their normal habitat

### Role Habitats
| Role | Normal Locations |
|------|------------------|
| Pilot | Rec Room, Corridor |
| Mechanic | Rec Room, Generator |
| Biologist | Infirmary, Rec Room |
| Doctor | Infirmary, Rec Room |
| Dog Handler | Kennel, Rec Room |
| Cook | Rec Room |

### Reveal Triggers
- **Mask Failure**: Integrity drops to 0
- **Critical Injury**: Health drops to 1
- **Blood Test**: Positive test result

---

## 3. Biological Tells

### Visual Tells (`entities/crew_member.py`)
Visible when observing infected NPCs with low mask integrity:

- Sweating profusely despite the cold
- Staring unblinkingly for too long
- Slight, unnatural tic in the left eye
- Fingers twitching rhythmically
- Skin looking waxy and artificial

**Detection Chance**: `(80 - MaskIntegrity) / 80` if mask < 80%

### Vapor Check
- **Condition**: Temperature < 0C
- **Human**: Always emits `[VAPOR]`
- **Thing**: Emits `[VAPOR]` 80% of the time; 20% chance of biological slip (missing vapor)
- **Slip Chance**: `(1.0 - MaskIntegrity/100) * 0.5`

---

## 4. Trust System (`systems/social.py`)

### Trust Matrix
- **Default Trust**: 50 (neutral)
- **Range**: 0-100

### Initial Biases
| Observer | Subject | Trust |
|----------|---------|-------|
| Childs | Garry | 30 |
| Palmer | Garry | 25 |
| Scientists (Blair, Copper, Fuchs) | Each other | 75 |
| Everyone | Loners (MacReady, Clark) | -10 modifier |

### Trust Modifiers
- **Evidence Tagged**: -10 to tagged character
- **Failed Accusation**: -20 from accused, -5 from all voters

### Lynch Mob
- **Threshold**: Average trust falls below 20
- **Effect**: Crew drags target to Rec Room (7,7)

---

## 5. Psychology System (`systems/psychology.py`)

### Stress
- **Max Stress**: 10
- **Environmental Gain**: +1 per -20C below zero

### Panic
- **Threshold**: `RESOLVE attribute + 2`
- **Trigger**: Stress exceeds threshold
- **Roll**: 1d6 vs (Stress - Threshold)

### Panic Effects
1. Drops primary item in terror
2. Freezes, unable to act next turn
3. Screams, alerting nearby characters
4. Flees to random room
5. Lashes out at random crew member

---

## 6. Combat System (`systems/combat.py`)

### Initiative
- **Formula**: `PROWESS + 1d6 + modifiers`
- **Thing Bonus**: +2 (alien reflexes)
- **Injury Penalty**: -1 per missing health

### Attack Resolution
- **Attack Pool**: `PROWESS + WeaponSkill`
- **Defense Pool**: `PROWESS + Melee + CoverBonus`
- **Hit**: Attack successes > Defense successes
- **Damage**: `WeaponDamage + NetHits`

### Cover Types
| Type | Defense Bonus | Notes |
|------|---------------|-------|
| None | +0 | Default |
| Light | +1 | Furniture, doors |
| Heavy | +2 | Walls, machinery |
| Full | +3 | Cannot attack |

### Retreat
- **Roll**: PROWESS vs average opponent PROWESS
- **Failure**: All opponents get free attacks (no cover)

---

## 7. Barricade System (`systems/room_state.py`)

### Barricade Strength
- **Max Strength**: 3
- **Reinforcement**: +1 per BARRICADE action

### Breaking Barricades
- **Roll**: `PROWESS + MELEE` (Things get +3 bonus)
- **Damage**: `1 + SuccessCount` per successful roll
- **Effect at 0**: Barricade destroyed, entry allowed

### Behavior
- NPCs respect barricades (won't enter)
- Revealed Things actively break barricades when hunting

---

## 8. Interrogation System (`systems/interrogation.py`)

### Topics
- WHEREABOUTS: Where were you?
- ALIBI: Who can vouch for you?
- SUSPICION: Who do you suspect?
- BEHAVIOR: Why did you do X?
- KNOWLEDGE: What do you know?

### Response Types
| Type | Trust Change |
|------|--------------|
| Honest | +2 |
| Nervous | 0 |
| Evasive | -3 |
| Defensive | -5 |
| Accusatory | -10 |

### Tell Detection
- **Roll**: `INFLUENCE + EMPATHY`
- **Success**: May notice behavioral tells
- **Infected Detection Chance**: 40% + (10% per prior interrogation)

---

## 9. Weather System (`systems/weather.py`)

### Storm Intensity
- **Range**: 0-100
- **Variance**: `(1d6 * 2) - 7` per turn (-5 to +5)

### Visibility Modifiers
| Intensity | Visibility |
|-----------|------------|
| 0-29 | Clear (100%) |
| 30-59 | Reduced (-30%) |
| 60-79 | Poor (-60%) |
| 80-100 | Whiteout (-100%) |

### Wind Chill
- **Formula**: `-1C per 10 intensity`
- **Northeasterly**: Additional -5C

### Nasty Northeasterly
- **Trigger**: 2% chance per turn
- **Duration**: 5 turns
- **Effect**: +50 storm intensity, wind from northeast

---

## 10. Sabotage Events (`systems/sabotage.py`)

### Event Types
| Event | Effect | Reversible |
|-------|--------|------------|
| Power Outage | Lights out, rooms go DARK | Yes (Generator) |
| Radio Smashing | Cannot call for help | No |
| Chopper Destruction | Cannot escape by air | No |
| Blood Sabotage | Blood bank destroyed, no serum tests | No |

### Power Restoration
- Requires visiting Generator room
- Cooldown: Duration + 10 turns before can be sabotaged again

---

## 11. Blood Test (`systems/forensics.py`)

### Requirements
- Scalpel (to draw blood)
- Copper Wire (to heat)
- Target must be present

### Procedure
1. START_TEST: Draw blood sample
2. HEAT: Increase wire temperature (+20-30C per action)
3. APPLY: Touch wire to blood when temp >= 90C

### Results
- **Human**: "Blood HISSES and smokes. Just a normal burn reaction."
- **Infected**: Blood screams, leaps away, or explodes

---

## 12. Room States (`systems/room_state.py`)

### State Types
| State | Effect |
|-------|--------|
| DARK | +40% communion chance, +2 paranoia |
| FROZEN | Health drain, resolve checks required |
| BARRICADED | Blocks entry, creates darkness |
| BLOODY | +5 paranoia modifier |

### Initial States
- Kennel: FROZEN

---

## 13. Map Layout

### Grid
- Size: 20x20
- Coordinate System: (x, y) where (0,0) is northwest corner

### Rooms
| Room | Coordinates (x1,y1,x2,y2) |
|------|---------------------------|
| Rec Room | 5,5 to 10,10 |
| Infirmary | 0,0 to 4,4 |
| Generator | 15,15 to 19,19 |
| Kennel | 0,15 to 4,19 |
| Radio Room | 11,0 to 14,4 |
| Storage | 15,0 to 19,4 |
| Lab | 11,11 to 14,14 |
| Sleeping Quarters | 0,6 to 4,10 |
| Mess Hall | 5,0 to 9,4 |

---

## 14. Difficulty Settings (`systems/architect.py`)

| Setting | Easy | Normal | Hard |
|---------|------|--------|------|
| Base Infection | 5% | 10% | 15% |
| Darkness Infection | 30% | 50% | 70% |
| Mask Decay Rate | 1 | 2 | 3 |
| Starting Paranoia | 0 | 0 | 20 |
| Initial Infected | 1 | 1-2 | 2-3 |

---

## 15. Alternative Endings (`systems/endgame.py`)

The EndgameSystem monitors game events and triggers one of six possible endings based on player actions and world state.

### Win Conditions

#### ESCAPE - Helicopter Escape
- **Trigger**: Player successfully repairs helicopter and escapes
- **Requirements**:
  - Helicopter status = "FIXED"
  - Player reaches Kennel helipad
  - Player pilots helicopter successfully
- **Event**: `ESCAPE_SUCCESS` → `ENDING_REPORT`
- **Message**: "You pilot the chopper through the storm, leaving the nightmare of Outpost 31 behind."

#### RESCUE - Radio Rescue
- **Trigger**: Rescue team arrives after SOS signal
- **Requirements**:
  - Player sends SOS signal via radio
  - Survive 20 turns after signal sent
  - Player is alive and human when rescue arrives
- **Events**: `SOS_EMITTED` → countdown → `ENDING_REPORT`
- **Countdown**: 20 turns (tracked via `rescue_turns_remaining`)
- **Message**: "Lights cut through the storm. The rescue team has arrived to extract you."

#### EXTERMINATION - Threat Neutralized
- **Trigger**: All Things eliminated, humans remain
- **Requirements**:
  - No living infected crew members
  - At least one human alive (including player)
  - Player is alive and human
- **Event**: Population check → `ENDING_REPORT`
- **Message**: "All Things have been eliminated. Humanity survives... for now."

#### SOLE_SURVIVOR - Last One Standing
- **Trigger**: Player is the only survivor
- **Requirements**:
  - All crew dead except player
  - Player is alive and human
  - No other living entities
- **Event**: `CREW_DEATH` → population check → `ENDING_REPORT`
- **Message**: "Silence falls over the station. You are the only one left alive. The threat is gone... you hope."

### Loss Conditions

#### CONSUMPTION - Humanity Lost
- **Trigger**: Thing victory condition
- **Scenarios**:
  - All humans dead or infected
  - Player infected and revealed (`is_revealed=True`)
  - No human survivors remain
- **Event**: Population check → `ENDING_REPORT`
- **Message**: "There are no humans left. The Thing has won."

#### DEATH - MacReady Deceased
- **Trigger**: Player character dies
- **Requirements**: Player health ≤ 0
- **Event**: `CREW_DEATH` (player) → `ENDING_REPORT`
- **Message**: "MacReady is dead. The Thing spreads unchecked across the ice."

### Ending System Events

The EndgameSystem subscribes to multiple events:
- `TURN_ADVANCE`: Checks rescue countdown and population status
- `CREW_DEATH`: Checks if player died or triggers population check
- `HELICOPTER_REPAIRED`: Enables escape ending
- `SOS_EMITTED`: Starts rescue countdown
- `ESCAPE_SUCCESS`: Triggers helicopter escape ending

Once an ending is resolved, `EndgameSystem.resolved = True` prevents multiple endings from triggering.

---

## 16. Stealth & Hiding Mechanics (`systems/stealth.py`)

The StealthSystem enables players to avoid detection by infected crew members through posture, environmental conditions, and tactical positioning.

### Stealth Postures (`entities/crew_member.py`)

Characters can adopt different stealth postures that affect detection probability:

| Posture | Stealth Bonus | Description |
|---------|---------------|-------------|
| `STANDING` | +0 | Normal stance, easily detected |
| `CROUCHING` | +1 | Reduced profile, slight stealth bonus |
| `CRAWLING` | +2 | Low profile, moderate stealth bonus |
| `HIDING` | +4 | Concealed in cover, high stealth bonus |
| `HIDDEN` | +4 | Successfully hidden, high stealth bonus |
| `EXPOSED` | -1 | Penalty to stealth, more visible |

### Detection System

Detection uses an **opposed dice pool** contest between observer and subject:

#### Observer Pool (Thing/Infected NPC)
- Base: `Logic + Observation skill`
- **Darkness modifier**: -2 dice
- **Noise bonus**: +1 die per 2 noise levels

#### Subject Pool (Player hiding)
- Base: `Prowess + Stealth skill`
- **Posture bonus**: +0 to +4 dice (see table above)
- **Darkness bonus**: +2 dice
- **Noise penalty**: -1 die per 2 noise levels

#### Detection Probability
```
detection_chance = observer_pool / (observer_pool + subject_pool)
```

Base detection chance: **35%** (configurable via `design_briefs.json`)

### Environmental Modifiers

#### Darkness (`RoomState.DARK`)
- **Subject bonus**: +2 dice to stealth pool
- **Observer penalty**: -2 dice to observation pool
- **Overall effect**: ~60% reduction in detection chance

#### Room States
- **Power off**: All rooms dark except Generator
- **Barricaded rooms**: Stay dark when power off
- **Lighting**: Some rooms may have local light sources

#### Hiding Spots (`station_map.py`)
Rooms can define hiding spots with properties:
- `cover_bonus`: Additional stealth dice
- `blocks_los`: Whether spot blocks line of sight
- Accessed via `station_map.get_hiding_spot(x, y)`

### Stealth Commands

| Command | Effect |
|---------|--------|
| `HIDE` | Set posture to HIDING, seek cover |
| `SNEAK <DIR>` | Move while maintaining CROUCHING posture |
| `CROUCH` | Lower profile without full concealment |
| `STAND` | Return to normal posture |

### Cooldown System
After a stealth encounter (detected or evaded):
- **Cooldown**: 2 turns (configurable)
- Prevents rapid repeated detection checks
- Resets after cooldown expires

### Stealth Events

The StealthSystem emits `STEALTH_REPORT` events with outcomes:
- `evaded`: Player successfully avoided detection
- `detected`: Player spotted by infected NPC
- Payload includes: room, opponent, dice pools, outcome

---

## 17. Crafting System (`systems/crafting.py`)

The CraftingSystem enables players to combine items into improvised tools and weapons using JSON-defined recipes.

### Recipe Structure (`data/crafting.json`)

Each recipe defines:
```json
{
  "id": "makeshift_torch",
  "name": "Makeshift Torch",
  "description": "A wired lantern bundled for stealth sweeps.",
  "category": "tool",
  "ingredients": ["Oil Lantern", "Copper Wire"],
  "craft_time": 1
}
```

### Crafting Time

- **Instant crafting**: `craft_time = 0` (completes immediately)
- **Queued crafting**: `craft_time ≥ 1` (takes N turns to complete)
- Crafting jobs progress on `TURN_ADVANCE` events
- Multiple jobs can be queued simultaneously

### Available Recipes

| Recipe | Ingredients | Time | Category | Effect |
|--------|-------------|------|----------|--------|
| **Makeshift Torch** | Oil Lantern + Copper Wire | 1 turn | Tool | Portable light source |
| **Improvised Spear** | Mop Handle + Copper Wire | 2 turns | Weapon | 2 damage, melee |
| **Heated Wire** | Copper Wire | 0 turns | Tool | Ready for blood test |
| **Molotov Cocktail** | Empty Bottle + Oil Lantern + Rag | 1 turn | Weapon | 4 damage, 1 use |
| **Reinforced Barricade Kit** | Wooden Plank + Rope + Hammer | 2 turns | Tool | +2 barricade strength |
| **Emergency Med Kit** | Bandage + Antiseptic + Rag | 1 turn | Medical | Heal 3 HP, 2 uses |
| **Grappling Hook** | Copper Wire + Rope + Metal Scrap | 3 turns | Tool | Climbing, 5 uses |
| **Lockpick Set** | Copper Wire + Scalpel | 1 turn | Tool | Bypass locks, 3 uses |
| **Signal Flare** | Oil Lantern + Rag + Metal Scrap | 2 turns | Tool | Illumination, 1 use |

### Crafting Workflow

1. **Validation**: Check crafter has required ingredients in inventory
2. **Consumption**: Remove ingredients from inventory
3. **Queue Job**: Add to `active_jobs` list with turn countdown
4. **Progress**: Each `TURN_ADVANCE` decrements `turns_remaining`
5. **Completion**: When `turns_remaining = 0`, create item and emit event
6. **Delivery**: Add crafted item to specified inventory

### Crafting Events

The CraftingSystem emits `CRAFTING_REPORT` events:

| Event Type | When | Payload |
|------------|------|---------|
| `queued` | Recipe started | actor, recipe, turns |
| `completed` | Item finished | actor, recipe, item_name |
| `error` | Invalid recipe or missing ingredients | message, actor |

### Crafting Command

```
CRAFT <recipe_id>
```

Example:
```
CRAFT improvised_spear
> Crafting queued: Improvised Spear (2 turns remaining)

[Turn advances twice...]

> Crafting completed: You finish the Improvised Spear!
```

### Serialization

Active crafting jobs are saved in game state:
```json
{
  "crafting": {
    "active_jobs": [
      {
        "crafter": "MacReady",
        "recipe": "improvised_spear",
        "turns_remaining": 1
      }
    ]
  }
}
```

Jobs resume from saved state when game is loaded.
