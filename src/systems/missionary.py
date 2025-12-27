import random
from src.core.event_system import event_bus, EventType, GameEvent

class MissionarySystem:
    def __init__(self):
        self.communion_range = 1 # Same room/adjacent
        self.base_decay = 2.0     # Mask decay per turn
        self.stress_multiplier = 1.5 # Multiplier if in high-stress environment
        
        # Subscribe to turn advance
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)
        
        # Agent 3: Role Habits (Standard Habits)
        self.role_habits = {
            "Pilot": ["Rec Room", "Corridor"], # MacReady moves around
            "Mechanic": ["Rec Room", "Generator"],
            "Biologist": ["Infirmary", "Rec Room"],
            "Commander": ["Rec Room", "Corridor"],
            "Cook": ["Rec Room"],
            "Radio Op": ["Rec Room", "Corridor"], 
            "Doctor": ["Infirmary", "Rec Room"],
            "Geologist": ["Rec Room", "Corridor"],
            "Meteorologist": ["Rec Room", "Corridor"],
            "Dog Handler": ["Kennel", "Rec Room"],
            "Assistant Mechanic": ["Rec Room", "Generator"]
        }
        # Register for turn advance
        event_bus.subscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def on_turn_advance(self, event):
        """
        Triggered by the event bus.
        """
        game_state = event.payload.get("game_state")
        if game_state:
            self.update(game_state)

    def on_turn_advance(self, event: GameEvent):
        """
        Triggered when turn advances.
        """
        game_state = event.payload.get("game_state")
        if game_state:
            self.update(game_state)

    def update(self, game_state):
        """
        Main loop for the Missionary system.
        1. Process Mask Decay for all infected.
        2. Check for Role-based Habit Dissonance.
        3. Check for Violent Reveal triggers.
        4. Simple AI: Attempt Communion if conditions match.
        """
        for member in game_state.crew:
            if not member.is_alive:
                continue
            
            if member.is_infected and not member.is_revealed:
                self.process_decay(member, game_state)
                self.process_habit_checks(member, game_state)
                self.check_reveal_triggers(member, game_state)
                
                # Simple AI: Try to infect others
                self.attempt_communion_ai(member, game_state)

    def process_habit_checks(self, member, game_state):
        """
        Calculates dissonance if NPC is away from their 'Standard' habitat.
        """
        current_room = game_state.station_map.get_room_name(*member.location)
        preferred = self.role_habits.get(member.role, ["Rec Room"])
        
        # If the room name contains any of the preferred room strings
        at_station = any(p in current_room for p in preferred)
        
        if not at_station:
            # DIREC DISSONANCE: Being in the wrong place is taxing for the organism
            dissonance_penalty = 5.0
            member.mask_integrity -= dissonance_penalty
            # print(f"[DEBUG] {member.name} (Role: {member.role}) is in {current_room} - NOT AT STATION (Penalty: {dissonance_penalty})")

    def process_decay(self, member, game_state):
        """
        Reduces Mask Integrity based on environment.
        """
        decay = self.base_decay
        
        # Environmental Stressors
        # 1. Temperature: Extreme cold stresses the biology
        if game_state.temperature < -50:
            decay *= 1.5
            
        # 2. Social Friction: If trusting no one / low trust, harder to maintain facade
        # (Simplified: if Paranoid, decay faster)
        if game_state.paranoia_level > 70:
            decay *= self.stress_multiplier

        member.mask_integrity -= decay
        if member.mask_integrity < 0:
            member.mask_integrity = 0
            
        # BIOLOGICAL SLIP HOOK
        if game_state.temperature < 0:
            # P(Slip) = (1.0 - integrity/100.0) * BaseChance
            # If integrity is 100, slip is 0. If 0, it's 50%.
            slip_chance = (1.0 - (member.mask_integrity / 100.0)) * 0.5
            if random.random() < slip_chance:
                event_bus.emit(GameEvent(EventType.BIOLOGICAL_SLIP, {
                    "character_name": member.name,
                    "type": "VAPOR"
                }))

    def check_reveal_triggers(self, member, game_state):
        """
        Checks if the entity should be forced to reveal.
        """
        # Trigger 1: Mask Failure
        if member.mask_integrity <= 0:
            self.trigger_reveal(member, "Mask Failure")
            return

        # Trigger 2: Mortal Danger (Low Health)
        # If health meets 1 (critical), self-preservation kicks in
        if member.health <= 1:
            self.trigger_reveal(member, "Critical Injury")
            return

    def trigger_reveal(self, member, reason):
        """
        Transforms the character into a monster.
        """
        print(f"!!! ALERT !!! {member.name} is convulsing... ({reason})")
        member.is_revealed = True
        member.role = "THING-BEAST"
        member.name = f"The-Thing-That-Was-{member.name}"
        member.health = 10 # hp buffer boost
        # Attributes buff
        # (In a full system, we'd swap stats properly)
        print(f"!!! {member.name} TEARS THROUGH HUMAN FLESH! !!!")

    def attempt_communion_ai(self, agent, game_state):
        """
        Agent attempts to infect another person in the same room.
        Conditions:
        - Must be alone with target (no witnesses).
        - Target not already infected.
        """
        # 1. Find targets in same room
        room_name = game_state.station_map.get_room_name(*agent.location)
        potential_targets = []
        witnesses = []

        for other in game_state.crew:
            if other == agent or not other.is_alive:
                continue
            
            other_room = game_state.station_map.get_room_name(*other.location)
            if other_room == room_name:
                if other.is_infected:
                    witnesses.append(other) # Other things don't count as witnesses against you, strictly speaking, but for now let's say they complicate the ritual? No, actually they help.
                    # Simplification: Only non-infected count as "Witnesses" that prevent the act.
                else:
                    potential_targets.append(other)
            else:
                # Someone near? (Not implementing complex LOS yet)
                pass

        # If there are witnesses (non-infected people other than target), we can't do it cleanly
        # Actually, if there is EXACTLY ONE target and NO ONE ELSE, we can do it.
        # If there are 2+ targets, we can't retain secrecy easily.
        
        if len(potential_targets) == 1:
            target = potential_targets[0]
            # Check for other human witnesses in the room?
            # potential_targets list implies these are humans. 
            # If len > 1, then there are witnesses.
            # So len == 1 means target is alone with Agent (and maybe other Things).
            
            self.perform_communion(agent, target, game_state)

    def perform_communion(self, agent, target, game_state):
        """
        Actual mechanics of assimilation.
        """
        # Chance to succeed? 
        # For now, deterministic if alone.
        
        print(f">>> SILENT EVENT: {agent.name} approaches {target.name}...")
        
        # Refill Agent's Mask
        agent.mask_integrity = min(100, agent.mask_integrity + 50)
        
        # SEARCHLIGHT HARVEST: Stealing the host's memory/mannerisms
        self.searchlight_harvest(agent, target)
        
        # Infect Target
        target.is_infected = True
        target.mask_integrity = 100 # Fresh mask
        
        # Log to hidden state (or debug)
        # print(f"[DEBUG] {target.name} ASSIMILATED by {agent.name}")

    def searchlight_harvest(self, agent, target):
        """
        Transfer nomenclature data from target to agent.
        Reduces the agent's slip chance by learning the host's logic.
        """
        print(f">>> SEARCHLIGHT HARVEST: {agent.name} extracts nomenclature from {target.name}.")
        
        # Reduce slip chances for the Agent (mimicry becomes more precise)
        # In this simplistic model, the agent just gets 'better' at being the host.
        for inv in agent.invariants:
            if 'slip_chance' in inv:
                # 50% reduction in detection chance
                inv['slip_chance'] *= 0.5
        
        # Generate Knowledge Tags / Memory Logs
        # The agent learns the target's role protocols and behaviors
        role_tag = f"Protocol: {target.role}"
        memory_tag = f"Memory: {target.name} interaction"

        agent.add_knowledge_tag(role_tag)
        agent.add_knowledge_tag(memory_tag)

        print(f">>> ACQUIRED KNOWLEDGE: {agent.name} learned '{role_tag}' and '{memory_tag}'")
