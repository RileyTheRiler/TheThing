from abc import ABC, abstractmethod
from typing import List, Dict, Optional, TYPE_CHECKING
from core.resolution import Attribute, Skill

if TYPE_CHECKING:
    from engine import GameState, CrewMember

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
    def execute(self, game_state: 'GameState', args: List[str]) -> None:
        pass

class MoveCommand(Command):
    name = "MOVE"
    aliases = ["N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST"]
    description = "Move in a direction."

    def execute(self, game_state: 'GameState', args: List[str]) -> None:
        direction = args[0] if args else None

        # Handle alias direction
        if not direction:
             # If command was alias (e.g. "N"), we need to know what triggered it.
             # This design assumes args[0] is the direction.
             pass

        # We will need to pass the full command string or handle aliases in Dispatcher
        # For now, let's assume args[0] is the direction if provided, otherwise fail

        # Actually, let's redesign slightly: Dispatcher should normalize aliases.
        # But wait, if I type "N", the command is "N".

        # Let's trust the args.
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

    def execute(self, game_state: 'GameState', args: List[str]) -> None:
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

    def execute(self, game_state: 'GameState', args: List[str]) -> None:
        print(f"\n--- {game_state.player.name}'s INVENTORY ---")
        if not game_state.player.inventory:
            print("(Empty)")
        for item in game_state.player.inventory:
            print(f"- {item.name}: {item.description}")

class GetCommand(Command):
    name = "GET"
    aliases = []
    description = "Pick up an item."

    def execute(self, game_state: 'GameState', args: List[str]) -> None:
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

    def execute(self, game_state: 'GameState', args: List[str]) -> None:
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

    def execute(self, game_state: 'GameState', args: List[str]) -> None:
        if not args:
            print("Usage: ATTACK <NAME>")
            return

        target_name = args[0]
        target = next((m for m in game_state.crew if m.name.upper() == target_name.upper()), None)
        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if not target:
            print(f"Unknown target: {target_name}")
        elif game_state.station_map.get_room_name(*target.location) != player_room:
            print(f"{target.name} is not here.")
        elif not target.is_alive:
            print(f"{target.name} is already dead.")
        else:
            weapon = next((i for i in game_state.player.inventory if i.damage > 0), None)
            w_name = weapon.name if weapon else "Fists"
            w_skill = weapon.weapon_skill if weapon else Skill.MELEE
            w_dmg = weapon.damage if weapon else 0

            print(f"Attacking {target.name} with {w_name}...")
            att_attr = Skill.get_attribute(w_skill)
            att_res = game_state.player.roll_check(att_attr, w_skill, game_state.rng)

            def_skill = Skill.MELEE
            def_attr = Attribute.PROWESS

            def_res = target.roll_check(def_attr, def_skill, game_state.rng)

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

class TagCommand(Command):
    name = "TAG"
    aliases = []
    description = "Tag a character with forensic notes."

    def execute(self, game_state: 'GameState', args: List[str]) -> None:
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

    def execute(self, game_state: 'GameState', args: List[str]) -> None:
        if not args:
            print("Usage: LOG <ITEM NAME>")
            return

        item_name = " ".join(args)
        print(game_state.evidence_log.get_history(item_name))

class DossierCommand(Command):
    name = "DOSSIER"
    aliases = []
    description = "View forensic dossier for a character."

    def execute(self, game_state: 'GameState', args: List[str]) -> None:
        if not args:
            print("Usage: DOSSIER <NAME>")
            return

        target_name = args[0]
        print(game_state.forensic_db.get_report(target_name))

class TestCommand(Command):
    name = "TEST"
    aliases = []
    description = "Perform a blood test."

    def execute(self, game_state: 'GameState', args: List[str]) -> None:
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

    def register(self, command: Command):
        self.commands[command.name] = command
        for alias in command.aliases:
            self.commands[alias] = command

    def dispatch(self, action: str, args: List[str], game_state: 'GameState') -> bool:
        command = self.commands.get(action.upper())
        if command:
            # Special handling for aliases that are implicit args (like "N" -> "MOVE N")
            # In my current design, "N" maps to MoveCommand.
            # But MoveCommand expects args[0] to be direction.
            # So if I type "N", action="N", args=[].
            # MoveCommand.execute needs to handle this or I preprocess here.

            # Let's adjust MoveCommand logic or preprocess.
            # If I map "N" to MoveCommand, inside MoveCommand I don't know I was called via "N".
            # Unless I pass the action name too.

            # Let's normalize args for MOVE aliases.
            if action.upper() in ["N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST"]:
                args = [action.upper()]

            command.execute(game_state, args)
            return True
        return False
