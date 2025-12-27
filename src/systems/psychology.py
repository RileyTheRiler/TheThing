from src.core.resolution import Attribute
from src.core.event_system import event_bus, EventType, GameEvent

class PsychologySystem:
    MAX_STRESS = 10
    
    def __init__(self):
        # Register for turn advance
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def update(self, game_state):
        """
        Main update loop for psychology.
        - Checks for environmental stress.
        - Resolves panic triggers.
        """
        # 1. Environmental Stress (Cold)
        if game_state.temperature < 0:
            for m in game_state.crew:
                if m.is_alive:
                    # Increment stress (+1 per -10 degrees below zero, capped)
                    stress_gain = abs(game_state.temperature) // 20
                    self.add_stress(m, max(1, int(stress_gain)))

        # 2. Panic Resolution
        for m in game_state.crew:
            if m.is_alive:
                is_panic, effect = self.resolve_panic(m, game_state)
                if is_panic:
                    game_state.journal.append(f"[TURN {game_state.turn}] {m.name} PANICKED: {effect}!")
                    if m == game_state.player:
                        print(f"\n*** SYSTEM WARNING: {m.name.upper()} IS PANICKING! Effect: {effect.upper()} ***")

    def calculate_panic_threshold(self, character):
        """
        Panic Threshold = RESOLVE Attribute + 2.
        """
        resolve = character.attributes.get(Attribute.RESOLVE, 
                  character.attributes.get(Attribute.LOGIC, 2))
        return resolve + 2

    def add_stress(self, character, amount):
        character.stress += amount
        if character.stress > self.MAX_STRESS:
            character.stress = self.MAX_STRESS
        return character.stress

    def resolve_panic(self, character, game_state):
        """
        Polls for a panic reaction if stress is high enough.
        """
        threshold = self.calculate_panic_threshold(character)
        if character.stress <= threshold:
            return False, None
            
        panic_intensity = character.stress - threshold
        roll = game_state.rng.roll_d6()
        
        if roll <= panic_intensity:
            effects = [
                "drops their primary item in terror",
                "freezes, unable to take actions next turn",
                "screams, alerting anyone nearby",
                "flees to a random nearby room",
                "lash out at a random crew member"
            ]
            effect = game_state.rng.choose(effects)
            
            if "flees" in effect:
                dx = game_state.rng.choose([-2, -1, 1, 2])
                dy = game_state.rng.choose([-2, -1, 1, 2])
                character.move(dx, dy, game_state.station_map)
                 
            return True, effect
            
        return False, "is visibly shaking"

    def on_turn_advance(self, event: GameEvent):
        """Handle turn advancement via event bus."""
        game_state = event.payload.get("game_state")
        if game_state:
            self.update(game_state)
