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

## 15. Win/Lose Conditions

### Victory
- All infected crew eliminated
- Player is alive

### Defeat
- Player killed
- Player infected and revealed

### Escape (Future)
- Radio operational AND helicopter operational
- Reach Kennel helipad
