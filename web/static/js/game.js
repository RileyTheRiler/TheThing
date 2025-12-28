// The Thing: Browser Interface JavaScript

let sessionId = 'session_' + Date.now();
let gameState = null;
let commandHistory = [];
let historyIndex = -1;
let crewFilter = 'nearby'; // 'nearby', 'alive', or 'all'
let currentEventMode = null; // 'blood-test', 'interrogation', 'combat', or null

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

    // Setup crew filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            crewFilter = this.dataset.filter;
            if (gameState) {
                updateCrewDisplay(gameState);
            }
        });
    });

    // Setup keyboard shortcuts for quick actions
    document.addEventListener('keydown', handleGlobalKeydown);
}

function handleGlobalKeydown(event) {
    // Don't trigger shortcuts when typing in command input
    const commandInput = document.getElementById('command-input');
    if (document.activeElement === commandInput) return;

    // Number keys 1-9 for quick action buttons
    if (event.key >= '1' && event.key <= '9') {
        const index = parseInt(event.key) - 1;
        const buttons = document.querySelectorAll('#context-actions .quick-btn');
        if (buttons[index]) {
            event.preventDefault();
            buttons[index].classList.add('shortcut-active');
            buttons[index].click();
            setTimeout(() => buttons[index].classList.remove('shortcut-active'), 150);
        }
    }

    // Letter shortcuts when not in input
    const letterShortcuts = {
        's': 'STATUS',
        'i': 'INVENTORY',
        'h': 'HELP',
        'l': 'LOOK',
        't': 'TALK',
        'w': 'WAIT'
    };

    const lowerKey = event.key.toLowerCase();
    if (letterShortcuts[lowerKey] && !event.ctrlKey && !event.altKey && !event.metaKey) {
        event.preventDefault();
        sendQuickCommand(letterShortcuts[lowerKey]);
    }

    // Focus command input on any other letter
    if (/^[a-z]$/i.test(event.key) && !letterShortcuts[lowerKey] &&
        !event.ctrlKey && !event.altKey && !event.metaKey) {
        commandInput.focus();
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

    // Add new buttons based on context with keyboard shortcuts
    actions.forEach((action, index) => {
        const button = document.createElement('button');
        const styleClass = styleClasses[action.style] || '';
        button.className = `quick-btn ${styleClass}`.trim();

        // Add keyboard shortcut hint (1-9)
        if (index < 9) {
            const shortcutSpan = document.createElement('span');
            shortcutSpan.className = 'shortcut-hint';
            shortcutSpan.textContent = (index + 1).toString();
            button.appendChild(shortcutSpan);
        }

        button.appendChild(document.createTextNode(action.label));
        button.onclick = () => sendQuickCommand(action.command);
        button.title = `${action.label} (Press ${index + 1})`;
        container.appendChild(button);
    });
}

// Update map legend with visible items and symbols
function updateMapLegend(state) {
    const legendContainer = document.getElementById('map-legend');
    if (!legendContainer) return;

    let legendItems = [];

    // Always show player marker
    legendItems.push('<span class="legend-item"><span class="legend-symbol player">@</span>=You</span>');

    // Add visible items
    if (state.items && state.items.length > 0) {
        const itemNames = state.items.map(item => item.name).join(', ');
        legendItems.push(`<span class="legend-item"><span class="legend-symbol item">*</span>=${itemNames}</span>`);
    }

    // Add nearby crew indicator if any crew in room
    if (state.crew) {
        const nearbyCrew = state.crew.filter(c => c.location === state.location && c.is_alive);
        if (nearbyCrew.length > 0) {
            const crewNames = nearbyCrew.map(c => c.name).join(', ');
            legendItems.push(`<span class="legend-item"><span class="legend-symbol crew">☺</span>=${crewNames}</span>`);
        }
    }

    legendContainer.innerHTML = legendItems.join('');
}

// Update event highlighting based on game state
function updateEventHighlight(state) {
    const outputContainer = document.getElementById('output-container');
    const eventBanner = document.getElementById('event-banner');
    if (!outputContainer || !eventBanner) return;

    // Remove all event classes
    outputContainer.classList.remove('event-blood-test', 'event-interrogation', 'event-combat');
    eventBanner.classList.remove('blood-test', 'interrogation', 'combat');
    eventBanner.classList.add('hidden');

    // Detect event mode from game state
    let newEventMode = null;

    if (state.blood_test_active) {
        newEventMode = 'blood-test';
        eventBanner.textContent = '⚠ BLOOD TEST IN PROGRESS ⚠';
        eventBanner.classList.remove('hidden');
        eventBanner.classList.add('blood-test');
        outputContainer.classList.add('event-blood-test');
    } else if (state.interrogation_active) {
        newEventMode = 'interrogation';
        eventBanner.textContent = '◉ INTERROGATION MODE ◉';
        eventBanner.classList.remove('hidden');
        eventBanner.classList.add('interrogation');
        outputContainer.classList.add('event-interrogation');
    } else if (state.combat_active) {
        newEventMode = 'combat';
        eventBanner.textContent = '⚔ COMBAT ACTIVE ⚔';
        eventBanner.classList.remove('hidden');
        eventBanner.classList.add('combat');
        outputContainer.classList.add('event-combat');
    }

    currentEventMode = newEventMode;
}

// Update crew display with filtering
function updateCrewDisplay(state) {
    const crewContainer = document.getElementById('crew-status');
    if (!crewContainer || !state.crew) {
        if (crewContainer) crewContainer.textContent = 'No crew data';
        return;
    }

    // Filter crew based on current filter
    let filteredCrew = state.crew;

    if (crewFilter === 'nearby') {
        filteredCrew = state.crew.filter(member =>
            member.location === state.location
        );
    } else if (crewFilter === 'alive') {
        filteredCrew = state.crew.filter(member => member.is_alive);
    }
    // 'all' shows everyone

    // Sort crew: same room first, then alive, then alphabetically
    const sortedCrew = [...filteredCrew].sort((a, b) => {
        const aInRoom = a.location === state.location;
        const bInRoom = b.location === state.location;

        if (aInRoom && !bInRoom) return -1;
        if (!aInRoom && bInRoom) return 1;

        // Then by alive status
        if (a.is_alive && !b.is_alive) return -1;
        if (!a.is_alive && b.is_alive) return 1;

        return a.name.localeCompare(b.name);
    });

    if (sortedCrew.length === 0) {
        crewContainer.innerHTML = `<div class="crew-empty">No crew ${crewFilter === 'nearby' ? 'in this room' : 'matching filter'}</div>`;
        return;
    }

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

    // Update map legend
    updateMapLegend(state);

    // Update event highlighting
    updateEventHighlight(state);

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

    // Update crew status with filtering
    updateCrewDisplay(state);

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
