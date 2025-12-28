# The Thing: Browser Interface

The game now supports a browser-based interface running on localhost!

## Quick Start

### Windows
**Easiest Method:**
1. Double-click `start_game.bat`
2. Your browser will automatically open to `http://localhost:5000`

**Alternative:**
1. Double-click `start_web_server.bat`
2. Manually navigate to `http://localhost:5000`

### Linux/Mac
1. Run `./start_web_server.sh` (or `python3 start_web_server.py`)
2. Open your browser to `http://localhost:5000`

> **Note:** `start_game.bat` now launches the browser interface by default. If you prefer the original terminal version, use `start_game_terminal.bat` instead.

## Features

- **Full Browser Interface**: Play the game in your web browser with a retro terminal aesthetic
- **Real-time Updates**: Game state updates dynamically without page refreshes
- **Visual Map**: ASCII map displayed in the browser
- **Quick Commands**: Buttons for common commands (STATUS, INVENTORY, TALK, HELP)
- **Command History**: Use arrow keys to navigate through previous commands
- **Crew Status Panel**: Live view of all crew members and their status
- **Inventory Panel**: Always-visible inventory display

## Requirements

The web interface requires these Python packages:
- Flask
- flask-socketio
- flask-cors
- python-socketio
- Werkzeug

These will be automatically installed when you run the launcher for the first time.

## Manual Installation

If you prefer to install dependencies manually:

```bash
pip install -r requirements_web.txt
```

Then start the server:

```bash
python3 server.py
```

## Game Controls

- Type commands in the command input box and press Enter
- Use arrow keys (↑/↓) to navigate command history
- Click quick command buttons for common actions
- All terminal commands work the same as the original terminal version

## Available Commands

Type `HELP` in-game for a full list of commands, including:

- `MOVE <NORTH/SOUTH/EAST/WEST>` - Move around the station
- `LOOK <NAME>` - Observe crew members
- `TALK` - Hear dialogue
- `TEST <NAME>` - Perform blood tests
- `ATTACK <NAME>` - Attack crew members
- `INV` - Check inventory
- `STATUS` - View all crew status
- And many more!

## Technical Details

### Architecture

- **Backend**: Flask web server with SocketIO for real-time communication
- **Frontend**: HTML/CSS/JavaScript with retro terminal styling
- **API**: RESTful API endpoints for game state and commands

### File Structure

```
TheThing/
├── server.py                 # Flask backend server
├── start_web_server.py       # Python launcher
├── start_web_server.bat      # Windows launcher
├── start_web_server.sh       # Linux/Mac launcher
├── requirements_web.txt      # Web dependencies
└── web/
    ├── templates/
    │   └── index.html        # Main game page
    └── static/
        ├── css/
        │   └── style.css     # Game styling
        └── js/
            └── game.js       # Game logic
```

## Troubleshooting

### Port Already in Use
If port 5000 is already in use, edit `server.py` and change the port number in the last line:
```python
socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

### Dependencies Not Installing
Manually install dependencies:
```bash
pip install Flask flask-socketio flask-cors python-socketio
```

### Game Not Loading
1. Check that the server started successfully
2. Look for error messages in the terminal
3. Try accessing `http://127.0.0.1:5000` instead of `localhost`
4. Clear your browser cache and refresh

## Original Terminal Version

The original terminal version is still available! Use:
- Windows: `start_game_terminal.bat`
- Linux/Mac: `python3 main.py`

Both versions use the same game engine and save files.

**Note:** The main `start_game.bat` launcher now opens the browser interface by default for the best experience.

## Enjoy!

Trust no one. The Thing is among us.
