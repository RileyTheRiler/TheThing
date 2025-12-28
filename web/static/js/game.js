// The Thing: Browser Interface JavaScript

let sessionId = 'session_' + Date.now();
let gameState = null;
let commandHistory = [];
let historyIndex = -1;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
});

function setupEventListeners() {
    const commandInput = document.getElementById('command-input');
    if (commandInput) {
        commandInput.addEventListener('keydown', handleCommandInput);
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
}

function updateGameDisplay(state) {
    if (!state) return;

    // Update status bar
    document.getElementById('turn-counter').textContent = state.turn;
    document.getElementById('game-time').textContent = state.time;
    document.getElementById('temperature').textContent = state.temperature + '°C';
    document.getElementById('power-status').textContent = state.power_on ? 'ON' : 'OFF';
    document.getElementById('location').textContent = state.location;

    // Update room info
    document.getElementById('room-description').textContent = state.room_description || '';
    document.getElementById('room-icons').textContent = state.room_icons || '';

    // Update map
    document.getElementById('game-map').textContent = state.map || 'Map unavailable';

    // Update room items
    const itemsContainer = document.getElementById('room-items');
    if (state.items && state.items.length > 0) {
        itemsContainer.innerHTML = state.items.map(item =>
            `<div>• ${item.name}</div>`
        ).join('');
    } else {
        itemsContainer.textContent = 'None';
    }

    // Update crew status
    const crewContainer = document.getElementById('crew-status');
    if (state.crew && state.crew.length > 0) {
        crewContainer.innerHTML = state.crew.map(member => {
            const statusClass = member.is_alive ? '' : 'danger';
            const statusText = member.is_alive ? 'ALIVE' : 'DEAD';
            return `<div class="${statusClass}">
                ${member.name} (${member.role}) - ${member.location}<br>
                HP: ${member.health} | ${statusText} | Trust: ${member.trust.toFixed(1)}
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
