import random
from core.event_system import event_bus, EventType, GameEvent

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
        Agent attempts to infect another person.
        Conditions:
        - Must be alone with target (no human witnesses).
        - Target not already infected.
        """
        room_name = game_state.station_map.get_room_name(*agent.location)
        is_corridor = "Corridor" in room_name

        potential_targets = []
        human_witnesses_count = 0

        # Corridor logic constants
        # If in corridor, we can see further than just adjacent
        CORRIDOR_VISUAL_RANGE = 4

        for other in game_state.crew:
            if other == agent or not other.is_alive:
                continue

            other_room = game_state.station_map.get_room_name(*other.location)
            is_visible = False
            if other_room == room_name:
                is_visible = True
            elif room_name and other_room and "Corridor" in room_name and "Corridor" in other_room:
                # LOS for Corridors: Check distance
                dist = ((agent.location[0] - other.location[0])**2 + (agent.location[1] - other.location[1])**2)**0.5
                if dist <= 5:  # Visibility range in corridors
                    is_visible = True

            if is_visible:
                if other.is_infected:
                    pass
                    # Simplification: Only non-infected count as "Witnesses" that prevent the act.
                else:
                    potential_targets.append(other)

            if is_corridor:
                # If agent is in corridor, only people in corridors are visible
                if "Corridor" in other_room:
                    # Calculate Manhattan distance
                    dist = abs(agent.location[0] - other.location[0]) + abs(agent.location[1] - other.location[1])
                    if dist <= CORRIDOR_VISUAL_RANGE:
                        is_visible = True
            else:
                # Named room: anyone in the same room is visible
                if other_room == room_name:
                    is_visible = True

            if is_visible:
                # If visible and not infected, they are a witness
                if not other.is_infected:
                    human_witnesses_count += 1

                    # Check if this person is close enough to be a target
                    is_in_range = False
                    if is_corridor:
                         # In corridors, must be adjacent or same tile (communion_range = 1)
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
        # 2. The total number of human witnesses (including the target) is exactly 1.
        #    This ensures the target is the ONLY human who sees us.
        
        if len(potential_targets) > 0 and human_witnesses_count == 1:
            # Pick the target (should be only one if witnesses_count is 1)
            target = potential_targets[0]
            self.perform_communion(agent, target, game_state)
            # Strict check: Must be in same 'room' (Same named room or same corridor tile)
            if other_room == room_name:
                if not other.is_infected:
                    potential_targets.append(other)

        # If there is EXACTLY ONE target in the immediate vicinity (same room/tile)
        if len(potential_targets) == 1:
            target = potential_targets[0]
            
            # 2. Robust Witness Check
            # Check if any uninfected crew member (who is not the target) can see the event.
            if not self.has_witnesses(agent, target, game_state):
                self.perform_communion(agent, target, game_state)

    def has_witnesses(self, agent, target, game_state):
        """
        Checks for any uninfected crew members who can see the agent.
        """
        for other in game_state.crew:
            if other == agent or other == target or not other.is_alive:
                continue

            # Infected don't count as witnesses (per simplification)
            if other.is_infected:
                continue

            if self.is_visible(agent.location, other.location, game_state.station_map):
                return True
        return False

    def is_visible(self, loc1, loc2, station_map):
        """
        Determines if loc2 is visible from loc1.
        - Named Room <-> Named Room: Visible only if same room.
        - Named Room <-> Corridor: Not visible (Walls).
        - Corridor <-> Corridor: Visible if within range (Sight line).
        """
        room1 = station_map.get_room_name(*loc1)
        room2 = station_map.get_room_name(*loc2)

        # Check if locations are in named rooms
        # Note: station_map.rooms keys are the named rooms.
        in_named_room1 = room1 in station_map.rooms
        in_named_room2 = room2 in station_map.rooms

        if in_named_room1:
            # Inside a room: Only visible if other is in the same room
            return room1 == room2
        elif in_named_room2:
            # Observer is in a room, Agent is in Corridor/Outside -> Blocked by wall
            return False
        else:
            # Both are in corridors/outside
            # Check Euclidean distance
            x1, y1 = loc1
            x2, y2 = loc2
            dist_sq = (x1 - x2)**2 + (y1 - y2)**2
            # Sight range of 5 tiles (squared = 25)
            return dist_sq <= 25

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
        # Advanced Mimicry: Grant Knowledge Tags
        # The agent learns personal details to use in social defense
        memories = [
            f"details about {target.name}'s life",
            f"a story about {target.name}'s childhood",
            f"{target.name}'s favorite song",
            f"{target.name}'s routine in the {target.role}",
            f"a secret {target.name} kept"
        ]
        new_tag = random.choice(memories)
        if hasattr(agent, 'knowledge_tags'):
            agent.knowledge_tags.append(new_tag)
            print(f">>> MIMICRY UPDATE: {agent.name} learned '{new_tag}'")
