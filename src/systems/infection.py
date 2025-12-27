import random

def check_for_communion(game_state):
    """
    Checks for infection transmission between crew members.
    Logic:
    - If two characters are in the same room.
    - If one is infected.
    - 10% chance per turn normally.
    - 50% chance per turn if POWER is OFF (Dark).
    """
    
    # 1. Group crew by location
    location_groups = {}
    for member in game_state.crew:
        if not member.is_alive:
            continue
        loc = member.location
        if loc not in location_groups:
            location_groups[loc] = []
        location_groups[loc].append(member)
    
    # 2. Check each group
    for loc, members in location_groups.items():
        if len(members) < 2:
            continue
            
        # Check if there is at least one infected member in the group
        infected_present = any(m.is_infected for m in members)
        
        if not infected_present:
            continue
            
        # Determine infection chance
        infection_chance = 0.10
        if not game_state.power_on:
            infection_chance = 0.50
            
        # Try to infect non-infected members
        for member in members:
            if not member.is_infected:
                roll = random.random()
                if roll < infection_chance:
                    member.is_infected = True
                    # In a real game, we might log this to a hidden GM log
                    # print(f"[DEBUG] {member.name} has been assimilated at {loc}.")
