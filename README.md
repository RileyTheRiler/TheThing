# The Thing: Antarctic Research Station 31

A text-based survival horror game inspired by John Carpenter's "The Thing" (1982). Navigate paranoia, deception, and alien horror in an isolated Antarctic research station.

## 🎮 Quick Start

### Terminal Version (Recommended)
```bash
python main.py
```

### Browser Version
```bash
start_game.bat          # Windows
./start_web_server.sh   # Linux/Mac
```

## 📋 Requirements

- Python 3.8+
- For browser version: Flask, SocketIO (auto-installed)

## 🎯 Game Overview

You are R.J. MacReady, helicopter pilot at U.S. Outpost 31. An alien organism - "The Thing" - has infiltrated the base, perfectly imitating its victims. 

**Your Mission:**
- Identify infected crew members
- Use blood tests and observation
- Survive and remain human
- Eliminate all Things

## 🕹️ Key Features

### 8 Integrated AI Systems
1. **The Architect** - Core mechanics, dice resolution, time
2. **Social Psychologist** - Trust dynamics, lynch mobs
3. **The Missionary** - Thing AI behavior and infection
4. **Forensic Analyst** - Blood tests, evidence tracking
5. **Terminal Designer** - Authentic 1982 CRT aesthetics
6. **Dungeon Master** - Weather, sabotage, environmental hazards
7. **Psychology System** - Stress, panic, mental state
8. **AI System** - NPC pathfinding and behavior

### Gameplay Systems
- **Blood Test Mini-Game** - Heat copper wire, test samples
- **Trust Matrix** - Dynamic crew relationships
- **Stealth & Detection** - Hide, sneak, avoid Things
- **Combat System** - Tactical encounters with cover
- **Crafting** - Combine items for survival tools
- **Interrogation** - Question crew for information
- **Schedule-Based AI** - NPCs follow daily routines

## 🎲 Commands

Type `HELP` in-game for full reference. Essential commands:

```
MOVE <DIR>           Navigate (N/S/E/W)
LOOK <NAME>          Observe for tells
TEST <NAME>          Start blood test
HEAT                 Heat copper wire
APPLY                Apply to blood sample
TAG <NAME> <NOTE>    Record evidence
INTERROGATE <NAME>   Question crew
ATTACK <NAME>        Combat
HIDE                 Stealth mode
CRAFT <RECIPE>       Create items
```

## 🧪 Detection Methods

### Biological Tells
- Missing breath vapor in cold
- Strange eye movements
- Unusual skin texture
- Out-of-place behavior

### Blood Test
1. Get SCALPEL and COPPER WIRE
2. `TEST <NAME>` to draw blood
3. `HEAT` repeatedly to heat wire
4. `APPLY` to test - infected blood reacts violently!

## 🏗️ Project Structure

```
The Thing/
├── main.py                 # Terminal launcher
├── src/
│   ├── game_loop.py       # Main game loop
│   ├── engine.py          # Core game state
│   ├── systems/           # All 8 agent systems
│   ├── core/              # Resolution, events
│   ├── ui/                # Renderer, CRT, parser
│   └── audio/             # Audio manager
├── config/
│   └── characters.json    # Crew profiles & schedules
├── data/                  # Items, rooms
├── web/                   # Browser interface
└── tests/                 # Test suite
```

## 🧪 Testing

Run the test suite:
```bash
python -m pytest tests/
```

Verify individual systems:
```bash
python verify_forensics.py
python verify_ai.py
python verify_social_psych.py
```

## 🎨 Accessibility

- Multiple color palettes (amber, green, colorblind-friendly)
- Adjustable text speed
- High contrast mode
- Command history (arrow keys)
- Natural language parsing

## 📖 Documentation

- `docs/` - Detailed system documentation
- `README_WEB.md` - Browser interface guide
- Type `HELP <CATEGORY>` in-game for command reference

## 🐛 Troubleshooting

### Windows Encoding Issues
Fixed in latest version - uses ASCII-safe characters.

### Import Errors
Ensure you run from project root: `python main.py`

### Port Conflicts (Browser)
Edit `server.py` to change port from 5000 to another.

## 🎯 Win Conditions

- Eliminate all infected crew members
- Remain human and alive
- Maintain station integrity

## ❌ Lose Conditions

- You are killed
- You become infected and revealed
- All humans are eliminated

## 🏆 Credits

Inspired by John Carpenter's "The Thing" (1982)
Based on the short story "Who Goes There?" by John W. Campbell Jr.

## 📜 License

This is a fan project for educational purposes.

---

**Trust no one. The Thing is among us.**
