import random
from systems.infection import check_for_communion

class CrewMember:
    def __init__(self, name, role, behavior_type):
        self.name = name
        self.role = role
        self.behavior_type = behavior_type
        self.is_infected = False  # The "Truth" hidden from the player
        self.trust_score = 50      # 0 to 100
        self.location = (0, 0)
        self.is_alive = True

    def get_dialogue(self, game_state):
        """
        Generates dialogue or status checks. 
        Implements the Vapor Check:
        - If temp < 0 and NOT infected: Always append [VAPOR]
        - If infected: 20% chance to MISS [VAPOR] (Biological Slip)
        """
        base_dialogue = f"I'm {self.behavior_type}."
        
        # Vapor Logic
        if game_state.temperature < 0:
            show_vapor = False
            if not self.is_infected:
                show_vapor = True
            else:
                # Infected: 80% chance to fake it, 20% chance to slip
                if random.random() > 0.2:
                    show_vapor = True
            
            if show_vapor:
                base_dialogue += " [VAPOR]"
        
        return base_dialogue

class StationMap:
    def __init__(self, width=20, height=20):
        self.width = width
        self.height = height
        # Initialize an empty grid
        self.grid = [['.' for _ in range(width)] for _ in range(height)]
        self.rooms = {
            "Rec Room": (5, 5, 10, 10),
            "Infirmary": (0, 0, 4, 4),
            "Generator": (15, 15, 19, 19),
            "Kennel": (0, 15, 4, 19)
        }

    def render(self, crew):
        # Create a copy of the grid to draw current positions
        display_grid = [row[:] for row in self.grid]
        for member in crew:
            if member.is_alive:
                x, y = member.location
                if 0 <= x < self.width and 0 <= y < self.height:
                    display_grid[y][x] = member.name[0] # Use first letter
        
        output = []
        for row in display_grid:
            output.append(" ".join(row))
        return "\n".join(output)

class GameState:
    def __init__(self):
        self.turn = 1
        self.temperature = -40
        self.power_on = True
        self.paranoia_level = 0
        self.station_map = StationMap()
        self.crew = self._initialize_crew()

    def _initialize_crew(self):
        # Based on the 1982 Script
        names = [
            ("MacReady", "Pilot", "Cynical"),
            ("Garry", "Commander", "Stiff"),
            ("Childs", "Mechanic", "Pragmatic"),
            ("Blair", "Biologist", "Sensitive"),
            ("Copper", "Doctor", "Professional")
        ]
        crew = []
        for name, role, behavior in names:
            m = CrewMember(name, role, behavior)
            # Random starting positions within the Rec Room (5,5 to 10,10)
            m.location = (random.randint(5, 10), random.randint(5, 10))
            crew.append(m)
        return crew

    def advance_turn(self):
        self.turn += 1
        # Thermal Decay logic
        if not self.power_on:
            self.temperature -= 5
        self.paranoia_level = min(100, self.paranoia_level + 1)
        
        # Systemic Checks
        check_for_communion(self)

# --- Basic Game Loop ---
if __name__ == "__main__":
    game = GameState()
    
    print("ROS THE SICK ROSE: TERMINAL INITIALIZED")
    print("--------------------------------------")
    
    while True:
        print(f"\n[TURN {game.turn}] TEMP: {game.temperature}C | POWER: {'ON' if game.power_on else 'OFF'}")
        print(game.station_map.render(game.crew))
        
        cmd = input("\nCMD> ").upper()
        
        if cmd == "EXIT":
            break
        elif cmd == "ADVANCE":
            game.advance_turn()
        elif cmd.startswith("STATUS"):
            for m in game.crew:
                print(f"{m.name} ({m.role}): Loc {m.location} | Trust {m.trust_score}")
        elif cmd.startswith("TALK"):
             for m in game.crew:
                print(f"{m.name}: {m.get_dialogue(game)}")
        else:
            print("Unknown command. Try: ADVANCE, STATUS, TALK, EXIT")
