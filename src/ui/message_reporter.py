"""
Message Reporter System (Tier 2.6)
Subscribes to reporting events and displays messages through CRT output.
Systems emit events instead of returning strings.
"""

from core.event_system import event_bus, EventType, GameEvent
from systems.architect import Verbosity


class MessageReporter:
    """
    Central message display handler.
    Subscribes to MESSAGE/WARNING/COMBAT_LOG etc. events and routes
    them through the CRT output system.
    Supports event coalescing (batching) to avoid output floods.
    Supports verbosity levels for filtering events.
    """

    # Map EventType to minimum required Verbosity
    VERBOSITY_MAP = {
        EventType.WARNING: Verbosity.MINIMAL,
        EventType.ERROR: Verbosity.MINIMAL,
        EventType.ITEM_PICKUP: Verbosity.MINIMAL,
        EventType.ENDING_REPORT: Verbosity.MINIMAL,
        
        EventType.MESSAGE: Verbosity.STANDARD,
        EventType.COMBAT_LOG: Verbosity.STANDARD,
        EventType.DIALOGUE: Verbosity.STANDARD,
        EventType.ATTACK_RESULT: Verbosity.STANDARD,
        EventType.TEST_RESULT: Verbosity.STANDARD,
        EventType.BARRICADE_ACTION: Verbosity.STANDARD,
        EventType.STEALTH_REPORT: Verbosity.STANDARD,
        EventType.INTERROGATION_RESULT: Verbosity.STANDARD,
        EventType.ACCUSATION_RESULT: Verbosity.STANDARD,
        
        EventType.MOVEMENT: Verbosity.VERBOSE,
        EventType.SYSTEM_LOG: Verbosity.VERBOSE,
        EventType.CRAFTING_REPORT: Verbosity.VERBOSE,
        EventType.ITEM_DROP: Verbosity.VERBOSE,
    }

    def __init__(self, crt_output, game_state=None):
        """
        Initialize with a CRTOutput instance for display.

        Args:
            crt_output: CRTOutput instance from ui.crt_effects
            game_state: Optional GameState instance to query verbosity.
        """
        self.crt = crt_output
        self.game_state = game_state
        self._combat_batch = []
        self._movement_batch = {} # destination -> [actors]
        self._subscribe_all()

    @property
    def verbosity(self) -> Verbosity:
        """Get current verbosity level from game state."""
        if self.game_state:
            return self.game_state.verbosity
        return Verbosity.STANDARD

    def _should_report(self, event_type: EventType) -> bool:
        """Check if event should be reported based on verbosity."""
        required = self.VERBOSITY_MAP.get(event_type, Verbosity.DEBUG)
        return self.verbosity.value >= required.value

    def flush(self):
        """Flush any batched messages to the output."""
        self._flush_combat()
        self._flush_movement()

    def _flush_combat(self):
        """Coalesce and output batched combat logs."""
        if not self._combat_batch:
            return
            
        # Coalesce by (attacker, target, action)
        coalesced = {}
        for entry in self._combat_batch:
            key = (entry['attacker'], entry['target'], entry['action'])
            if key not in coalesced:
                coalesced[key] = {'count': 0, 'damage': 0, 'results': set()}
            coalesced[key]['count'] += 1
            coalesced[key]['damage'] += entry.get('damage', 0)
            if entry.get('result'):
                coalesced[key]['results'].add(entry['result'])

        for (attacker, target, action), data in coalesced.items():
            count = data['count']
            dmg = data['damage']
            results = ", ".join(data['results'])
            
            msg = f"[COMBAT] {attacker} {action} {target}"
            if count > 1:
                msg += f" {count} times"
            if dmg > 0:
                msg += f" for total {dmg} damage"
            if results:
                msg += f" ({results})"
            
            self.crt.output(msg)
            
        self._combat_batch = []

    def _flush_movement(self):
        """Coalesce and output batched movement logs."""
        if not self._movement_batch:
            return
            
        for destination, actors in self._movement_batch.items():
            if not actors:
                continue
            
            if len(actors) > 2:
                actor_str = f"{actors[0]}, {actors[1]} and {len(actors)-2} others"
            else:
                actor_str = " and ".join(actors)
                
            self.crt.output(f"{actor_str} moved to {destination}.")
            
        self._movement_batch = {}

    def _subscribe_all(self):
        """Subscribe to all reporting event types."""
        event_bus.subscribe(EventType.MESSAGE, self._handle_message)
        event_bus.subscribe(EventType.WARNING, self._handle_warning)
        event_bus.subscribe(EventType.ERROR, self._handle_error)
        event_bus.subscribe(EventType.COMBAT_LOG, self._handle_combat)
        event_bus.subscribe(EventType.DIALOGUE, self._handle_dialogue)
        event_bus.subscribe(EventType.SYSTEM_LOG, self._handle_system)
        event_bus.subscribe(EventType.MOVEMENT, self._handle_movement)
        event_bus.subscribe(EventType.ITEM_PICKUP, self._handle_item_pickup)
        event_bus.subscribe(EventType.ITEM_DROP, self._handle_item_drop)
        event_bus.subscribe(EventType.ATTACK_RESULT, self._handle_attack)
        event_bus.subscribe(EventType.TEST_RESULT, self._handle_test)
        event_bus.subscribe(EventType.BARRICADE_ACTION, self._handle_barricade)
        event_bus.subscribe(EventType.STEALTH_REPORT, self._handle_stealth)
        event_bus.subscribe(EventType.CRAFTING_REPORT, self._handle_crafting)
        event_bus.subscribe(EventType.ENDING_REPORT, self._handle_ending)
        event_bus.subscribe(EventType.INTERROGATION_RESULT, self._handle_interrogation)
        event_bus.subscribe(EventType.ACCUSATION_RESULT, self._handle_accusation)

    def cleanup(self):
        """Unsubscribe from all reporting event types."""
        event_bus.unsubscribe(EventType.MESSAGE, self._handle_message)
        event_bus.unsubscribe(EventType.WARNING, self._handle_warning)
        event_bus.unsubscribe(EventType.ERROR, self._handle_error)
        event_bus.unsubscribe(EventType.COMBAT_LOG, self._handle_combat)
        event_bus.unsubscribe(EventType.DIALOGUE, self._handle_dialogue)
        event_bus.unsubscribe(EventType.SYSTEM_LOG, self._handle_system)
        event_bus.unsubscribe(EventType.MOVEMENT, self._handle_movement)
        event_bus.unsubscribe(EventType.ITEM_PICKUP, self._handle_item_pickup)
        event_bus.unsubscribe(EventType.ITEM_DROP, self._handle_item_drop)
        event_bus.unsubscribe(EventType.ATTACK_RESULT, self._handle_attack)
        event_bus.unsubscribe(EventType.TEST_RESULT, self._handle_test)
        event_bus.unsubscribe(EventType.BARRICADE_ACTION, self._handle_barricade)
        event_bus.unsubscribe(EventType.STEALTH_REPORT, self._handle_stealth)
        event_bus.unsubscribe(EventType.CRAFTING_REPORT, self._handle_crafting)
        event_bus.unsubscribe(EventType.ENDING_REPORT, self._handle_ending)
        event_bus.unsubscribe(EventType.INTERROGATION_RESULT, self._handle_interrogation)
        event_bus.unsubscribe(EventType.ACCUSATION_RESULT, self._handle_accusation)

    def _handle_message(self, event: GameEvent):
        """Handle general messages."""
        if not self._should_report(event.type):
            return
        text = event.payload.get('text', '')
        crawl = event.payload.get('crawl', False)
        self.crt.output(text, crawl=crawl)

    def _handle_warning(self, event: GameEvent):
        """Handle warning messages with high visibility."""
        if not self._should_report(event.type):
            return
        text = event.payload.get('text', '')
        self.crt.warning(text)

    def _handle_error(self, event: GameEvent):
        """Handle error messages."""
        if not self._should_report(event.type):
            return
        text = event.payload.get('text', '')
        self.crt.output(f"[ERROR] {text}")

    def _handle_combat(self, event: GameEvent):
        """Handle combat log messages with batching."""
        if not self._should_report(event.type):
            return
        
        # Add to batch for coalescing on flush
        self._combat_batch.append(event.payload)
        # If batch gets too large, flush early
        if len(self._combat_batch) >= 10:
            self._flush_combat()

    def _handle_dialogue(self, event: GameEvent):
        """Handle NPC dialogue."""
        if not self._should_report(event.type):
            return
        speaker = event.payload.get('speaker', 'Unknown')
        text = event.payload.get('text', '')
        self.crt.output(f'{speaker}: "{text}"')

    def _handle_system(self, event: GameEvent):
        """Handle system/mechanical info."""
        if not self._should_report(event.type):
            return
        text = event.payload.get('text', '')
        self.crt.output(f"[SYS] {text}")

    def _handle_movement(self, event: GameEvent):
        """Handle movement messages with batching."""
        if not self._should_report(event.type):
            return
        actor = event.payload.get('actor', 'You')
        destination = event.payload.get('destination', '')

        if not destination:
            # Non-batchable movement (no destination specified)
            direction = event.payload.get('direction', '')
            self.crt.output(f"{actor} moved {direction}.")
            return

        # Batch relative to destination
        if destination not in self._movement_batch:
            self._movement_batch[destination] = []
        self._movement_batch[destination].append(actor)
        
        # Flush if too many move events
        if sum(len(v) for v in self._movement_batch.values()) >= 5:
            self._flush_movement()

    def _handle_item_pickup(self, event: GameEvent):
        """Handle item pickup messages."""
        if not self._should_report(event.type):
            return
        actor = event.payload.get('actor', 'You')
        item = event.payload.get('item', 'something')
        self.crt.output(f"{actor} picked up {item}.")

    def _handle_item_drop(self, event: GameEvent):
        """Handle item drop messages."""
        if not self._should_report(event.type):
            return
        actor = event.payload.get('actor', 'You')
        item = event.payload.get('item', 'something')
        self.crt.output(f"{actor} dropped {item}.")

    def _handle_attack(self, event: GameEvent):
        """Handle attack result messages."""
        if not self._should_report(event.type):
            return
        attacker = event.payload.get('attacker', '?')
        target = event.payload.get('target', '?')
        weapon = event.payload.get('weapon', 'fists')
        hit = event.payload.get('hit', False)
        damage = event.payload.get('damage', 0)
        killed = event.payload.get('killed', False)

        if hit:
            msg = f"{attacker} hits {target} with {weapon} for {damage} damage!"
            self.crt.output(msg)
            if killed:
                self.crt.output(f"*** {target} HAS DIED ***")
        else:
            self.crt.output(f"{attacker} misses {target}.")

    def _handle_test(self, event: GameEvent):
        """Handle blood test results."""
        subject = event.payload.get('subject', '?')
        result = event.payload.get('result', 'unknown')
        infected = event.payload.get('infected', False)

        self.crt.output(f"[BLOOD TEST: {subject}]")
        if infected:
            self.crt.output("THE BLOOD LEAPS FROM THE PETRI DISH!", crawl=True)
            self.crt.warning(f"{subject} IS INFECTED!")
        else:
            self.crt.output(f"No reaction. {subject} appears human.")

    def _handle_barricade(self, event: GameEvent):
        """Handle barricade action messages."""
        action = event.payload.get('action', 'built')
        room = event.payload.get('room', 'room')
        strength = event.payload.get('strength', 1)
        actor = event.payload.get('actor', 'You')

        if action == 'built':
            self.crt.output(f"{actor} barricaded {room}. (Strength: {strength}/3)")
        elif action == 'reinforced':
            self.crt.output(f"{actor} reinforced the barricade. (Strength: {strength}/3)")
        elif action == 'broken':
            self.crt.output(f"The barricade in {room} has been broken!")
        elif action == 'damaged':
            self.crt.output(f"The barricade shudders! (Strength: {strength}/3)")

    def _handle_stealth(self, event: GameEvent):
        """Handle stealth encounter updates."""
        opponent = event.payload.get('opponent', 'someone')
        room = event.payload.get('room', 'somewhere')
        outcome = event.payload.get('outcome', 'evaded')
        prefix = "[STEALTH]"
        if outcome == "detected":
            self.crt.warning(f"{prefix} {opponent} spots you in the {room}!")
        else:
            self.crt.output(f"{prefix} You evade {opponent} in the {room}.")

    def _handle_crafting(self, event: GameEvent):
        """Handle crafting progress updates."""
        actor = event.payload.get('actor', 'You')
        recipe = event.payload.get('recipe', 'unknown')
        event_stage = event.payload.get('event', 'queued')
        item_name = event.payload.get('item_name')
        if event_stage == "completed" and item_name:
            self.crt.output(f"{actor} completed {recipe}: {item_name}.")
        elif event_stage == "invalid":
            missing = event.payload.get('missing', [])
            if missing:
                missing_list = ", ".join(missing)
                self.crt.output(f"{actor} cannot craft {recipe}: missing {missing_list}.")
            else:
                self.crt.output(f"{actor} cannot craft {recipe}.")
        elif event_stage == "queued":
            turns = event.payload.get('turns')
            if turns and turns > 1:
                self.crt.output(f"{actor} starts crafting {recipe} ({turns} turns).")
            else:
                self.crt.output(f"{actor} starts crafting {recipe}.")

    def _handle_ending(self, event: GameEvent):
        """Handle ending triggers."""
        message = event.payload.get('message', 'An ending has been reached.')
        result = event.payload.get('result', 'win')
        label = "VICTORY" if result == "win" else "DEFEAT"
        self.crt.output(f"[{label}] {message}", crawl=True)

    def _handle_interrogation(self, event: GameEvent):
        """Handle interrogation dialogues/results."""
        interrogator = event.payload.get('interrogator', 'You')
        subject = event.payload.get('subject', 'Someone')
        topic = event.payload.get('topic', '').upper()
        dialogue = event.payload.get('dialogue', '')
        response_type = event.payload.get('response_type', '').upper()
        tells = event.payload.get('tells', [])
        trust_change = event.payload.get('trust_change', 0)

        header = f"[INTERROGATION: {subject}"
        if topic:
            header += f" - {topic}"
        header += "]"
        self.crt.output(header)
        self.crt.output(f"\"{dialogue}\"")
        if response_type:
            self.crt.output(f"[Response: {response_type}]")
        if tells:
            self.crt.output("[OBSERVATION]")
            for tell in tells:
                self.crt.output(f"  - {tell}")
        if trust_change:
            change_str = f"+{trust_change}" if trust_change > 0 else str(trust_change)
            self.crt.output(f"[Trust: {change_str}]")

    def _handle_accusation(self, event: GameEvent):
        """Handle accusation result messages."""
        target = event.payload.get('target', '?')
        outcome = event.payload.get('outcome', '')
        supporters = event.payload.get('supporters', [])
        opposers = event.payload.get('opposers', [])
        
        self.crt.output(f"[ACCUSATION: {target}]")
        self.crt.output(outcome)
        if supporters or opposers:
            self.crt.output(f"Supporters: {', '.join(supporters) if supporters else 'None'}")
            self.crt.output(f"Opposers: {', '.join(opposers) if opposers else 'None'}")


# Utility function to emit messages easily
def emit_message(text, crawl=False):
    """Emit a general message event."""
    event_bus.emit(GameEvent(EventType.MESSAGE, {'text': text, 'crawl': crawl}))


def emit_warning(text):
    """Emit a warning event."""
    event_bus.emit(GameEvent(EventType.WARNING, {'text': text}))


def emit_combat(attacker, target, action='attacks', result='', damage=0):
    """Emit a combat log event."""
    event_bus.emit(GameEvent(EventType.COMBAT_LOG, {
        'attacker': attacker,
        'target': target,
        'action': action,
        'result': result,
        'damage': damage
    }))


def emit_dialogue(speaker, text):
    """Emit a dialogue event."""
    event_bus.emit(GameEvent(EventType.DIALOGUE, {'speaker': speaker, 'text': text}))


def emit_movement(actor, destination=None, direction=None):
    """Emit a movement event."""
    event_bus.emit(GameEvent(EventType.MOVEMENT, {
        'actor': actor,
        'destination': destination,
        'direction': direction
    }))
