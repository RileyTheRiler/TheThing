import random
from core.event_system import event_bus, EventType, GameEvent

class MissionarySystem:
    def __init__(self):
        self.communion_range = 1 # Adjacent for corridors
        self.base_decay = 2.0     # Mask decay per turn
        self.stress_multiplier = 1.5 # Multiplier if in high-stress environment
        
        # Agent 3: Role Habits (Standard Habits)
        self.role_habits = {
            "Pilot": ["Rec Room", "Corridor"],
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

    def cleanup(self):
        event_bus.unsubscribe(EventType.TURN_ADVANCE, self.on_turn_advance)

    def on_turn_advance(self, event: GameEvent):
        """
        Triggered when turn advances.
        """
        game_state = event.payload.get("game_state")
        if game_state:
            # Reset per-turn flags
            for member in game_state.crew:
                member.slipped_vapor = False
            self.update(game_state)

    def update(self, game_state):
        """
        Main loop for the Missionary system.
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
            # DIRECT DISSONANCE: Being in the wrong place is taxing for the organism
            dissonance_penalty = 5.0
            member.mask_integrity -= dissonance_penalty

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
        if game_state.paranoia_level > 70:
            decay *= self.stress_multiplier

        member.mask_integrity -= decay
        if member.mask_integrity < 0:
            member.mask_integrity = 0
            
        # BIOLOGICAL SLIP HOOK
        if game_state.temperature < 0:
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
        if member.health <= 1:
            self.trigger_reveal(member, "Critical Injury")
            return

    def trigger_reveal(self, member, reason):
        """
        Transforms the character into a monster.
        """
        revealed_name = f"The-Thing-That-Was-{member.name}"
        member.revealed_name = revealed_name

        print(f"!!! ALERT !!! {member.name} is convulsing... ({reason})")
        member.is_revealed = True
        member.role = "THING-BEAST"
        member.health = 10
        print(f"!!! {revealed_name} TEARS THROUGH HUMAN FLESH! !!!")
        # Preserve the character's name to keep references stable for AI/tests;
        # use a themed alias only for messaging to avoid breaking lookups.
        thing_alias = f"The-Thing-That-Was-{member.name}"
        member.health = 10
        print(f"!!! {thing_alias} TEARS THROUGH HUMAN FLESH! !!!")

    def attempt_communion_ai(self, agent, game_state):
        """
        Agent attempts to infect another person.
        Conditions:
        - Must be alone with target (no human witnesses).
        - Target not already infected.
        """
        room_name = game_state.station_map.get_room_name(*agent.location)
        is_corridor = "Corridor" in room_name

        CORRIDOR_VISUAL_RANGE = 5 # As per memory/test expectations

        potential_targets = []

        # Identify valid targets and witnesses
        for other in game_state.crew:
            if other == agent or not other.is_alive:
                continue

            other_room = game_state.station_map.get_room_name(*other.location)
            is_visible = False

            # Visibility Check
            if is_corridor:
                if "Corridor" in other_room:
                     # Euclidean distance for visibility in corridors
                     dist = ((agent.location[0] - other.location[0])**2 + (agent.location[1] - other.location[1])**2)**0.5
                     if dist <= CORRIDOR_VISUAL_RANGE:
                         is_visible = True
            else:
                # Named Room: Visible if in same room
                if other_room == room_name:
                    is_visible = True

            if is_visible:
                # If ANY human can see us, we cannot commune (unless they are the target and we are alone with them)
                # We collect potential targets first
                if not other.is_infected:
                    # Check distance for communion
                    is_in_range = False
                    if is_corridor:
                         # Manhattan distance for adjacency check
                         dist = abs(agent.location[0] - other.location[0]) + abs(agent.location[1] - other.location[1])
                         if dist <= self.communion_range:
                             is_in_range = True
                    else:
                        # In named rooms, being in the room is sufficient
                        is_in_range = True

                    if is_in_range:
                        potential_targets.append(other)

        # We can proceed ONLY if:
        # 1. We have at least one valid target.
        # 2. There are no witnesses OTHER than the target.
        
        if len(potential_targets) == 1:
            target = potential_targets[0]
            if not self.has_witnesses(agent, target, game_state):
                self.perform_communion(agent, target, game_state)

    def has_witnesses(self, agent, target, game_state):
        """
        Checks for any uninfected crew members who can see the agent.
        """
        CORRIDOR_VISUAL_RANGE = 5

        for other in game_state.crew:
            if other == agent or other == target or not other.is_alive:
                continue

            # Infected don't count as witnesses
            if other.is_infected:
                continue

            if self.is_visible(agent.location, other.location, game_state.station_map):
                return True
        return False

    def is_visible(self, loc1, loc2, station_map):
        """
        Determines if loc2 is visible from loc1.
        """
        room1 = station_map.get_room_name(*loc1)
        room2 = station_map.get_room_name(*loc2)

        in_named_room1 = room1 in station_map.rooms
        in_named_room2 = room2 in station_map.rooms

        if in_named_room1:
            return room1 == room2
        elif in_named_room2:
            return False
        else:
            # Both corridors
            x1, y1 = loc1
            x2, y2 = loc2
            dist_sq = (x1 - x2)**2 + (y1 - y2)**2
            return dist_sq <= 25 # 5^2

    def perform_communion(self, agent, target, game_state):
        """
        Actual mechanics of assimilation.
        """
        print(f">>> SILENT EVENT: {agent.name} approaches {target.name}...")
        
        # Refill Agent's Mask
        agent.mask_integrity = min(100, agent.mask_integrity + 50)
        
        # SEARCHLIGHT HARVEST: Stealing the host's memory/mannerisms
        self.searchlight_harvest(agent, target)
        
        # Infect Target
        target.is_infected = True
        target.mask_integrity = 100 # Fresh mask

    def searchlight_harvest(self, agent, target):
        """
        Transfer nomenclature data from target to agent.
        """
        print(f">>> SEARCHLIGHT HARVEST: {agent.name} extracts nomenclature from {target.name}.")
        
        # Reduce slip chances for the Agent
        for inv in agent.invariants:
            if 'slip_chance' in inv:
                inv['slip_chance'] *= 0.5
        
        # Generate Knowledge Tags
        role_tag = f"Protocol: {target.role}"
        memory_tag = f"Memory: {target.name} interaction"

        if hasattr(agent, 'knowledge_tags'):
             if role_tag not in agent.knowledge_tags:
                 agent.knowledge_tags.append(role_tag)
             if memory_tag not in agent.knowledge_tags:
                 agent.knowledge_tags.append(memory_tag)
