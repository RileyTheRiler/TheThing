// The Thing: Browser Interface JavaScript

let sessionId = 'session_' + Date.now();
let gameState = null;
let commandHistory = [];
let historyIndex = -1;

// Common commands for autocomplete
const COMMON_COMMANDS = [
    'STATUS', 'INVENTORY', 'INV', 'TALK', 'HELP', 'LOOK', 'TAKE', 'DROP',
    'GO', 'NORTH', 'SOUTH', 'EAST', 'WEST', 'USE', 'EXAMINE', 'SEARCH',
    'WAIT', 'REST', 'HIDE', 'SNEAK', 'TEST', 'TAG', 'ACCUSE'
];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
});

function setupEventListeners() {
    const commandInput = document.getElementById('command-input');
    if (commandInput) {
        commandInput.addEventListener('keydown', handleCommandInput);
        commandInput.addEventListener('input', updateAutoComplete);
    }
}

function handleCommandInput(event) {
    if (event.key === 'Enter') {
        const input = event.target.value.trim();
        if (input) {
            sendCommand(input);
            commandHistory.push(input);
            historyIndex = commandHistory.length;
            event.target.value = '';
        }
    } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (historyIndex > 0) {
            historyIndex--;
            event.target.value = commandHistory[historyIndex];
        }
    } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (historyIndex < commandHistory.length - 1) {
            historyIndex++;
            event.target.value = commandHistory[historyIndex];
        } else {
            historyIndex = commandHistory.length;
            event.target.value = '';
        }
    }
}

function showDifficultySelect() {
    document.querySelector('.menu').style.display = 'none';
    document.getElementById('difficulty-select').classList.remove('hidden');
}

function hideDifficultySelect() {
    document.querySelector('.menu').style.display = 'block';
    document.getElementById('difficulty-select').classList.add('hidden');
}

function startGame(difficulty) {
    addOutput('Initializing system...');
    addOutput(`Difficulty: ${difficulty}`);
    addOutput('Starting new game...');

    fetch('/api/new_game', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            difficulty: difficulty,
            session_id: sessionId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            gameState = data.game_state;
            switchToGameScreen();
            updateGameDisplay(gameState);
            addOutput('System initialized. Welcome to Outpost 31.');
            addOutput('Type HELP for available commands.');
        } else {
            addOutput('Error starting game: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        addOutput('Network error: ' + error.message);
    });
}

function switchToGameScreen() {
    document.getElementById('start-screen').classList.remove('active');
    document.getElementById('game-screen').classList.add('active');
    document.getElementById('command-input').focus();
}

function sendCommand(command) {
    addOutput('> ' + command, 'input');

    fetch('/api/command', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            session_id: sessionId,
            command: command
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (data.message) {
                addOutput(data.message);
            }
            gameState = data.game_state;
            updateGameDisplay(gameState);

            // Check for game over
            if (gameState.game_over) {
                showGameOver(gameState.won, gameState.game_over_message);
            }
        } else {
            addOutput('Error: ' + (data.error || 'Command failed'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        addOutput('Network error: ' + error.message);
    });
}

function sendQuickCommand(command) {
    const input = document.getElementById('command-input');
    input.value = command;
    sendCommand(command);
    input.value = '';
    updateAutoComplete();
}

// Autocomplete system
function getCommandSuggestion(input) {
    if (!input || input.length === 0) return null;
    
    const upperInput = input.toUpperCase();
    const match = COMMON_COMMANDS.find(cmd => 
        cmd.startsWith(upperInput) && cmd !== upperInput
    );
    
    return match || null;
}

function updateAutoComplete() {
    const input = document.getElementById('command-input');
    const hint = document.getElementById('autocomplete-hint');
    
    if (!input || !hint) return;
    
    const suggestion = getCommandSuggestion(input.value);
    
    if (suggestion && input.value.length > 0) {
        hint.textContent = suggestion;
        hint.style.paddingLeft = (input.value.length * 9.6) + 'px'; // Approximate char width
    } else {
        hint.textContent = '';
    }
}

// Trust bar rendering
function renderTrustBar(trustValue) {
    const maxBars = 10;
    const filledBars = Math.round((trustValue / 100) * maxBars);
    const emptyBars = maxBars - filledBars;
    
    const filled = '|'.repeat(filledBars);
    const empty = '.'.repeat(emptyBars);
    
    let cssClass = 'trust-high';
    if (trustValue < 30) {
        cssClass = 'trust-low';
    } else if (trustValue < 60) {
        cssClass = 'trust-medium';
    }
    
    return `<span class="trust-bar ${cssClass}">[${filled}${empty}] ${trustValue.toFixed(0)}%</span>`;
}

// Room danger detection
function getRoomDangerLevel(roomState) {
    if (!roomState) return 'safe';
    
    const description = (roomState.room_description || '').toUpperCase();
    const icons = (roomState.room_icons || '').toUpperCase();
    
    if (description.includes('BLOODY') || description.includes('UNSAFE') || 
        icons.includes('BLOODY') || icons.includes('DANGER')) {
        return 'danger';
    }
    
    if (description.includes('DARK') || description.includes('COLD') ||
        icons.includes('WARNING')) {
        return 'warning';
    }
    
    return 'safe';
}

// Flavor text for empty rooms
function getDefaultRoomFlavor(location) {
    const flavors = {
        'Generator Room': 'The diesel generator hums steadily. The air is thick with fumes.',
        'Radio Room': 'Static crackles from the equipment. The smell of ozone lingers.',
        'Kitchen': 'The air is stale. A faint smell of coffee and canned food.',
        'Rec Room': 'Silence hangs heavy. Magazines scattered on worn furniture.',
        'Lab': 'Sterile and cold. The scent of chemicals and antiseptic.',
        'Storage': 'Musty air. Stacks of supplies cast long shadows.',
        'Kennel': 'The smell of wet fur and fear still lingers here.',
        'Hallway': 'Fluorescent lights flicker overhead. Your footsteps echo.',
        'default': 'The air is cold and still. Nothing seems out of place.'
    };
    
    return flavors[location] || flavors['default'];
}

// Enhance map display
function enhanceMapDisplay(mapString) {
    if (!mapString) return 'Map unavailable';
    
    // Wrap player marker in span for pulsing effect
    let enhanced = mapString.replace(/@/g, '<span class="player-marker">@</span>');
    
    return enhanced;
}

function updateQuickActions(actions) {
    const container = document.getElementById('context-actions');
    if (!container) return;

    // Clear existing buttons
    container.innerHTML = '';

    // Style mapping for different action types
    const styleClasses = {
        'info': 'quick-btn-info',
        'social': 'quick-btn-social',
        'forensic': 'quick-btn-forensic',
        'item': 'quick-btn-item',
        'danger': 'quick-btn-danger'
    };

    // Add new buttons based on context
    actions.forEach(action => {
        const button = document.createElement('button');
        const styleClass = styleClasses[action.style] || 'quick-btn';
        button.className = `quick-btn ${styleClass}`;
        button.textContent = action.label;
        button.onclick = () => sendQuickCommand(action.command);
        container.appendChild(button);
    });
}

function updateGameDisplay(state) {
    if (!state) return;

    // Update status bar
    document.getElementById('turn-counter').textContent = state.turn;
    document.getElementById('game-time').textContent = state.time;
    document.getElementById('temperature').textContent = state.temperature + '°C';
    document.getElementById('power-status').textContent = state.power_on ? 'ON' : 'OFF';
    document.getElementById('location').textContent = state.location;
    
    // Update wind speed if available
    const windSpeed = state.wind_speed || 0;
    document.getElementById('wind-speed').textContent = windSpeed + ' mph';
    
    // Update fuel bar
    const fuelPercent = state.fuel_percent || 100;
    const fuelBars = Math.round((fuelPercent / 100) * 8);
    const fuelDisplay = '█'.repeat(fuelBars) + '░'.repeat(8 - fuelBars);
    const fuelBar = document.getElementById('fuel-bar');
    fuelBar.textContent = fuelDisplay;
    fuelBar.className = 'fuel-bar';
    if (fuelPercent < 25) {
        fuelBar.classList.add('low');
    } else if (fuelPercent < 50) {
        fuelBar.classList.add('medium');
    }

    // Update context-aware quick actions
    if (state.quick_actions) {
        updateQuickActions(state.quick_actions);
    }

    // Update room info
    document.getElementById('room-description').textContent = state.room_description || '';
    document.getElementById('room-icons').textContent = state.room_icons || '';
    
    // Update room flavor text
    const flavorDiv = document.getElementById('room-flavor');
    if (!state.room_description || state.room_description.trim() === '') {
        flavorDiv.textContent = getDefaultRoomFlavor(state.location);
    } else {
        flavorDiv.textContent = '';
    }

    // Update map with enhancements
    const mapDisplay = document.getElementById('game-map');
    if (state.map) {
        mapDisplay.innerHTML = enhanceMapDisplay(state.map);
    } else {
        mapDisplay.textContent = 'Map unavailable';
    }

    // Update room items with shortcuts
    const itemsContainer = document.getElementById('room-items');
    if (state.items && state.items.length > 0) {
        itemsContainer.innerHTML = state.items.map((item, index) => {
            const shortcut = String.fromCharCode(65 + index); // A, B, C...
            return `<div><span class="item-shortcut">[${shortcut}]</span> ${item.name}</div>`;
        }).join('');
    } else {
        itemsContainer.textContent = 'None';
    }

    // Update crew status with proximity sorting and trust bars
    const crewContainer = document.getElementById('crew-status');
    if (state.crew && state.crew.length > 0) {
        // Sort crew: same room first, then alphabetically
        const sortedCrew = [...state.crew].sort((a, b) => {
            const aInRoom = a.location === state.location;
            const bInRoom = b.location === state.location;
            
            if (aInRoom && !bInRoom) return -1;
            if (!aInRoom && bInRoom) return 1;
            return a.name.localeCompare(b.name);
        });
        
        crewContainer.innerHTML = sortedCrew.map(member => {
            const isNearby = member.location === state.location;
            const proximityClass = isNearby ? 'crew-nearby' : 'crew-distant';
            const statusClass = member.is_alive ? '' : 'danger';
            const statusText = member.is_alive ? 'ALIVE' : 'DEAD';
            const trustBar = renderTrustBar(member.trust);
            
            return `<div class="crew-member ${proximityClass} ${statusClass}">
                ${member.name} (${member.role}) - ${member.location}<br>
                HP: ${member.health} | ${statusText}<br>
                Trust: ${trustBar}
            </div>`;
        }).join('');
    } else {
        crewContainer.textContent = 'No crew data';
    }

    // Update inventory
    const inventoryContainer = document.getElementById('player-inventory');
    if (state.inventory && state.inventory.length > 0) {
        inventoryContainer.innerHTML = state.inventory.map(item =>
            `<div>• ${item.name}: ${item.description}</div>`
        ).join('');
    } else {
        inventoryContainer.textContent = 'Empty';
    }

    // Update sabotage status if any
    if (state.sabotage_status) {
        addOutput('[WARNING] ' + state.sabotage_status, 'warning');
    }
}

function addOutput(text, type = 'normal') {
    const output = document.getElementById('game-output');
    const line = document.createElement('div');
    line.className = 'output-line';

    if (type === 'input') {
        line.style.color = '#00ff41';
        line.style.fontWeight = 'bold';
    } else if (type === 'warning') {
        line.style.color = '#ffaa00';
    } else if (type === 'danger') {
        line.style.color = '#ff3333';
    }

    line.textContent = text;
    output.appendChild(line);

    // Auto-scroll to bottom
    output.scrollTop = output.scrollHeight;
}

function showGameOver(won, message) {
    setTimeout(() => {
        const title = document.getElementById('gameover-title');
        const messageDiv = document.getElementById('gameover-message');

        if (won) {
            title.textContent = '*** VICTORY ***';
            title.style.color = '#00ff41';
            title.style.textShadow = '0 0 10px #00ff41';
        } else {
            title.textContent = '*** GAME OVER ***';
            title.style.color = '#ff3333';
            title.style.textShadow = '0 0 10px #ff3333';
        }

        messageDiv.textContent = message;

        document.getElementById('game-screen').classList.remove('active');
        document.getElementById('gameover-screen').classList.add('active');
    }, 1000);
}

// Periodically refresh game state
function startGameStateRefresh() {
    setInterval(() => {
        if (gameState && !gameState.game_over) {
            fetch(`/api/game_state/${sessionId}`)
                .then(response => response.json())
                .then(data => {
                    if (data && !data.error) {
                        gameState = data;
                        updateGameDisplay(gameState);

                        if (gameState.game_over) {
                            showGameOver(gameState.won, gameState.game_over_message);
                        }
                    }
                })
                .catch(error => {
                    console.error('State refresh error:', error);
                });
        }
    }, 5000); // Refresh every 5 seconds
}

// Start refresh when game begins
setTimeout(startGameStateRefresh, 1000);
