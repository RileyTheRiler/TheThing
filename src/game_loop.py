"""Main game loop for The Thing game."""

from core.resolution import Attribute, Skill
from core.event_system import event_bus, EventType, GameEvent
from systems.architect import Difficulty, DifficultySettings
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


def main():
    """Main game loop - can be called from launcher or run directly."""
    # Select difficulty before starting
    difficulty = _select_difficulty()
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


def _execute_command(game, cmd):
    """Execute a parsed command. Returns False if game should exit."""
    if not cmd:
        return True

    player_room = game.station_map.get_room_name(*game.player.location)
    action = cmd[0]

    if action == "EXIT":
        return False
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
                weapon = next((i for i in game.player.inventory if i.damage > 0), None)
                w_name = weapon.name if weapon else "Fists"
                w_skill = weapon.weapon_skill if weapon else Skill.MELEE
                w_dmg = weapon.damage if weapon else 0

                print(f"Attacking {target.name} with {w_name}...")
                att_attr = Skill.get_attribute(w_skill)
                att_res = game.player.roll_check(att_attr, w_skill, game.rng)

                def_skill = Skill.MELEE
                def_attr = Attribute.PROWESS

                def_res = target.roll_check(def_attr, def_skill, game.rng)

                print(f"Attack: {att_res['success_count']} vs Defense: {def_res['success_count']}")

                if att_res['success_count'] > def_res['success_count']:
                    net_hits = att_res['success_count'] - def_res['success_count']
                    total_dmg = w_dmg + net_hits
                    died = target.take_damage(total_dmg)
                    print(f"HIT! Dealt {total_dmg} damage.")
                    if died:
                        print(f"*** {target.name} HAS DIED ***")
                else:
                    print("MISS/BLOCKED!")

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

            if game.player.move(dx, dy, game.station_map):
                print(f"You moved {direction}.")
                game.advance_turn()
            else:
                print("Blocked.")

    # --- ENVIRONMENT ---
    elif action == "BARRICADE":
        result = game.room_states.barricade_room(player_room)
        print(result)

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
        print("Unknown command. Try: MOVE, LOOK, GET, DROP, USE, INV, TAG, TEST, HEAT, APPLY, ATTACK, STATUS, SAVE, LOAD, EXIT")

    return True


if __name__ == "__main__":
    main()
