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
        
        # The InterrogationSystem already emits ACCUSATION_RESULT event
        # No need to emit again here
