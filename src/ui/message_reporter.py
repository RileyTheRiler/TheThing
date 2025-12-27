"""
Message Reporter System (Tier 2.6)
Subscribes to reporting events and displays messages through CRT output.
Systems emit events instead of returning strings.
"""

from core.event_system import event_bus, EventType, GameEvent


class MessageReporter:
    """
    Central message display handler.
    Subscribes to MESSAGE/WARNING/COMBAT_LOG etc. events and routes
    them through the CRT output system.
    """

    def __init__(self, crt_output):
        """
        Initialize with a CRTOutput instance for display.

        Args:
            crt_output: CRTOutput instance from ui.crt_effects
        """
        self.crt = crt_output
        self._subscribe_all()

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

    def _handle_message(self, event: GameEvent):
        """Handle general messages."""
        text = event.payload.get('text', '')
        crawl = event.payload.get('crawl', False)
        self.crt.output(text, crawl=crawl)

    def _handle_warning(self, event: GameEvent):
        """Handle warning messages with high visibility."""
        text = event.payload.get('text', '')
        self.crt.warning(text)

    def _handle_error(self, event: GameEvent):
        """Handle error messages."""
        text = event.payload.get('text', '')
        self.crt.output(f"[ERROR] {text}")

    def _handle_combat(self, event: GameEvent):
        """Handle combat log messages."""
        attacker = event.payload.get('attacker', '?')
        target = event.payload.get('target', '?')
        action = event.payload.get('action', 'attacks')
        result = event.payload.get('result', '')
        damage = event.payload.get('damage', 0)

        msg = f"[COMBAT] {attacker} {action} {target}"
        if damage > 0:
            msg += f" for {damage} damage"
        if result:
            msg += f" - {result}"

        self.crt.output(msg)

    def _handle_dialogue(self, event: GameEvent):
        """Handle NPC dialogue."""
        speaker = event.payload.get('speaker', 'Unknown')
        text = event.payload.get('text', '')
        self.crt.output(f'{speaker}: "{text}"')

    def _handle_system(self, event: GameEvent):
        """Handle system/mechanical info."""
        text = event.payload.get('text', '')
        self.crt.output(f"[SYS] {text}")

    def _handle_movement(self, event: GameEvent):
        """Handle movement messages."""
        actor = event.payload.get('actor', 'You')
        direction = event.payload.get('direction', '')
        destination = event.payload.get('destination', '')

        if destination:
            self.crt.output(f"{actor} moved {direction} to {destination}.")
        else:
            self.crt.output(f"{actor} moved {direction}.")

    def _handle_item_pickup(self, event: GameEvent):
        """Handle item pickup messages."""
        actor = event.payload.get('actor', 'You')
        item = event.payload.get('item', 'something')
        self.crt.output(f"{actor} picked up {item}.")

    def _handle_item_drop(self, event: GameEvent):
        """Handle item drop messages."""
        actor = event.payload.get('actor', 'You')
        item = event.payload.get('item', 'something')
        self.crt.output(f"{actor} dropped {item}.")

    def _handle_attack(self, event: GameEvent):
        """Handle attack result messages."""
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
