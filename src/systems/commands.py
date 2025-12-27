import sys
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass
from core.resolution import Attribute, Skill
from core.event_system import event_bus, EventType, GameEvent

if TYPE_CHECKING:
    from engine import GameState, CrewMember

@dataclass
class GameContext:
    game: 'GameState'

class Command(ABC):
    """Base class for all game commands."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def aliases(self) -> List[str]:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def execute(self, context: GameContext, args: List[str]) -> None:
        pass

class MoveCommand(Command):
    name = "MOVE"
    aliases = ["N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST"]
    description = "Move in a direction."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        direction = args[0] if args else None

        # Handle alias direction
        if not direction:
             pass

        if not args:
             print("Usage: MOVE <NORTH/SOUTH/EAST/WEST>")
             return

        direction = args[0].upper()
        dx, dy = 0, 0
        if direction in ["NORTH", "N"]: dy = -1
        elif direction in ["SOUTH", "S"]: dy = 1
        elif direction in ["EAST", "E"]: dx = 1
        elif direction in ["WEST", "W"]: dx = -1

        if game_state.player.move(dx, dy, game_state.station_map):
            print(f"You moved {direction}.")
            game_state.advance_turn()
        else:
            print("Blocked.")

class LookCommand(Command):
    name = "LOOK"
    aliases = []
    description = "Look at a character or object."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            print("Usage: LOOK <NAME>")
            return

        target_name = args[0].upper()
        target = next((m for m in game_state.crew if m.name.upper() == target_name), None)

        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if target:
            if game_state.station_map.get_room_name(*target.location) == player_room:
                print(target.get_description(game_state))
            else:
                print(f"There is no {target_name} here.")
        else:
            print(f"Unknown target: {target_name}")

class InventoryCommand(Command):
    name = "INVENTORY"
    aliases = ["INV"]
    description = "Check your inventory."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        print(f"\n--- {game_state.player.name}'s INVENTORY ---")
        if not game_state.player.inventory:
            print("(Empty)")
        for item in game_state.player.inventory:
            print(f"- {item.name}: {item.description}")

class GetCommand(Command):
    name = "GET"
    aliases = []
    description = "Pick up an item."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            print("Usage: GET <ITEM NAME>")
            return

        item_name = " ".join(args)
        found_item = game_state.station_map.remove_item_from_room(item_name, *game_state.player.location)
        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if found_item:
            game_state.player.add_item(found_item, game_state.turn)
            game_state.evidence_log.record_event(found_item.name, "GET", game_state.player.name, player_room, game_state.turn)
            print(f"You picked up {found_item.name}.")
        else:
            print(f"You don't see '{item_name}' here.")

class DropCommand(Command):
    name = "DROP"
    aliases = []
    description = "Drop an item."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            print("Usage: DROP <ITEM NAME>")
            return

        item_name = " ".join(args)
        dropped_item = game_state.player.remove_item(item_name)
        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if dropped_item:
            game_state.station_map.add_item_to_room(dropped_item, *game_state.player.location, game_state.turn)
            game_state.evidence_log.record_event(dropped_item.name, "DROP", game_state.player.name, player_room, game_state.turn)
            print(f"You dropped {dropped_item.name}.")
        else:
            print(f"You don't have '{item_name}'.")

class AttackCommand(Command):
    name = "ATTACK"
    aliases = []
    description = "Attack a target."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: ATTACK <NAME>"}))
            return

        target_name = args[0]
        target = next((m for m in game_state.crew if m.name.upper() == target_name.upper()), None)
        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if not target:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": f"Unknown target: {target_name}"}))
        elif game_state.station_map.get_room_name(*target.location) != player_room:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"{target.name} is not here."}))
        elif not target.is_alive:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"{target.name} is already dead."}))
        else:
            weapon = next((i for i in game_state.player.inventory if i.damage > 0), None)
            w_name = weapon.name if weapon else "Fists"
            w_skill = weapon.weapon_skill if weapon else Skill.MELEE
            w_dmg = weapon.damage if weapon else 0

            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"Attacking {target.name} with {w_name}..."
            }))
            att_attr = Skill.get_attribute(w_skill)
            att_res = game_state.player.roll_check(att_attr, w_skill, game_state.rng)

            def_skill = Skill.MELEE
            def_attr = Attribute.PROWESS

            def_res = target.roll_check(def_attr, def_skill, game_state.rng)

            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                "text": f"Attack: {att_res['success_count']} vs Defense: {def_res['success_count']}"
            }))

            if att_res['success_count'] > def_res['success_count']:
                net_hits = att_res['success_count'] - def_res['success_count']
                total_dmg = w_dmg + net_hits
                died = target.take_damage(total_dmg)
                event_bus.emit(GameEvent(EventType.ATTACK_RESULT, {
                    "attacker": game_state.player.name,
                    "target": target.name,
                    "weapon": w_name,
                    "hit": True,
                    "damage": total_dmg,
                    "killed": died
                }))
            else:
                event_bus.emit(GameEvent(EventType.ATTACK_RESULT, {
                    "attacker": game_state.player.name,
                    "target": target.name,
                    "weapon": w_name,
                    "hit": False,
                    "damage": 0,
                    "killed": False
                }))

class TagCommand(Command):
    name = "TAG"
    aliases = []
    description = "Tag a character with forensic notes."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if len(args) < 3:
            print("Usage: TAG <NAME> <CATEGORY> <NOTE...>")
            print("Categories: IDENTITY, TRUST, SUSPICION, BEHAVIOR")
            return

        target_name = args[0]
        category = args[1]
        note = " ".join(args[2:])
        target = next((m for m in game_state.crew if m.name.upper() == target_name.upper()), None)

        if target:
            game_state.forensic_db.add_tag(target.name, category, note, game_state.turn)
            # Emit Event for Social System to lower trust
            from core.event_system import event_bus, EventType, GameEvent
            event_bus.emit(GameEvent(EventType.EVIDENCE_TAGGED, {"target": target.name, "game_state": game_state}))
            print(f"Logged forensic tag for {target.name} [{category}].")
        else:
            print(f"Unknown target: {target_name}")

class LogCommand(Command):
    name = "LOG"
    aliases = []
    description = "Check evidence log for an item."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            print("Usage: LOG <ITEM NAME>")
            return

        item_name = " ".join(args)
        print(game_state.evidence_log.get_history(item_name))

class DossierCommand(Command):
    name = "DOSSIER"
    aliases = []
    description = "View forensic dossier for a character."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            print("Usage: DOSSIER <NAME>")
            return

        target_name = args[0]
        print(game_state.forensic_db.get_report(target_name))

class TestCommand(Command):
    name = "TEST"
    aliases = []
    description = "Perform a blood test."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            print("Usage: TEST <NAME>")
            return

        target_name = args[0]
        player_room = game_state.station_map.get_room_name(*game_state.player.location)
        target = next((m for m in game_state.crew if m.name.upper() == target_name.upper()), None)

        if not target:
            print(f"Unknown target: {target_name}")
        elif game_state.station_map.get_room_name(*target.location) != player_room:
            print(f"{target.name} is not here.")
        else:
            # Check for required items
            scalpel = next((i for i in game_state.player.inventory if "SCALPEL" in i.name.upper()), None)
            wire = next((i for i in game_state.player.inventory if "WIRE" in i.name.upper()), None)

            if not scalpel:
                print("You need a SCALPEL to draw a blood sample.")
            elif not wire:
                print("You need COPPER WIRE for the test.")
            else:
                print(f"Drawing blood from {target.name}...")
                print(game_state.blood_test_sim.start_test(target.name))
                # Rapid heating and application
                print(game_state.blood_test_sim.heat_wire())
                print(game_state.blood_test_sim.heat_wire())
                print(game_state.blood_test_sim.heat_wire())
                print(game_state.blood_test_sim.heat_wire())

                result = game_state.blood_test_sim.apply_wire(target.is_infected)
                print(result)

                if target.is_infected:
                    # Reveal infection!
                    game_state.missionary_system.trigger_reveal(target, "Blood Test Exposure")

class TalkCommand(Command):
    name = "TALK"
    aliases = []
    description = "Talk to crew members in the room."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        player_room = game_state.station_map.get_room_name(*game_state.player.location)
        for m in game_state.crew:
            room = game_state.station_map.get_room_name(*m.location)
            if room == player_room: # Only talk to people in the same room
                print(f"{m.name}: {m.get_dialogue(game_state)}")

class BarricadeCommand(Command):
    name = "BARRICADE"
    aliases = []
    description = "Barricade the current room."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        player_room = game_state.station_map.get_room_name(*game_state.player.location)
        game_state.room_states.barricade_room(player_room)

class JournalCommand(Command):
    name = "JOURNAL"
    aliases = []
    description = "Read MacReady's journal."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        print("\n--- MACREADY'S JOURNAL ---")
        if not game_state.journal:
            print("(No direct diary entries - use DOSSIER for tags)")
        for entry in game_state.journal:
            print(entry)
        print("--------------------------")

class StatusCommand(Command):
    name = "STATUS"
    aliases = []
    description = "Check crew status and trust."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        for m in game_state.crew:
            status = "Alive" if m.is_alive else "DEAD"
            msg = f"{m.name} ({m.role}): Loc {m.location} | HP: {m.health} | {status}"
            avg_trust = game_state.trust_system.get_average_trust(m.name)
            msg += f" | Trust: {avg_trust:.1f}"
            print(msg)

class SaveCommand(Command):
    name = "SAVE"
    aliases = []
    description = "Save the game."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        slot = args[0] if args else "auto"
        game_state.save_manager.save_game(game_state, slot)

class LoadCommand(Command):
    name = "LOAD"
    aliases = []
    description = "Load a saved game."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        slot = args[0] if args else "auto"
        data = game_state.save_manager.load_game(slot)
        if data:
            # 1. Cleanup old game state (unsubscribe events)
            if hasattr(game_state, 'cleanup'):
                game_state.cleanup()

            # 2. Create new game state
            # Note: We need a way to create it. Assuming GameState.from_dict exists.
            from engine import GameState # Import locally to avoid circular dep at module level if any
            new_game = GameState.from_dict(data)

            # 3. Replace in context
            context.game = new_game
            print("*** GAME LOADED ***")

class AdvanceCommand(Command):
    name = "ADVANCE"
    aliases = []
    description = "Wait and advance time."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        game_state.advance_turn()

class ExitCommand(Command):
    name = "EXIT"
    aliases = ["QUIT"]
    description = "Exit the game."

    def execute(self, context: GameContext, args: List[str]) -> None:
        print("Exiting...")
        sys.exit(0)

class TrustCommand(Command):
    name = "TRUST"
    aliases = []
    description = "Check trust matrix for a character."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            print("Usage: TRUST <NAME>")
            return

        target_name = args[0]
        print(f"--- TRUST MATRIX FOR {target_name.upper()} ---")
        for m in game_state.crew:
            if m.name in game_state.trust_system.matrix:
                val = game_state.trust_system.matrix[m.name].get(target_name.title(), 50)
                print(f"{m.name} -> {target_name.title()}: {val}")

class CheckCommand(Command):
    name = "CHECK"
    aliases = []
    description = "Perform a skill check."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            print("Usage: CHECK <SKILL> (e.g., CHECK MELEE)")
            return

        skill_name = args[0].title()
        try:
            skill_enum = next((s for s in Skill if s.value.upper() == skill_name.upper()), None)
            if skill_enum:
                assoc_attr = Skill.get_attribute(skill_enum)
                result = game_state.player.roll_check(assoc_attr, skill_enum, game_state.rng)
                outcome = "SUCCESS" if result['success'] else "FAILURE"
                print(f"Checking {skill_name} ({assoc_attr.value} + Skill)...")
                print(f"Pool: {len(result['dice'])} dice -> {result['dice']}")
                print(f"[{outcome}] ({result['success_count']} successes)")
            else:
                print(f"Unknown skill: {skill_name}")
                print("Available: " + ", ".join([s.value for s in Skill]))
        except Exception as e:
            print(f"Error resolving check: {e}")

class CommandDispatcher:
    def __init__(self):
        self.commands: Dict[str, Command] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(MoveCommand())
        self.register(LookCommand())
        self.register(InventoryCommand())
        self.register(GetCommand())
        self.register(DropCommand())
        self.register(AttackCommand())
        self.register(TagCommand())
        self.register(LogCommand())
        self.register(DossierCommand())
        self.register(TestCommand())
        self.register(TalkCommand())
        self.register(BarricadeCommand())
        self.register(JournalCommand())
        self.register(StatusCommand())
        self.register(SaveCommand())
        self.register(LoadCommand())
        self.register(AdvanceCommand())
        self.register(ExitCommand())
        self.register(TrustCommand())
        self.register(CheckCommand())

    def register(self, command: Command):
        self.commands[command.name] = command
        for alias in command.aliases:
            self.commands[alias] = command

    def dispatch(self, action: str, args: List[str], context: GameContext) -> bool:
        command = self.commands.get(action.upper())
        if command:
            # Special handling for aliases that are implicit args (like "N" -> "MOVE N")
            if action.upper() in ["N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST"]:
                args = [action.upper()]

            command.execute(context, args)
            return True
        return False
