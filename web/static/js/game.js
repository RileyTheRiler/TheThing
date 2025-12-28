// The Thing: Browser Interface JavaScript

let sessionId = 'session_' + Date.now();
let gameState = null;
let commandHistory = [];
let historyIndex = -1;
let crewFilter = 'nearby'; // 'nearby', 'alive', or 'all'
let currentEventMode = null; // 'blood-test', 'interrogation', 'combat', or null
let commandModalOpen = false;
let currentCommandCategory = 'all';
let journalFilter = 'all';
let previousCrewState = {}; // Track crew changes for notifications

// Game statistics tracking
let gameStats = {
    roomsVisited: new Set(),
    bloodTests: 0,
    interrogations: 0,
    itemsFound: 0,
    combatEncounters: 0,
    thingsKilled: 0,
    damageTaken: 0,
    infectedFound: 0
};

// Journal entries
let journalEntries = [];

// Command database for the command browser
const COMMAND_DATABASE = [
    // Movement
    { name: 'NORTH', syntax: 'NORTH, N, GO NORTH', desc: 'Move north to an adjacent room', category: 'movement' },
    { name: 'SOUTH', syntax: 'SOUTH, S, GO SOUTH', desc: 'Move south to an adjacent room', category: 'movement' },
    { name: 'EAST', syntax: 'EAST, E, GO EAST', desc: 'Move east to an adjacent room', category: 'movement' },
    { name: 'WEST', syntax: 'WEST, W, GO WEST', desc: 'Move west to an adjacent room', category: 'movement' },
    { name: 'GO', syntax: 'GO <direction>', desc: 'Move in the specified direction', category: 'movement' },

    // Investigation
    { name: 'LOOK', syntax: 'LOOK, LOOK <target>', desc: 'Examine your surroundings or a specific target', category: 'investigation' },
    { name: 'EXAMINE', syntax: 'EXAMINE <target>', desc: 'Closely examine a person, item, or feature', category: 'investigation' },
    { name: 'SEARCH', syntax: 'SEARCH, SEARCH <location>', desc: 'Search the room or a specific area for hidden items', category: 'investigation' },
    { name: 'LISTEN', syntax: 'LISTEN', desc: 'Listen carefully for sounds or movement', category: 'investigation' },

    // Social
    { name: 'TALK', syntax: 'TALK, TALK <person>', desc: 'Talk to nearby crew members', category: 'social' },
    { name: 'INTERROGATE', syntax: 'INTERROGATE <person>', desc: 'Begin an interrogation to gather information', category: 'social' },
    { name: 'ASK', syntax: 'ASK <topic>', desc: 'Ask about whereabouts, alibi, suspicions, behavior, or knowledge', category: 'social' },
    { name: 'ACCUSE', syntax: 'ACCUSE <person>', desc: 'Formally accuse someone of being infected', category: 'social' },
    { name: 'TAG', syntax: 'TAG <person>', desc: 'Mark someone as suspicious for tracking', category: 'social' },

    // Combat
    { name: 'ATTACK', syntax: 'ATTACK <target>', desc: 'Attack a target with your equipped weapon', category: 'combat' },
    { name: 'DEFEND', syntax: 'DEFEND', desc: 'Take a defensive stance to reduce incoming damage', category: 'combat' },
    { name: 'RETREAT', syntax: 'RETREAT <direction>', desc: 'Attempt to flee combat in a direction', category: 'combat' },
    { name: 'HIDE', syntax: 'HIDE', desc: 'Attempt to hide from enemies', category: 'combat' },
    { name: 'SNEAK', syntax: 'SNEAK <direction>', desc: 'Move quietly to avoid detection', category: 'combat' },

    // Items
    { name: 'TAKE', syntax: 'TAKE <item>, GET <item>', desc: 'Pick up an item from the room', category: 'items' },
    { name: 'DROP', syntax: 'DROP <item>', desc: 'Drop an item from your inventory', category: 'items' },
    { name: 'USE', syntax: 'USE <item>, USE <item> ON <target>', desc: 'Use an item, optionally on a target', category: 'items' },
    { name: 'EQUIP', syntax: 'EQUIP <weapon>', desc: 'Equip a weapon for combat', category: 'items' },
    { name: 'CRAFT', syntax: 'CRAFT <item1> <item2>', desc: 'Combine two items to create something new', category: 'items' },
    { name: 'INVENTORY', syntax: 'INVENTORY, INV, I', desc: 'View your current inventory', category: 'items' },

    // Blood Testing
    { name: 'TEST', syntax: 'TEST <person>', desc: 'Begin a blood test on someone (requires blood test kit)', category: 'investigation' },
    { name: 'HEAT', syntax: 'HEAT', desc: 'Heat the test wire during blood testing', category: 'investigation' },
    { name: 'APPLY', syntax: 'APPLY', desc: 'Apply heated wire to blood sample', category: 'investigation' },

    // System
    { name: 'STATUS', syntax: 'STATUS', desc: 'View your current status and health', category: 'system' },
    { name: 'HELP', syntax: 'HELP, HELP <command>', desc: 'Show available commands or help for a specific command', category: 'system' },
    { name: 'WAIT', syntax: 'WAIT', desc: 'Wait and let time pass', category: 'system' },
    { name: 'REST', syntax: 'REST', desc: 'Rest to recover health (if safe)', category: 'system' },
    { name: 'BARRICADE', syntax: 'BARRICADE <direction>', desc: 'Barricade a door to slow enemies', category: 'system' },
    { name: 'SAVE', syntax: 'SAVE', desc: 'Save your current game progress', category: 'system' },
    { name: 'QUIT', syntax: 'QUIT', desc: 'End the current game session', category: 'system' }
];

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

    // Setup navigation buttons
    document.querySelectorAll('.nav-btn[data-dir]').forEach(btn => {
        btn.addEventListener('click', function() {
            const direction = this.dataset.dir.toUpperCase();
            sendQuickCommand(direction);
        });
    });

    // Setup command category buttons
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentCommandCategory = this.dataset.category;
            filterCommands();
        });
    });

    // Setup command modal close on outside click
    const modal = document.getElementById('command-modal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeCommandModal();
            }
        });
    }

    // Populate command list on load
    populateCommandList();

    // Setup keyboard shortcuts for quick actions
    document.addEventListener('keydown', handleGlobalKeydown);

    // Setup journal filter buttons
    document.querySelectorAll('.journal-filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            filterJournalEntries(this.dataset.filter);
        });
    });

    // Setup stats modal close on outside click
    const statsModal = document.getElementById('stats-modal');
    if (statsModal) {
        statsModal.addEventListener('click', function(e) {
            if (e.target === statsModal) {
                closeStatsModal();
            }
        });
    }

    // Setup journal modal close on outside click
    const journalModal = document.getElementById('journal-modal');
    if (journalModal) {
        journalModal.addEventListener('click', function(e) {
            if (e.target === journalModal) {
                closeJournalModal();
            }
        });
    }
}

function handleGlobalKeydown(event) {
    // Handle Escape key to close modals
    if (event.key === 'Escape') {
        if (commandModalOpen) {
            closeCommandModal();
            event.preventDefault();
            return;
        }
        if (statsModalOpen) {
            closeStatsModal();
            event.preventDefault();
            return;
        }
        if (journalModalOpen) {
            closeJournalModal();
            event.preventDefault();
            return;
        }
    }

    // Handle ? key to open command browser
    if (event.key === '?' || (event.key === '/' && event.shiftKey)) {
        event.preventDefault();
        openCommandModal();
        return;
    }

    // Don't trigger shortcuts when typing in command input or search
    const commandInput = document.getElementById('command-input');
    const searchInput = document.getElementById('command-search');
    if (document.activeElement === commandInput || document.activeElement === searchInput) {
        // Allow arrow keys for navigation when in command input
        if (document.activeElement === commandInput) {
            if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
                return; // Let handleCommandInput handle history
            }
        }
        return;
    }

    // Arrow keys for navigation
    const arrowDirs = {
        'ArrowUp': 'NORTH',
        'ArrowDown': 'SOUTH',
        'ArrowLeft': 'WEST',
        'ArrowRight': 'EAST'
    };

    if (arrowDirs[event.key] && !event.ctrlKey && !event.altKey && !event.metaKey) {
        event.preventDefault();
        sendQuickCommand(arrowDirs[event.key]);
        // Visual feedback on nav buttons
        const navBtn = document.querySelector(`.nav-btn[data-dir="${arrowDirs[event.key].toLowerCase()}"]`);
        if (navBtn) {
            navBtn.classList.add('shortcut-active');
            setTimeout(() => navBtn.classList.remove('shortcut-active'), 150);
        }
        return;
    }

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

    // G key for game statistics
    if (event.key.toLowerCase() === 'g' && !event.ctrlKey && !event.altKey && !event.metaKey) {
        event.preventDefault();
        openStatsModal();
        return;
    }

    // J key for journal
    if (event.key.toLowerCase() === 'j' && !event.ctrlKey && !event.altKey && !event.metaKey) {
        event.preventDefault();
        openJournalModal();
        return;
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

// Store previous state for event detection
let previousGameState = null;

function updateGameDisplay(state) {
    if (!state) return;

    // Detect and log game events
    detectAndLogEvents(state, previousGameState);
    previousGameState = JSON.parse(JSON.stringify(state)); // Deep copy for comparison

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

    // Update minigame panels
    updateBloodTestPanel(state);
    updateInterrogationPanel(state);

    // Update navigation buttons availability
    updateNavigationButtons(state);

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

// ===== COMMAND BROWSER MODAL =====

function openCommandModal() {
    const modal = document.getElementById('command-modal');
    if (modal) {
        modal.classList.remove('hidden');
        commandModalOpen = true;
        const searchInput = document.getElementById('command-search');
        if (searchInput) {
            searchInput.value = '';
            searchInput.focus();
        }
        filterCommands();
    }
}

function closeCommandModal() {
    const modal = document.getElementById('command-modal');
    if (modal) {
        modal.classList.add('hidden');
        commandModalOpen = false;
        document.getElementById('command-input').focus();
    }
}

function populateCommandList() {
    const container = document.getElementById('command-list');
    if (!container) return;

    container.innerHTML = COMMAND_DATABASE.map(cmd => `
        <div class="command-item" data-category="${cmd.category}" data-name="${cmd.name}" onclick="insertCommand('${cmd.name}')">
            <div class="command-item-header">
                <span class="command-name">${cmd.name}</span>
                <span class="command-category">${cmd.category}</span>
            </div>
            <div class="command-syntax">${cmd.syntax}</div>
            <div class="command-desc">${cmd.desc}</div>
        </div>
    `).join('');
}

function filterCommands() {
    const searchInput = document.getElementById('command-search');
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    const items = document.querySelectorAll('.command-item');

    items.forEach(item => {
        const name = item.dataset.name.toLowerCase();
        const category = item.dataset.category;
        const desc = item.querySelector('.command-desc').textContent.toLowerCase();
        const syntax = item.querySelector('.command-syntax').textContent.toLowerCase();

        const matchesSearch = name.includes(searchTerm) ||
                             desc.includes(searchTerm) ||
                             syntax.includes(searchTerm);
        const matchesCategory = currentCommandCategory === 'all' || category === currentCommandCategory;

        if (matchesSearch && matchesCategory) {
            item.classList.remove('hidden');
        } else {
            item.classList.add('hidden');
        }
    });
}

function insertCommand(command) {
    closeCommandModal();
    const input = document.getElementById('command-input');
    if (input) {
        input.value = command + ' ';
        input.focus();
    }
}

// ===== BLOOD TEST PANEL =====

function updateBloodTestPanel(state) {
    const panel = document.getElementById('blood-test-panel');
    if (!panel) return;

    if (state.blood_test_active) {
        panel.classList.remove('hidden');

        // Update subject
        const subject = document.getElementById('blood-test-subject');
        if (subject && state.blood_test_subject) {
            subject.textContent = `Testing: ${state.blood_test_subject}`;
        }

        // Update thermometer
        const thermometerFill = document.getElementById('thermometer-fill');
        const wireTemp = document.getElementById('wire-temp');
        const sampleStatus = document.getElementById('sample-status');

        const temp = state.wire_temperature || 0;
        if (thermometerFill) {
            thermometerFill.style.width = `${temp}%`;
        }
        if (wireTemp) {
            wireTemp.textContent = temp;
        }
        if (sampleStatus) {
            if (temp >= 70) {
                sampleStatus.textContent = 'READY TO APPLY';
                sampleStatus.style.color = '#00ff41';
            } else if (temp >= 40) {
                sampleStatus.textContent = 'Warming...';
                sampleStatus.style.color = '#ffaa00';
            } else {
                sampleStatus.textContent = 'Wire cold';
                sampleStatus.style.color = '#ff3333';
            }
        }
    } else {
        panel.classList.add('hidden');
    }
}

// ===== INTERROGATION PANEL =====

function updateInterrogationPanel(state) {
    const panel = document.getElementById('interrogation-panel');
    if (!panel) return;

    if (state.interrogation_active) {
        panel.classList.remove('hidden');

        // Update subject
        const subject = document.getElementById('interrogation-subject');
        if (subject && state.interrogation_subject) {
            subject.textContent = `Interrogating: ${state.interrogation_subject}`;
        }
    } else {
        panel.classList.add('hidden');
    }
}

// ===== NAVIGATION AVAILABILITY =====

function updateNavigationButtons(state) {
    const directions = ['north', 'south', 'east', 'west'];

    directions.forEach(dir => {
        const btn = document.querySelector(`.nav-btn[data-dir="${dir}"]`);
        if (btn) {
            // Check if direction is available (if the game state provides this info)
            const available = state.available_exits ?
                state.available_exits.includes(dir.toUpperCase()) : true;

            if (available) {
                btn.classList.remove('nav-unavailable');
                btn.disabled = false;
            } else {
                btn.classList.add('nav-unavailable');
                btn.disabled = true;
            }
        }
    });
}

// ===== TOAST NOTIFICATIONS =====

function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    // Icon based on type
    const icons = {
        'info': 'ℹ',
        'success': '✓',
        'warning': '⚠',
        'danger': '☠',
        'discovery': '🔍'
    };

    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
    `;

    container.appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ===== STATISTICS MODAL =====

let statsModalOpen = false;

function openStatsModal() {
    const modal = document.getElementById('stats-modal');
    if (modal) {
        updateStats();
        modal.classList.remove('hidden');
        statsModalOpen = true;
    }
}

function closeStatsModal() {
    const modal = document.getElementById('stats-modal');
    if (modal) {
        modal.classList.add('hidden');
        statsModalOpen = false;
        document.getElementById('command-input').focus();
    }
}

function updateStats() {
    if (!gameState) return;

    // Update from game state
    const statTurns = document.getElementById('stat-turns');
    const statTime = document.getElementById('stat-time');
    const statRooms = document.getElementById('stat-rooms');
    const statCrewAlive = document.getElementById('stat-crew-alive');
    const statCrewDead = document.getElementById('stat-crew-dead');
    const statInfected = document.getElementById('stat-infected');
    const statTests = document.getElementById('stat-tests');
    const statInterrogations = document.getElementById('stat-interrogations');
    const statItems = document.getElementById('stat-items');
    const statEncounters = document.getElementById('stat-encounters');
    const statKills = document.getElementById('stat-kills');
    const statDamage = document.getElementById('stat-damage');

    if (statTurns) statTurns.textContent = gameState.turn || 0;
    if (statTime) statTime.textContent = gameState.time || '00:00';
    if (statRooms) statRooms.textContent = gameStats.roomsVisited.size;

    // Count crew stats
    if (gameState.crew) {
        const alive = gameState.crew.filter(c => c.is_alive).length;
        const dead = gameState.crew.filter(c => !c.is_alive).length;
        if (statCrewAlive) statCrewAlive.textContent = alive;
        if (statCrewDead) statCrewDead.textContent = dead;
    }

    if (statInfected) statInfected.textContent = gameStats.infectedFound;
    if (statTests) statTests.textContent = gameStats.bloodTests;
    if (statInterrogations) statInterrogations.textContent = gameStats.interrogations;
    if (statItems) statItems.textContent = gameStats.itemsFound;
    if (statEncounters) statEncounters.textContent = gameStats.combatEncounters;
    if (statKills) statKills.textContent = gameStats.thingsKilled;
    if (statDamage) statDamage.textContent = gameStats.damageTaken;
}

// ===== INVESTIGATION JOURNAL =====

let journalModalOpen = false;

function addJournalEntry(type, title, details, turn) {
    const entry = {
        id: Date.now(),
        type: type, // 'discovery', 'test', 'death', 'event'
        title: title,
        details: details,
        turn: turn || (gameState ? gameState.turn : 0),
        time: gameState ? gameState.time : '00:00'
    };

    journalEntries.unshift(entry); // Add to beginning

    // Show toast for new entry
    const toastTypes = {
        'discovery': 'discovery',
        'test': 'info',
        'death': 'danger',
        'event': 'warning'
    };
    showToast(`Journal: ${title}`, toastTypes[type] || 'info', 3000);
}

function openJournalModal() {
    const modal = document.getElementById('journal-modal');
    if (modal) {
        modal.classList.remove('hidden');
        journalModalOpen = true;
        renderJournalEntries();
    }
}

function closeJournalModal() {
    const modal = document.getElementById('journal-modal');
    if (modal) {
        modal.classList.add('hidden');
        journalModalOpen = false;
        document.getElementById('command-input').focus();
    }
}

function renderJournalEntries() {
    const container = document.getElementById('journal-entries');
    if (!container) return;

    const filtered = journalFilter === 'all'
        ? journalEntries
        : journalEntries.filter(e => e.type === journalFilter);

    if (filtered.length === 0) {
        container.innerHTML = '<div class="journal-empty">No entries matching filter.</div>';
        return;
    }

    container.innerHTML = filtered.map(entry => {
        const typeIcons = {
            'discovery': '🔍',
            'test': '🧪',
            'death': '💀',
            'event': '⚡'
        };
        const icon = typeIcons[entry.type] || '📝';

        return `
            <div class="journal-entry journal-entry-${entry.type}">
                <div class="journal-entry-header">
                    <span class="journal-icon">${icon}</span>
                    <span class="journal-title">${entry.title}</span>
                    <span class="journal-entry-time">Turn ${entry.turn} - ${entry.time}</span>
                </div>
                <div class="journal-entry-content">${entry.details}</div>
            </div>
        `;
    }).join('');
}

function filterJournalEntries(filter) {
    journalFilter = filter;

    // Update active button
    document.querySelectorAll('.journal-filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === filter);
    });

    renderJournalEntries();
}

// ===== EVENT DETECTION FOR TOASTS AND JOURNAL =====

function detectAndLogEvents(newState, previousState) {
    if (!newState) return;

    // Track room visits
    if (newState.location) {
        const wasVisited = gameStats.roomsVisited.has(newState.location);
        gameStats.roomsVisited.add(newState.location);

        // Log first visit to a room
        if (!wasVisited && previousState && previousState.location !== newState.location) {
            addJournalEntry('discovery', `Explored ${newState.location}`,
                `Entered ${newState.location} for the first time.`, newState.turn);
        }
    }

    // Track blood test events
    if (newState.blood_test_active && (!previousState || !previousState.blood_test_active)) {
        gameStats.bloodTests++;
        showToast(`Blood test started on ${newState.blood_test_subject || 'subject'}`, 'warning', 3000);
    }

    // Track blood test completion
    if (previousState && previousState.blood_test_active && !newState.blood_test_active) {
        if (newState.blood_test_result) {
            const result = newState.blood_test_result;
            if (result.infected) {
                gameStats.infectedFound++;
                addJournalEntry('test', `INFECTED: ${result.subject}`,
                    `Blood test confirmed ${result.subject} is a Thing!`, newState.turn);
                showToast(`${result.subject} IS INFECTED!`, 'danger', 5000);
            } else {
                addJournalEntry('test', `CLEAR: ${result.subject}`,
                    `Blood test confirmed ${result.subject} is human.`, newState.turn);
                showToast(`${result.subject} is human`, 'success', 3000);
            }
        }
    }

    // Track interrogation events
    if (newState.interrogation_active && (!previousState || !previousState.interrogation_active)) {
        gameStats.interrogations++;
    }

    // Track combat events
    if (newState.combat_active && (!previousState || !previousState.combat_active)) {
        gameStats.combatEncounters++;
        showToast('COMBAT INITIATED!', 'danger', 3000);
        addJournalEntry('event', 'Combat Encounter',
            `Combat started in ${newState.location}.`, newState.turn);
    }

    // Track crew deaths
    if (previousState && previousState.crew && newState.crew) {
        newState.crew.forEach(member => {
            const prevMember = previousState.crew.find(c => c.name === member.name);
            if (prevMember && prevMember.is_alive && !member.is_alive) {
                addJournalEntry('death', `${member.name} died`,
                    `${member.name} (${member.role}) was found dead in ${member.location}.`, newState.turn);
                showToast(`${member.name} has died!`, 'danger', 5000);
            }
        });
    }

    // Track items picked up
    if (previousState && previousState.inventory && newState.inventory) {
        const prevItems = new Set(previousState.inventory.map(i => i.name));
        newState.inventory.forEach(item => {
            if (!prevItems.has(item.name)) {
                gameStats.itemsFound++;
                showToast(`Picked up: ${item.name}`, 'success', 2500);
            }
        });
    }
}
