"""Main game loop for The Thing game."""

import os
import atexit

# Cross-platform readline support for command history
READLINE_AVAILABLE = False
try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    # Windows fallback - try pyreadline3
    try:
        import pyreadline3 as readline
        READLINE_AVAILABLE = True
    except ImportError:
        pass

# History file path (in user's home directory)
HISTORY_FILE = os.path.expanduser("~/.thething_history")
MAX_HISTORY_LENGTH = 100


def _setup_readline():
    """Configure readline for command history and arrow key navigation."""
    if not READLINE_AVAILABLE:
        return

    # Set history file length
    readline.set_history_length(MAX_HISTORY_LENGTH)

    # Load existing history
    try:
        if os.path.exists(HISTORY_FILE):
            readline.read_history_file(HISTORY_FILE)
    except (IOError, OSError):
        pass  # History file doesn't exist or is unreadable

    # Save history on exit
    atexit.register(_save_history)


def _save_history():
    """Save command history to file."""
    if not READLINE_AVAILABLE:
        return

    try:
        readline.write_history_file(HISTORY_FILE)
    except (IOError, OSError):
        pass  # Can't write history file


from core.resolution import Attribute, Skill
from core.event_system import event_bus, EventType, GameEvent
from systems.architect import Difficulty, DifficultySettings
from systems.combat import CombatSystem, CoverType, CombatEncounter
from systems.interrogation import InterrogationSystem, InterrogationTopic
from audio.audio_manager import Sound
from engine import GameState


def _select_difficulty():
    """Display difficulty selection menu and return chosen difficulty."""
    print("\n" + "=" * 50)
    print("   THE THING: ANTARCTIC RESEARCH STATION 31")
    print("=" * 50)
    print("\nSelect Difficulty:")
    print()

    for i, diff in enumerate(Difficulty, 1):
        settings = DifficultySettings.get_all(diff)
        print(f"  [{i}] {diff.value}")
        print(f"      {settings['description']}")
        print()

    while True:
        try:
            choice = input("Enter choice (1-3) [2]: ").strip()
            if not choice:
                return Difficulty.NORMAL
            choice = int(choice)
            if 1 <= choice <= 3:
                return list(Difficulty)[choice - 1]
            print("Invalid choice. Enter 1, 2, or 3.")
        except ValueError:
            print("Invalid input. Enter a number.")
        except EOFError:
            return Difficulty.NORMAL


def _show_tutorial():
    """Display optional tutorial for new players."""
    print("\n" + "=" * 60)
    print("   TUTORIAL: SURVIVING OUTPOST 31")
    print("=" * 60)

    sections = [
        ("""
THE SITUATION
-------------
You are R.J. MacReady, helicopter pilot at U.S. Antarctic
Research Station 31. An alien organism - "The Thing" - has
infiltrated the base. It perfectly imitates its victims.

Trust no one. The person next to you might not be human.
""", "Continue..."),
        ("""
YOUR GOAL
---------
- Identify who is infected using observation and blood tests
- Eliminate all infected crew members
- Stay alive and remain human

You LOSE if:
- You are killed
- You become infected and are revealed as a Thing
""", "Continue..."),
        ("""
BASIC COMMANDS
--------------
MOVE <DIR>    - Move NORTH/SOUTH/EAST/WEST (or N/S/E/W)
LOOK <NAME>   - Observe someone for suspicious behavior
TALK          - Hear what everyone in the room is saying
STATUS        - See all crew locations and health
INV           - Check your inventory
HELP          - Full command reference
""", "Continue..."),
        ("""
DETECTING THE THING
-------------------
Watch for biological tells:
- Missing breath vapor in cold (below 0C)
- Strange eye movements or skin texture
- Unusual behavior or being in wrong locations

Use INTERROGATE <NAME> to question crew members.
Their responses may reveal inconsistencies.
""", "Continue..."),
        ("""
THE BLOOD TEST
--------------
The definitive test requires:
1. A SCALPEL (to draw blood)
2. COPPER WIRE (to heat)

Commands: TEST <NAME>, then HEAT repeatedly, then APPLY

If the blood reacts violently - they're infected!
Warning: A revealed Thing becomes hostile.
""", "Continue..."),
        ("""
COMBAT & SURVIVAL
-----------------
ATTACK <NAME>  - Attack someone (need weapon for damage)
COVER          - Take cover for defense bonus
RETREAT        - Try to escape from revealed Things
BARRICADE      - Block a room entrance
BREAK <DIR>    - Break through a barricade

Revealed Things will hunt humans aggressively.
""", "Begin Game..."),
    ]

    for text, prompt in sections:
        print(text)
        try:
            input(f"[Press ENTER to {prompt}]")
        except EOFError:
            break
        print()

    print("\n" + "=" * 60)
    print("   Good luck, MacReady. Trust no one.")
    print("=" * 60 + "\n")


def main():
    """Main game loop - can be called from launcher or run directly."""
    # Set up readline for command history (arrow keys, history file)
    _setup_readline()

    # Select difficulty before starting
    difficulty = _select_difficulty()

    # Offer tutorial for new players
    print("\nWould you like to see the tutorial? (y/N): ", end="")
    try:
        response = input().strip().lower()
        if response in ['y', 'yes']:
            _show_tutorial()
    except EOFError:
        pass

    print(f"\nStarting game on {difficulty.value} difficulty...")

    game = GameState(seed=None, difficulty=difficulty)

    # Agent 5 Boot Sequence
    game.crt.boot_sequence()
    game.audio.ambient_loop(Sound.THRUM)

    while True:
        # Check for game over conditions
        game_over, won, message = game.check_game_over()
        if game_over:
            _handle_game_over(game, won, message)
            break

        # Render the current game state
        _render_game_state(game)

        # Get and parse player input
        cmd = _get_player_input(game)
        if cmd is None:
            break

        # Execute the command
        if not _execute_command(game, cmd):
            break


def _handle_game_over(game, won, message):
    """Display game over screen with final statistics."""
    game.crt.output("\n" + "=" * 50)
    if won:
        game.crt.output("*** VICTORY ***", crawl=True)
        game.audio.trigger_event('success')
    else:
        game.crt.output("*** GAME OVER ***", crawl=True)
        game.audio.trigger_event('alert')
    game.crt.output(message, crawl=True)
    game.crt.output("=" * 50)
    game.crt.output(f"\nFinal Statistics:")
    game.crt.output(f"  Turns Survived: {game.turn}")
    living = len([m for m in game.crew if m.is_alive])
    game.crt.output(f"  Crew Remaining: {living}/{len(game.crew)}")
    game.crt.output("\nPress ENTER to exit...")
    try:
        input()
    except EOFError:
        pass


def _render_game_state(game):
    """Render the current game state to the terminal."""
    # Update CRT glitch based on paranoia
    game.crt.set_glitch_level(game.paranoia_level)

    player_room = game.station_map.get_room_name(*game.player.location)
    weather_status = game.weather.get_status()
    room_icons = game.room_states.get_status_icons(player_room)

    game.crt.output(f"\n[TURN {game.turn}] MODE: {game.mode.value} | TIME: {game.time_system.hour:02}:00 | TEMP: {game.temperature:.1f}C | POWER: {'ON' if game.power_on else 'OFF'}")
    game.crt.output(f"[LOC: {player_room}] {room_icons}")
    game.crt.output(f"[{weather_status}]")

    # Sabotage status
    if not game.sabotage.radio_operational or not game.sabotage.chopper_operational:
        game.crt.warning(game.sabotage.get_status())

    # Room modifiers
    room_desc = game.room_states.get_room_description_modifiers(player_room)
    if room_desc:
        game.crt.output(f">>> {room_desc}", crawl=True)

    room_items = game.station_map.get_items_in_room(*game.player.location)
    if room_items:
        item_list = ", ".join([str(i) for i in room_items])
        game.crt.output(f"[VISIBLE ITEMS]: {item_list}")

    # Agent 5 Map Rendering
    game.crt.output(game.renderer.render(game, game.player))


def _get_player_input(game):
    """Get and parse player input. Returns command list or None on EOF."""
    try:
        prompt = game.crt.prompt("CMD")
        user_input = input(prompt).strip()
        if not user_input:
            return []

        # Use CommandParser
        parsed = game.parser.parse(user_input)
        if not parsed:
            # Fallback to legacy
            cmd = user_input.upper().split()
        else:
            action = parsed['action']
            target = parsed.get('target')
            cmd = [action]
            if target:
                cmd.append(target)
            if parsed.get('args'):
                cmd.extend(parsed['args'])

        game.audio.trigger_event('success')
        return cmd
    except EOFError:
        return None


def _show_help(topic=None):
    """Display help information for commands."""
    help_topics = {
        "MOVEMENT": """
=== MOVEMENT ===
MOVE <DIR>    - Move in a direction (NORTH/SOUTH/EAST/WEST or N/S/E/W)
ADVANCE       - Pass time without moving
""",
        "COMBAT": """
=== COMBAT ===
ATTACK <NAME> - Attack a crew member (initiates combat with initiative rolls)
COVER [TYPE]  - Take cover (LIGHT/HEAVY/FULL or auto-select best)
RETREAT       - Attempt to flee from revealed Things
BREAK <DIR>   - Break through a barricade in the given direction
""",
        "SOCIAL": """
=== SOCIAL ===
TALK               - Hear dialogue from everyone in the room
LOOK <NAME>        - Observe a crew member for visual tells
INTERROGATE <NAME> [TOPIC] - Question someone
                     Topics: WHEREABOUTS, ALIBI, SUSPICION, BEHAVIOR, KNOWLEDGE
ACCUSE <NAME>      - Make a formal accusation (triggers crew vote)
""",
        "FORENSICS": """
=== FORENSICS ===
TEST <NAME>   - Perform blood test (requires Scalpel + Copper Wire)
HEAT          - Heat the wire during a test
APPLY         - Apply hot wire to blood sample
CANCEL        - Cancel current blood test
TAG <NAME> <CATEGORY> <NOTE> - Log forensic observation
                Categories: IDENTITY, TRUST, SUSPICION, BEHAVIOR
DOSSIER <NAME> - View forensic file on a crew member
LOG <ITEM>    - View chain of custody for an item
""",
        "INVENTORY": """
=== INVENTORY ===
INV / INVENTORY - View your inventory
GET <ITEM>      - Pick up an item from the room
DROP <ITEM>     - Drop an item in the room
""",
        "ENVIRONMENT": """
=== ENVIRONMENT ===
BARRICADE     - Barricade the current room (reinforces if already barricaded)
STATUS        - View all crew locations and health
TRUST <NAME>  - View trust matrix for a crew member
JOURNAL       - View MacReady's journal entries
""",
        "SYSTEM": """
=== SYSTEM ===
SAVE [SLOT]   - Save game (default: auto)
LOAD [SLOT]   - Load game (default: auto)
EXIT          - Quit the game
HELP [TOPIC]  - Show help (topics: MOVEMENT, COMBAT, SOCIAL, FORENSICS,
                           INVENTORY, ENVIRONMENT, SYSTEM)
""",
    }

    if topic and topic in help_topics:
        print(help_topics[topic])
    elif topic:
        print(f"Unknown help topic: {topic}")
        print("Available topics: " + ", ".join(help_topics.keys()))
    else:
        print("""
=== THE THING: COMMAND REFERENCE ===

Type HELP <TOPIC> for detailed help on a category.
Topics: MOVEMENT, COMBAT, SOCIAL, FORENSICS, INVENTORY, ENVIRONMENT, SYSTEM

--- QUICK REFERENCE ---
MOVE <DIR>         Move in a direction
LOOK <NAME>        Observe someone
TALK               Hear dialogue
INTERROGATE <NAME> Question someone
ATTACK <NAME>      Attack someone
TEST <NAME>        Blood test (need Scalpel + Wire)
BARRICADE          Barricade room
STATUS             View crew status
INV                View inventory
SAVE / LOAD        Save/load game
EXIT               Quit game
""")


def _execute_command(game, cmd):
    """Execute a parsed command. Returns False if game should exit."""
    if not cmd:
        return True

    player_room = game.station_map.get_room_name(*game.player.location)
    action = cmd[0]

    if action == "EXIT":
        return False

    elif action == "HELP":
        topic = cmd[1].upper() if len(cmd) > 1 else None
        _show_help(topic)

    elif action == "ADVANCE":
        game.advance_turn()
    elif action == "SAVE":
        slot = cmd[1] if len(cmd) > 1 else "auto"
        game.save_manager.save_game(game, slot)
    elif action == "LOAD":
        slot = cmd[1] if len(cmd) > 1 else "auto"
        data = game.save_manager.load_game(slot)
        if data:
            # Note: This modifies the local game variable but won't affect the caller
            # For a proper implementation, we'd need to return the new game state
            game.__dict__.update(GameState.from_dict(data).__dict__)
            print("*** GAME LOADED ***")
    elif action == "STATUS":
        for m in game.crew:
            status = "Alive" if m.is_alive else "DEAD"
            msg = f"{m.name} ({m.role}): Loc {m.location} | HP: {m.health} | {status}"
            avg_trust = game.trust_system.get_average_trust(m.name)
            msg += f" | Trust: {avg_trust:.1f}"
            print(msg)
    elif action == "TRUST":
        if len(cmd) < 2:
            print("Usage: TRUST <NAME>")
        else:
            target_name = cmd[1]
            print(f"--- TRUST MATRIX FOR {target_name.upper()} ---")
            for m in game.crew:
                if m.name in game.trust_system.matrix:
                    val = game.trust_system.matrix[m.name].get(target_name.title(), 50)
                    print(f"{m.name} -> {target_name.title()}: {val}")

    # --- FORENSIC COMMANDS ---
    elif action == "HEAT":
        print(game.blood_test_sim.heat_wire())
    elif action == "APPLY":
        if not game.blood_test_sim.active:
            print("No test in progress.")
        else:
            sample_name = game.blood_test_sim.current_sample
            subject = next((m for m in game.crew if m.name == sample_name), None)
            if subject:
                print(game.blood_test_sim.apply_wire(subject.is_infected))
    elif action == "CANCEL":
        print(game.blood_test_sim.cancel())

    # --- SOCIAL COMMANDS ---
    elif action == "TALK":
        for m in game.crew:
            room = game.station_map.get_room_name(*m.location)
            if room == player_room:
                print(f"{m.name}: {m.get_dialogue(game)}")

    elif action == "INTERROGATE" or action == "ASK":
        if len(cmd) < 2:
            print("Usage: INTERROGATE <NAME> [TOPIC]")
            print("Topics: WHEREABOUTS, ALIBI, SUSPICION, BEHAVIOR, KNOWLEDGE")
        else:
            target_name = cmd[1]
            target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)

            if not target:
                print(f"Unknown target: {target_name}")
            elif game.station_map.get_room_name(*target.location) != player_room:
                print(f"{target.name} is not here.")
            elif not target.is_alive:
                print(f"{target.name} cannot answer...")
            else:
                # Determine topic
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

                # Initialize interrogation system if needed
                if not hasattr(game, 'interrogation_system'):
                    game.interrogation_system = InterrogationSystem(game.rng)

                result = game.interrogation_system.interrogate(
                    game.player, target, topic, game
                )

                print(f"\n[INTERROGATION: {target.name} - {topic.value.upper()}]")
                print(f"\"{result.dialogue}\"")
                print(f"[Response: {result.response_type.value}]")

                if result.tells:
                    print("\n[OBSERVATION]")
                    for tell in result.tells:
                        print(f"  - {tell}")

                # Apply trust change
                game.trust_system.modify_trust(target.name, game.player.name, result.trust_change)
                if result.trust_change != 0:
                    change_str = f"+{result.trust_change}" if result.trust_change > 0 else str(result.trust_change)
                    print(f"[Trust: {change_str}]")

    elif action == "ACCUSE":
        if len(cmd) < 2:
            print("Usage: ACCUSE <NAME>")
            print("This makes a formal accusation against a crew member.")
            print("The crew will vote on whether to support your accusation.")
        else:
            target_name = cmd[1]
            target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)

            if not target:
                print(f"Unknown target: {target_name}")
            elif not target.is_alive:
                print(f"{target.name} is already dead.")
            else:
                # Gather evidence from forensic database
                evidence = []
                if hasattr(game, 'forensic_db'):
                    tags = game.forensic_db.tags.get(target.name, [])
                    evidence = [t for t in tags if t.get('category') == 'SUSPICION']

                print(f"\n[FORMAL ACCUSATION AGAINST {target.name.upper()}]")
                print(f"Evidence presented: {len(evidence)} item(s)")

                # Initialize interrogation system if needed
                if not hasattr(game, 'interrogation_system'):
                    game.interrogation_system = InterrogationSystem(game.rng)

                result = game.interrogation_system.make_accusation(
                    game.player, target, evidence, game
                )

                print(f"\nSupporters: {[s.name for s in result.supporters]}")
                print(f"Opposers: {[o.name for o in result.opposers]}")
                print(f"\n{result.outcome_message}")

                if result.supported:
                    # Activate lynch mob
                    game.lynch_mob.form_mob(target)
                    print(f"\n*** LYNCH MOB FORMED AGAINST {target.name.upper()}! ***")

    elif action == "LOOK":
        if len(cmd) < 2:
            print("Usage: LOOK <NAME>")
        else:
            target_name = cmd[1]
            target = next((m for m in game.crew if m.name.upper() == target_name), None)
            if target:
                if game.station_map.get_room_name(*target.location) == player_room:
                    print(target.get_description(game))
                else:
                    print(f"There is no {target_name} here.")
            else:
                print(f"Unknown crew member: {target_name}")
    elif action == "TAG":
        if len(cmd) < 3:
            print("Usage: TAG <NAME> <CATEGORY> <NOTE...>")
            print("Categories: IDENTITY, TRUST, SUSPICION, BEHAVIOR")
        else:
            target_name = cmd[1]
            category = cmd[2]
            note = " ".join(cmd[3:])
            target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
            if target:
                game.forensic_db.add_tag(target.name, category, note, game.turn)
                event_bus.emit(GameEvent(EventType.EVIDENCE_TAGGED, {"target": target.name, "game_state": game}))
                print(f"Logged forensic tag for {target.name} [{category}].")
            else:
                print(f"Unknown target: {target_name}")
    elif action == "LOG":
        if len(cmd) < 2:
            print("Usage: LOG <ITEM NAME>")
        else:
            item_name = " ".join(cmd[1:])
            print(game.evidence_log.get_history(item_name))
    elif action == "DOSSIER":
        if len(cmd) < 2:
            print("Usage: DOSSIER <NAME>")
        else:
            target_name = cmd[1]
            print(game.forensic_db.get_report(target_name))
    elif action == "JOURNAL":
        print("\n--- MACREADY'S JOURNAL ---")
        if not game.journal:
            print("(No direct diary entries - use DOSSIER for tags)")
        for entry in game.journal:
            print(entry)
        print("--------------------------")

    # --- SKILL CHECKS ---
    elif action == "CHECK":
        if len(cmd) < 2:
            print("Usage: CHECK <SKILL> (e.g., CHECK MELEE)")
        else:
            skill_name = cmd[1].title()
            try:
                skill_enum = next((s for s in Skill if s.value.upper() == skill_name.upper()), None)
                if skill_enum:
                    assoc_attr = Skill.get_attribute(skill_enum)
                    result = game.player.roll_check(assoc_attr, skill_enum, game.rng)
                    outcome = "SUCCESS" if result['success'] else "FAILURE"
                    print(f"Checking {skill_name} ({assoc_attr.value} + Skill)...")
                    print(f"Pool: {len(result['dice'])} dice -> {result['dice']}")
                    print(f"[{outcome}] ({result['success_count']} successes)")
                else:
                    print(f"Unknown skill: {skill_name}")
                    print("Available: " + ", ".join([s.value for s in Skill]))
            except Exception as e:
                print(f"Error resolving check: {e}")

    # --- INVENTORY COMMANDS ---
    elif action == "INVENTORY" or action == "INV":
        print(f"\n--- {game.player.name}'s INVENTORY ---")
        if not game.player.inventory:
            print("(Empty)")
        for item in game.player.inventory:
            print(f"- {item.name}: {item.description}")
    elif action == "GET":
        if len(cmd) < 2:
            print("Usage: GET <ITEM NAME>")
        else:
            item_name = " ".join(cmd[1:])
            found_item = game.station_map.remove_item_from_room(item_name, *game.player.location)
            if found_item:
                game.player.add_item(found_item, game.turn)
                game.evidence_log.record_event(found_item.name, "GET", game.player.name, player_room, game.turn)
                print(f"You picked up {found_item.name}.")
            else:
                print(f"You don't see '{item_name}' here.")
    elif action == "DROP":
        if len(cmd) < 2:
            print("Usage: DROP <ITEM NAME>")
        else:
            item_name = " ".join(cmd[1:])
            dropped_item = game.player.remove_item(item_name)
            if dropped_item:
                game.station_map.add_item_to_room(dropped_item, *game.player.location, game.turn)
                game.evidence_log.record_event(dropped_item.name, "DROP", game.player.name, player_room, game.turn)
                print(f"You dropped {dropped_item.name}.")
            else:
                print(f"You don't have '{item_name}'.")

    # --- COMBAT ---
    elif action == "ATTACK":
        if len(cmd) < 2:
            print("Usage: ATTACK <NAME>")
        else:
            target_name = cmd[1]
            target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
            if not target:
                print(f"Unknown target: {target_name}")
            elif game.station_map.get_room_name(*target.location) != player_room:
                print(f"{target.name} is not here.")
            elif not target.is_alive:
                print(f"{target.name} is already dead.")
            else:
                # Initialize combat system
                combat = CombatSystem(game.rng)

                # Roll initiative
                player_init = combat.roll_initiative(game.player)
                target_init = combat.roll_initiative(target)
                print(f"\n[COMBAT] Initiative: {game.player.name} ({player_init}) vs {target.name} ({target_init})")

                # Get weapons
                weapon = next((i for i in game.player.inventory if i.damage > 0), None)
                w_name = weapon.name if weapon else "Fists"

                # Get target's cover (if any)
                target_cover = getattr(game, 'combat_cover', {}).get(target.name, CoverType.NONE)

                print(f"Attacking {target.name} with {w_name}...")
                if target_cover != CoverType.NONE:
                    print(f"[COVER] {target.name} has {target_cover.value} cover!")

                result = combat.calculate_attack(game.player, target, weapon, target_cover)
                print(result.message)

                if result.success:
                    died = target.take_damage(result.damage)
                    if died:
                        print(f"*** {target.name} HAS DIED ***")
                        # Clear cover assignment
                        if hasattr(game, 'combat_cover') and target.name in game.combat_cover:
                            del game.combat_cover[target.name]

    elif action == "COVER":
        # Take cover in the current room
        if not hasattr(game, 'combat_cover'):
            game.combat_cover = {}

        combat = CombatSystem(game.rng)
        available = combat.get_available_cover(player_room)

        if len(cmd) > 1:
            # Specific cover type requested
            cover_type_name = cmd[1].upper()
            cover_map = {"LIGHT": CoverType.LIGHT, "HEAVY": CoverType.HEAVY, "FULL": CoverType.FULL, "NONE": CoverType.NONE}
            requested = cover_map.get(cover_type_name)
            if requested and requested in available:
                game.combat_cover[game.player.name] = requested
                print(f"You take {requested.value} cover behind nearby objects.")
                if requested == CoverType.FULL:
                    print("(You cannot attack while in Full cover)")
            elif requested == CoverType.NONE:
                if game.player.name in game.combat_cover:
                    del game.combat_cover[game.player.name]
                print("You leave cover.")
            else:
                print(f"That cover type is not available. Available: {[c.value for c in available]}")
        else:
            # Auto-assign best cover
            if available:
                best = max(available, key=lambda c: combat.COVER_BONUS[c])
                game.combat_cover[game.player.name] = best
                print(f"You take {best.value} cover behind nearby objects.")
                print(f"(+{combat.COVER_BONUS[best]} defense dice)")
            else:
                print("No cover available in this room!")

    elif action == "RETREAT":
        # Attempt to retreat from combat
        if not hasattr(game, 'combat_cover'):
            game.combat_cover = {}

        # Find hostile entities in the room
        hostiles = [m for m in game.crew
                   if m.is_alive and m.location == game.player.location
                   and getattr(m, 'is_revealed', False)]

        if not hostiles:
            print("There are no hostiles here to retreat from.")
        else:
            combat = CombatSystem(game.rng)
            exits = ["NORTH", "SOUTH", "EAST", "WEST"]

            # Check which exits are valid
            valid_exits = []
            dx_map = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
            for direction in exits:
                dx, dy = dx_map[direction]
                new_x = game.player.location[0] + dx
                new_y = game.player.location[1] + dy
                if game.station_map.is_walkable(new_x, new_y):
                    valid_exits.append(direction)

            success, message, exit_dir = combat.attempt_retreat(game.player, hostiles, valid_exits)
            print(message)

            if success:
                # Move player in that direction
                dx, dy = dx_map[exit_dir]
                game.player.move(dx, dy, game.station_map)
                print(f"You flee {exit_dir}!")
                # Clear cover
                if game.player.name in game.combat_cover:
                    del game.combat_cover[game.player.name]
                game.advance_turn()
            else:
                # Failed retreat - hostiles get free attacks
                print("[COMBAT] Hostiles get free attacks!")
                for hostile in hostiles:
                    free_result = combat.process_free_attack(hostile, game.player)
                    print(f"  {hostile.name}: {free_result.message}")
                    if free_result.success:
                        died = game.player.take_damage(free_result.damage)
                        if died:
                            print("*** YOU HAVE BEEN KILLED! ***")

    # --- MOVEMENT ---
    elif action == "MOVE":
        if len(cmd) < 2:
            print("Usage: MOVE <NORTH/SOUTH/EAST/WEST>")
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

            # Calculate target position and room
            new_x = game.player.location[0] + dx
            new_y = game.player.location[1] + dy

            if game.station_map.is_walkable(new_x, new_y):
                target_room = game.station_map.get_room_name(new_x, new_y)

                # Check if target room is barricaded
                if game.room_states.is_entry_blocked(target_room) and target_room != player_room:
                    strength = game.room_states.get_barricade_strength(target_room)
                    print(f"The {target_room} is barricaded! (Strength: {strength}/3)")
                    print("Use BREAK <DIRECTION> to force entry.")
                else:
                    game.player.location = (new_x, new_y)
                    print(f"You moved {direction}.")
                    game.advance_turn()
            else:
                print("Blocked.")

    elif action == "BREAK":
        if len(cmd) < 2:
            print("Usage: BREAK <DIRECTION>")
            print("Attempt to break through a barricade in the given direction.")
        else:
            direction = cmd[1].upper()
            dx, dy = 0, 0
            if direction in ["NORTH", "N"]:
                dy = -1
            elif direction in ["SOUTH", "S"]:
                dy = 1
            elif direction in ["EAST", "E"]:
                dx = 1
            elif direction in ["WEST", "W"]:
                dx = -1
            else:
                print(f"Invalid direction: {direction}")
                return True

            new_x = game.player.location[0] + dx
            new_y = game.player.location[1] + dy

            if game.station_map.is_walkable(new_x, new_y):
                target_room = game.station_map.get_room_name(new_x, new_y)

                if not game.room_states.is_entry_blocked(target_room):
                    print(f"There is no barricade blocking the {target_room}.")
                else:
                    print(f"You slam your body against the barricade...")
                    success, message, remaining = game.room_states.attempt_break_barricade(
                        target_room, game.player, game.rng, is_thing=False
                    )
                    print(message)

                    if success:
                        # Barricade broken - enter the room
                        game.player.location = (new_x, new_y)
                        print(f"You burst into the {target_room}!")

                    game.advance_turn()
            else:
                print("Nothing to break through in that direction.")

    # --- ENVIRONMENT ---
    elif action == "BARRICADE":
        result = game.room_states.barricade_room(player_room)
        print(result)
        game.advance_turn()

    # --- BLOOD TEST ---
    elif action == "TEST":
        if len(cmd) < 2:
            print("Usage: TEST <NAME>")
        else:
            target_name = cmd[1]
            target = next((m for m in game.crew if m.name.upper() == target_name.upper()), None)
            if not target:
                print(f"Unknown target: {target_name}")
            elif game.station_map.get_room_name(*target.location) != player_room:
                print(f"{target.name} is not here.")
            else:
                scalpel = next((i for i in game.player.inventory if "SCALPEL" in i.name.upper()), None)
                wire = next((i for i in game.player.inventory if "WIRE" in i.name.upper()), None)

                if not scalpel:
                    print("You need a SCALPEL to draw a blood sample.")
                elif not wire:
                    print("You need COPPER WIRE for the test.")
                else:
                    print(f"Drawing blood from {target.name}...")
                    print(game.blood_test_sim.start_test(target.name))
                    # Rapid heating and application
                    print(game.blood_test_sim.heat_wire())
                    print(game.blood_test_sim.heat_wire())
                    print(game.blood_test_sim.heat_wire())
                    print(game.blood_test_sim.heat_wire())

                    result = game.blood_test_sim.apply_wire(target.is_infected)
                    print(result)

                    if target.is_infected:
                        game.missionary_system.trigger_reveal(target, "Blood Test Exposure")
    else:
        print("Unknown command. Type HELP for a list of commands.")

    return True


if __name__ == "__main__":
    main()
