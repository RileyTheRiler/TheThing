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
from systems.architect import Difficulty, DifficultySettings, RandomnessEngine
from systems.combat import CombatSystem, CoverType, CombatEncounter
from systems.interrogation import InterrogationSystem, InterrogationTopic
from systems.commands import GameContext
from systems.statistics import stats
from audio.audio_manager import Sound
from ui.settings import settings, show_settings_menu
from ui.crt_effects import CRTOutput
from ui.title_screen import show_title_screen
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
STEALTH MECHANICS
-----------------
HIDE           - Attempt to hide in the current room
SNEAK <DIR>    - Move stealthily to avoid detection

Darkness and room conditions affect detection chances.
Use stealth to avoid confrontations or observe unnoticed.
""", "Continue..."),
        ("""
CRAFTING SYSTEM
---------------
CRAFT <RECIPE> - Combine items to create new tools

Crafting allows you to create useful items from components.
Check your inventory and experiment with combinations.
Some items require multiple turns to craft.
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


def _show_help(topic=None):
    """Display help information from command registry."""
    from core.command_registry import COMMAND_REGISTRY, get_commands_by_category, get_all_categories
    
    if topic:
        # Show commands for a specific category
        topic = topic.upper()
        commands = get_commands_by_category(topic)
        if commands:
            print(f"\n=== {topic} COMMANDS ===\n")
            for cmd in commands:
                print(f"{cmd.name:15} - {cmd.description}")
                if cmd.aliases:
                    print(f"{'':15}   Aliases: {', '.join(cmd.aliases)}")
                print(f"{'':15}   Usage: {cmd.usage}")
                print()
        else:
            print(f"Unknown help topic: {topic}")
            print("Available topics: " + ", ".join(get_all_categories()))
    else:
        # Show overview with all categories
        print("""
=== THE THING: COMMAND REFERENCE ===

Commands are organized by category. Use HELP <CATEGORY> for details.
For example: HELP MOVEMENT, HELP COMBAT, HELP FORENSICS

Available Categories:
""")
        categories = get_all_categories()
        for category in categories:
            commands = get_commands_by_category(category)
            cmd_names = [cmd.name for cmd in commands[:5]]  # Show first 5
            more = f" (+{len(commands)-5} more)" if len(commands) > 5 else ""
            print(f"  {category:12} - {', '.join(cmd_names)}{more}")
        
        print("\nType HELP <CATEGORY> for detailed command information.")


def main():
    """Main game loop - can be called from launcher or run directly."""
    # Set up readline for command history (arrow keys, history file)
    _setup_readline()

    # Show title screen first
    temp_crt = CRTOutput(palette="green")
    temp_rng = RandomnessEngine()

    menu_choice = show_title_screen(temp_crt, temp_rng)

    # Handle menu selection
    if menu_choice == 3:  # TERMINATE
        print("\n\033[38;5;46mSystem terminated. Goodbye.\033[0m\n")
        return
    elif menu_choice == 1:  # ACCESS RECORDS
        print("\n\033[38;5;46m[ACCESS DENIED] Personnel records are classified.\033[0m")
        print("\033[38;5;46mPress ENTER to continue...\033[0m")
        try:
            input()
        except EOFError:
            pass
        # Return to main menu by recursing
        return main()
    elif menu_choice == 2:  # SYSTEM CONFIG
        print("\n\033[38;5;46m[SYSTEM CONFIG] This option will be available in a future update.\033[0m")
        print("\033[38;5;46mPress ENTER to continue...\033[0m")
        try:
            input()
        except EOFError:
            pass
        # Return to main menu by recursing
        return main()

    # menu_choice == 0: BEGIN SIMULATION
    # Continue with game setup

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

    # Start statistics tracking (Tier 6.4)
    stats.start_session(difficulty.value)

    # Apply saved settings (palette, text speed, audio)
    settings.apply_to_game(game)

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
    # Determine outcome for statistics
    if won:
        outcome = "victory"
    elif game.player and not game.player.is_alive:
        outcome = "death"
    elif game.player and game.player.is_infected:
        outcome = "infection"
    else:
        outcome = "quit"

    # End statistics session
    stats.end_session(outcome, game.turn)

    game.crt.output("\n" + "=" * 50)
    if won:
        game.crt.output("*** VICTORY ***", crawl=True)
        game.audio.trigger_event('success')
    else:
        game.crt.output("*** GAME OVER ***", crawl=True)
        game.audio.trigger_event('alert')
    game.crt.output(message, crawl=True)
    game.crt.output("=" * 50)

    # Session statistics
    game.crt.output(f"\nSession Statistics:")
    game.crt.output(f"  Turns Survived: {game.turn}")
    living = len([m for m in game.crew if m.is_alive])
    game.crt.output(f"  Crew Remaining: {living}/{len(game.crew)}")

    if stats.current_session:
        s = stats.current_session
        game.crt.output(f"  Things Killed: {s.things_killed}")
        game.crt.output(f"  Blood Tests: {s.blood_tests_performed}")

    # Career highlights
    game.crt.output(f"\nCareer: {stats.career.victories} victories / {stats.career.total_games} games")

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

        # Single-key shortcuts (roguelike style)
        if len(user_input) == 1:
            shortcuts = {
                'i': 'INVENTORY',
                's': 'STATUS',
                '?': 'HELP',
                '.': 'ADVANCE',
                ',': 'GET',  # Context: will list items if multiple
                ';': 'LOOK',  # Look around
                'w': 'MOVE NORTH',
                'a': 'MOVE WEST',
                'd': 'MOVE EAST',
            }

            if user_input.lower() in shortcuts:
                expanded = shortcuts[user_input.lower()]
                game.crt.output(f"[{expanded}]", crawl=False)
                user_input = expanded

        # Store original input for feedback comparison
        original_input = user_input.upper()

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

            # Show command feedback if parser transformed the input
            # (e.g., fuzzy matching, synonyms, natural language)
            if parsed.get('raw') and parsed['raw'] != original_input:
                interpreted_cmd = ' '.join(cmd)
                if interpreted_cmd != original_input:
                    game.crt.output(f"→ {interpreted_cmd}", crawl=False)

        game.audio.trigger_event('success')
        return cmd
    except EOFError:
        return None


def _show_help(topic=None):
    """Display help information from command registry."""
    from core.command_registry import COMMAND_REGISTRY, get_commands_by_category, get_all_categories
    
    if topic:
        # Show commands for a specific category
        topic = topic.upper()
        commands = get_commands_by_category(topic)
        if commands:
            print(f"\n=== {topic} COMMANDS ===\n")
            for cmd in commands:
                print(f"{cmd.name:15} - {cmd.description}")
                if cmd.aliases:
                    print(f"{'':15}   Aliases: {', '.join(cmd.aliases)}")
                print(f"{'':15}   Usage: {cmd.usage}")
                print()
        else:
            print(f"Unknown help topic: {topic}")
            print("Available topics: " + ", ".join(get_all_categories()))
    else:
        # Show overview with all categories
        print("""
=== THE THING: COMMAND REFERENCE ===

Commands are organized by category. Use HELP <CATEGORY> for details.
For example: HELP MOVEMENT, HELP COMBAT, HELP FORENSICS

Available Categories:
""")
        categories = get_all_categories()
        for category in categories:
            commands = get_commands_by_category(category)
            cmd_names = [cmd.name for cmd in commands[:5]]  # Show first 5
            more = f" (+{len(commands)-5} more)" if len(commands) > 5 else ""
            print(f"  {category:12} - {', '.join(cmd_names)}{more}")
        
        print("\nType HELP <CATEGORY> for detailed command information.")


def _execute_command(game, cmd):
    """Execute a parsed command. Returns False if game should exit."""
    if not cmd:
        return True

    player_room = game.station_map.get_room_name(*game.player.location)
    
    # Use the CommandParser if available (Unified Command Handling)
    if hasattr(game.parser, 'parse_and_execute'):
        # Ensure context is set
        context = GameContext(game)
        game.parser.execute(cmd, context)
        return True

    # FALLBACK for legacy or direct handling if parser fails/missing
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
         game.save_manager.load_game(slot)
    
    # ... (Most other logic is now handled by parser.execute)
    # Keeping minimal fallback or specific debug commands if needed
    
    # Re-enable loop for legacy structure if parser wasn't enough?
    # Actually, let's trust the parser. The parser should handle EVERYTHING in commands.py
    
    return True
                        "SUSPICION": InterrogationTopic.SUSPICION,
                        "BEHAVIOR": InterrogationTopic.BEHAVIOR,
                        "KNOWLEDGE": InterrogationTopic.KNOWLEDGE
                    }
                    topic = topic_map.get(topic_name, InterrogationTopic.WHEREABOUTS)
                else:
                    topic = InterrogationTopic.WHEREABOUTS

                # Initialize interrogation system if needed
                if not hasattr(game, 'interrogation_system'):
                    game.interrogation_system = InterrogationSystem(game.rng, game.room_states)

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
                    game.interrogation_system = InterrogationSystem(game.rng, game.room_states)

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
                combat = CombatSystem(game.rng, game.room_states)

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

                result = combat.calculate_attack(
                    game.player,
                    target,
                    weapon,
                    target_cover,
                    player_room,
                    game
                )
                print(result.message)

                if result.success:
                    died = target.take_damage(result.damage, game_state=game)
                    if died:
                        print(f"*** {target.name} HAS DIED ***")
                        # Clear cover assignment
                        if hasattr(game, 'combat_cover') and target.name in game.combat_cover:
                            del game.combat_cover[target.name]

    elif action == "COVER":
        # Take cover in the current room
        if not hasattr(game, 'combat_cover'):
            game.combat_cover = {}

        combat = CombatSystem(game.rng, game.room_states)
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
            combat = CombatSystem(game.rng, game.room_states)
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
                    free_result = combat.process_free_attack(hostile, game.player, room_name=player_room)
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

    # --- ALTERNATIVE ENDINGS (Tier 6.3) ---
    elif action == "REPAIR":
        if cmd[1:] and "HELICOPTER" in " ".join(cmd[1:]).upper():
             print(game.attempt_repair_helicopter())
        else:
            # Default behavior if specific object not mentioned, try to infer context or fail
            # For now, only helicopter needs specific repair action
            print(game.attempt_repair_helicopter())
        game.advance_turn()

    elif action == "SIGNAL":
        print(game.attempt_radio_signal())
        game.advance_turn()

    elif action == "ESCAPE":
        print(game.attempt_escape())
        # The win condition check in main loop will catch the status change
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
                    print("Sample prepared. Use HEAT to heat the wire, then APPLY.")
    else:
        print("Unknown command. Type HELP for a list of commands.")
        # Suggest correction if available
        suggestion = game.parser.suggest_correction(' '.join(cmd))
        if suggestion:
            print(suggestion)

    return True


if __name__ == "__main__":
    main()
