import sys
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass
from core.resolution import Attribute, Skill
from core.event_system import event_bus, EventType, GameEvent
<<<<<<< HEAD
from ui.message_reporter import emit_message, emit_warning, emit_combat, emit_dialogue
=======
from systems.interrogation import InterrogationSystem, InterrogationTopic
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503

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


def _get_blood_test_sim(game_state):
    """Return the active blood test simulator, supporting legacy attributes."""
    if hasattr(game_state, 'blood_test_sim'):
        return game_state.blood_test_sim
    if hasattr(game_state, 'forensics') and hasattr(game_state.forensics, 'blood_test'):
        game_state.blood_test_sim = game_state.forensics.blood_test
        return game_state.blood_test_sim
    raise AttributeError("Game state missing blood test simulator")

class MoveCommand(Command):
    name = "MOVE"
    aliases = ["N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST"]
    description = "Move in a direction."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        direction = args[0] if args else None

        if not direction:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": "Usage: MOVE <NORTH/SOUTH/EAST/WEST>"
            }))
            return

        direction = direction.upper()
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
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": f"Invalid direction: {direction}"
            }))
            return

        if game_state.player.move(dx, dy, game_state.station_map):
<<<<<<< HEAD
            event_bus.emit(GameEvent(EventType.MOVEMENT, {
                "actor": game_state.player.name,
                "direction": direction,
                "destination": game_state.station_map.get_room_name(*game_state.player.location)
            }))
            game_state.advance_turn()
        else:
            emit_message("Path blocked.")
=======
            destination = game_state.station_map.get_room_name(*game_state.player.location)
            event_bus.emit(GameEvent(EventType.MOVEMENT, {
                "actor": getattr(game_state.player, "name", "You"),
                "direction": direction,
                "destination": destination
            }))
            game_state.advance_turn()
        else:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": "Blocked."}))
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503

class LookCommand(Command):
    name = "LOOK"
    aliases = []
    description = "Look at a character or object."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: LOOK <NAME>"}))
            return

        target_name = args[0].upper()
        target = next((m for m in game_state.crew if m.name.upper() == target_name), None)

        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if target:
            if game_state.station_map.get_room_name(*target.location) == player_room:
<<<<<<< HEAD
                emit_message(target.get_description(game_state))
            else:
                emit_message(f"There is no {target_name} here.")
        else:
            emit_message(f"Unknown target: {target_name}")
=======
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": target.get_description(game_state)
                }))
            else:
                event_bus.emit(GameEvent(EventType.WARNING, {
                    "text": f"There is no {target_name} here."
                }))
        else:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"Unknown target: {target_name}"
            }))
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503

class InventoryCommand(Command):
    name = "INVENTORY"
    aliases = ["INV"]
    description = "Check your inventory."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        emit_message(f"--- {game_state.player.name}'s INVENTORY ---")
        if not game_state.player.inventory:
            emit_message("(Empty)")
        for item in game_state.player.inventory:
            emit_message(f"- {item.name}: {item.description}")

class CraftCommand(Command):
    name = "CRAFT"
    aliases = []
    description = "Craft an item from known recipes."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not hasattr(game_state, "crafting_system"):
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Crafting system unavailable."}))
            return

        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: CRAFT <RECIPE_ID>"}))
            return

        recipe_id = args[0]
        success = game_state.crafting_system.queue_craft(
            game_state.player,
            recipe_id,
            game_state,
            game_state.player.inventory,
        )
        if success:
            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                "text": f"Queued crafting for recipe '{recipe_id}'."
            }))

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
            event_bus.emit(GameEvent(EventType.ITEM_PICKUP, {
                "actor": game_state.player.name,
                "item": found_item.name
            }))
        else:
            emit_message(f"You don't see '{item_name}' here.")

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
            event_bus.emit(GameEvent(EventType.ITEM_DROP, {
                "actor": game_state.player.name,
                "item": dropped_item.name
            }))
        else:
            emit_message(f"You don't have '{item_name}'.")

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
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"Unknown target: {target_name}"
            }))
        elif game_state.station_map.get_room_name(*target.location) != player_room:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"{target.name} is not here."
            }))
        elif not target.is_alive:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"{target.name} is already dead."
            }))
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

<<<<<<< HEAD
            emit_message(f"Attacking {target.name} with {w_name}...")
=======
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"Attacking {target.name} with {w_name}..."
            }))
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503
            att_attr = Skill.get_attribute(w_skill)
            att_res = game_state.player.roll_check(att_attr, w_skill, game_state.rng)

            def_skill = Skill.MELEE
            def_attr = Attribute.PROWESS

            def_res = target.roll_check(def_attr, def_skill, game_state.rng)

<<<<<<< HEAD
            emit_message(f"Attack: {att_res['success_count']} vs Defense: {def_res['success_count']}")

            hit = att_res['success_count'] > def_res['success_count']
            damage = 0
            killed = False
            
            if hit:
                net_hits = att_res['success_count'] - def_res['success_count']
                damage = w_dmg + net_hits
                killed = target.take_damage(damage)
            
            event_bus.emit(GameEvent(EventType.ATTACK_RESULT, {
                "attacker": game_state.player.name,
                "target": target.name,
                "weapon": w_name,
                "hit": hit,
                "damage": damage,
                "killed": killed
            }))
=======
            hit = att_res['success_count'] > def_res['success_count']
            total_dmg = 0
            killed = False
            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                "text": f"Attack: {att_res['success_count']} vs Defense: {def_res['success_count']}"
            }))

            if hit:
                net_hits = att_res['success_count'] - def_res['success_count']
                total_dmg = w_dmg + net_hits
                killed = target.take_damage(total_dmg)

            event_bus.emit(GameEvent(EventType.ATTACK_RESULT, {
                "attacker": getattr(game_state.player, "name", "You"),
                "target": target.name,
                "weapon": w_name,
                "hit": hit,
                "damage": total_dmg,
                "killed": killed
            }))
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
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503

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
            event_bus.emit(GameEvent(EventType.EVIDENCE_TAGGED, {"target": target.name, "game_state": game_state}))
            emit_message(f"Logged forensic tag for {target.name} [{category}].")
        else:
            emit_message(f"Unknown target: {target_name}")

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
        emit_message(game_state.evidence_log.get_history(item_name))

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
        emit_message(game_state.forensic_db.get_report(target_name))

class TestCommand(Command):
    name = "TEST"
    aliases = []
    description = "Perform a blood test."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: TEST <NAME>"}))
            return

        target_name = args[0]
        player_room = game_state.station_map.get_room_name(*game_state.player.location)
        target = next((m for m in game_state.crew if m.name.upper() == target_name.upper()), None)

        if not target:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"Unknown target: {target_name}"}))
        elif game_state.station_map.get_room_name(*target.location) != player_room:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"{target.name} is not here."}))
        else:
            # Check for required items
            scalpel = next((i for i in game_state.player.inventory if "SCALPEL" in i.name.upper()), None)
            wire = next((i for i in game_state.player.inventory if "WIRE" in i.name.upper()), None)

            if not scalpel:
                event_bus.emit(GameEvent(EventType.WARNING, {"text": "You need a SCALPEL to draw a blood sample."}))
            elif not wire:
                event_bus.emit(GameEvent(EventType.WARNING, {"text": "You need COPPER WIRE for the test."}))
            else:
<<<<<<< HEAD
                emit_message(f"Drawing blood from {target.name}...")
                game_state.forensics.blood_test.start_test(target.name)
                # Rapid heating and application
                game_state.forensics.blood_test.heat_wire()
                game_state.forensics.blood_test.heat_wire()
                game_state.forensics.blood_test.heat_wire()
                game_state.forensics.blood_test.heat_wire()

                # Use the forensics system's simulator
                event_bus.emit(GameEvent(EventType.TEST_RESULT, {
                    "subject": target.name,
                    "infected": target.is_infected,
                    "result": "reactive" if target.is_infected else "neutral"
=======
                sim = _get_blood_test_sim(game_state)
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": f"Drawing blood from {target.name}..."
                }))
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": sim.start_test(target.name)
                }))

                # Rapid heating and application to keep legacy behavior
                for _ in range(4):
                    event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                        "text": sim.heat_wire()
                    }))

                result = sim.apply_wire(target.is_infected)
                event_bus.emit(GameEvent(EventType.TEST_RESULT, {
                    "subject": target.name,
                    "result": result,
                    "infected": target.is_infected
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503
                }))

                if target.is_infected:
                    game_state.missionary_system.trigger_reveal(target, "Blood Test Exposure")


class HeatCommand(Command):
    name = "HEAT"
    aliases = []
    description = "Heat the wire during a blood test."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        sim = _get_blood_test_sim(game_state)
        if not sim.active:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "No test in progress."}))
            return
        event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {"text": sim.heat_wire()}))


class ApplyCommand(Command):
    name = "APPLY"
    aliases = []
    description = "Apply the heated wire to the blood sample."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        sim = _get_blood_test_sim(game_state)
        if not sim.active:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "No test in progress."}))
            return

        sample_name = sim.current_sample
        subject = next((m for m in game_state.crew if m.name == sample_name), None)
        infected = subject.is_infected if subject else False

        result = sim.apply_wire(infected)
        event_bus.emit(GameEvent(EventType.TEST_RESULT, {
            "subject": sample_name or "Unknown",
            "result": result,
            "infected": infected
        }))


class CancelTestCommand(Command):
    name = "CANCEL"
    aliases = []
    description = "Cancel the current blood test."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        sim = _get_blood_test_sim(game_state)
        if not sim.active:
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "No test in progress."}))
            return
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": sim.cancel()}))

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
                event_bus.emit(GameEvent(EventType.DIALOGUE, {
                    "speaker": m.name,
                    "text": m.get_dialogue(game_state)
                }))


class InterrogateCommand(Command):
    name = "INTERROGATE"
    aliases = ["ASK"]
    description = "Question a crew member about a topic."

    TOPIC_MAP = {
        "WHEREABOUTS": InterrogationTopic.WHEREABOUTS,
        "ALIBI": InterrogationTopic.ALIBI,
        "SUSPICION": InterrogationTopic.SUSPICION,
        "BEHAVIOR": InterrogationTopic.BEHAVIOR,
        "KNOWLEDGE": InterrogationTopic.KNOWLEDGE
    }

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": "Usage: INTERROGATE <NAME> [TOPIC]"
            }))
            return

        target_name = args[0]
        target = next((m for m in game_state.crew if m.name.upper() == target_name.upper()), None)

        if not target:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"Unknown target: {target_name}"}))
            return
        if game_state.station_map.get_room_name(*target.location) != player_room:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"{target.name} is not here."}))
            return
        if not target.is_alive:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"{target.name} cannot answer..."}))
            return

        if len(args) > 1:
            topic_input = args[1].upper()
            topic = self.TOPIC_MAP.get(topic_input, InterrogationTopic.WHEREABOUTS)
        else:
            topic = InterrogationTopic.WHEREABOUTS

        if not hasattr(game_state, "interrogation_system"):
            game_state.interrogation_system = InterrogationSystem(game_state.rng)

        result = game_state.interrogation_system.interrogate(
            game_state.player, target, topic, game_state
        )

        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"[INTERROGATE: {target.name} - {topic.value.upper()}]"
        }))
        event_bus.emit(GameEvent(EventType.DIALOGUE, {
            "speaker": target.name,
            "text": result.dialogue
        }))

        if result.tells:
            for tell in result.tells:
                event_bus.emit(GameEvent(EventType.MESSAGE, {"text": tell}))

        if result.trust_change != 0:
            game_state.trust_system.update_trust(target.name, game_state.player.name, result.trust_change)
            change_str = f"+{result.trust_change}" if result.trust_change > 0 else str(result.trust_change)
            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {"text": f"Trust {change_str}"}))

class BarricadeCommand(Command):
    name = "BARRICADE"
    aliases = []
    description = "Barricade the current room."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        player_room = game_state.station_map.get_room_name(*game_state.player.location)
<<<<<<< HEAD
        # Note: barricade_room currently returns a string, we should eventually refactor it to emit events.
        # But for now, we wrap it in an event or capture its result.
        # Wait, I refactored the Barricade action in message_reporter to handle BARRICADE_ACTION.
        # Let's see what barricade_room returns and if it should emit instead.
        # For now, let's just emit a message.
        result = game_state.room_states.barricade_room(player_room)
        emit_message(result)
=======
        game_state.room_states.barricade_room(player_room, actor=getattr(game_state.player, "name", "You"))
        game_state.advance_turn()
        game_state.room_states.barricade_room(player_room)
>>>>>>> 5f60c32382977f3ce71f15301c071f8d32a06503

class JournalCommand(Command):
    name = "JOURNAL"
    aliases = []
    description = "Read MacReady's journal."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        emit_message("\n--- MACREADY'S JOURNAL ---")
        if not game_state.journal:
            emit_message("(No direct diary entries - use DOSSIER for tags)")
        for entry in game_state.journal:
            emit_message(entry)
        emit_message("--------------------------")

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
            emit_message(msg)

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
        emit_message(f"--- TRUST MATRIX FOR {target_name.upper()} ---")
        for m in game_state.crew:
            if m.name in game_state.trust_system.matrix:
                val = game_state.trust_system.matrix[m.name].get(target_name.title(), 50)
                emit_message(f"{m.name} -> {target_name.title()}: {val}")

class CraftCommand(Command):
    name = "CRAFT"
    aliases = []
    description = "Craft an item using a recipe. Usage: CRAFT <recipe_id>"

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            emit_message("Usage: CRAFT <recipe_id>")
            emit_message("Available recipes: " + ", ".join(game_state.crafting.recipes.keys()))
            return

        recipe_id = args[0].lower()
        success = game_state.crafting.queue_craft(game_state.player, recipe_id, game_state)
        
        if success:
            # If instant craft (handled inside queue_craft), we might want to advance turn?
            # Or maybe crafting always takes a turn even if 0 craft_time?
            # The requirements say "emit crafting events".
            # Let's advance turn to make it a meaningful action.
            game_state.advance_turn()

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
                event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                    "text": f"Checking {skill_name} ({assoc_attr.value} + Skill)... Pool: {len(result['dice'])} dice -> {result['dice']} | [{outcome}] ({result['success_count']} successes)"
                }))
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
        self.register(CraftCommand())
        self.register(GetCommand())
        self.register(DropCommand())
        self.register(AttackCommand())
        self.register(TagCommand())
        self.register(LogCommand())
        self.register(DossierCommand())
        self.register(TestCommand())
        self.register(HeatCommand())
        self.register(ApplyCommand())
        self.register(CancelTestCommand())
        self.register(TalkCommand())
        self.register(InterrogateCommand())
        self.register(BarricadeCommand())
        self.register(JournalCommand())
        self.register(StatusCommand())
        self.register(SaveCommand())
        self.register(LoadCommand())
        self.register(AdvanceCommand())
        self.register(ExitCommand())
        self.register(TrustCommand())
        self.register(CheckCommand())
        self.register(CraftCommand())

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
