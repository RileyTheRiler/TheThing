#!/usr/bin/env python3
"""
Flask Backend Server for The Thing Browser Interface
Handles game state and provides API endpoints for the browser client
"""

import sys
import os
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# Add src directory to Python path
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, src_path)

from engine import GameState
from systems.architect import Difficulty
from ui.settings import settings

app = Flask(__name__,
            static_folder='web/static',
            template_folder='web/templates')
app.config['SECRET_KEY'] = 'the-thing-secret-key-2025'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global game state
game_sessions = {}


def serialize_game_state(game):
    """Convert game state to JSON-serializable format"""
    player_room = game.station_map.get_room_name(*game.player.location)
    weather_status = game.weather.get_status()
    room_icons = game.room_states.get_status_icons(player_room)

    # Get room items
    room_items = game.station_map.get_items_in_room(*game.player.location)
    item_list = [{"name": str(i), "description": i.description} for i in room_items]

    # Get crew status
    crew_status = []
    for m in game.crew:
        room = game.station_map.get_room_name(*m.location)
        crew_status.append({
            'name': m.name,
            'role': m.role,
            'location': room,
            'coords': m.location,
            'health': m.health,
            'is_alive': m.is_alive,
            'is_infected': m.is_infected if hasattr(m, 'is_infected') else False,
            'trust': game.trust_system.get_average_trust(m.name)
        })

    # Get player inventory
    inventory = [{"name": item.name, "description": item.description} for item in game.player.inventory]

    # Get map rendering
    map_display = game.renderer.render(game, game.player)

    # Room description modifiers
    room_desc = game.room_states.get_room_description_modifiers(player_room)

    return {
        'turn': game.turn,
        'mode': game.mode.value,
        'time': f"{game.time_system.hour:02}:00",
        'temperature': round(game.temperature, 1),
        'power_on': game.power_on,
        'location': player_room,
        'room_icons': room_icons,
        'room_description': room_desc,
        'weather': weather_status,
        'sabotage_status': game.sabotage.get_status() if not game.sabotage.radio_operational or not game.sabotage.chopper_operational else None,
        'items': item_list,
        'crew': crew_status,
        'inventory': inventory,
        'map': map_display,
        'paranoia': game.paranoia_level,
        'player_health': game.player.health,
        'player_alive': game.player.is_alive
    }


@app.route('/')
def index():
    """Serve the main game page"""
    return render_template('index.html')


@app.route('/api/new_game', methods=['POST'])
def new_game():
    """Start a new game"""
    data = request.json
    difficulty_str = data.get('difficulty', 'NORMAL').upper()

    # Map difficulty string to enum
    difficulty_map = {
        'EASY': Difficulty.EASY,
        'NORMAL': Difficulty.NORMAL,
        'HARD': Difficulty.HARD
    }
    difficulty = difficulty_map.get(difficulty_str, Difficulty.NORMAL)

    # Create new game
    session_id = data.get('session_id', 'default')
    game = GameState(seed=None, difficulty=difficulty)
    settings.apply_to_game(game)

    game_sessions[session_id] = game

    return jsonify({
        'success': True,
        'session_id': session_id,
        'game_state': serialize_game_state(game)
    })


@app.route('/api/game_state/<session_id>', methods=['GET'])
def get_game_state(session_id):
    """Get current game state"""
    if session_id not in game_sessions:
        return jsonify({'error': 'Session not found'}), 404

    game = game_sessions[session_id]

    # Check for game over
    game_over, won, message = game.check_game_over()

    state = serialize_game_state(game)
    state['game_over'] = game_over
    state['won'] = won
    state['game_over_message'] = message if game_over else None

    return jsonify(state)


@app.route('/api/command', methods=['POST'])
def execute_command():
    """Execute a game command"""
    data = request.json
    session_id = data.get('session_id', 'default')
    command = data.get('command', '').strip().upper()

    if session_id not in game_sessions:
        return jsonify({'error': 'Session not found'}), 404

    game = game_sessions[session_id]

    # Parse command
    cmd = command.split()
    if not cmd:
        return jsonify({'success': True, 'message': '', 'game_state': serialize_game_state(game)})

    # Execute command and capture output
    result = _execute_game_command(game, cmd)

    # Check for game over
    game_over, won, message = game.check_game_over()

    state = serialize_game_state(game)
    state['game_over'] = game_over
    state['won'] = won
    state['game_over_message'] = message if game_over else None

    return jsonify({
        'success': True,
        'message': result,
        'game_state': state
    })


def _execute_game_command(game, cmd):
    """Execute a game command and return result message"""
    from systems.combat import CombatSystem, CoverType
    from systems.interrogation import InterrogationSystem, InterrogationTopic
    from core.resolution import Skill

    action = cmd[0]
    player_room = game.station_map.get_room_name(*game.player.location)
    output = []

    if action == "HELP":
        output.append(_get_help_text())

    elif action == "ADVANCE":
        game.advance_turn()
        output.append("Time passes...")

    elif action == "MOVE":
        if len(cmd) < 2:
            output.append("Usage: MOVE <NORTH/SOUTH/EAST/WEST>")
        else:
            direction = cmd[1]
            dx, dy = 0, 0
            if direction in ["NORTH", "N"]:
                dy = -1
            elif direction in ["SOUTH", "S"]:
                dy = 1
            elif direction in ["EAST", "E"]:
                dx = 1
            elif direction in ["WEST", "W"]:
                dx = -1

            new_x = game.player.location[0] + dx
            new_y = game.player.location[1] + dy

            if game.station_map.is_walkable(new_x, new_y):
                target_room = game.station_map.get_room_name(new_x, new_y)

                if game.room_states.is_entry_blocked(target_room) and target_room != player_room:
                    strength = game.room_states.get_barricade_strength(target_room)
                    output.append(f"The {target_room} is barricaded! (Strength: {strength}/3)")
                    output.append("Use BREAK <DIRECTION> to force entry.")
                else:
                    game.player.location = (new_x, new_y)
                    output.append(f"You moved {direction}.")
                    game.advance_turn()
            else:
                output.append("Blocked.")

    elif action == "LOOK":
        if len(cmd) < 2:
            output.append("Usage: LOOK <NAME>")
        else:
            target_name = cmd[1]
            target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
            if target:
                if game.station_map.get_room_name(*target.location) == player_room:
                    output.append(target.get_description(game))
                else:
                    output.append(f"There is no {target_name} here.")
            else:
                output.append(f"Unknown crew member: {target_name}")

    elif action == "TALK":
        for m in game.crew:
            room = game.station_map.get_room_name(*m.location)
            if room == player_room:
                output.append(f"{m.name}: {m.get_dialogue(game)}")

    elif action == "STATUS":
        for m in game.crew:
            status = "Alive" if m.is_alive else "DEAD"
            avg_trust = game.trust_system.get_average_trust(m.name)
            output.append(f"{m.name} ({m.role}): {m.location} | HP: {m.health} | {status} | Trust: {avg_trust:.1f}")

    elif action in ["INVENTORY", "INV"]:
        output.append(f"--- {game.player.name}'s INVENTORY ---")
        if not game.player.inventory:
            output.append("(Empty)")
        for item in game.player.inventory:
            output.append(f"- {item.name}: {item.description}")

    elif action == "GET":
        if len(cmd) < 2:
            output.append("Usage: GET <ITEM NAME>")
        else:
            item_name = " ".join(cmd[1:])
            found_item = game.station_map.remove_item_from_room(item_name, *game.player.location)
            if found_item:
                game.player.add_item(found_item, game.turn)
                game.evidence_log.record_event(found_item.name, "GET", game.player.name, player_room, game.turn)
                output.append(f"You picked up {found_item.name}.")
            else:
                output.append(f"You don't see '{item_name}' here.")

    elif action == "DROP":
        if len(cmd) < 2:
            output.append("Usage: DROP <ITEM NAME>")
        else:
            item_name = " ".join(cmd[1:])
            dropped_item = game.player.remove_item(item_name)
            if dropped_item:
                game.station_map.add_item_to_room(dropped_item, *game.player.location, game.turn)
                game.evidence_log.record_event(dropped_item.name, "DROP", game.player.name, player_room, game.turn)
                output.append(f"You dropped {dropped_item.name}.")
            else:
                output.append(f"You don't have '{item_name}'.")

    elif action == "ATTACK":
        if len(cmd) < 2:
            output.append("Usage: ATTACK <NAME>")
        else:
            target_name = cmd[1]
            target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
            if not target:
                output.append(f"Unknown target: {target_name}")
            elif game.station_map.get_room_name(*target.location) != player_room:
                output.append(f"{target.name} is not here.")
            elif not target.is_alive:
                output.append(f"{target.name} is already dead.")
            else:
                combat = CombatSystem(game.rng, game.room_states)
                player_init = combat.roll_initiative(game.player)
                target_init = combat.roll_initiative(target)
                output.append(f"[COMBAT] Initiative: {game.player.name} ({player_init}) vs {target.name} ({target_init})")

                weapon = next((i for i in game.player.inventory if i.damage > 0), None)
                w_name = weapon.name if weapon else "Fists"
                target_cover = getattr(game, 'combat_cover', {}).get(target.name, CoverType.NONE)

                output.append(f"Attacking {target.name} with {w_name}...")
                if target_cover != CoverType.NONE:
                    output.append(f"[COVER] {target.name} has {target_cover.value} cover!")

                result = combat.calculate_attack(game.player, target, weapon, target_cover, player_room)
                output.append(result.message)

                if result.success:
                    died = target.take_damage(result.damage, game_state=game)
                    if died:
                        output.append(f"*** {target.name} HAS DIED ***")
                        if hasattr(game, 'combat_cover') and target.name in game.combat_cover:
                            del game.combat_cover[target.name]

    elif action == "TEST":
        if len(cmd) < 2:
            output.append("Usage: TEST <NAME>")
        else:
            target_name = cmd[1]
            target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
            if not target:
                output.append(f"Unknown target: {target_name}")
            elif game.station_map.get_room_name(*target.location) != player_room:
                output.append(f"{target.name} is not here.")
            else:
                scalpel = next((i for i in game.player.inventory if "SCALPEL" in i.name.upper()), None)
                wire = next((i for i in game.player.inventory if "WIRE" in i.name.upper()), None)

                if not scalpel:
                    output.append("You need a SCALPEL to draw a blood sample.")
                elif not wire:
                    output.append("You need COPPER WIRE for the test.")
                else:
                    output.append(f"Drawing blood from {target.name}...")
                    output.append(game.blood_test_sim.start_test(target.name))
                    output.append("Sample prepared. Use HEAT to heat the wire, then APPLY.")

    elif action == "HEAT":
        output.append(game.blood_test_sim.heat_wire())

    elif action == "APPLY":
        if not game.blood_test_sim.active:
            output.append("No test in progress.")
        else:
            sample_name = game.blood_test_sim.current_sample
            subject = next((m for m in game.crew if m.name == sample_name), None)
            if subject:
                output.append(game.blood_test_sim.apply_wire(subject.is_infected))

    elif action == "CANCEL":
        output.append(game.blood_test_sim.cancel())

    elif action == "BARRICADE":
        result = game.room_states.barricade_room(player_room)
        output.append(result)
        game.advance_turn()

    elif action == "SAVE":
        slot = cmd[1] if len(cmd) > 1 else "auto"
        game.save_manager.save_game(game, slot)
        output.append(f"Game saved to slot: {slot}")

    elif action == "LOAD":
        slot = cmd[1] if len(cmd) > 1 else "auto"
        new_game_state = game.save_manager.load_game(slot)
        if new_game_state:
            if isinstance(new_game_state, dict):
                new_game_state = GameState.from_dict(new_game_state)
            game.__dict__.update(new_game_state.__dict__)
            output.append("*** GAME LOADED ***")
        else:
            output.append("Failed to load game.")

    elif action == "INTERROGATE" or action == "ASK":
        if len(cmd) < 2:
            output.append("Usage: INTERROGATE <NAME> [TOPIC]")
            output.append("Topics: WHEREABOUTS, ALIBI, SUSPICION, BEHAVIOR, KNOWLEDGE")
        else:
            target_name = cmd[1]
            target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)

            if not target:
                output.append(f"Unknown target: {target_name}")
            elif game.station_map.get_room_name(*target.location) != player_room:
                output.append(f"{target.name} is not here.")
            elif not target.is_alive:
                output.append(f"{target.name} cannot answer...")
            else:
                if len(cmd) > 2:
                    topic_name = cmd[2].upper()
                    topic_map = {
                        "WHEREABOUTS": InterrogationTopic.WHEREABOUTS,
                        "ALIBI": InterrogationTopic.ALIBI,
                        "SUSPICION": InterrogationTopic.SUSPICION,
                        "BEHAVIOR": InterrogationTopic.BEHAVIOR,
                        "KNOWLEDGE": InterrogationTopic.KNOWLEDGE
                    }
                    topic = topic_map.get(topic_name, InterrogationTopic.WHEREABOUTS)
                else:
                    topic = InterrogationTopic.WHEREABOUTS

                if not hasattr(game, 'interrogation_system'):
                    game.interrogation_system = InterrogationSystem(game.rng, game.room_states)

                result = game.interrogation_system.interrogate(game.player, target, topic, game)

                output.append(f"[INTERROGATION: {target.name} - {topic.value.upper()}]")
                output.append(f'"{result.dialogue}"')
                output.append(f"[Response: {result.response_type.value}]")

                if result.tells:
                    output.append("[OBSERVATION]")
                    for tell in result.tells:
                        output.append(f"  - {tell}")

                game.trust_system.modify_trust(target.name, game.player.name, result.trust_change)
                if result.trust_change != 0:
                    change_str = f"+{result.trust_change}" if result.trust_change > 0 else str(result.trust_change)
                    output.append(f"[Trust: {change_str}]")

    else:
        output.append(f"Unknown command: {action}. Type HELP for available commands.")

    return "\n".join(output)


def _get_help_text():
    """Return help text for commands"""
    return """
=== THE THING: COMMAND REFERENCE ===

MOVEMENT:
  MOVE <DIR>    - Move NORTH/SOUTH/EAST/WEST (or N/S/E/W)
  ADVANCE       - Pass time without moving

SOCIAL:
  TALK               - Hear dialogue from everyone in the room
  LOOK <NAME>        - Observe a crew member
  INTERROGATE <NAME> - Question someone

FORENSICS:
  TEST <NAME>   - Perform blood test (requires Scalpel + Copper Wire)
  HEAT          - Heat the wire during a test
  APPLY         - Apply hot wire to blood sample
  CANCEL        - Cancel current blood test

COMBAT:
  ATTACK <NAME> - Attack a crew member

INVENTORY:
  INV           - View your inventory
  GET <ITEM>    - Pick up an item
  DROP <ITEM>   - Drop an item

ENVIRONMENT:
  BARRICADE     - Barricade the current room
  STATUS        - View all crew locations and health

SYSTEM:
  SAVE [SLOT]   - Save game
  LOAD [SLOT]   - Load game
  HELP          - Show this help
"""


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('connected', {'data': 'Connected to The Thing server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')


if __name__ == '__main__':
    print("=" * 60)
    print("   THE THING: ANTARCTIC RESEARCH STATION 31")
    print("   Browser Interface Server")
    print("=" * 60)
    print("\nStarting server...")
    print("Navigate to: http://localhost:5000")
    print("\nPress CTRL+C to stop the server")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
