from core.event_system import EventType, GameEvent, event_bus
from core.resolution import ResolutionSystem

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
    
    # Instantiate ResolutionSystem once
    res = ResolutionSystem()

    # 2. Check each group
    for loc, members in location_groups.items():
        if len(members) < 2:
            continue
            
        # Check if there is at least one infected member in the group
        infected_present = any(m.is_infected for m in members)
        
        if not infected_present:
            continue
            
        # Try to infect non-infected members
        for member in members:
            if member.is_infected:
                continue

            # Determine lighting (mocked for now, or derived from power)
            lighting = "DARK" if not game_state.power_on else "LIGHT"

            # Fixed call to match ResolutionSystem.calculate_infection_risk signature
            risk = res.calculate_infection_risk(lighting, member.mask_integrity, game_state.paranoia_level)

            rng = game_state.rng
            if rng.random_float() < risk:
                member.is_infected = True
                # Emit event for other systems (e.g., forensics)
                event_bus.emit(GameEvent(EventType.COMMUNION_SUCCESS, {"target": member.name, "location": loc}))
            if not member.is_infected:
                # Use ResolutionSystem for calculation (Source of Truth)
                # We need a resolution instance, normally passed or instantiated
                # Use the instance from GameState
                res = game_state.resolution
                
                # Determine lighting (mocked for now, or derived from power)
                lighting = "DARK" if not game_state.power_on else "LIGHT"
                
                # Determine lighting (mocked for now, or derived from power)
                lighting = "DARK" if not game_state.power_on else "LIGHT"
                
                # Corrected call signature: removed game_state argument
                # Fixed call to match ResolutionSystem.calculate_infection_risk signature
                risk = res.calculate_infection_risk(lighting, member.mask_integrity, game_state.paranoia_level)
                
                rng = game_state.rng
                if rng.random_float() < risk:
                    member.is_infected = True
                    # Emit event for other systems (e.g., forensics)
                    event_bus.emit(GameEvent(EventType.COMMUNION_SUCCESS, {"target": member.name, "location": loc}))

def on_turn_advance(event: GameEvent):
    game_state = event.payload.get("game_state")
    if game_state:
        check_for_communion(game_state)

# Register the listener
event_bus.subscribe(EventType.TURN_ADVANCE, on_turn_advance)
