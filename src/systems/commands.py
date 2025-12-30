import sys
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass
from core.resolution import Attribute, Skill
from core.event_system import event_bus, EventType, GameEvent

from systems.distraction import DistractionSystem
from systems.interrogation import InterrogationSystem, InterrogationTopic
from systems.security import SecuritySystem
from systems.stealth import StealthPosture
from systems.dialogue_system import DialogueBranchingSystem

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


def _current_hiding_spot(game_state: "GameState"):
    """Return hiding spot metadata for the player's current position."""
    station_map = getattr(game_state, "station_map", None)
    if not station_map or not hasattr(station_map, "get_hiding_spot"):
        return None
    return station_map.get_hiding_spot(*game_state.player.location)


def _movement_blocked_by_hiding(game_state: "GameState") -> bool:
    """Check if the player must leave cover before moving."""
    hiding_spot = _current_hiding_spot(game_state)
    if hiding_spot and getattr(game_state.player, "stealth_posture", StealthPosture.STANDING) == StealthPosture.HIDING:
        event_bus.emit(GameEvent(EventType.WARNING, {
            "text": "You are tucked into cover. Use STAND or UNHIDE before moving."
        }))
        return True
    return False


def _handle_hiding_entry(game_state: "GameState"):
    """Auto-apply posture changes and messaging when stepping into cover tiles."""
    station_map = getattr(game_state, "station_map", None)
    if not station_map or not hasattr(station_map, "get_hiding_spot"):
        return

    hiding_spot = station_map.get_hiding_spot(*game_state.player.location)
    if hiding_spot:
        game_state.player.set_posture(StealthPosture.HIDING)
        cover_bonus = hiding_spot.get("cover_bonus", 0)
        los_note = " It blocks line-of-sight." if hiding_spot.get("blocks_los") else ""
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"You slip behind {hiding_spot.get('label', 'cover')} (+{cover_bonus} stealth).{los_note}"
        }))
    elif getattr(game_state.player, "stealth_posture", StealthPosture.STANDING) == StealthPosture.HIDING:
        game_state.player.set_posture(StealthPosture.CROUCHING)


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

        if getattr(game_state.player, "in_vent", False):
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": "You are inside the vents. Use VENT EXIT to climb out."
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

        if _movement_blocked_by_hiding(game_state):
            return
        
        # Reset posture to STANDING on move, unless sneaking
        if hasattr(game_state.player, 'set_posture'):
             game_state.player.set_posture(StealthPosture.STANDING)

        if game_state.player.move(dx, dy, game_state.station_map):
            destination = game_state.station_map.get_room_name(*game_state.player.location)
            event_bus.emit(GameEvent(EventType.MOVEMENT, {
                "actor": getattr(game_state.player, "name", "You"),
                "mover": game_state.player,
                "to": game_state.player.location,
                "direction": direction,
                "destination": destination,
                "game_state": game_state
            }))
            _handle_hiding_entry(game_state)
            game_state.advance_turn()
        else:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": "Blocked."}))

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

class InventoryCommand(Command):
    name = "INVENTORY"
    aliases = ["INV"]
    description = "Check your inventory."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"--- {game_state.player.name}'s INVENTORY ---"
        }))
        if not game_state.player.inventory:
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "(Empty)"}))
        for item in game_state.player.inventory:
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"- {item.name}: {item.description}"
            }))

class CraftCommand(Command):
    name = "CRAFT"
    aliases = []
    description = "Craft an item using a recipe. Usage: CRAFT <recipe_id>"

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not hasattr(game_state, "crafting") or game_state.crafting is None:
             event_bus.emit(GameEvent(EventType.ERROR, {"text": "Crafting system unavailable."}))
             return

        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: CRAFT <recipe_id>"}))
            recipes_list = ", ".join(game_state.crafting.recipes.keys())
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": f"Available recipes: {recipes_list}"}))
            return

        recipe_id = args[0].lower()
        success = game_state.crafting.queue_craft(game_state.player, recipe_id, game_state)
        
        if success:
            game_state.advance_turn()

class GetCommand(Command):
    name = "GET"
    aliases = []
    description = "Pick up an item."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: GET <ITEM NAME>"}))
            return

        item_name = " ".join(args)
        found_item = game_state.station_map.remove_item_from_room(item_name, *game_state.player.location)
        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if found_item:
            game_state.player.add_item(found_item, game_state.turn)
            game_state.evidence_log.record_event(found_item.name, "GET", game_state.player.name, player_room, game_state.turn)
            event_bus.emit(GameEvent(EventType.ITEM_PICKUP, {
                "actor": game_state.player.name,
                "item": found_item.name,
                "room": player_room
            }))
        else:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"You don't see '{item_name}' here."
            }))

class DropCommand(Command):
    name = "DROP"
    aliases = []
    description = "Drop an item."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: DROP <ITEM NAME>"}))
            return

        item_name = " ".join(args)
        dropped_item = game_state.player.remove_item(item_name)
        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if dropped_item:
            game_state.station_map.add_item_to_room(dropped_item, *game_state.player.location, game_state.turn)
            game_state.evidence_log.record_event(dropped_item.name, "DROP", game_state.player.name, player_room, game_state.turn)
            event_bus.emit(GameEvent(EventType.ITEM_DROP, {
                "actor": game_state.player.name,
                "item": dropped_item.name,
                "room": player_room
            }))
        else:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"You don't have '{item_name}'."
            }))

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

            hit = att_res['success_count'] > def_res['success_count']
            damage = 0
            killed = False
            
            if hit:
                # Combat breaks stealth (obviously)
                if hasattr(game_state.player, 'set_posture'):
                     game_state.player.set_posture(StealthPosture.STANDING)

                net_hits = att_res['success_count'] - def_res['success_count']
                damage = w_dmg + net_hits
                killed = target.take_damage(damage, game_state=game_state)
            
            event_bus.emit(GameEvent(EventType.ATTACK_RESULT, {
                "attacker": game_state.player.name,
                "target": target.name,
                "weapon": w_name,
                "hit": hit,
                "damage": damage,
                "killed": killed,
                "room": player_room
            }))

class TagCommand(Command):
    name = "TAG"
    aliases = []
    description = "Tag a character with forensic notes."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if len(args) < 3:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": "Usage: TAG <NAME> <CATEGORY> <NOTE...>\nCategories: IDENTITY, TRUST, SUSPICION, BEHAVIOR"
            }))
            return

        target_name = args[0]
        category = args[1]
        note = " ".join(args[2:])
        target = next((m for m in game_state.crew if m.name.upper() == target_name.upper()), None)

        if target:
            game_state.forensic_db.add_tag(target.name, category, note, game_state.turn)
            # Emit Event for Social System to lower trust
            event_bus.emit(GameEvent(EventType.EVIDENCE_TAGGED, {"target": target.name, "game_state": game_state}))
            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                "text": f"Logged forensic tag for {target.name} [{category}]."
            }))
        else:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"Unknown target: {target_name}"
            }))

class LogCommand(Command):
    name = "LOG"
    aliases = []
    description = "Check evidence log for an item."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: LOG <ITEM NAME>"}))
            return

        item_name = " ".join(args)
        log_text = game_state.evidence_log.get_history(item_name)
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": log_text}))

class DossierCommand(Command):
    name = "DOSSIER"
    aliases = []
    description = "View forensic dossier for a character."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: DOSSIER <NAME>"}))
            return

        target_name = args[0]
        report = game_state.forensic_db.get_report(target_name)
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": report}))

class TestCommand(Command):
    name = "TEST"
    aliases = []
    description = "Perform a blood test. Requires scalpel + wire OR a Portable Blood Test Kit."

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
            return

        if game_state.station_map.get_room_name(*target.location) != player_room:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"{target.name} is not here."}))
            return

        # Check for Portable Blood Test Kit first (allows testing anywhere)
        portable_kit = next(
            (i for i in game_state.player.inventory
             if getattr(i, 'effect', None) == 'portable_test' and getattr(i, 'uses', 0) != 0),
            None
        )

        if portable_kit:
            # Use the portable kit
            self._perform_test_with_kit(game_state, target, portable_kit)
        else:
            # Fall back to requiring scalpel + wire
            scalpel = next((i for i in game_state.player.inventory if "SCALPEL" in i.name.upper()), None)
            wire = next((i for i in game_state.player.inventory if "WIRE" in i.name.upper()), None)

            if not scalpel:
                event_bus.emit(GameEvent(EventType.WARNING, {"text": "You need a SCALPEL to draw a blood sample, or a Portable Blood Test Kit."}))
            elif not wire:
                event_bus.emit(GameEvent(EventType.WARNING, {"text": "You need COPPER WIRE for the test, or a Portable Blood Test Kit."}))
            else:
                self._perform_test(game_state, target)

    def _perform_test_with_kit(self, game_state, target, kit):
        """Perform blood test using a Portable Blood Test Kit."""
        # Consume one use of the kit
        if hasattr(kit, 'consume'):
            kit.consume()

        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"Using {kit.name} to test {target.name}..."
        }))

        # Check remaining uses
        remaining = getattr(kit, 'uses', 0)
        if remaining > 0:
            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
                "text": f"{kit.name}: {remaining} uses remaining."
            }))
        elif remaining == 0:
            # Remove depleted kit from inventory
            game_state.player.inventory.remove(kit)
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"Your {kit.name} is depleted and discarded."
            }))

        self._perform_test(game_state, target)

    def _perform_test(self, game_state, target):
        """Common test execution logic."""
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
                "text": sim.heat_wire(game_state.rng)
            }))

        result = sim.apply_wire(target.is_infected, game_state.rng)
        event_bus.emit(GameEvent(EventType.TEST_RESULT, {
            "subject": target.name,
            "result": result,
            "infected": target.is_infected
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
        event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {"text": sim.heat_wire(game_state.rng)}))


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

        result = sim.apply_wire(infected, game_state.rng)
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
        "KNOWLEDGE": InterrogationTopic.KNOWLEDGE,
        "SLIP": InterrogationTopic.SCHEDULE_SLIP,
        "SCHEDULE": InterrogationTopic.SCHEDULE_SLIP
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

        # Show schedule disruption indicator if target is out of expected location
        if result.out_of_schedule and result.schedule_message:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": result.schedule_message
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


class ExplainAwayCommand(Command):
    name = "EXPLAIN_AWAY"
    aliases = ["EXPLAIN", "EXCUSE"]
    description = "Explain suspicious behavior with a contested Influence + Deception roll."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game

        if not hasattr(game_state, "dialogue_branching"):
            game_state.dialogue_branching = DialogueBranchingSystem(rng=getattr(game_state, "rng", None))

        explain_sys = game_state.dialogue_branching

        pending = explain_sys.get_pending_observers()
        if not pending:
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": "There's no one expecting an explanation right now."
            }))
            return

        observer = None
        if args:
            target_name = args[0].upper()
            if target_name not in [p.upper() for p in pending]:
                event_bus.emit(GameEvent(EventType.WARNING, {
                    "text": f"{target_name} isn't waiting for an explanation from you."
                }))
                return
            for name in pending:
                if name.upper() == target_name:
                    observer = next((m for m in game_state.crew if m.name == name), None)
                    break
        else:
            observer_name = pending[0]
            observer = next((m for m in game_state.crew if m.name == observer_name), None)

        if not observer:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": "Could not find the observer to explain to."
            }))
            explain_sys.clear_pending()
            return

        player_room = game_state.station_map.get_room_name(*game_state.player.location)
        observer_room = game_state.station_map.get_room_name(*observer.location)

        if player_room != observer_room:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"{observer.name} is no longer here. The moment has passed."
            }))
            explain_sys.clear_pending(observer.name)
            return

        result = explain_sys.explain_away(game_state.player, observer, game_state)

        event_bus.emit(GameEvent(EventType.DIALOGUE, {
            "speaker": game_state.player.name,
            "target": observer.name,
            "text": result.dialogue
        }))

        if result.success:
            outcome_text = f"[SUCCESS] {observer.name}'s suspicion decreased by {abs(result.suspicion_change)}."
        elif result.critical:
            outcome_text = f"[CRITICAL FAILURE] {observer.name} is now hostile!"
        else:
            outcome_text = f"[FAILURE] {observer.name}'s suspicion increased. Trust penalty: {result.trust_change}"

        event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
            "text": f"EXPLAIN_AWAY: Player {result.player_successes} successes vs {observer.name} {result.observer_successes} successes"
        }))
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": outcome_text}))

        game_state.advance_turn()

class ConfrontSlipCommand(Command):
    name = "CONFRONT"
    aliases = ["CALLOUT"]
    description = "Confront a crew member who is off their schedule."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": "Usage: CONFRONT <NAME>"
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
        if not getattr(target, "schedule_slip_flag", False):
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"{target.name} seems to be where they're supposed to be. No slip to confront."
            }))
            return

        if not hasattr(game_state, "interrogation_system"):
            game_state.interrogation_system = InterrogationSystem(game_state.rng, game_state.room_states)

        result = game_state.interrogation_system.confront_schedule_slip(
            game_state.player, target, game_state
        )

        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"[CONFRONT: {target.name} - OFF-SCHEDULE]"
        }))
        event_bus.emit(GameEvent(EventType.DIALOGUE, {
            "speaker": target.name,
            "text": result.dialogue
        }))

        for tell in result.tells:
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": tell}))

        if result.trust_change != 0 and hasattr(game_state, "trust_system"):
            game_state.trust_system.update_trust(target.name, game_state.player.name, result.trust_change)
            change_str = f"+{result.trust_change}" if result.trust_change > 0 else str(result.trust_change)
            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {"text": f"Trust {change_str}"}))

class AccuseCommand(Command):
    name = "ACCUSE"
    aliases = []
    description = "Publicly accuse a crew member of being The Thing."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: ACCUSE <NAME>"}))
            return

        target_name = args[0]
        target = next((m for m in game_state.crew if m.name.upper() == target_name.upper()), None)

        if not target:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"Who is {target_name}?"}))
            return

        # Emit result event for UI handling
        event_bus.emit(GameEvent(EventType.ACCUSATION_RESULT, {
            "target": target.name,
            "outcome": f"You point an accusing finger at {target.name}!",
            "supporters": [],
            "opposers": []
        }))
        
        # In a real scenario, we'd pass evidence, but for now we trigger logic via event
        if hasattr(game_state, 'lynch_mob'):
             game_state.lynch_mob.form_mob(target)


class BarricadeCommand(Command):
    name = "BARRICADE"
    aliases = []
    description = "Barricade the current room."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        player_room = game_state.station_map.get_room_name(*game_state.player.location)
        result = game_state.room_states.barricade_room(player_room)
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": result}))
        game_state.advance_turn()

class JournalCommand(Command):
    name = "JOURNAL"
    aliases = []
    description = "Read MacReady's journal."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "\n--- MACREADY'S JOURNAL ---"}))
        if not game_state.journal:
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "(No direct diary entries - use DOSSIER for tags)"}))
        for entry in game_state.journal:
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": entry}))
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "--------------------------"}))

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
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": msg}))

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
            from engine import GameState 
            new_game = GameState.from_dict(data)

            # 3. Replace in context
            context.game = new_game
            event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {"text": "*** GAME LOADED ***"}))

class WaitCommand(Command):
    name = "WAIT"
    aliases = ["Z", "ADVANCE"]
    description = "Wait one turn."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        game_state.advance_turn()

class ExitCommand(Command):
    name = "EXIT"
    aliases = ["QUIT"]
    description = "Exit the game."

    def execute(self, context: GameContext, args: List[str]) -> None:
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Exiting..."}))
        sys.exit(0)

class TrustCommand(Command):
    name = "TRUST"
    aliases = []
    description = "Check trust matrix for a character."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: TRUST <NAME>"}))
            return

        target_name = args[0]
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": f"--- TRUST MATRIX FOR {target_name.upper()} ---"}))
        for m in game_state.crew:
            if m.name in game_state.trust_system.matrix:
                val = game_state.trust_system.matrix[m.name].get(target_name.title(), 50)
                event_bus.emit(GameEvent(EventType.MESSAGE, {"text": f"{m.name} -> {target_name.title()}: {val}"}))

class CheckCommand(Command):
    name = "CHECK"
    aliases = []
    description = "Perform a skill check."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: CHECK <SKILL> (e.g., CHECK MELEE)"}))
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
                event_bus.emit(GameEvent(EventType.WARNING, {"text": f"Unknown skill: {skill_name}"}))
                event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Available: " + ", ".join([s.value for s in Skill])}))
        except Exception as e:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": f"Error resolving check: {e}"}))


# === STEALTH COMMANDS ===

class HideCommand(Command):
    name = "HIDE"
    aliases = []
    description = "Attempt to hide in the current room."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        player_room = game_state.station_map.get_room_name(*game_state.player.location)
        
        # Check if hiding is possible (simplified)
        # Assuming system is available
        stealth_sys = getattr(game_state, 'stealth_system', None) # Or however we access it
        # Actually stealth system is reactive, but we need to check environmental conditions
        
        # Reuse stealth.py helper if available or check room states manually
        room_states = getattr(game_state, "room_states", None)
        can_hide = True 
        if room_states:
             # Basic check: Need furniture or darkness?
             # For now, always allow trying to hide, effectiveness depends on system
             pass

        hiding_spot = _current_hiding_spot(game_state)
        game_state.player.set_posture(StealthPosture.HIDING)
        if hiding_spot:
            cover_bonus = hiding_spot.get("cover_bonus", 0)
            los_note = " Your vision is narrow from here." if hiding_spot.get("blocks_los") else ""
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"You slip behind {hiding_spot.get('label', 'cover')} (+{cover_bonus} stealth).{los_note}"
            }))
        else:
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"You slip into the shadows of the {player_room}..."
            }))
        # Hiding takes a turn
        game_state.advance_turn()

class UnhideCommand(Command):
    name = "UNHIDE"
    aliases = ["EXITCOVER"]
    description = "Leave your hiding spot and stand up."

    def execute(self, context: GameContext, args: List[str]) -> None:
        context.game.player.set_posture(StealthPosture.STANDING)
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "You step out from cover and stand up."}))
        context.game.advance_turn()

class CrouchCommand(Command):
    name = "CROUCH"
    aliases = []
    description = "Lower your profile to be stealthier."

    def execute(self, context: GameContext, args: List[str]) -> None:
        context.game.player.set_posture(StealthPosture.CROUCHING)
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "You crouch down low."}))

class VentCommand(Command):
    name = "VENT"
    aliases = ["DUCT"]
    description = "Enter or crawl through the ventilation network."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        player = game_state.player
        station_map = game_state.station_map

        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: VENT ENTER|EXIT|<DIRECTION>"}))
            return

        if not station_map.is_at_vent(*player.location):
            event_bus.emit(GameEvent(EventType.WARNING, {"text": "You don't see a vent access here."}))
            return

        action = args[0].upper()

        if action in ["ENTER", "IN"]:
            if not station_map.is_vent_entry(*player.location):
                event_bus.emit(GameEvent(EventType.WARNING, {"text": "This grate is too narrow to enter."}))
                return
            player.in_vent = True
            player.set_posture(StealthPosture.CRAWLING)
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "You slip into the ventilation duct."}))
            game_state.advance_turn()
            return

        if action in ["EXIT", "OUT"]:
            if not player.in_vent:
                event_bus.emit(GameEvent(EventType.WARNING, {"text": "You are not inside a vent."}))
                return
            if not station_map.is_vent_entry(*player.location):
                event_bus.emit(GameEvent(EventType.WARNING, {"text": "You need an entry grate to drop out."}))
                return
            player.in_vent = False
            player.set_posture(StealthPosture.CROUCHING)
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "You drop out of the vent, brushing off dust."}))
            game_state.advance_turn()
            return

        # Movement inside ducts
        direction = action
        if not player.in_vent:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": "Enter a vent first (VENT ENTER)."}))
            return

        target = station_map.get_vent_neighbor_in_direction(*player.location, direction)
        if not target:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": "The duct doesn't run that way."}))
            return

        player.location = target
        player.set_posture(StealthPosture.CRAWLING)
        destination_room = station_map.get_room_name(*target)

        movement_payload = {
            "actor": getattr(player, "name", "You"),
            "mover": player,
            "to": target,
            "direction": direction,
            "destination": destination_room,
            "vent": True,
            "mode": "vent",
            "noise": player.get_noise_level(),
            "game_state": game_state
        }
        event_bus.emit(GameEvent(EventType.MOVEMENT, movement_payload))
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Metal scrapes under you as you crawl through the vent."}))

        # Handle vent movement with enhanced mechanics (echoing noise, encounters)
        stealth_sys = getattr(game_state, "stealth", None) or getattr(game_state, "stealth_system", None)
        encounter_result = None
        if stealth_sys and hasattr(stealth_sys, "handle_vent_movement"):
            encounter_result = stealth_sys.handle_vent_movement(game_state, player, target)

        # Vent crawling takes multiple turns (slow movement in cramped space)
        crawl_turns = 2  # Default
        if stealth_sys and hasattr(stealth_sys, "get_vent_crawl_turns"):
            crawl_turns = stealth_sys.get_vent_crawl_turns()

        for _ in range(crawl_turns):
            game_state.advance_turn()

        # If player was caught in vent encounter, they may be forced out
        if encounter_result and encounter_result.get("encounter") and not encounter_result.get("escaped"):
            player.in_vent = False
            player.set_posture(StealthPosture.CROUCHING)
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": "You are knocked out of the vent!"
            }))

class CrawlCommand(Command):
    name = "CRAWL"
    aliases = []
    description = "Drop to the floor to minimize visibility."

    def execute(self, context: GameContext, args: List[str]) -> None:
        context.game.player.set_posture(StealthPosture.CRAWLING)
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "You drop to the floor and crawl."}))

class StandCommand(Command):
    name = "STAND"
    aliases = []
    description = "Stand up normally."

    def execute(self, context: GameContext, args: List[str]) -> None:
        was_hiding = getattr(context.game.player, "stealth_posture", StealthPosture.STANDING) == StealthPosture.HIDING
        context.game.player.set_posture(StealthPosture.STANDING)
        text = "You step out from cover and stand up." if was_hiding else "You stand up."
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": text}))

class SneakCommand(Command):
    name = "SNEAK"
    aliases = []
    description = "Move while keeping a low profile."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Sneak where? Usage: SNEAK <direction>"}))
            return
        if getattr(game_state.player, "in_vent", False):
            event_bus.emit(GameEvent(EventType.WARNING, {"text": "You are inside the vents. Use VENT EXIT first."}))
            return
            
        direction = args[0].upper()
        # Set posture to crouching
        game_state.player.set_posture(StealthPosture.CROUCHING)
        
        # Reuse move logic
        dx, dy = 0, 0
        if direction in ["NORTH", "N"]: dy = -1
        elif direction in ["SOUTH", "S"]: dy = 1
        elif direction in ["EAST", "E"]: dx = 1
        elif direction in ["WEST", "W"]: dx = -1
        else:
             event_bus.emit(GameEvent(EventType.ERROR, {"text": f"Invalid direction: {direction}"}))
             return

        if _movement_blocked_by_hiding(game_state):
            return

        if game_state.player.move(dx, dy, game_state.station_map):
            destination = game_state.station_map.get_room_name(*game_state.player.location)
            event_bus.emit(GameEvent(EventType.MOVEMENT, {
                "actor": "You",
                "mover": game_state.player,
                "to": game_state.player.location,
                "direction": direction,
                "destination": destination,
                "game_state": game_state
            }))
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "(Sneaking)"}))
            _handle_hiding_entry(game_state)
            game_state.advance_turn()
        else:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": "Blocked."}))

class GiveCommand(Command):
    name = "GIVE"
    aliases = []
    description = "Give an item to someone. Usage: GIVE <item> TO <target>"

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if len(args) < 3 or args[1].upper() != "TO":
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: GIVE <item> TO <target>"}))
            return

        item_name = args[0].upper()
        target_name = args[2].upper()

        # Find target
        target = next((m for m in game_state.crew if m.name.upper() == target_name), None)
        if not target:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"Who is {target_name}?"}))
            return

        # Find item in player inventory
        item = next((i for i in game_state.player.inventory if i.name.upper() == item_name), None)
        if not item:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"You don't have a {item_name}."}))
            return

        # Perform transfer
        game_state.player.inventory.remove(item)
        target.inventory.append(item)
        
        event_bus.emit(GameEvent(EventType.ITEM_DROP, {
            "item": item.name,
            "actor": "You",
            "target": target.name
        }))
        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"You give the {item.name} to {target.name}."
        }))
        game_state.advance_turn()

class RepairCommand(Command):
    name = "REPAIR"
    aliases = ["FIX"]
    description = "Repair station equipment. Usage: REPAIR <RADIO/HELICOPTER>"

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Usage: REPAIR <RADIO/HELICOPTER>"}))
            return

        target_type = args[0].upper()
        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        if target_type == "RADIO":
            success, message, evt_type = game_state.attempt_repair_radio()
            event_bus.emit(GameEvent(evt_type, {"text": message}))
            if success:
                game_state.advance_turn()

        elif target_type in ["HELICOPTER", "CHOPPER"]:
            success, message, evt_type = game_state.attempt_repair_helicopter()
            event_bus.emit(GameEvent(evt_type, {"text": message}))
            if success:
                game_state.advance_turn()
        else:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": f"You can't repair '{target_type}'."}))

class FlyCommand(Command):
    name = "FLY"
    aliases = ["ESCAPE", "TAKEOFF"]
    description = "Fly the helicopter to safety. Requires helicopter to be FIXED."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        success, message, evt_type = game_state.attempt_escape()
        event_bus.emit(GameEvent(evt_type, {"text": message}))
        if success:
            game_state.advance_turn()

class SOSCommand(Command):
    name = "SOS"
    aliases = ["SIGNAL"]
    description = "Broadcast an SOS signal. Requires operational Radio."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        success, message, evt_type = game_state.attempt_radio_signal()
        event_bus.emit(GameEvent(evt_type, {"text": message}))
        if success:
            game_state.advance_turn()

class AccuseCommand(Command):
    name = "ACCUSE"
    aliases = []
    description = "Formally accuse someone of being The Thing."

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": "Accuse whom? Usage: ACCUSE <name>"}))
            return
        
        target_name = args[0]
        target = next((m for m in game_state.crew if m.name.lower() == target_name.lower()), None)
        
        if not target:
            event_bus.emit(GameEvent(EventType.ERROR, {"text": f"No crew member named '{target_name}'."}))
            return
        
        if not target.is_alive:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": f"{target.name} is already dead."}))
            return
        
        # Use InterrogationSystem's make_accusation method
        if not hasattr(game_state, "interrogation_system"):
            from systems.interrogation import InterrogationSystem
            game_state.interrogation_system = InterrogationSystem(game_state.rng, game_state.room_states)
        
        # Make accusation with empty evidence list (player can expand this later)
        result = game_state.interrogation_system.make_accusation(
            game_state.player, target, [], game_state
        )

class ThrowCommand(Command):
    name = "THROW"
    aliases = ["TOSS"]
    description = "Throw an item toward a target tile. Usage: THROW <ITEM> <TARGET>"
    description = "Throw an item to create a distraction. Usage: THROW <ITEM> <TARGET>"

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game

        if len(args) < 2:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": "Usage: THROW <ITEM> <TARGET>\nTARGET can be coordinates (X Y) or a room name."
            }))
            return

        item, target = self._parse_item_and_target(args, game_state)
        if not item or not target:
                "text": "Usage: THROW <ITEM> <TARGET>\nTargets: direction (N/S/E/W/NE/NW/SE/SW) or coordinates (X,Y)"
            }))
            return

        item_name = " ".join(args[:-1]).upper()
        target = args[-1].upper()

        # Find item in player inventory
        item = next((i for i in game_state.player.inventory
                     if i.name.upper() == item_name or i.name.upper() == item_name.replace(",", " ")), None)

        if not item:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"You don't have a {item_name}."
            }))
            # Show available throwable items
            if not hasattr(game_state, 'distraction_system'):
                game_state.distraction_system = DistractionSystem()
            throwables = game_state.distraction_system.get_throwable_items(game_state.player)
            if throwables:
                names = ", ".join([i.name for i in throwables])
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": f"Throwable items: {names}"
                }))
            return

        if not hasattr(game_state, "distraction_system"):
            game_state.distraction_system = DistractionSystem()

        success, message = game_state.distraction_system.throw_toward(
        # Attempt to throw the item
        success, message = game_state.distraction_system.throw_item(
            game_state.player, item, target, game_state
        )

        if success:
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": message}))
            game_state.advance_turn()
        else:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": message}))

    def _parse_item_and_target(self, args: List[str], game_state: "GameState"):
        """Split args into (item, target) supporting multi-word names."""
        inventory_names = [i.name.upper() for i in game_state.player.inventory]
        split_index = None

        # Coordinate target: last two args numeric
        if len(args) >= 3 and args[-2].lstrip("+-").isdigit() and args[-1].lstrip("+-").isdigit():
            split_index = len(args) - 2

        if split_index is None:
            for i in range(len(args) - 1, 0, -1):
                cand = " ".join(args[:i]).upper()
                if cand in inventory_names:
                    split_index = i
                    break

        if split_index is None:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": "Couldn't find a matching item to throw in your inventory."
            }))
            return None, None

        item_name = " ".join(args[:split_index]).upper()
        item = next((i for i in game_state.player.inventory if i.name.upper() == item_name), None)
        if not item:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"You don't have '{item_name}'."
            }))
            return None, None
        if not getattr(item, "throwable", False):
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"The {item.name} can't be thrown."
            }))
            return None, None

        target_tokens = args[split_index:]
        target_location = self._resolve_target(target_tokens, game_state)
        if not target_location:
            return item, None
        return item, target_location

    def _resolve_target(self, tokens: List[str], game_state: "GameState"):
        """Resolve target tokens into map coordinates."""
        # Numeric coordinates
        if len(tokens) == 2 and all(t.lstrip("+-").isdigit() for t in tokens):
            x, y = int(tokens[0]), int(tokens[1])
            if not game_state.station_map.is_walkable(x, y):
                event_bus.emit(GameEvent(EventType.WARNING, {"text": "That throw target is outside the station."}))
                return None
            return (x, y)

        room_name = " ".join(tokens)
        room_center = game_state.station_map.get_room_center(room_name)
        if room_center:
            return room_center
        # Case-insensitive room lookup
        for known_name in game_state.station_map.rooms.keys():
            if known_name.lower() == room_name.lower():
                return game_state.station_map.get_room_center(known_name)

        event_bus.emit(GameEvent(EventType.WARNING, {
            "text": f"Unknown target '{room_name}'. Provide coordinates or a room name."
        }))
        return None


class SettingsCommand(Command):
    name = "SETTINGS"
    aliases = ["CONFIG"]
    description = "Change game settings."

    def execute(self, context: GameContext, args: List[str]) -> None:
        if not args:
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Usage: SETTINGS <key> <value>"}))
            return
        # Placeholder
        event_bus.emit(GameEvent(EventType.MESSAGE, {"text": "Settings updated (simulated)."}))


class DeployCommand(Command):
    name = "DEPLOY"
    aliases = ["PLACE", "SET"]
    description = "Deploy a placeable item like a tripwire. Usage: DEPLOY <item>"

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game

        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": "Usage: DEPLOY <item>\nDeployable items create traps or alerts at your location."
            }))
            # Show deployable items in inventory
            deployables = [i for i in game_state.player.inventory
                          if getattr(i, 'deployable', False) or
                          (hasattr(i, 'effect') and i.effect == 'alerts_on_trigger')]
            if deployables:
                names = ", ".join([i.name for i in deployables])
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": f"Deployable items: {names}"
                }))
            return

        item_name = " ".join(args).upper()

        # Find deployable item in player inventory
        item = next((i for i in game_state.player.inventory
                    if i.name.upper() == item_name or item_name in i.name.upper()), None)

        if not item:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"You don't have a {item_name}."
            }))
            return

        # Check if item is deployable
        is_deployable = getattr(item, 'deployable', False) or \
                       (hasattr(item, 'effect') and item.effect == 'alerts_on_trigger')

        if not is_deployable:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"The {item.name} can't be deployed."
            }))
            return

        # Initialize deployed items tracker if needed
        if not hasattr(game_state, 'deployed_items'):
            game_state.deployed_items = {}

        player_pos = game_state.player.location
        player_room = game_state.station_map.get_room_name(*player_pos)

        # Check if there's already a deployed item at this location
        if player_pos in game_state.deployed_items:
            existing = game_state.deployed_items[player_pos]
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": f"There's already a {existing['item_name']} deployed here."
            }))
            return

        # Remove item from inventory and deploy it
        deployed_item = game_state.player.remove_item(item.name)

        if not deployed_item:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": "Failed to deploy item."
            }))
            return

        # Store deployment info
        game_state.deployed_items[player_pos] = {
            'item_name': deployed_item.name,
            'item': deployed_item,
            'room': player_room,
            'turn_deployed': game_state.turn,
            'effect': getattr(deployed_item, 'effect', 'alerts_on_trigger'),
            'triggered': False
        }

        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"You carefully deploy the {deployed_item.name} at your location."
        }))
        event_bus.emit(GameEvent(EventType.SYSTEM_LOG, {
            "text": f"Deployed {deployed_item.name} in {player_room} at {player_pos}."
        }))

        # Deploying takes a turn
        game_state.advance_turn()


class SecurityCommand(Command):
    name = "SECURITY"
    aliases = ["CAMERAS"]
    description = "Check security console for alerts. Usage: SECURITY [STATUS]"

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game
        player_room = game_state.station_map.get_room_name(*game_state.player.location)

        # Initialize security system if needed
        if not hasattr(game_state, 'security_system'):
            game_state.security_system = SecuritySystem(game_state)

        security_sys = game_state.security_system

        if args and args[0].upper() == "STATUS":
            # Show device status
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"--- SECURITY STATUS ---\n{security_sys.get_status()}"
            }))
            return

        # Check the security console (only in Radio Room)
        if player_room != "Radio Room":
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": "The security console is in the Radio Room."
            }))
            return

        unread = security_sys.check_console()

        if not unread:
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": "--- SECURITY LOG ---\nNo new alerts."
            }))
        else:
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": f"--- SECURITY LOG ({len(unread)} alerts) ---"
            }))
            for entry in unread[-10:]:  # Show last 10
                device = entry['device_type'].replace('_', ' ').title()
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": f"[Turn {entry['turn']}] {device} ({entry['device_room']}): {entry['target']} detected at {entry['position']}"
                }))


class SabotageSecurityCommand(Command):
    name = "SABOTAGE"
    aliases = ["DISABLE"]
    description = "Sabotage a security device. Usage: SABOTAGE CAMERA/SENSOR"

    def execute(self, context: GameContext, args: List[str]) -> None:
        game_state = context.game

        if not args:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": "Usage: SABOTAGE <CAMERA/SENSOR>\nYou must be at the device's location."
            }))
            return

        target_type = args[0].upper()

        if target_type not in ["CAMERA", "SENSOR", "MOTION_SENSOR"]:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": "You can sabotage: CAMERA, SENSOR"
            }))
            return

        # Initialize security system if needed
        if not hasattr(game_state, 'security_system'):
            game_state.security_system = SecuritySystem(game_state)

        security_sys = game_state.security_system
        player_pos = game_state.player.location

        # Check if there's a device at player's location
        device = security_sys.get_device_at(player_pos)

        if not device:
            # Check for nearby devices in the same room
            player_room = game_state.station_map.get_room_name(*player_pos)
            room_devices = security_sys.get_devices_in_room(player_room)

            if not room_devices:
                event_bus.emit(GameEvent(EventType.WARNING, {
                    "text": "There's no security device here to sabotage."
                }))
                return

            # Find matching device type
            matching = [d for d in room_devices if
                       (target_type == "CAMERA" and d.device_type == "camera") or
                       (target_type in ["SENSOR", "MOTION_SENSOR"] and d.device_type == "motion_sensor")]

            if not matching:
                event_bus.emit(GameEvent(EventType.WARNING, {
                    "text": f"There's no {target_type.lower()} in this room."
                }))
                return

            device = matching[0]
            device_pos = device.position
        else:
            device_pos = player_pos

        # Check for required tools
        tools = next((i for i in game_state.player.inventory if "TOOLS" in i.name.upper()), None)
        if not tools:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": "You need Tools to sabotage security devices."
            }))
            return

        # Attempt sabotage
        success, message = security_sys.sabotage_device(device_pos, game_state)

        if success:
            event_bus.emit(GameEvent(EventType.MESSAGE, {"text": message}))
            game_state.advance_turn()
        else:
            event_bus.emit(GameEvent(EventType.WARNING, {"text": message}))


class ThermalCommand(Command):
    name = "THERMAL"
    aliases = ["SCAN", "HEATSCAN"]
    description = "Scan for heat signatures with thermal goggles. Only works in darkness."

    def execute(self, context: GameContext, args: List[str]) -> None:
        from core.resolution import ResolutionSystem
        from systems.room_state import RoomState

        game_state = context.game
        player = game_state.player
        player_room = game_state.station_map.get_room_name(*player.location)
        room_states = getattr(game_state, 'room_states', None)

        # Check if player has thermal goggles
        has_goggles = any(
            hasattr(item, 'effect') and item.effect == 'thermal_detection'
            for item in getattr(player, 'inventory', [])
        )

        if not has_goggles:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": "You need Thermal Goggles to scan for heat signatures."
            }))
            return

        # Check room darkness
        is_dark = room_states.has_state(player_room, RoomState.DARK) if room_states else False
        if not is_dark:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": "Thermal scanning only works in darkness. The ambient light washes out heat signatures."
            }))
            return

        # Check if room is frozen (blocks thermal)
        is_frozen = room_states.has_state(player_room, RoomState.FROZEN) if room_states else False
        if is_frozen:
            event_bus.emit(GameEvent(EventType.WARNING, {
                "text": "The room is frozen solid. All heat signatures are masked by the extreme cold."
            }))
            return

        # Get player's thermal detection pool
        if hasattr(player, 'get_thermal_detection_pool'):
            thermal_pool = player.get_thermal_detection_pool()
        else:
            thermal_pool = 2

        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": "You activate the thermal goggles and scan the room..."
        }))

        # Find all characters in the same room
        crew_in_room = [
            m for m in game_state.crew
            if m.is_alive and m.location == player.location and m != player
        ]

        if not crew_in_room:
            event_bus.emit(GameEvent(EventType.MESSAGE, {
                "text": "No heat signatures detected in this area."
            }))
            game_state.advance_turn()
            return

        res = ResolutionSystem()
        rng = game_state.rng

        detections = []
        for target in crew_in_room:
            # Get target's thermal signature (Things run hotter)
            if hasattr(target, 'get_thermal_signature'):
                target_thermal = target.get_thermal_signature()
            else:
                target_thermal = 2

            # Roll thermal detection
            scan_result = res.roll_check(thermal_pool, rng)

            # Higher thermal signature = easier to detect
            # Infected creatures have +3 thermal, so threshold is lower
            if target_thermal > 3:  # Infected (5+ thermal)
                thermal_desc = "ELEVATED"
                intensity = "burns brightly"
            else:
                thermal_desc = "normal"
                intensity = "glows steadily"

            # Detection success - always see something in thermal
            detections.append({
                "name": target.name,
                "thermal": thermal_desc,
                "intensity": intensity,
                "successes": scan_result['success_count'],
                "is_elevated": target_thermal > 3
            })

        event_bus.emit(GameEvent(EventType.MESSAGE, {
            "text": f"--- THERMAL SCAN RESULTS ({player_room}) ---"
        }))

        for d in detections:
            if d['is_elevated']:
                event_bus.emit(GameEvent(EventType.WARNING, {
                    "text": f"  {d['name']}: {d['thermal'].upper()} - Their heat signature {d['intensity']}!"
                }))
            else:
                event_bus.emit(GameEvent(EventType.MESSAGE, {
                    "text": f"  {d['name']}: {d['thermal']} body temperature"
                }))

        game_state.advance_turn()


class CommandDispatcher:
    """Manages command registration and dispatching."""

    def __init__(self):
        self.commands: Dict[str, Command] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register all available commands."""
        self.register(MoveCommand())
        self.register(LookCommand())
        self.register(InventoryCommand())
        self.register(CraftCommand())
        self.register(GetCommand())
        self.register(DropCommand())
        self.register(ThrowCommand())
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
        self.register(ExplainAwayCommand())
        self.register(ConfrontSlipCommand())
        self.register(BarricadeCommand())
        self.register(JournalCommand())
        self.register(StatusCommand())
        self.register(SaveCommand())
        self.register(LoadCommand())
        self.register(WaitCommand())
        self.register(ExitCommand())
        self.register(TrustCommand())
        self.register(CheckCommand())
        self.register(HideCommand())
        self.register(UnhideCommand())
        self.register(VentCommand())
        self.register(CrouchCommand())
        self.register(StandCommand())
        self.register(SneakCommand())
        self.register(GiveCommand())
        self.register(RepairCommand())
        self.register(FlyCommand())
        self.register(SOSCommand())
        self.register(AccuseCommand())
        self.register(ThrowCommand())
        self.register(SecurityCommand())
        self.register(SabotageSecurityCommand())
        self.register(ThermalCommand())
        self.register(SettingsCommand())
        self.register(DeployCommand())

    def register(self, command: Command):
        """Register a command and its aliases."""
        self.commands[command.name] = command
        for alias in command.aliases:
            self.commands[alias] = command

    def dispatch(self, context: GameContext, user_input: str) -> None:
        """Dispatch a command from user input string."""
        if not user_input.strip():
            return

        parts = user_input.split()
        command_name = parts[0].upper()
        args = parts[1:]

        if command_name in self.commands:
            self.commands[command_name].execute(context, args)
        else:
            event_bus.emit(GameEvent(EventType.ERROR, {
                "text": f"Unknown command: {command_name}\\nType HELP for valid commands."
            }))
